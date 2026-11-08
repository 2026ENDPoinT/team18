"""Evaluate human-reviewed labels; drafts only contribute descriptive counts.

course_relevance_json: {"csv-row-NNN": 0..3}; excluded_skills use skill IDs.
"""
import argparse,csv,json,math,sys
from collections import Counter,defaultdict
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from course_recommendation import load_bundle,recommend_courses
from course_recommendation.interpret import interpret,occurrences
p=argparse.ArgumentParser();p.add_argument('--input',default=str(Path(__file__).with_name('draft_200.csv')));p.add_argument('--split',choices=['adjustment','holdout_candidate'],default='adjustment');p.add_argument('--bundle',default=str(root/'artifacts/seoultech-bundle-experimental'));p.add_argument('--output',default=str(Path(__file__).with_name('draft_adjustment_metrics.json')));a=p.parse_args()
b=load_bundle(a.bundle);cat=b['catalogs']['seoultech-csv-test'];rows=json.loads((root/'artifacts/seoultech-data/rows.json').read_text());names={x['course_id']:x['교과목명'] for x in rows}
snap=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',target_role=None)
with open(a.input,encoding='utf-8-sig',newline='') as f: inputs=[r for r in csv.DictReader(f) if r['split']==a.split]
def collapse(scores):
 groups=cat.get('equivalent_course_groups',[]);members={x for g in groups for x in g};out=[(s,cid) for cid,s in scores.items() if cid not in members and s>0 and s>=b['config']['course_threshold']]
 for group in groups:
  valid=[(scores.get(cid,0),cid) for cid in group if scores.get(cid,0)>0 and scores.get(cid,0)>=b['config']['course_threshold']]
  if valid:out.append((max(s for s,_ in valid),valid[0][1]))
 return [cid for _,cid in sorted(out,key=lambda x:(-x[0],x[1]))[:5]]
def baseline(text,mode):
 if mode=='keyword':
  scores={cid:1 for cid,name in names.items() if occurrences(text,name)};return [],collapse(scores)
 parsed=interpret(text,b['skills'],b['roles']);skills=[x for x in parsed['positive_skills'] if x not in parsed['excluded_skills'] and x not in parsed['blocked_direct']]
 if parsed['ambiguous']:return [],[]
 w={sid:1/(i+1) for i,sid in enumerate(skills[:8])};total=sum(w.values());w={k:v/total for k,v in w.items()} if total else {}
 scores={c['course_id']:sum(w.get(t['skill_id'],0)*t['coverage'] for t in c['skills']) for c in cat['profiles']}
 return skills,collapse(scores)
profiles={c['course_id']:{t['skill_id'] for t in c['skills']} for c in cat['profiles']}
all_results={}
for mode in ('semantic','keyword','alias'):
 statuses=Counter();bytype=defaultdict(Counter); reviewed=[]
 for row in inputs:
  if mode=='semantic':
   r=recommend_courses(dict(snap,career_goal=row['sentence']),b); status=r['status'];skill_ids=[x['skill_id'] for x in r['goal_skills']];courses=[c['course_id'] for c in r['courses']]
  else:
   skill_ids,courses=baseline(row['sentence'],mode);status='ok' if courses else 'no_match'
  statuses[status]+=1;bytype[row['type']][status]+=1
  if row['review_status'].strip().lower()!='reviewed':continue
  gold=set(filter(None,row['allowed_skills'].split('|')));pred=set(skill_ids);excluded=set(filter(None,row['excluded_skills'].split('|')))
  relevance=json.loads(row['course_relevance_json']) if row['course_relevance_json'].strip() else None
  reviewed.append(dict(row=row,gold=gold,pred=pred,excluded=excluded,courses=courses,relevance=relevance,status=status))
 def avg(xs):return sum(xs)/len(xs) if xs else None
 precision=[len(r['pred']&r['gold'])/len(r['pred']) for r in reviewed if r['pred'] and r['gold']] if mode!='keyword' else []
 recall=[len(r['pred']&r['gold'])/len(r['gold']) for r in reviewed if r['gold']] if mode!='keyword' else []
 judged_courses=[r for r in reviewed if r['relevance'] is not None]
 course_precision=[sum(r['relevance'].get(cid,0)>0 for cid in r['courses'])/len(r['courses']) for r in judged_courses if r['courses']]
 def ndcg(r):
  rel=r['relevance'];values=[rel.get(cid,0) for cid in r['courses']]; ideal=sorted(rel.values(),reverse=True)[:5]
  dcg=lambda v:sum((2**x-1)/math.log2(i+2) for i,x in enumerate(v))
  return dcg(values)/dcg(ideal) if dcg(ideal)>0 else None
 nd=[v for r in judged_courses if (v:=ndcg(r)) is not None]
 support=[r for r in reviewed if r['row']['decision']=='recommend']; out=[r for r in reviewed if r['row']['type']=='out_of_scope']; negatives=[r for r in reviewed if r['excluded']];complexes=[r for r in reviewed if r['row']['type']=='complex' and r['gold']]
 all_results[mode]={'count':len(inputs),'statuses':dict(statuses),'by_type':{k:dict(v) for k,v in bytype.items()},'reviewed':len(reviewed),'unreviewed':len(inputs)-len(reviewed),'review_counts_by_type':{t:{'total':sum(x['type']==t for x in inputs),'reviewed':sum(r['row']['type']==t for r in reviewed),'reviewed_defer':sum(r['row']['type']==t and r['row']['decision']=='defer' for r in reviewed)} for t in sorted({x['type'] for x in inputs})},'metrics':{'skill_precision_macro':avg(precision),'skill_recall_macro':avg(recall),'returned_course_relevance':avg(course_precision),'ndcg_at_5':avg(nd),'mean_returned_course_count_reviewed':avg([len(r['courses']) for r in reviewed]),'explicit_exclusion_violation_rate':avg([bool(r['pred']&r['excluded']) for r in negatives]),'excluded_course_tag_incidence':avg([any(bool(profiles.get(cid,set())&r['excluded']) for cid in r['courses']) for r in negatives]),'supported_return_rate':avg([r['status']=='ok' for r in support]),'out_of_scope_recommendation_rate':avg([r['status']=='ok' for r in out]),'complex_goal_skill_coverage':avg([len(r['pred']&r['gold'])/len(r['gold']) for r in complexes])},'metric_note':'null = no reviewed eligible labels; draft labels are excluded. Keyword has no predicted skill labels. Unlisted courses in supplied relevance JSON are graded zero; excluded course tag incidence is a proxy, not a verified semantic violation.'}
Path(a.output).write_text(json.dumps(all_results,ensure_ascii=False,indent=2)+'\n');print('Saved',a.output,'sample count',len(inputs),'split',a.split)
