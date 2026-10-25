"""Read-only result packaging. No model, grading or experiment execution."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv, hashlib, html, json, math, os, re, shutil, sys

OUT = Path(__file__).resolve().parent
E = OUT.parent / 'skillflow_mechanism_20261013'
sys.path.insert(0, str(E))
SOURCE_FILES = []
SECRETS = [v.encode() for k,v in os.environ.items()
           if re.search(r'(API_?KEY|SSH_PASSWORD)$', k, re.I) and len(v) >= 8]

def load(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def checked(raw):
    assert not any(v in raw for v in SECRETS), 'configured credential present; content withheld'
    return raw

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def copy_file(src, dest):
    raw = checked(src.read_bytes())
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        assert dest.read_bytes() == raw, 'existing packaged file differs: '+str(dest.relative_to(OUT))
    else:
        dest.write_bytes(raw)
    SOURCE_FILES.append({'source':str(src), 'destination':dest.relative_to(OUT).as_posix(),
                         'sha256':digest(raw), 'bytes':len(raw)})

def csv_write(name, rows):
    with (OUT/name).open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def result(suite, variant, n, a, b, metric, scope, source, **kw):
    return dict(benchmark=suite, variant=variant, tasks=n, metric=metric,
                system_score=a, control_score=b, difference=a-b,
                system_mean=a/n, control_mean=b/n, scope=scope,
                source=source, paperReady=False, **kw)

def main():
    assert SECRETS, 'Load normal credential environment for configured-value exclusion checks.'
    tb=load(E/'tb-v5/full-summary.json'); sql=load(E/'sql-v21/full-summary.json')
    ic=load(E/'intercode-official-summary.json'); tau=load(E/'tau-official-summary.json')
    assert tb['fullComparisonAudited'] and tb['completeQualifiedCoverage'] and all(tb['checks'].values())
    assert load(E/'tb-v5/goal-completion-audit.json')['readyToComplete']
    assert sql['allPairedOfficialComplete'] and sql['comparison']['allAuditsPassed']
    assert ic['complete'] and tau['complete']
    results=[
      result('Terminal-Bench 2.1','trained-terminal-v5',63,tb['sums']['trained-terminal-v5'],tb['sums']['control-terminal-interface-v3'],'official pass count','资源兼容63题；不是89题整榜','sources/tb-v5/full-summary.json',higher=12,lower=8,ties=43,control='control-terminal-interface-v3'),
      result('InterCode Bash','native-trained-frozen-source',200,ic['bashFrozen']['rewardSum'],ic['bashStart']['rewardSum'],'official reward sum','Bash200题','sources/root/intercode-official-summary.json',higher=30,lower=21,ties=149,control=ic['bashStart']['arm']),
      result('InterCode SQL','native-trained-sql-closed-choice-v21',1015,sql['arms']['trained']['officialRewardSum'],sql['arms']['start']['officialRewardSum'],'official reward sum','Spider dev预检通过1015/1034题；排除19题','sources/sql-v21/full-summary.json',higher=23,lower=13,ties=979,control='唯一匹配v18接口无规划对照，原样复用'),
      result('τ-bench','native-trained-public-planner-v2',165,tau['trained']['passed'],tau['start']['passed'],'official pass^1 count','零售115+航空50；实际用户模拟器deepseek-flash','sources/root/tau-official-summary.json',higher=14,lower=7,ties=144,control=tau['start']['arm'])]
    csv_write('final-results.csv',results)
    write_json(OUT/'final-results.json', {'schema':'janus-robustness-consolidated-v1','createdAt':datetime.now(timezone(timedelta(hours=8))).isoformat(),'paperReady':False,'results':results,'costUSD':None,'newModelCalls':0,'newGraderCalls':0})

    # Copy reports without altering original ledgers, receipts or frozen files.
    root_names={'robustness-ledger.json','robustness-evidence-status.json','native-system-freeze.json','native-target-launch.json','goal-completion-audit.json','deepseek-mode-audit.json','model-contract-audit.json','HANDOFF-robustness-20261019.zh-CN.md'}
    for f in E.iterdir():
        if f.is_file() and (f.name in root_names or (f.suffix=='.json' and any(s in f.name for s in ['audit','summary','oracle','precheck','exposure']))):
            copy_file(f,OUT/'sources/root'/f.name)
    variants=sorted([d for d in E.iterdir() if d.is_dir() and re.fullmatch(r'(sql|tb)-v\d+',d.name)],key=lambda d:(d.name.split('-')[0],int(d.name.split('v')[-1])))
    excluded=('launch','runtime','live-snapshot','transport','preplan','development-plans')
    for d in variants:
        for f in d.rglob('*'):
            if not f.is_file() or f.suffix not in ['.json','.jsonl']: continue
            rel=f.relative_to(d)
            if any(x in rel.parts for x in ['evidence','__pycache__','preplan-attempts']):continue
            if any(x in f.name for x in excluded):continue
            copy_file(f,OUT/'sources'/d.name/rel)
    manual=OUT.parent/'all-experiments-20260930/next-program/06-鲁棒性实验.zh-CN.md'
    copy_file(manual,OUT/'sources/constraints'/manual.name)

    # Canonical final TB archives: one shared hash-addressed object pool.
    object_count=0
    for version in ['tb-v4','tb-v5']:
        latest=load(E/version/'evidence-latest.json'); snapshot=Path(latest['snapshot']); manifest=load(snapshot)
        assert digest(snapshot.read_bytes())==latest['manifestSha256']
        copy_file(snapshot,OUT/'evidence'/version/'manifest.json')
        for meta in manifest['files'].values():
            sha=meta['sha256']; src=E/version/'evidence/objects'/sha
            if not src.exists(): src=E/version/'evidence/objects'/sha[:2]/sha
            assert src.exists(), 'missing evidence object '+sha
            raw=checked(src.read_bytes()); assert digest(raw)==sha and len(raw)==meta['bytes']
            dest=OUT/'evidence/objects'/sha
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);object_count+=1

    # Archive the original full-suite receipts and every available SQL pilot.
    # Downloads read only existing JSONL. No environment reset or score recomputation.
    sources={}
    def remote_receipt(root, sha=None, label=None, filename='receipts.jsonl'):
        path=root.rstrip('/')+'/'+filename
        if path in sources:
            if sha: assert sources[path]['expectedSha256'] in [None,sha]; sources[path]['expectedSha256']=sha
            return
        sources[path]={'expectedSha256':sha,'label':label or root.split('/')[-1]}
    for k,v in ic.items():
        if isinstance(v,dict) and 'root' in v:remote_receipt(v['root'],v['receiptsSha256'],k)
    for k in ['trained','start']:remote_receipt(tau[k]['root'],tau[k]['receiptsSha256'],'tau-'+k)
    for d in variants:
        if not d.name.startswith('sql-'):continue
        for name in ['pilot-trained-launch.json','pilot-start-launch.json','trained-launch.json','start-launch.json']:
            f=d/name
            if not f.exists():continue
            v=load(f);root=v.get('score')
            if root:remote_receipt(root,label=d.name+'-'+name.replace('-launch.json',''))
        f=d/'full-summary.json'
        if f.exists():
            summary=load(f)
            for arm,info in summary['arms'].items():
                if arm=='start' and d.name=='sql-v21':root=summary['matchedInitialInterfaceAudit']['controlRoot']
                else:
                    f2=d/('trained-launch.json' if arm=='trained' else 'start-launch.json')
                    if not f2.exists():
                        # v16 never executed a full control; its adopted48 are the whole file.
                        root='/benchmark/skillflow-main-20261008/cross-benchmark-20261013/intercode-sql-closed-'+d.name.split('-')[1]+'-'+('trained' if arm=='trained' else 'start')+'-c3e46d827cfc9d4c704ec078f7abf9f41e3191d8'
                    else:root=load(f2)['score']
                remote_receipt(root,info['receiptsSha256'],d.name+'-full-'+arm)
                for block in info.get('sourceBlocks',[]):remote_receipt(block['source'],block['receiptSha256'])
    original=load(E/'terminal-paired-baseline-audit.json')
    for root,sha in original['receiptDigests'].items():remote_receipt(root,sha,'terminal-original-'+root.split('/')[-1],filename='target-receipts.json')
    from native_preflight import connect
    client=connect('LIGHTHOUSE');sftp=client.open_sftp(); remote_records=[]
    try:
        for path,meta in sources.items():
            with sftp.open(path,'rb') as f:raw=f.read()
            checked(raw);sha=digest(raw)
            if meta['expectedSha256']:assert sha==meta['expectedSha256'],'source receipt hash changed: '+meta['label']
            rows=json.loads(raw) if path.endswith('.json') else [json.loads(x) for x in raw.splitlines() if x.strip()]
            dest=OUT/'receipts'/Path(path).parent.name/Path(path).name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(raw)
            rec={'source':path,'destination':dest.relative_to(OUT).as_posix(),'sha256':sha,'bytes':len(raw),'rows':len(rows),'priorAuditDigestMatched':bool(meta['expectedSha256']),'label':meta['label']}
            remote_records.append(rec)
            print('Archived receipt',meta['label'],len(rows),flush=True)
    finally:sftp.close();client.close()
    write_json(OUT/'remote-receipt-index.json',remote_records)

    # Task-level final comparisons: data are taken from the archived official receipts.
    by_sha={r['sha256']:OUT/r['destination'] for r in remote_records}
    taskrows=[]
    def pair_rows(suite,ta,co):
        assert set(ta)==set(co)
        for key in sorted(ta):taskrows.append({'benchmark':suite,'id':key,'system_reward':ta[key],'control_reward':co[key],'difference':ta[key]-co[key]})
    pair_rows('Terminal-Bench 2.1 v5',{k:v['trained-terminal-v5'] for k,v in tb['pairs'].items()},{k:v['control-terminal-interface-v3'] for k,v in tb['pairs'].items()})
    pair_rows('InterCode SQL v21',sql['arms']['trained']['rows'],sql['arms']['start']['rows'])
    def receipt_rewards(v,trained=False):
        rows=[json.loads(x) for x in by_sha[v['receiptsSha256']].read_bytes().splitlines() if x.strip()]
        valid=[r for r in rows if r.get('arm')==v['arm'] and not r.get('error') and type(r.get('reward')) in [int,float] and math.isfinite(r['reward']) and (r.get('frozenWeightPromptTokens',0)>=1 if trained else r.get('frozenWeightPromptTokens')==0)]
        assert len(valid)==len({r['id'] for r in valid})==v['tasks']
        assert abs(math.fsum(r['reward'] for r in valid)-v.get('rewardSum',v.get('officialRewardSum')))<1e-8
        return {r['id']:r['reward'] for r in valid}
    pair_rows('InterCode Bash',receipt_rewards(ic['bashFrozen'],True),receipt_rewards(ic['bashStart']))
    pair_rows('τ-bench',receipt_rewards(tau['trained'],True),receipt_rewards(tau['start']))
    # Check SQL task rows against full original raw receipts, including their error flags.
    for arm in ['trained','start']:
        info=sql['arms'][arm];raw=by_sha[info['receiptsSha256']].read_bytes();rs=[json.loads(x) for x in raw.splitlines() if x.strip()]
        good={r['id']:r['reward'] for r in rs if not r.get('error') and type(r.get('reward')) in [int,float] and math.isfinite(r['reward'])}
        assert good==info['rows'] and len(good)==1015
    csv_write('per-task-final-results.csv',taskrows)

    history=[]
    for d in variants:
        for f in sorted(d.rglob('*summary*.json')):
            if 'evidence' in f.relative_to(d).parts:continue
            v=load(f);c=v.get('comparison',{});arms=v.get('arms',{})
            t=v.get('trained',arms.get('trained',{}));b=v.get('control',arms.get('start',{}))
            if isinstance(t,dict) and 'officialRewardSum' in t:
                a=t.get('officialRewardSum');z=b.get('officialRewardSum')
            else:
                sums=v.get('qualifiedPairedSums',v.get('sums',{}));a=next((x for k,x in sums.items() if k.startswith('trained')),None);z=next((x for k,x in sums.items() if k.startswith('control')),None)
            complete=v.get('allPairedOfficialComplete',v.get('completeQualifiedCoverage'))
            history.append({'variant':d.name,'report':f.relative_to(E).as_posix(),'system_score':a,'control_score':z,'difference':c.get('officialRewardDifference',v.get('qualifiedPairedDelta',v.get('delta'))),'complete_pair':complete,'audits_passed':c.get('allAuditsPassed',c.get('consumptionAuditPassed',v.get('passed'))),'expansion_screen':c.get('passesPreregisteredExpansionScreen',v.get('passesExpansionGate')),'report_kind':'synthetic' if 'development' in f.name or 'budget' in f.name else 'official_or_historical','tasks':c.get('tasks',v.get('qualifiedPairedTasks',v.get('tasks')))} )
        if not (d/'pilot-summary.json').exists() and not (d/'full-summary.json').exists():
            history.append({'variant':d.name,'report':(d/'development-result.json' if (d/'development-result.json').exists() else d/'development-summary.json').relative_to(E).as_posix(),'system_score':None,'control_score':None,'difference':None,'complete_pair':False,'audits_passed':None,'expansion_screen':False,'report_kind':'no_completed_official_summary','tasks':None})
    write_json(OUT/'version-history.json',history);csv_write('version-history.csv',history)
    write_json(OUT/'source-copy-index.json',SOURCE_FILES)

    notes='''本文件夹是2026-10-19（北京时间）的只读归档；未调用模型、未调用评分器、未重写原始实验文件。paperReady=false。
最终对照均以各自匹配接口为准，不将旧低分接口混入新变体，不合并不同基准的分数。
TB v5：固定12题小试8:4；新增51题25:25；整体63题33:29。不是89题整榜，也不是新增阶段独立提升。
SQL v21：1015题865.1833333333333:856.3433333333334，精确1分题836:828。固定48题43.64:42.64；属于公开开发自适应过程。
SQL原冻结644.7095238:622.09的规划未实际采用，不能算训练收益。public-v2为761.78:783.3033333，必须保留负结果。
SQL v16：1015个有限官方分中4个消费审计失败，仅1011个合格；没有完整匹配对照，不报完整提分。v18完整配对856.0933333:856.3433333，差-0.25。
TB原冻结47/63；其历史可比59题45:46，旧逐题取低规则局限于该历史记录。不能与v5接口直接比较，不能用它替换v5唯一对照。
TB v4保留1个正式验收超时未出分；不能补0或当完整合格实验。v3中断记录原样保留。
τ-bench为retail115+airline50，pass^1，实际用户模拟器deepseek-flash，非论文gpt-4；零售97:93、航空29:26。
Bash reward不是成功率，精确1分44:43，146.83:146.70的差仅0.13。
系统结构、提示及调用路径发生过调整；真实权重消费不等于LoRA训练因果效果，不能据此声称未见泛化、统计显著或外部SOTA。
成本：原始usage与缺口见各报告；独立财务账单缺失，美元成本保持null，不把缺失记为0。
evidence/objects为TB v4/v5最终快照引用对象的去重副本，按SHA256查找；manifest保留原远端路径、官方结果及采用来源。
receipts保留下载的原始JSONL字节（含失败行），remote-receipt-index记录远端来源及校验。SQL/τ/Bash的大体积完整轨迹仍在原远端，未声称全部离线归档；本包含收据、结果、既有审计和源位置。
sources包含版本设计、自建验证、正式/历史汇总、审计、独立账本与约束；其旧时间点状态（包括active、旧TB未赢）作为历史保留，不能覆盖本包最终汇总。
manifest.json列出本包每个文件的字节数与SHA256（不包含manifest本身及verification.json）；source-copy-index和remote-receipt-index支持回查。原目录全部保留。
'''
    (OUT/'README.txt').write_text(notes,encoding='utf-8')
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [r['benchmark'],r['tasks'],r['variant'],format(r['system_score'],'.6f').rstrip('0').rstrip('.'),format(r['control_score'],'.6f').rstrip('0').rstrip('.'),f"{r['difference']:+.6f}".rstrip('0').rstrip('.'),r['metric'],r['scope']])+'</tr>' for r in results)
    hist=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ['variant','report_kind','system_score','control_score','difference','complete_pair','audits_passed','report'])+'</tr>' for r in history)
    report='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Janus 鲁棒性实验最终汇总</title><style>body{font:16px/1.7 system-ui,sans-serif;color:#20313b;max-width:1380px;margin:40px auto;padding:0 28px;background:#fafaf8}h1{font-size:32px}h2{margin-top:36px}table{border-collapse:collapse;width:100%;background:white;font-size:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd;vertical-align:top}th{background:#e7eeed}a{color:#196e72}pre{white-space:pre-wrap;font:15px/1.8 system-ui}small{color:#536570}.scroll{overflow-x:auto}</style><h1>Janus 鲁棒性实验 · 最终结果</h1><p>2026-10-19 · 三项基准，四组读数 · <strong>paperReady=false</strong></p><p>以下结果分别使用本版本的匹配对照。分数来自已经完成的官方执行；本次仅整理归档。</p><div class="scroll"><table><tr><th>基准</th><th>题数</th><th>系统版本</th><th>系统</th><th>对照</th><th>差值</th><th>指标</th><th>范围</th></tr>'''+rows+'''</table></div><h2>查阅文件</h2><p><a href="final-results.csv">最终结果 CSV</a> · <a href="final-results.json">最终结果 JSON</a> · <a href="per-task-final-results.csv">逐题配对结果</a> · <a href="version-history.csv">全部版本汇总 CSV</a> · <a href="source-copy-index.json">本地来源索引</a> · <a href="remote-receipt-index.json">原始收据索引</a> · <a href="manifest.json">文件校验清单</a></p><h2>结果解释与归档范围</h2><pre>'''+html.escape(notes)+'''</pre><h2>全部版本的报告索引</h2><small>None 表示该报告未提供相应字段，不能视为零分；synthetic 为自建验证，不是正式基准成绩。历史文件中的旧状态按其原始时间解释。</small><div class="scroll"><table><tr><th>版本</th><th>报告类型</th><th>系统</th><th>对照</th><th>差值</th><th>完整配对</th><th>审计</th><th>原报告</th></tr>'''+hist+'''</table></div></html>'''
    (OUT/'00-总览.html').write_text(report,encoding='utf-8')
    entries=[]
    for f in sorted(OUT.rglob('*')):
        if f.is_file() and f not in [OUT/'manifest.json',OUT/'verification.json']:
            raw=f.read_bytes();entries.append({'path':f.relative_to(OUT).as_posix(),'bytes':len(raw),'sha256':digest(raw)})
    write_json(OUT/'manifest.json',{'schema':'robustness-results-file-manifest-v1','paperReady':False,'files':entries,'newModelCalls':0,'newGraderCalls':0})
    print(json.dumps({'bundle':str(OUT),'files':len(entries),'bytes':sum(x['bytes'] for x in entries),'canonicalEvidenceObjectsAdded':object_count,'remoteReceiptFiles':len(remote_records),'perTaskPairs':len(taskrows),'paperReady':False}),flush=True)

if __name__=='__main__':main()
