"""Offline ablations: injected skill weights, coverage, role choice and ordering."""
import argparse, json, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from course_recommendation import load_bundle,recommend_courses
p=root/'artifacts'; b=load_bundle(p/'model'); cat=b['catalogs']['seoultech-csv-test']; names={r['course_id']:r['교과목명'] for r in json.loads((p/'seoultech-data/rows.json').read_text())}
def injected(weights):
 total=sum(weights.values()); weights={k:v/total for k,v in weights.items()}; scores=[]
 for c in cat['profiles']:
  score=sum(weights.get(t['skill_id'],0)*t['coverage'] for t in c['skills'])
  if score>0 and score>=b['config']['course_threshold']: scores.append((score,c['source_type']=='description',c['course_id']))
 grouped={x for group in cat['equivalent_course_groups'] for x in group}; by_id={x[2]:x for x in scores}; out=[x for x in scores if x[2] not in grouped]
 for group in cat['equivalent_course_groups']:
  available=[by_id[x] for x in group if x in by_id]
  if available:
   best=max(available,key=lambda x:(x[0],x[1]));out.append((best[0],best[1],available[0][2]))
 return [(names[cid],round(score,4)) for score,_,cid in sorted(out,key=lambda x:(-x[0],-x[1],x[2]))[:5]]
parser=argparse.ArgumentParser();parser.add_argument('--weights',help='JSON object of skill IDs to nonnegative weights');args=parser.parse_args()
if args.weights:
 weights=json.loads(args.weights)
 if not isinstance(weights,dict) or not weights or any(k not in {s['skill_id'] for s in b['skills']} or not isinstance(v,(int,float)) or v<0 for k,v in weights.items()) or sum(weights.values())<=0: raise SystemExit('Invalid weights')
 print(json.dumps({'injected':weights,'courses':injected(weights)},ensure_ascii=False,indent=2));sys.exit(0)
coverage={s['skill_id']:{'count':0,'name_inferred':0,'description':0} for s in b['skills']}
for profile in cat['profiles']:
 for t in profile['skills']:
  v=coverage[t['skill_id']];v['count']+=1;v[profile['source_type']]+=1
cases={'G021':{'data_analysis':1,'statistics':1},'G031':{'computer_vision':1,'machine_learning':1},'G071':{'databases':1,'data_analysis':1},'G074':{'mobile':1,'computer_vision':1},'G088':{'model_deployment':1}}
result={'note':'Injected weights are unreviewed diagnostic hypotheses, not gold labels.', 'injected':{k:injected(v) for k,v in cases.items()},'coverage':coverage,'broad_ai':injected({'ai':1}),'broad_programming':injected({'programming':1})}
snap=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',career_goal='데이터를 분석하는 일을 하고 싶어요')
result['role_comparison']={str(role):recommend_courses(dict(snap,target_role=role),b) for role in (None,'데이터 분석가')}
# Reverse stored profile order; tie sorting must not depend on insertion order.
initial=injected({'programming':1});cat['profiles'].reverse();result['profile_order_stable']=(initial==injected({'programming':1}));cat['profiles'].reverse()
result['input_ids_order_stable']=(recommend_courses(dict(snap,target_role='데이터 분석가'),b)==recommend_courses(dict(snap,course_ids=list(reversed(snap['course_ids'])),target_role='데이터 분석가'),b))
out=root/'artifacts/diagnostics.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('Diagnostic results:',out,'order stable:',result['profile_order_stable'],result['input_ids_order_stable'])
