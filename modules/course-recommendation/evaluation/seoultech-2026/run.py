"""Smoke tests on provisional profiles; no ground truth or quality scoring."""
import json, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(root))
from course_recommendation import load_bundle,recommend_courses
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
data=root/'artifacts/seoultech-data'; bundle=load_bundle(root/'artifacts/model'); rows=read(data/'rows.json'); names={r['course_id']:r['교과목명'] for r in rows}
cat=bundle['catalogs']['seoultech-csv-test']; snap=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed')
cases=[('백엔드 직무','서버를 만드는 백엔드 개발자가 되고 싶어요','백엔드',[]),('데이터 분석 직무','데이터를 분석하는 일을 하고 싶어요','데이터 분석가',[]),('기계학습 직무','기계학습 모델을 만들고 싶어요','머신러닝 엔지니어',[]),('정보 보안 직무','시스템을 안전하게 보호하고 싶어요','보안 엔지니어',[]),('직접 SQL','SQL을 배우고 싶어요',None,[]),('명시 직무 없는 목표','데이터를 분석하는 일을 하고 싶어요',None,[]),('지원 범위 밖','우주 비행사가 되고 싶어요',None,[]),('복합 부정','프론트엔드 말고 백엔드 개발자가 되고 싶어요',None,[]),('한국어 이수 제외','서버를 만드는 백엔드 개발자가 되고 싶어요','백엔드',['csv-row-042']),('영어 이수 제외','서버를 만드는 백엔드 개발자가 되고 싶어요','백엔드',['csv-row-043'])]
results=[]
for label,goal,role,completed in cases:
 r=recommend_courses(dict(snap,career_goal=goal,target_role=role,completed_course_ids=completed),bundle)
 results.append(dict(case=label,goal=goal,target_role=role,completed=completed,status=r['status'],skills=[x['skill_id'] for x in r['goal_skills']],courses=[dict(course_id=c['course_id'],course_name=names[c['course_id']],score=round(c['score'],4)) for c in r['courses']]))
for result in results[-2:]:
    assert not {'csv-row-042','csv-row-043'} & {c['course_id'] for c in result['courses']}
for result in results:
    selected={c['course_id'] for c in result['courses']}
    assert all(len(selected.intersection(group)) <= 1 for group in cat['equivalent_course_groups'])
print(json.dumps(results,ensure_ascii=False,indent=2))
