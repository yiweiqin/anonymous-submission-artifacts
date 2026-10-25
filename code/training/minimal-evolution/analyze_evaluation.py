"""Recompute task metrics from downloaded raw outputs and frozen local cases."""
import argparse
import json
from collections import Counter
from pathlib import Path

from audit import rows
from compare import compare
from evaluate import parse, score, summarize
from prepare import HERE, sha
from policy import propose_next_plan
from engine import answer, dumps, verify_prediction


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--data', type=Path, default=HERE / 'data')
    a = p.parse_args()
    run = json.loads((a.snapshot / 'runs/minimal-evolution-sft-seed20260923/run_manifest.json').read_text())
    snapshot = json.loads((a.snapshot / 'snapshot.json').read_text())
    for name, expected in snapshot['files'].items():
        if sha(a.snapshot / name) != expected['sha256']:
            raise ValueError('local_evidence_changed:' + name)
    result = {'endpoint': snapshot['endpoint'], 'pending': snapshot['pending'],
              'trainingSteps': run['steps'], 'arms': {}, 'comparisons': {}}
    for name in snapshot['completed']:
        folder = a.snapshot / 'eval' / name
        summary = json.loads((folder / 'summary.json').read_text())
        meta = json.loads((folder / 'provenance.json').read_text())
        file = a.data / (meta['split'] + '.cases.jsonl')
        if sha(file) != meta['caseSha256'] or sha(HERE / 'engine.py') != meta['engineSha256']:
            raise ValueError('case_or_engine_mismatch:' + name)
        if sha(folder / 'requests.jsonl') != meta['requestSha256']:
            raise ValueError('requests_mismatch:' + name)
        cases = {c['id']: c for c in rows(file)}
        predictions = list(rows(folder / 'predictions.jsonl'))
        if len(predictions) != len(cases) or {r['id'] for r in predictions} != set(cases):
            raise ValueError('incomplete_or_duplicate_predictions:' + name)
        if meta['arm'] in ('trained', 'H3_base'):
            expected = {k: v['sha256'] for k, v in run['environment']['baseFiles'].items()
                        if k.endswith('.safetensors')}
            if meta['baseHashes'] != expected:
                raise ValueError('base_weights_changed:' + name)
            if meta['arm'] == 'trained' and meta['adapterHashes'] != run['adapterHashes']:
                raise ValueError('adapter_changed:' + name)
        confusion = Counter()
        failure_reasons = Counter()
        modes = {}
        examples = []
        omissions = Counter()
        gate = {'adopted': 0, 'unsafeAfterVisibleGate': 0, 'blockedUnsafeProposals': 0}
        source_only = 0
        for r in predictions:
            c = cases[r['id']]
            if meta['arm'] in ('trained', 'H3_base') and parse(r['raw']) != r['prediction']:
                raise ValueError('raw_prediction_mismatch:' + r['id'])
            if r['groupId'] != c['groupId'] or r['goldDecision'] != c['oracle']['answer']['decision']:
                raise ValueError('gold_or_group_mismatch:' + r['id'])
            checked = score(c, r['prediction'])
            if checked != r['metrics']:
                raise ValueError('score_not_reproducible:' + r['id'])
            predicted = (r['prediction'] or {}).get('decision', 'parse_error')
            confusion[f"{r['goldDecision']} -> {predicted}"] += 1
            mode = modes.setdefault(r['mode'], {'n': 0, 'repairN': 0, 'minimal': 0, 'unsafe': 0})
            mode['n'] += 1
            mode['repairN'] += r['goldDecision'] == 'adopt'
            mode['minimal'] += bool(checked['minimalRepair'])
            mode['unsafe'] += bool(checked['unsafeAdoption'])
            if checked['unsafeAdoption'] or checked['parseError']:
                reason = checked.get('verification', {}).get('reason', 'parse_error')
                failure_reasons[reason] += 1
                if len(examples) < 8:
                    examples.append({'id': r['id'], 'mode': r['mode'], 'reason': reason,
                                     'prediction': r['prediction'], 'gold': c['oracle']['answer']})
            if meta['arm'] == 'trained':
                # The operational gate sees no gold, hidden or transfer worlds.
                visible = {k: c[k] for k in ('task', 'G_plan', 'G_exec', 'executionEvidence', 'observedWorlds')}
                accepted = propose_next_plan(visible, r['prediction'])['adopted']
                gate['adopted'] += accepted
                gate['unsafeAfterVisibleGate'] += accepted and checked['unsafeAdoption']
                gate['blockedUnsafeProposals'] += not accepted and checked['unsafeAdoption']
                if checked['unsafeAdoption'] and isinstance(r['prediction'], dict):
                    edits = r['prediction'].get('edits', [])
                    predicted_edits = {dumps(e) for e in edits}
                    for e in c['oracle']['answer']['edits']:
                        if dumps(e) not in predicted_edits:
                            omissions[e.get('field', e['op'])] += 1
                    # Diagnostic only: never rewrite raw predictions or official scores.
                    if checked.get('verification', {}).get('reason') == 'source_patch_mismatch':
                        bound = answer(c, edits)
                        source_only += (verify_prediction(c, bound)['valid'] and
                                        verify_prediction(c, bound, c['transferWorlds'])['valid'])
        recalculated = summarize(predictions)
        if any(summary[k] != v for k, v in recalculated.items()):
            raise ValueError('summary_not_reproducible:' + name)
        result['arms'][name] = {**recalculated, 'confusion': dict(confusion),
                               'failureReasons': dict(failure_reasons), 'modes': modes,
                               'failureExamples': examples, 'weightsAndScoresVerified': True}
        if meta['arm'] == 'trained':
            result['arms'][name]['diagnostics'] = {'visibleGate': gate, 'missingOracleFieldsOnUnsafe': dict(omissions),
                                                  'validPatchWithWrongSource': source_only,
                                                  'posthocNotUsedToAlterOfficialScores': True}
    for split in ('holdout', 'test'):
        if all(f'{arm}-{split}-batch' in result['arms'] for arm in ('sft', 'h3')):
            result['comparisons'][split] = compare(a.snapshot / f'eval/sft-{split}-batch',
                                                   a.snapshot / f'eval/h3-{split}-batch')
    out = a.snapshot / 'analysis.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'verifiedArms': list(result['arms']), 'comparisons': result['comparisons'],
                      'pending': result['pending']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
