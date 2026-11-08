"""Run the 100 career goals against the provisional SeoulTech bundle."""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from course_recommendation import load_bundle, recommend_courses, InputTooLong

folder = Path(__file__).resolve().parent
read = lambda path: json.loads(path.read_text(encoding='utf-8'))
bundle_dir = root / 'artifacts/seoultech-bundle'
data_dir = root / 'artifacts/seoultech-data'
manifest = read(bundle_dir / 'manifest.json')
bundle = load_bundle(bundle_dir)
if bundle['bundle_version'] != 'seoultech-test-v4':
    raise SystemExit('Expected seoultech-test-v4; rebuild the bundle before running.')
cat = bundle['catalogs']['seoultech-csv-test']
course_rows = read(data_dir / 'rows.json')
if [r['course_id'] for r in course_rows] != cat['course_ids']:
    raise SystemExit('Course labels do not match bundle membership.')
names = {r['course_id']: r['교과목명'] for r in course_rows}
skill_names = {s['skill_id']: s['name'] for s in bundle['skills']}
snapshot = dict(catalog_id='seoultech-csv-test', catalog_version=cat['version'], course_ids=cat['course_ids'], completed_course_ids=[], selection_review_status='unconfirmed', target_role=None)
input_file = folder / 'career_goals_100.csv'
with input_file.open(encoding='utf-8-sig', newline='') as f:
    inputs = list(csv.DictReader(f))
if len(inputs) != 100 or len({r['id'] for r in inputs}) != 100:
    raise SystemExit('Expected 100 distinct input IDs.')
results=[]
for row in inputs:
    try:
        result = recommend_courses(dict(snapshot, career_goal=row['희망_진로_예시']), bundle)
    except InputTooLong:
        result = {'status': 'input_too_long', 'goal_skills': [], 'courses': []}
    if result['status'] == 'unavailable':
        raise SystemExit('Recommendation unavailable; outputs not replaced.')
    selected = {c['course_id'] for c in result['courses']}
    if not selected <= set(cat['course_ids']) or any(len(selected.intersection(group)) > 1 for group in cat['equivalent_course_groups']):
        raise SystemExit('Invalid recommendation membership or duplicate group.')
    results.append({
        'id': row['id'], '분류': row['분류'], '희망_진로_예시': row['희망_진로_예시'],
        '관련_역량_가설': row['관련_역량_가설'], '판정': row['판정'], '상태': result['status'],
        '모델_역량': ' | '.join(f"{skill_names[s['skill_id']]} [{s['skill_id']}] ({s['priority_weight']:.4f})" for s in result['goal_skills']),
        **{f'추천{i}': (f"{names[c['course_id']]} [{c['course_id']}] ({c['score']:.4f})" if i <= len(result['courses']) else '') for i,c in enumerate(result['courses'],1)},
    })
    for i in range(1,6): results[-1].setdefault(f'추천{i}','')
counts=Counter(r['상태'] for r in results)
by_category=defaultdict(Counter)
for r in results: by_category[r['분류']][r['상태']]+=1
fields=['id','분류','희망_진로_예시','관련_역량_가설','판정','상태','모델_역량',*[f'추천{i}' for i in range(1,6)]]
out=folder/'recommendations_100.csv'
with out.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(results)
summary={'bundle_version':bundle['bundle_version'],'model_revision':manifest['model_revision'],'goal_file_sha256':hashlib.sha256(input_file.read_bytes()).hexdigest(),'catalog_csv_sha256':cat['version'],'snapshot':{'target_role':None,'completed_course_ids':[],'selection_review_status':'unconfirmed'},'counts':dict(counts),'by_category':{k:dict(v) for k,v in by_category.items()},'limits':'실제 이수 상태와 직무 선택 없음; 미검토 과목명 추론 태그 및 검증 전 임계값; 사람의 정답 평가 아님'}
(folder/'recommendations_100_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
