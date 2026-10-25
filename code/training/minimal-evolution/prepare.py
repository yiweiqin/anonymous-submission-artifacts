"""Generate paired, executable counterfactual supervision; no LLM labeling."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from engine import SCHEMA, answer, catalog, cost, digest, dumps, prompt, solve, succeeds, verify_prediction

HERE = Path(__file__).resolve().parent
MODES = ('single', 'multiple', 'rewire', 'insert', 'no_change', 'failed', 'unverified', 'false_success')


def worlds(rng, count, task):
    result = []
    for i in range(count):
        rows = []
        for j in range(8 + i % 3):
            rows.append({'id': j % 5, 'category': j % 3, 'quality': rng.randint(-2, 8), 'value': rng.randint(-8, 30)})
        # Explicit boundary / duplicate counterexamples supplement randomized worlds.
        rows += [{'id': 90, 'category': 90, 'quality': task['minimum']-1, 'value': 19},
                 {'id': 91, 'category': 91, 'quality': task['minimum'], 'value': 7},
                 {'id': 91, 'category': 91, 'quality': task['minimum']+1, 'value': 31}]
        result.append(rows)
    return result


def make_group(split, index, seed):
    rng = random.Random(f'{seed}:{split}:{index}')
    suffix = digest([seed, split, index])[:12]
    labels = list(range(100, 999)); rng.shuffle(labels)
    ids = {name: f'n{labels[i]}' for i, name in enumerate(('source', 'filter', 'dedup', 'scale', 'aggregate', 'side', 'identity'))}
    task = {'name': rng.choice(['订单汇总', '样本统计', '库存核对', '实验数据汇总']),
            'minimum': rng.randint(0, 5), 'factor': rng.randint(2, 7),
            'dedupKey': rng.choice(['id', 'category']),
            'aggregate': 'mean' if split == 'holdout' else rng.choice(['sum', 'count']),
            'outputNodeId': ids['aggregate']}
    params = {'source': {}, 'filter': {'minimum': task['minimum']}, 'dedup': {'key': task['dedupKey']},
              'scale': {'factor': task['factor']}, 'aggregate': {'method': task['aggregate']},
              'side': {'factor': 9}, 'identity': {}}
    order = ['source', 'filter', 'dedup', 'scale', 'aggregate']
    if rng.random() < .5:
        order = ['source', 'scale', 'filter', 'dedup', 'aggregate']
    if split == 'holdout':
        order.insert(-1, 'identity')
    exec_graph = {'nodes': [{'id': ids[k], 'op': 'scale' if k == 'side' else k, 'params': params[k]}
                            for k in order + ['side']],
                  'edges': [[ids[a], ids[b]] for a, b in zip(order, order[1:])] + [[ids['source'], ids['side']]]}
    rng.shuffle(exec_graph['nodes']); rng.shuffle(exec_graph['edges'])
    observed = worlds(rng, 2, task)
    verification = observed + worlds(rng, 6, task) + [[]]
    transfer = worlds(rng, 8, task)
    for mode in MODES:
        execution = copy.deepcopy(exec_graph); plan = copy.deepcopy(exec_graph)
        by_id = {n['id']: n for n in plan['nodes']}
        # Irrelevant execution difference is present in every case, so copying all diffs costs more.
        by_id[ids['side']]['params']['factor'] = 1
        evidence = {'status': 'completed', 'acceptance': 'passed'}
        if mode in ('single', 'failed', 'unverified', 'false_success'):
            by_id[ids['filter']]['params']['minimum'] += 2
        elif mode == 'multiple':
            by_id[ids['filter']]['params']['minimum'] += 2
            by_id[ids['dedup']]['params']['key'] = 'category' if task['dedupKey'] == 'id' else 'id'
            if split == 'holdout':
                by_id[ids['scale']]['params']['factor'] = 1
        elif mode == 'rewire':
            chosen = ids['dedup'] if split == 'holdout' else ids['filter']
            prior = next(a for a, b in plan['edges'] if b == chosen)
            successor = next(b for a, b in plan['edges'] if a == chosen)
            plan['edges'].remove([chosen, successor]); plan['edges'].append([prior, successor])
        elif mode == 'insert':
            chosen = ids['dedup'] if split == 'holdout' else ids['scale']
            prior = next(a for a, b in plan['edges'] if b == chosen)
            successor = next(b for a, b in plan['edges'] if a == chosen)
            plan['nodes'] = [n for n in plan['nodes'] if n['id'] != chosen]
            plan['edges'] = [e for e in plan['edges'] if chosen not in e] + [[prior, successor]]
        if mode == 'failed':
            evidence = {'status': rng.choice(['failed', 'cancelled']), 'acceptance': 'failed'}
        elif mode == 'unverified':
            evidence = {'status': 'completed', 'acceptance': 'unknown'}
        elif mode == 'false_success':
            next(n for n in execution['nodes'] if n['id'] == ids['filter'])['params']['minimum'] += 3
        case = {'id': f'{split}-{suffix}-{mode}', 'groupId': f'{split}-{suffix}', 'split': split,
                'task': task, 'G_plan': plan, 'G_exec': execution, 'executionEvidence': evidence,
                'observedWorlds': observed, 'verificationWorlds': verification, 'transferWorlds': transfer,
                'generation': {'mode': mode, 'seed': seed, 'index': index, 'synthetic': True}}
        yield case


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def build(out, config):
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': SCHEMA, 'seed': config['seed'], 'status': 'BUILDING',
                'scope': 'synthetic_executable_table_workflows', 'files': {}, 'splits': {},
                'heldout': {'aggregate': 'mean', 'insertedOperation': 'dedup', 'rewiredOperation': 'dedup', 'simultaneousParameterChanges': 3},
                'labelWorlds': 'observed+verification', 'transferWorldsUsedForLabels': False,
                'generatorSha256': sha(__file__), 'engineSha256': sha(HERE/'engine.py'),
                'configSha256': sha(HERE/'config.json')}
    for split in ('train', 'development', 'test', 'holdout'):
        counts = Counter(); min_costs = Counter(); max_candidates = 0
        count = int(config[f'{split}Groups'])
        with (out/f'{split}.cases.jsonl').open('w', encoding='utf8', newline='\n') as raw, \
             (out/f'{split}.sft.jsonl').open('w', encoding='utf8', newline='\n') as sft, \
             (out/f'{split}.preferences.jsonl').open('w', encoding='utf8', newline='\n') as prefs:
            for index in range(count):
                for case in make_group(split, index, config['seed']):
                    oracle = solve(case, budget=config['searchBudget'], candidate_limit=config['candidateLimit'])
                    if not oracle['certified']:
                        raise ValueError(f'uncertified_label:{case["id"]}:{oracle}')
                    case['oracle'] = oracle
                    gold = oracle['answer']
                    if not verify_prediction(case, gold)['valid']:
                        raise ValueError(f'invalid_gold:{case["id"]}')
                    raw.write(dumps(case)+'\n')
                    row = {'id': case['id'], 'groupId': case['groupId'], 'split': split,
                           'prompt': prompt(case), 'completion': dumps(gold), 'decision': gold['decision']}
                    sft.write(dumps(row)+'\n')
                    counts[gold['decision']] += 1
                    if gold['decision'] == 'adopt':
                        min_costs[oracle['minimumCost']] += 1
                    cat = catalog(case['G_plan'], case['G_exec']); max_candidates = max(max_candidates, len(cat))
                    negatives = [answer(case, cat), answer(case, decision='no_change')]
                    if gold['decision'] == 'adopt':
                        negatives += [answer(case, gold['edits'][:-1]), {**gold, 'sourceNodeIds': []}]
                    for negative in {dumps(n): n for n in negatives}.values():
                        checked = verify_prediction(case, negative)
                        worse = not checked['valid'] or (gold['decision'] == 'adopt' and checked.get('cost', 0) > oracle['minimumCost'])
                        if negative != gold and worse:
                            prefs.write(dumps({'id': case['id'], 'groupId': case['groupId'], 'chosen': gold,
                                              'rejected': negative, 'reason': checked['reason'] if not checked['valid'] else 'excess_cost'})+'\n')
        manifest['splits'][split] = {'groups': count, 'rows': sum(counts.values()), 'decisions': dict(counts),
                                     'minimumCosts': dict(min_costs), 'maxCandidates': max_candidates}
        print(dumps({split: manifest['splits'][split]}), flush=True)
    for f in sorted(out.glob('*.jsonl')):
        manifest['files'][f.name] = {'sha256': sha(f), 'bytes': f.stat().st_size,
                                     'rows': sum(1 for _ in f.open(encoding='utf8'))}
    manifest['status'] = 'PREPARED_NOT_TRAINED'
    (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    return manifest


def main():
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, default=HERE/'data')
    p.add_argument('--smoke', action='store_true'); args=p.parse_args()
    cfg=json.loads((HERE/'config.json').read_text())
    if args.smoke:
        cfg.update({f'{s}Groups': 2 for s in ('train','development','test','holdout')})
    build(args.out, cfg)


if __name__ == '__main__':
    main()
