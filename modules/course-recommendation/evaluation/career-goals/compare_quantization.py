"""Compare separately indexed FP32 and INT8 bundles on development goals."""
import csv,json,sys
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from course_recommendation import load_bundle
from course_recommendation.engine import recommend_with_trace
p=Path(__file__).resolve().parent; art=root/'artifacts'
bundles=[load_bundle(art/name) for name in ('seoultech-bundle-experimental','seoultech-bundle-int8')]
with (p/'career_goals_100.csv').open(encoding='utf-8-sig',newline='') as f: goals=list(csv.DictReader(f))
rows=[]
for goal in goals:
 outputs=[]
 for b in bundles:
  cat=b['catalogs']['seoultech-csv-test'];s=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',target_role=None,career_goal=goal['희망_진로_예시'])
  r,t=recommend_with_trace(s,b);outputs.append((r,t))
 a,b=outputs; alist=[c['course_id'] for c in a[0]['courses']]; blist=[c['course_id'] for c in b[0]['courses']]
 rows.append({'id':goal['id'],'fp32_status':a[0]['status'],'int8_status':b[0]['status'],'fp32_courses':alist,'int8_courses':blist,'same_order':alist==blist,'fp32_excluded':a[1]['matching'].get('excluded_skills',[]),'int8_excluded':b[1]['matching'].get('excluded_skills',[]),'fp32_exclusion_violation':bool(set(a[1]['matching'].get('excluded_skills',[])) & {x['skill_id'] for x in a[0]['goal_skills']}),'int8_exclusion_violation':bool(set(b[1]['matching'].get('excluded_skills',[])) & {x['skill_id'] for x in b[0]['goal_skills']})})
summary={'scope':'development 100; draft labels; not quality validation','n':len(rows),'status_transitions':dict(Counter(r['fp32_status']+' -> '+r['int8_status'] for r in rows)),'changed_rankings':sum(not r['same_order'] for r in rows),'exclusion_changes':sum(r['fp32_excluded']!=r['int8_excluded'] for r in rows),'fp32_exclusion_violations':sum(r['fp32_exclusion_violation'] for r in rows),'int8_exclusion_violations':sum(r['int8_exclusion_violation'] for r in rows),'exclusion_note':'checks rule-detected skill exclusions, not reviewed semantic violations','reviewed_quality_metrics':None,'rows':rows}
(p/'fp32_int8_comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in summary.items() if k!='rows'})
