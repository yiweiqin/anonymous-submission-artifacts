import unittest
import csv,json,tempfile
from pathlib import Path
from fractions import Fraction
from aggregate_results import family_mean,rate,aggregate

class Metrics(unittest.TestCase):
    def test_equal_family_is_not_micro_average(self):
        rows=[dict(family='small',reward=1)]+[dict(family='large',reward=0) for _ in range(9)]
        self.assertEqual(family_mean(rows,['small','large']),Fraction(1,2))
        self.assertEqual(rate(rows),Fraction(1,10))

    def test_threshold_is_at_least_one(self):
        rows=[dict(reward=x) for x in [0,0.99,1,2]]
        self.assertEqual(rate(rows),Fraction(1,2))

    def test_real_historical_arm_and_metric_are_recognized(self):
        here=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'preparation-request.json').write_bytes((here/'preparation-request.json').read_bytes())
            report=aggregate(root,root/'summary',here/'historical-result-provenance.json')
            self.assertFalse(report['complete'])
            with (root/'summary/method-summary.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            janus=next(x for x in rows if x['kind']=='historical-main-table-janus')
            vanilla=next(x for x in rows if x['kind']=='historical-main-table-vanilla')
            self.assertEqual(int(janus['passed']),39)
            self.assertEqual(int(vanilla['passed']),33)
            self.assertAlmostEqual(float(janus['liftVsHistoricalVanillaPP']),float(Fraction(23,288)*100),places=12)

    def test_validation_pass_does_not_replace_online_zero_or_complete_frozen_coverage(self):
        here=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'preparation-request.json').write_bytes((here/'preparation-request.json').read_bytes())
            sample=json.loads((here/'preparation-request.json').read_text(encoding='utf-8'))['tasks'][0]
            for index,(phase,reward) in enumerate([('formal-online',0),('formal-validation',1)]):
                directory=root/'executions'/str(index);directory.mkdir(parents=True)
                row=dict(phase=phase,logicalId='formal/c1/2/online/'+sample['family']+'/'+sample['task']+('/validation' if index else ''),
                         reward=reward,**sample,inputStateSha256='synthetic-unit-test',protocolSha256='synthetic-unit-test',inputConsumed=True,attempts=[])
                (directory/'commit.json').write_text(json.dumps(row))
            report=aggregate(root,root/'summary',here/'historical-result-provenance.json')
            with (root/'summary/task-ledger.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            primary=next(x for x in rows if x['kind']=='uniform-online-primary')
            replay=next(x for x in rows if x['kind']=='candidate-validation-adoption-only')
            self.assertEqual(float(primary['reward']),0)
            self.assertEqual(float(replay['reward']),1)
            self.assertEqual(replay['usedForPrimaryMetrics'],'False')
            self.assertFalse(report['complete'])
            self.assertEqual(next(x['count'] for x in report['coverage'] if x['kind']=='terminal-snapshot-frozen' and x['chain']=='c1' and x['round']==2),0)

if __name__=='__main__':unittest.main()
