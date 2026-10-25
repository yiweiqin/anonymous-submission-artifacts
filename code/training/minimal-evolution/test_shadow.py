import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parents[1] / 'assets/rdmd_minimal_evolution'
spec = importlib.util.spec_from_file_location('shadow', ASSETS / 'shadow.py')
shadow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)
from engine import answer, catalog, execute


class ShadowTests(unittest.TestCase):
    def case(self):
        return json.loads((HERE / 'shadow_case.json').read_text(encoding='utf8'))

    def test_bundled_engine_and_encoding_match_evaluated_version(self):
        for file in ('engine.py', 'model_io.py'):
            self.assertEqual((HERE / file).read_bytes(), (ASSETS / file).read_bytes())

    def test_minimum_preview_and_rollback_without_mutating_input(self):
        c = self.case(); original = copy.deepcopy(c)
        result = shadow.preview(c)
        self.assertEqual(result['status'], 'candidate')
        self.assertEqual(result['cost'], 1)
        self.assertEqual(result['edits'][0]['nodeId'], 'scale')
        self.assertEqual(result['rollbackPlan'], original['G_plan'])
        self.assertEqual(execute(result['nextPlan'], c['observedWorlds'][0], 'total'), 12)
        self.assertEqual(c, original)
        self.assertFalse(result['applied'])
        self.assertFalse(result['productionApproved'])

    def test_failed_or_false_success_never_produces_candidate(self):
        for status in ('failed', 'cancelled', 'running'):
            c = self.case(); c['executionEvidence']['status'] = status
            called = []
            result = shadow.preview(c, 'trained', lambda _: called.append(True))
            self.assertEqual(result['decision'], 'abstain')
            self.assertEqual(called, [])
        c = self.case(); c['G_exec']['nodes'][3]['params']['factor'] = 2
        self.assertNotEqual(shadow.preview(c)['status'], 'candidate')
        called = []
        self.assertEqual(shadow.preview(c, 'trained', lambda _: called.append(True))['reason'], 'execution_failed_replay')
        self.assertEqual(called, [])

    def test_missing_hidden_only_empty_and_unsupported_evidence(self):
        c = self.case(); c['oracle'] = {'answer': 'do not consume'}
        self.assertEqual(shadow.preview(c)['status'], 'rejected')
        for worlds in ([], [[]], None, [None]):
            c = self.case(); c['observedWorlds'] = worlds
            self.assertEqual(shadow.preview(c)['status'], 'rejected')
        c = self.case(); c['G_plan']['nodes'][0]['op'] = 'agent_task'
        self.assertEqual(shadow.preview(c)['status'], 'rejected')

    def test_model_does_not_validate_itself_or_get_silent_rule_fallback(self):
        c = self.case()
        result = shadow.preview(c, 'trained', lambda c: answer(c, catalog(c['G_plan'], c['G_exec'])))
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['reason'], 'minimum_not_certified')
        malformed = shadow.preview(c, 'trained', lambda _: {'decision': 'adopt'})
        self.assertEqual(malformed['status'], 'rejected')
        self.assertNotIn('nextPlan', malformed)
        self.assertEqual(shadow.preview(c, 'trained')['reason'], 'invalid_or_unsupported_evidence')
        false_no_change = shadow.preview(c, 'trained', lambda _: answer(c, decision='no_change'))
        self.assertEqual(false_no_change['reason'], 'false_no_change')
        self.assertEqual(false_no_change['status'], 'rejected')
        self.assertNotIn('nextPlan', false_no_change)

    def test_source_binding_and_stale_precondition_rejected(self):
        c = self.case()
        e = next(e for e in catalog(c['G_plan'], c['G_exec']) if e['nodeId'] == 'scale')
        p = answer(c, [e]); p['sourceNodeIds'] = ['total']
        self.assertEqual(shadow.preview(c, 'trained', lambda _: p)['reason'], 'source_patch_mismatch')
        p = answer(c, [e]); p['edits'][0]['before'] = 123
        self.assertEqual(shadow.preview(c, 'trained', lambda _: p)['status'], 'rejected')


if __name__ == '__main__':
    unittest.main()
