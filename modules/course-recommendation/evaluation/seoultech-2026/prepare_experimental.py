"""Build a separate unreviewed experimental dictionary; never modify baseline data."""
import json
import shutil
from pathlib import Path
root=Path(__file__).resolve().parents[2]
src=root/'artifacts/seoultech-data'; dst=root/'artifacts/seoultech-data-experimental'
shutil.copytree(src,dst,dirs_exist_ok=True)
path=dst/'skills.json'; skills=json.loads(path.read_text())
extra=[
 {'skill_id':'api_design','name':'API 설계','aliases':['REST API','API'],'description':'서비스 간에 데이터를 주고받는 API의 인터페이스를 설계한다'},
 {'skill_id':'experiment_analysis','name':'실험 결과 분석','aliases':['A/B 테스트','에이비 테스트'],'description':'비교 실험의 데이터를 통계적으로 분석하고 결과를 해석한다'},
 {'skill_id':'model_deployment','name':'모델 배포','aliases':['모델을 배포','모델 배포'],'description':'학습된 기계학습 모델을 서비스 환경에 배포한다'},
]
assert not set(s['skill_id'] for s in skills)&set(s['skill_id'] for s in extra)
skills.extend(extra)
for s in skills:
 if s['skill_id']=='web_development': s['aliases'] += ['웹사이트','웹 사이트']
path.write_text(json.dumps(skills,ensure_ascii=False,indent=2)+'\n')
roles_path=dst/'roles.json'; roles=json.loads(roles_path.read_text())
roles.append({'role_id':'frontend','name':'프론트엔드 개발자','aliases':['프론트엔드'],'description':'웹 서비스의 사용자 화면과 상호작용을 개발한다','skills':[{'skill_id':'web_development','priority':3},{'skill_id':'programming','priority':2},{'skill_id':'software_engineering','priority':1}]})
roles_path.write_text(json.dumps(roles,ensure_ascii=False,indent=2)+'\n')
config=json.loads((dst/'config.json').read_text()); config['interpretation_version']='experimental-v2'
(dst/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
print('Unreviewed experimental data:',dst,'skills:',len(skills))
