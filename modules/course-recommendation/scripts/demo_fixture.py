"""Dependency-free scoring demonstration, deliberately not semantic inference."""
import json, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
from course_recommendation import recommend_courses
read=lambda n:json.loads((root/'data'/n).read_text(encoding='utf-8'))
class FixtureEncoder:
    def encode(self,text): return [1.,0.]
skills,roles=read('skills.json'),read('roles.json')
b=dict(bundle_version='fictional-demo-only',dimension=2,skills=skills,roles=roles,catalogs=read('course_profiles.json'),config=read('config.json'),skill_vectors=[[0.,1.] for _ in skills],role_vectors=[[0.,1.] for _ in roles],encoder=FixtureEncoder())
print('가상 데이터와 고정 벡터를 이용한 점수 계산 예시: 의미 검색 결과가 아닙니다.')
print(json.dumps(recommend_courses(read('sample_input.json'),b),ensure_ascii=False,indent=2))
