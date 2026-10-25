"""Offline integrity and aggregate checks for the packaged robustness results."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,math

P=Path(__file__).resolve().parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    manifest=load(P/'manifest.json')
    listed={x['path'] for x in manifest['files']}
    actual={f.relative_to(P).as_posix() for f in P.rglob('*') if f.is_file() and f not in [P/'manifest.json',P/'verification.json']}
    assert listed==actual,'manifest coverage differs'
    for row in manifest['files']:
        b=(P/row['path']).read_bytes();assert len(b)==row['bytes'] and sha(b)==row['sha256'],row['path']
    copied=load(P/'source-copy-index.json')
    for row in copied:
        # Also prove that the organization pass did not modify original evidence.
        assert sha(Path(row['source']).read_bytes())==row['sha256'],row['source']
        assert sha((P/row['destination']).read_bytes())==row['sha256'],row['destination']
    receipts=load(P/'remote-receipt-index.json')
    for row in receipts:
        b=(P/row['destination']).read_bytes();assert sha(b)==row['sha256']
        rs=json.loads(b) if row['destination'].endswith('.json') else [json.loads(x) for x in b.splitlines() if x.strip()]
        assert len(rs)==row['rows']
    evidence_maps=0
    for version in ['tb-v4','tb-v5']:
        m=load(P/'evidence'/version/'manifest.json')
        for meta in m['files'].values():
            b=(P/'evidence/objects'/meta['sha256']).read_bytes()
            assert sha(b)==meta['sha256'] and len(b)==meta['bytes'];evidence_maps+=1
    results=load(P/'final-results.json');assert results['paperReady'] is False
    with (P/'per-task-final-results.csv').open(encoding='utf-8-sig',newline='') as f:tasks=list(csv.DictReader(f))
    suite_map={'Terminal-Bench 2.1':'Terminal-Bench 2.1 v5','InterCode SQL':'InterCode SQL v21','InterCode Bash':'InterCode Bash','τ-bench':'τ-bench'}
    for r in results['results']:
        rows=[x for x in tasks if x['benchmark']==suite_map[r['benchmark']]]
        assert len(rows)==len({x['id'] for x in rows})==r['tasks']
        a=math.fsum(float(x['system_reward']) for x in rows);b=math.fsum(float(x['control_reward']) for x in rows)
        assert abs(a-r['system_score'])<1e-8 and abs(b-r['control_score'])<1e-8
        assert sum(float(x['difference'])>1e-9 for x in rows)==r['higher']
        assert sum(float(x['difference']) < -1e-9 for x in rows)==r['lower']
        assert sum(abs(float(x['difference']))<=1e-9 for x in rows)==r['ties']
    audit=load(P/'sources/tb-v5/goal-completion-audit.json');assert audit['readyToComplete'] and all(audit['checks'].values())
    sql=load(P/'sources/sql-v21/full-summary.json');assert sql['comparison']['allAuditsPassed'] and sql['allPairedOfficialComplete']
    expansion=load(P/'sources/tb-v5/expansion-analysis.json');assert expansion['expansionOnly']['qualifiedPairedDelta']==0
    report={'schema':'robustness-bundle-verification-v1','checkedAt':datetime.now(timezone.utc).isoformat(),'passed':True,'fileManifestSha256':sha((P/'manifest.json').read_bytes()),'filesVerified':len(listed),'originalSourceFilesUnchanged':len(copied),'remoteReceiptFilesVerified':len(receipts),'tbEvidenceMappingsVerified':evidence_maps,'finalTaskPairsVerified':len(tasks),'finalComparisons':len(results['results']),'newModelCalls':0,'newGraderCalls':0,'paperReady':False,'scope':'Local bytes, source digests, archived receipt counts, existing audit gates and per-task aggregates. No model calls, official regrading or independent reenactment of remote SQL/tau trajectories.'}
    (P/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
