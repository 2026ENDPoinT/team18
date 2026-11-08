"""Development-only threshold probes, no reviewed quality labels."""
import copy,csv,json,sys
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from course_recommendation import load_bundle
from course_recommendation.engine import recommend_with_trace
p=Path(__file__).resolve().parent;b=load_bundle(root/'artifacts/model');cat=b['catalogs']['seoultech-csv-test']
s=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',target_role=None)
with (p/'career_goals_100.csv').open(encoding='utf-8-sig',newline='') as f:goals=list(csv.DictReader(f))
class Memo:
 def __init__(self,encoder):self.encoder=encoder;self.cache={}
 def encode(self,t):
  if t not in self.cache:self.cache[t]=self.encoder.encode(t)
  return self.cache[t]
b['encoder']=Memo(b['encoder'])
variants={'current':{},'skill_085':{'skill_threshold':.85},'role_085':{'role_threshold':.85},'course_010':{'course_threshold':.1}}
results={}
for name,change in variants.items():
 run=dict(b);run['config']=dict(b['config'],**change);out=[]
 for goal in goals:
  r,t=recommend_with_trace(dict(s,career_goal=goal['희망_진로_예시']),run);out.append({'id':goal['id'],'status':r['status'],'courses':[c['course_id'] for c in r['courses']]})
 results[name]={'config':run['config'],'statuses':dict(Counter(x['status'] for x in out)),'rows':out}
for name,run in results.items():
 if name!='current':run['changed_course_lists']=sum(a['courses']!=c['courses'] for a,c in zip(results['current']['rows'],run['rows']))
(root/'artifacts/ablation_dev.json').write_text(json.dumps({'scope':'development inputs only; no reviewed quality metrics; NOT a basis for promotion','variants':results},ensure_ascii=False,indent=2)+'\n')
for name,run in results.items(): print(name,run['statuses'],'changed',run.get('changed_course_lists',0))
