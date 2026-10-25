import json,tempfile,unittest
from pathlib import Path
from summarize_single_online import summarize

class SingleOnlineMetrics(unittest.TestCase):
    def test_excluded_chain_and_validation_do_not_enter_primary_or_variance(self):
        here=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['historical-result-provenance.json','preparation-request.json']:
                (root/name).write_bytes((here/name).read_bytes())
            (root/'single-online-scope.json').write_text(json.dumps(dict(chains=['c1'],frozenEvaluation=False)))
            tasks=json.loads((root/'preparation-request.json').read_text())['tasks']
            rows=[]
            for task in tasks:
                for r in [2,3,4]:
                    rows.append(dict(**task,phase='formal-online',logicalId='formal/c1/'+str(r)+'/online/'+task['family']+'/'+task['task'],reward=0 if r==2 else 1))
                rows.append(dict(**task,phase='formal-vanilla',logicalId='formal-vanilla/shared/1/vanilla/'+task['family']+'/'+task['task'],reward=0))
                rows.append(dict(**task,phase='formal-online',logicalId='formal/c2/2/online/'+task['family']+'/'+task['task'],reward=1))
                rows.append(dict(**task,phase='formal-validation',logicalId='formal/c1/2/online/'+task['family']+'/'+task['task']+'/validation',reward=1))
            for i,row in enumerate(rows):
                p=root/'executions'/str(i);p.mkdir(parents=True)
                row.update(inputStateSha256='fixture',protocolSha256='fixture',attempts=[])
                (p/'commit.json').write_text(json.dumps(row))
            report=summarize(root,root/'summary',strict=True)
            self.assertTrue(report['complete']);self.assertFalse(report['chainVarianceEstimable'])
            self.assertIsNone(report['sampleStdPP']);self.assertEqual(report['bestOnlineRound'],3)
            rounds={x['round']:x for x in report['methods'] if x['kind']=='c1-online'}
            self.assertEqual(rounds[2]['passed'],0)
            self.assertEqual(rounds[3]['passed'],66)
            self.assertTrue(all(x['sampleStdPP'] is None for x in rounds.values()))
            self.assertEqual((root/'summary/auxiliary-retained-ledger.csv').read_text(encoding='utf-8-sig').count('\n'),133)

if __name__=='__main__':unittest.main()
