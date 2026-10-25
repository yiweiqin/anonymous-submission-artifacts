import copy
import unittest
from engine import answer, apply_patch, catalog, cost, execute, prompt, solve, verify_prediction
from prepare import make_group
from model_io import encode, token_ids
from evaluate import score
from policy import propose_next_plan


class EngineTests(unittest.TestCase):
    def case(self, mode='multiple', split='train'):
        return next(c for c in make_group(split, 8, 20260923) if c['generation']['mode']==mode)

    def test_all_modes_verified(self):
        for split in ('train','holdout'):
            for c in make_group(split, 8, 20260923):
                result=solve(c)
                self.assertTrue(result['certified'])
                self.assertTrue(verify_prediction(c, result['answer'])['valid'], c['id'])

    def test_noop_and_failure_gate(self):
        self.assertEqual(solve(self.case('no_change'))['answer']['decision'], 'no_change')
        for mode in ('failed','unverified','false_success'):
            c=self.case(mode)
            self.assertEqual(solve(c)['answer']['decision'], 'abstain')
            self.assertFalse(verify_prediction(c, answer(c,catalog(c['G_plan'],c['G_exec'])))['valid'])

    def test_cheapest_not_first_depth_first_solution(self):
        c=self.case('single'); result=solve(c)
        self.assertEqual(result['minimumCost'],1)
        self.assertEqual(len(result['answer']['edits']),1)
        self.assertGreater(cost(catalog(c['G_plan'],c['G_exec'])),1)

    def test_structural_patch_atomicity(self):
        c=self.case('insert','holdout'); result=solve(c)
        self.assertEqual(result['answer']['decision'],'adopt')
        self.assertTrue(any(e['op']=='add_node' for e in result['answer']['edits']))
        self.assertEqual(result['minimumCost'],9)  # node + 2 edges + remove bypass edge
        self.assertTrue(verify_prediction(c,result['answer'])['valid'])
        for e in result['answer']['edits']:
            negative=answer(c,[x for x in result['answer']['edits'] if x!=e])
            self.assertFalse(verify_prediction(c,negative)['valid'])

    def test_source_binding_and_precondition(self):
        c=self.case('single'); result=solve(c)['answer']
        self.assertFalse(verify_prediction(c,{**result,'sourceNodeIds':['not-a-node']})['valid'])
        bad=copy.deepcopy(result); bad['edits'][0]['before']='forged'
        self.assertFalse(verify_prediction(c,bad)['valid'])

    def test_budget_and_candidate_limit_never_certify(self):
        c=self.case()
        self.assertFalse(solve(c,budget=0)['certified'])
        self.assertFalse(solve(c,candidate_limit=0)['certified'])

    def test_no_label_or_hidden_world_leak(self):
        c=self.case(); before=prompt(c)
        c['oracle']={'answer':'SECRET'}; c['verificationWorlds']=[]; c['transferWorlds']=[]
        self.assertEqual(prompt(c),before)

    def test_semantic_effect_matters(self):
        c=self.case('single'); result=solve(c)
        fixed=apply_patch(c['G_plan'],result['answer']['edits'])
        w=c['verificationWorlds'][0]; oid=c['task']['outputNodeId']
        self.assertNotEqual(execute(c['G_plan'],w,oid),execute(fixed,w,oid))
        self.assertEqual(execute(fixed,w,oid),execute(c['G_exec'],w,oid))

    def test_multiple_edits_supported(self):
        c=self.case('multiple','holdout'); result=solve(c)
        self.assertGreaterEqual(len(result['answer']['edits']),2)
        self.assertTrue(verify_prediction(c,result['answer'])['valid'])

    def test_tokenizer_list_and_batch_encoding(self):
        self.assertEqual(token_ids({'input_ids':[[1,2]]}),[1,2])
        class Tokenizer:
            def apply_chat_template(self,messages,**kwargs):
                return {'input_ids':[[1,2,3] if len(messages)==1 else [1,2,3,4,5]]}
        result=encode(Tokenizer(),'prompt','{"decision":"abstain"}',5)
        self.assertEqual(result['labels'],[-100,-100,-100,4,5])
        with self.assertRaisesRegex(ValueError,'truncation_forbidden'):
            encode(Tokenizer(),'prompt','{}',4)

    def test_valid_but_excessive_patch_not_minimal(self):
        c=self.case('single'); c['oracle']=solve(c)
        all_edits=answer(c,catalog(c['G_plan'],c['G_exec']))
        checked=score(c,all_edits)
        self.assertTrue(checked['verifiedSuccess'])
        self.assertFalse(checked['minimalRepair'])
        self.assertGreater(checked['costRegret'],0)

    def test_parse_failure_not_removed_from_denominator(self):
        c=self.case(); c['oracle']=solve(c)
        result=score(c,None)
        self.assertTrue(result['parseError'])
        self.assertFalse(result['minimalRepair'])

    def test_joint_edges_required_and_no_hidden_deletion(self):
        c=self.case('rewire','holdout'); result=solve(c)
        self.assertEqual(result['minimumCost'],4)
        e=next(e for e in result['answer']['edits'] if e['op']=='add_edge')
        with self.assertRaisesRegex(ValueError,'input_arity'):
            apply_patch(c['G_plan'],[e])

    def test_no_verification_worlds_never_certify(self):
        self.assertFalse(solve(self.case(),worlds=[])['certified'])

    def test_planner_consumer_has_actual_plan_and_rollback(self):
        c=self.case('single'); old=copy.deepcopy(c)
        pred=solve(c)['answer']; c['verificationWorlds']=[]; c['transferWorlds']=[]
        result=propose_next_plan(c,pred)
        self.assertTrue(result['adopted'])
        self.assertNotEqual(result['nextPlan'],old['G_plan'])
        self.assertEqual(result['rollbackPlan'],old['G_plan'])
        self.assertEqual(c['G_plan'],old['G_plan'])
        self.assertFalse(result['productionApproved'])
        c['executionEvidence']['status']='failed'
        self.assertFalse(propose_next_plan(c,pred)['adopted'])


if __name__=='__main__':
    unittest.main()
