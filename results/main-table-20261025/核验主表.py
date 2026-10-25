import csv, pathlib, collections
from decimal import Decimal
root=pathlib.Path(__file__).resolve().parent
with (root/'主表.csv').open(encoding='utf-8-sig',newline='') as f: table={x['method']:x for x in csv.DictReader(f)}
count=0
for p in sorted((root/'逐题数据').glob('*.csv')):
    groups=collections.defaultdict(list)
    with p.open(encoding='utf-8-sig',newline='') as f:
        for x in csv.DictReader(f): groups[x['method']].append(x)
    assert set(groups)==set(table)
    tasksets=[]
    for method,rows in groups.items():
        ids={x['task_id'] for x in rows};assert len(ids)==len(rows);tasksets.append(ids)
        values=[Decimal(x['official_reward']) for x in rows]
        raw=sum(x>=1 for x in values) if p.stem in ['SkillFlow','tau-bench'] else sum(values,Decimal(0))
        display=format(float(raw)/(len(rows)/100),'.2f')
        assert display==table[method][p.stem],(method,p.stem,display)
        count+=1
    assert all(ids==tasksets[0] for ids in tasksets)
assert count==32
print('PASS: all 32 scores match; task IDs unique and method task sets identical.')
