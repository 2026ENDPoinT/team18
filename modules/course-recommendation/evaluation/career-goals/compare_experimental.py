"""Compare frozen baseline with explicit experimental bundle, retaining private traces by input ID."""
import csv, json, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(root))
from course_recommendation import load_bundle
from course_recommendation.engine import recommend_with_trace
p=Path(__file__).resolve().parent; art=root/'artifacts'
b=load_bundle(art/'seoultech-bundle-experimental'); cat=b['catalogs']['seoultech-csv-test']
rows=json.loads((art/'seoultech-data/rows.json').read_text()); names={r['course_id']:r['교과목명'] for r in rows}
snap=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',target_role=None)
with (p/'career_goals_100.csv').open(encoding='utf-8-sig',newline='') as f: goals=list(csv.DictReader(f))
with (root/'evaluation/baseline/recommendations_100.csv').open(encoding='utf-8-sig',newline='') as f: old={r['id']:r for r in csv.DictReader(f)}
results=[]; traces=[]
for g in goals:
 result,trace=recommend_with_trace(dict(snap,career_goal=g['희망_진로_예시']),b)
 if result['status']=='unavailable': raise SystemExit('Experimental bundle error: '+g['id'])
 results.append(dict(id=g['id'],분류=g['분류'],희망_진로_예시=g['희망_진로_예시'],이전상태=old[g['id']]['상태'],현재상태=result['status'],내부사유=trace['status_reason'],역량=' | '.join(x['skill_id'] for x in result['goal_skills']),과목=' | '.join(names[c['course_id']]+' ['+c['course_id']+']' for c in result['courses'])))
 traces.append({'id':g['id'],'trace':trace})
with (p/'before_after.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
# Trace intentionally includes only input IDs and spans, no goal text.
with (p/'experimental_traces.jsonl').open('w',encoding='utf-8') as f:
 for t in traces: f.write(json.dumps(t,ensure_ascii=False)+'\n')
from collections import Counter
print('Transitions:',dict(Counter((r['이전상태'],r['현재상태']) for r in results)))
for r in results:
 if r['id'] in ['G004','G021','G025','G031','G071','G074','G085','G088','G095']: print(r['id'],r['현재상태'],r['내부사유'],r['역량'],r['과목'])
