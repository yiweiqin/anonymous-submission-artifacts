"""Host-owned native table execution journal, separate from official Harbor grading.

Graphs are executed, never inferred from an Agent DAG. Input rows must be read
by the host from the task environment. A public DSL acceptance check cannot
qualify a source for learning until its independent Harbor receipt also passes.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ENGINE_DIR = Path(__file__).resolve().parents[2] / "training" / "minimal-evolution"
sys.path.insert(0, str(ENGINE_DIR))
from engine import apply_patch, catalog, digest, execute, reference, solve, verify_prediction


def fingerprint(value):
    return digest(value)


class NativeWorkflow:
    def __init__(self, root, run_id, task_instruction_sha, frozen=None, public_source_paths=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if (self.root / 'native-events.jsonl').exists():
            raise ValueError('new_journal_required')
        self.run_id = run_id
        self.instruction_sha = task_instruction_sha
        self.states = {}
        self.frozen = copy.deepcopy(frozen or [])
        self.public_source_paths = set(public_source_paths or [])
        self.original_inputs = {}
        self.inputs_captured = False
        self.sequence = 0
        self.previous_hash = '0' * 64

    def event(self, kind, **fields):
        self.sequence += 1
        row = dict(sequence=self.sequence, runId=self.run_id,
                   taskInstructionSha256=self.instruction_sha, kind=kind,
                   time=time.time(), previousHash=self.previous_hash, **fields)
        row['eventHash'] = digest(row)
        self.previous_hash = row['eventHash']
        with (self.root / 'native-events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
            handle.flush()
        return row

    def register(self, request, rows, raw_source_sha, original_snapshot=False):
        if set(request) != {'action', 'workflowId', 'task', 'graph', 'source'}:
            raise ValueError('register_schema')
        ident = request['workflowId']
        if not isinstance(ident, str) or not ident or len(ident) > 100 or ident in self.states:
            raise ValueError('immutable_workflow_identity')
        case = dict(task=copy.deepcopy(request['task']), G_plan=copy.deepcopy(request['graph']),
                    G_exec=copy.deepcopy(request['graph']), observedWorlds=[copy.deepcopy(rows)],
                    executionEvidence={'status': 'pending', 'acceptance': 'unverified'})
        # Use the unchanged bundled boundary, including integer/row/graph limits.
        from shadow import checked_case
        checked_case(case)
        state = dict(case=case, source=copy.deepcopy(request['source']), rawSourceSha256=raw_source_sha,
                     activePlan=copy.deepcopy(request['graph']), executions=[], consumedUpdates=[],
                     originalInputSnapshot=original_snapshot)
        self.states[ident] = state
        self.event('registered', workflowId=ident, planningHash=digest(case),
                   source=state['source'], rawSourceSha256=raw_source_sha, case=case,
                   originalInputSnapshot=original_snapshot)
        # Transfer only exact public task semantics and original graph preconditions.
        # No automatic renaming or guessed adaptation between task DSLs.
        for update in self.frozen:
            task_scope = {k: v for k, v in case['task'].items() if k != 'name'}
            if update['taskScope'] != task_scope or update['basePlanHash'] != digest(case['G_plan']):
                continue
            patched = apply_patch(case['G_plan'], update['prediction']['edits'])
            state['activePlan'] = patched
            state['consumedUpdates'].append(update['updateId'])
            self.event('frozen_plan_bound', workflowId=ident, updateId=update['updateId'],
                       basePlanHash=digest(case['G_plan']), activePlanHash=digest(patched))
            break
        return {'workflowId': ident, 'planHash': digest(state['activePlan']),
                'activeGraph': state['activePlan'], 'consumedUpdates': state['consumedUpdates']}

    def run(self, request):
        if set(request) not in ({'action', 'workflowId'}, {'action', 'workflowId', 'graph'}):
            raise ValueError('execute_schema')
        ident = request['workflowId']
        state = self.states[ident]
        graph = copy.deepcopy(request.get('graph', state['activePlan']))
        case = state['case']
        result = execute(graph, case['observedWorlds'][0], case['task']['outputNodeId'])
        accepted = result == reference(case['task'], case['observedWorlds'][0])
        receipt = self.event('executed', workflowId=ident, graph=graph, graphHash=digest(graph),
                             result=result, publicDslAcceptance=accepted,
                             rawSourceSha256=state['rawSourceSha256'],
                             consumedUpdates=state['consumedUpdates'] if graph == state['activePlan'] else [],
                             consumedNativeDecisionIds=[state['activeNativeDecisionId']] if graph == state['activePlan'] and state.get('activeNativeDecisionId') else [])
        state['executions'].append(receipt)
        return {'result': result, 'publicDslAcceptance': accepted,
                'executionReceiptHash': receipt['eventHash'], 'officialHarborAcceptance': 'not_yet_graded'}

    def qualified_cases(self, official_receipt, receipt_sha):
        reward = official_receipt.get('reward')
        valid = type(reward) in (int, float) and math.isfinite(reward) and reward >= 1 and not official_receipt.get('error')
        self.event('official_source_gate', reward=reward, error=official_receipt.get('error'),
                   officialReceiptSha256=receipt_sha, qualified=valid)
        if not valid:
            return []
        cases = []
        for ident, state in self.states.items():
            if not state['originalInputSnapshot']:
                self.event('case_rejected', workflowId=ident, reason='original_input_provenance_required')
                continue
            passed = [r for r in state['executions'] if r['publicDslAcceptance']]
            if not passed:
                continue
            case = copy.deepcopy(state['case'])
            case['G_exec'] = copy.deepcopy(passed[-1]['graph'])
            case['executionEvidence'] = {'status': 'completed', 'acceptance': 'passed'}
            try:
                candidate_count = len(catalog(case['G_plan'], case['G_exec']))
            except (ValueError, KeyError, TypeError):
                self.event('case_rejected', workflowId=ident, reason='outside_native_catalog')
                continue
            if candidate_count > 12:
                self.event('case_rejected', workflowId=ident, reason='catalog_limit')
                continue
            cases.append(dict(workflowId=ident, case=case, executionReceiptHash=passed[-1]['eventHash'],
                              officialReceiptSha256=receipt_sha, originalInputSnapshot=True,
                              rawSourceSha256=state['rawSourceSha256'],runId=self.run_id,
                              taskInstructionSha256=self.instruction_sha))
        return cases


def certify_update(bound_case, prediction, require_minimum=True):
    case = bound_case['case']
    verification = verify_prediction(case, prediction, worlds=case['observedWorlds'])
    if not verification['valid'] or prediction.get('decision') != 'adopt':
        return {'adopted': False, 'reason': verification['reason']}
    if bound_case.get('originalInputSnapshot') is not True:
        return {'adopted': False, 'reason': 'original_input_provenance_required'}
    solution = solve(case, worlds=case['observedWorlds'], budget=64, candidate_limit=12)
    if require_minimum and (not solution['certified'] or verification['cost'] != solution.get('minimumCost')):
        return {'adopted': False, 'reason': 'minimum_not_certified'}
    update = dict(taskScope={k: v for k, v in case['task'].items() if k != 'name'},
                  basePlanHash=digest(case['G_plan']), prediction=copy.deepcopy(prediction),
                  executionReceiptHash=bound_case['executionReceiptHash'],
                  officialReceiptSha256=bound_case['officialReceiptSha256'],
                  sourceCaseHash=digest(case),rawSourceSha256=bound_case.get('rawSourceSha256'),
                  sourceRunId=bound_case.get('runId'),taskInstructionSha256=bound_case.get('taskInstructionSha256'),
                  verification=verification, minimumRequired=require_minimum)
    update['updateId'] = digest(update)
    return {'adopted': True, 'update': update}
