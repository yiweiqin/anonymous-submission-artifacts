"""Offline planning consumer. Produces a new plan plus rollback data; no live writes.

Only visible observations are used here. Hidden benchmark worlds are unavailable
to this consumer. A candidate is never called globally safe based on this check.
"""
import argparse
import copy
import json
from pathlib import Path
from engine import apply_patch, digest, dumps, verify_prediction


def propose_next_plan(case, prediction):
    checked=verify_prediction(case,prediction,worlds=case.get('observedWorlds',[]))
    if not checked['valid'] or prediction.get('decision')!='adopt':
        return {'adopted':False,'reason':checked['reason'],'nextPlan':copy.deepcopy(case['G_plan']),
                'productionApproved':False}
    next_plan=apply_patch(case['G_plan'],prediction['edits'])
    return {'adopted':True,'reason':'visible_acceptance_passed','nextPlan':next_plan,
            'basePlanHash':digest(case['G_plan']),'nextPlanHash':digest(next_plan),
            'patch':copy.deepcopy(prediction['edits']),'sourceNodeIds':prediction['sourceNodeIds'],
            'rollbackPlan':copy.deepcopy(case['G_plan']),'productionApproved':False,
            'scope':'same_task_spec_and_matching_patch_preconditions; requires independent future-task regression'}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--case',type=Path,required=True)
    p.add_argument('--prediction',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists(): raise ValueError('new_output_required')
    result=propose_next_plan(json.loads(a.case.read_text(encoding='utf8')),json.loads(a.prediction.read_text(encoding='utf8')))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(dumps({'adopted':result['adopted'],'reason':result['reason']}))
