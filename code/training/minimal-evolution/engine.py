"""Finite, executable workflow laboratory. No model or production database imports.

Labels certify minimal cost only in the declared exec-derived candidate catalog.
Task success is measured by executing programs against independent acceptance tests.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
from fractions import Fraction

SCHEMA = 'rdmd_minimal_evolution_v1'
COSTS = {'set_param': 1, 'add_edge': 2, 'drop_edge': 2, 'add_node': 3, 'drop_node': 3}
PARAMS = {'source': set(), 'identity': set(), 'filter': {'minimum'},
          'scale': {'factor'}, 'dedup': {'key'}, 'aggregate': {'method'}}
INSTRUCTION = '''你是规划演化器。G_plan 是旧规划，G_exec 是一次执行后的工作流。
任务目标及验收由 task 给出，observations 是有限的可见验收样本，不是全部未来任务。
source 节点读取数据；filter 保留 quality>=minimum；scale 将 value 乘 factor；
dedup 按 key 去重且保留第一行；aggregate 按 method(sum/count/mean)聚合 value；identity 原样传递。
每个非 source 节点必须恰有一个输入。task.outputNodeId 指定交付节点。
方向只能 plan_toward_verified_exec。执行失败、取消或验收证据不足时必须 abstain。
从候选 catalog 选择具体 edits，保持其 op、前置条件和目标值原样；不要复制执行的 output/status。
只学习满足任务验收且不破坏观察样本的最低代价改动；代价=set_param:1,边:2,节点:3。
旧规划已满足时 no_change。无法给出可信改动时 abstain。sourceNodeIds 是所选改动的上游前沿，
只表示此候选空间内的干预位置，不能声称真实因果已被证明。多点修复可以有多个源。
仅输出 JSON：{"decision":"adopt|no_change|abstain","direction":"plan_toward_verified_exec|none",
"sourceNodeIds":[],"edits":[]}。不得输出解释。'''


def dumps(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(x):
    return hashlib.sha256(dumps(x).encode()).hexdigest()


def validate_graph(g):
    nodes = g['nodes']
    ids = [n['id'] for n in nodes]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError('node_identity')
    edges = [tuple(e) for e in g['edges']]
    if len(edges) != len(set(edges)):
        raise ValueError('duplicate_edge')
    for a, b in edges:
        if a not in ids or b not in ids or a == b:
            raise ValueError('edge_endpoint')
    done, order = set(), []
    while len(done) < len(nodes):
        ready = [n for n in nodes if n['id'] not in done and
                 all(a in done for a, b in edges if b == n['id'])]
        if not ready:
            raise ValueError('cycle')
        for n in ready:
            op, p = n['op'], n['params']
            if op not in PARAMS or set(p) != PARAMS[op]:
                raise ValueError('unsupported_operation_or_params')
            incoming = [a for a, b in edges if b == n['id']]
            if len(incoming) != (0 if op == 'source' else 1):
                raise ValueError('input_arity')
            if op in ('filter', 'scale') and (type(next(iter(p.values()))) is not int):
                raise ValueError('numeric_param')
            if op == 'dedup' and p['key'] not in ('id', 'category'):
                raise ValueError('dedup_key')
            if op == 'aggregate' and p['method'] not in ('sum', 'count', 'mean'):
                raise ValueError('aggregation_method')
            done.add(n['id']); order.append(n)
    return order


def execute(graph, rows, output_id):
    values = {}
    for n in validate_graph(graph):
        op, p = n['op'], n['params']
        value = copy.deepcopy(rows) if op == 'source' else copy.deepcopy(values[next(a for a, b in graph['edges'] if b == n['id'])])
        if op not in ('source', 'identity') and not isinstance(value, list):
            raise ValueError('table_required')
        if op == 'filter':
            value = [r for r in value if r['quality'] >= p['minimum']]
        elif op == 'scale':
            value = [{**r, 'value': r['value'] * p['factor']} for r in value]
        elif op == 'dedup':
            seen, unique = set(), []
            for r in value:
                if r[p['key']] not in seen:
                    seen.add(r[p['key']]); unique.append(r)
            value = unique
        elif op == 'aggregate':
            row_count = len(value)
            total = sum(r['value'] for r in value)
            value = row_count if p['method'] == 'count' else total
            if p['method'] == 'mean':
                value = Fraction(total, row_count) if row_count else Fraction(0)
        values[n['id']] = value
    if output_id not in values:
        raise ValueError('missing_output')
    value = values[output_id]
    return str(value) if isinstance(value, Fraction) else value


def reference(task, rows):
    """Independent task-spec evaluator, does not inspect G_exec or edit labels."""
    qualifying = [dict(r) for r in rows if r['quality'] >= task['minimum']]
    unique = {}
    for r in qualifying:
        unique.setdefault(r[task['dedupKey']], r['value'])
    vals = [v * task['factor'] for v in unique.values()]
    if task['aggregate'] == 'count':
        return len(vals)
    if task['aggregate'] == 'mean':
        return str(Fraction(sum(vals), len(vals))) if vals else '0'
    return sum(vals)


def succeeds(graph, case, worlds):
    try:
        return all(execute(graph, w, case['task']['outputNodeId']) == reference(case['task'], w) for w in worlds)
    except (ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError):
        return False


def catalog(plan, execution):
    left = {n['id']: n for n in plan['nodes']}
    right = {n['id']: n for n in execution['nodes']}
    edits = []
    for nid in sorted(right):
        target = right[nid]
        if nid not in left:
            edits.append({'op': 'add_node', 'nodeId': nid, 'before': None, 'after': copy.deepcopy(target)})
        else:
            original = left[nid]
            if original['op'] != target['op']:
                raise ValueError('operation_change_outside_catalog')
            for key in sorted(target['params']):
                if original['params'][key] != target['params'][key]:
                    edits.append({'op': 'set_param', 'nodeId': nid, 'field': key,
                                  'before': original['params'][key], 'after': target['params'][key]})
    for nid in sorted(set(left) - set(right)):
        edits.append({'op': 'drop_node', 'nodeId': nid, 'before': copy.deepcopy(left[nid]), 'after': None})
    le, re = set(map(tuple, plan['edges'])), set(map(tuple, execution['edges']))
    for edge in sorted(re - le):
        edits.append({'op': 'add_edge', 'from': edge[0], 'to': edge[1]})
    for edge in sorted(le - re):
        edits.append({'op': 'drop_edge', 'from': edge[0], 'to': edge[1]})
    return sorted(edits, key=dumps)


def apply_patch(plan, edits):
    """Atomic patch: validate all preconditions on original, then the complete DAG.

    Node deletion does NOT silently delete its edges; explicit edge edits cost money.
    """
    g = copy.deepcopy(plan)
    orig = {n['id']: n for n in plan['nodes']}
    nodes = {n['id']: n for n in g['nodes']}
    edges = set(map(tuple, g['edges']))
    seen = set()
    for e in edits:
        op = e['op']; nid = e.get('nodeId')
        key = (op, nid, e.get('field'), e.get('from'), e.get('to'))
        if key in seen or op not in COSTS:
            raise ValueError('duplicate_or_unknown_edit')
        seen.add(key)
        if op == 'set_param':
            if orig[nid]['params'][e['field']] != e['before']:
                raise ValueError('stale_precondition')
            nodes[nid]['params'][e['field']] = e['after']
        elif op == 'add_node':
            if nid in orig or e['before'] is not None or e['after']['id'] != nid:
                raise ValueError('add_precondition')
            nodes[nid] = copy.deepcopy(e['after'])
        elif op == 'drop_node':
            if orig[nid] != e['before'] or e['after'] is not None:
                raise ValueError('drop_precondition')
            del nodes[nid]
        elif op == 'add_edge':
            edge = (e['from'], e['to'])
            if edge in set(map(tuple, plan['edges'])):
                raise ValueError('edge_exists')
            edges.add(edge)
        elif op == 'drop_edge':
            edges.remove((e['from'], e['to']))
    g = {'nodes': list(nodes.values()), 'edges': [list(e) for e in sorted(edges)]}
    validate_graph(g)
    return g


def cost(edits):
    return sum(COSTS[e['op']] for e in edits)


def frontier(plan, execution, edits):
    affected = {e.get('nodeId') or e['to'] for e in edits}
    edges = set(map(tuple, plan['edges'] + execution['edges']))
    def ancestors(nid):
        todo, seen = [a for a, b in edges if b == nid], set()
        while todo:
            cur = todo.pop()
            if cur in seen:
                continue
            seen.add(cur); todo.extend(a for a, b in edges if b == cur)
        return seen
    return sorted(n for n in affected if not (ancestors(n) & (affected - {n})))


def answer(case, edits=None, decision='adopt'):
    edits = sorted(edits or [], key=dumps)
    return {'decision': decision, 'direction': 'plan_toward_verified_exec' if decision == 'adopt' else 'none',
            'sourceNodeIds': frontier(case['G_plan'], case['G_exec'], edits) if decision == 'adopt' else [], 'edits': edits}


def evidence_qualified(case):
    return case['executionEvidence'] == {'status': 'completed', 'acceptance': 'passed'}


def solve(case, worlds=None, budget=4096, candidate_limit=12):
    worlds = worlds if worlds is not None else case['verificationWorlds']
    if not worlds:
        return {'answer': answer(case, decision='abstain'), 'reason': 'no_verification_worlds', 'certified': False}
    if not evidence_qualified(case):
        return {'answer': answer(case, decision='abstain'), 'reason': 'unverified_execution', 'certified': True}
    if not succeeds(case['G_exec'], case, worlds):
        return {'answer': answer(case, decision='abstain'), 'reason': 'execution_failed_replay', 'certified': True}
    if succeeds(case['G_plan'], case, worlds):
        return {'answer': answer(case, decision='no_change'), 'reason': 'already_successful', 'certified': True, 'minimumCost': 0}
    candidates = catalog(case['G_plan'], case['G_exec'])
    if len(candidates) > candidate_limit:
        return {'answer': answer(case, decision='abstain'), 'reason': 'catalog_limit', 'certified': False}
    subsets = (list(s) for k in range(1, len(candidates)+1) for s in itertools.combinations(candidates, k))
    subsets = sorted(subsets, key=lambda es: (cost(es), dumps(es)))
    tried = 0; valid = []; minimum = None
    for edits in subsets:
        if minimum is not None and cost(edits) > minimum:
            break
        if tried >= budget:
            return {'answer': answer(case, decision='abstain'), 'reason': 'search_budget', 'certified': False, 'searched': tried}
        tried += 1
        try:
            patched = apply_patch(case['G_plan'], edits)
        except (ValueError, KeyError, TypeError):
            continue
        if succeeds(patched, case, worlds):
            minimum = cost(edits); valid.append(edits)
    if not valid:
        return {'answer': answer(case, decision='abstain'), 'reason': 'no_feasible_patch', 'certified': True, 'searched': tried}
    return {'answer': answer(case, valid[0]), 'reason': 'minimum_in_declared_catalog', 'certified': True,
            'minimumCost': minimum, 'equivalentOptima': len(valid), 'searched': tried,
            'witnessHash': digest(worlds), 'catalogHash': digest(candidates)}


def verify_prediction(case, pred, worlds=None):
    worlds = case['verificationWorlds'] if worlds is None else worlds
    if not isinstance(pred, dict) or set(pred) != {'decision', 'direction', 'sourceNodeIds', 'edits'}:
        return {'valid': False, 'reason': 'output_schema'}
    if pred['decision'] not in ('adopt', 'no_change', 'abstain'):
        return {'valid': False, 'reason': 'decision'}
    if pred['decision'] != 'adopt':
        legal = pred['direction'] == 'none' and pred['edits'] == [] and pred['sourceNodeIds'] == []
        if not legal:
            return {'valid': False, 'reason': 'non_adopt_has_patch'}
        if pred['decision'] == 'abstain':
            return {'valid': True, 'reason': 'abstained', 'cost': 0}
        ok = bool(worlds) and evidence_qualified(case) and succeeds(case['G_exec'], case, worlds) and succeeds(case['G_plan'], case, worlds)
        return {'valid': ok, 'reason': 'no_change_verified' if ok else 'false_no_change', 'cost': 0}
    if not evidence_qualified(case) or not worlds:
        return {'valid': False, 'reason': 'unverified_execution'}
    if pred['direction'] != 'plan_toward_verified_exec' or not isinstance(pred['edits'], list) or not pred['edits']:
        return {'valid': False, 'reason': 'patch_shape'}
    try:
        allowed = {dumps(e) for e in catalog(case['G_plan'], case['G_exec'])}
        if any(dumps(e) not in allowed for e in pred['edits']):
            return {'valid': False, 'reason': 'outside_catalog'}
        if pred['sourceNodeIds'] != frontier(case['G_plan'], case['G_exec'], pred['edits']):
            return {'valid': False, 'reason': 'source_patch_mismatch'}
        patched = apply_patch(case['G_plan'], pred['edits'])
        ok = succeeds(case['G_exec'], case, worlds) and succeeds(patched, case, worlds)
        return {'valid': ok, 'reason': 'replay_pass' if ok else 'replay_failed', 'cost': cost(pred['edits'])}
    except (ValueError, KeyError, TypeError):
        return {'valid': False, 'reason': 'invalid_patch'}


def prompt(case):
    payload = {k: case[k] for k in ('task', 'G_plan', 'G_exec', 'executionEvidence')}
    payload['catalog'] = catalog(case['G_plan'], case['G_exec'])
    payload['observations'] = [{'rows': w, 'expected': reference(case['task'], w)} for w in case['observedWorlds']]
    return INSTRUCTION + '\nINPUT=' + dumps(payload)
