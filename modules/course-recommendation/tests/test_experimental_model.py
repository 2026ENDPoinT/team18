"""Optional end-to-end checks against a locally built, unreviewed E5 bundle."""
import importlib.util,json,sys,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from course_recommendation import load_bundle
from course_recommendation.engine import recommend_with_trace
bundle_path=root/'artifacts/seoultech-bundle-experimental'
@unittest.skipUnless(bundle_path.exists() and importlib.util.find_spec('onnxruntime') and importlib.util.find_spec('numpy'),'experimental model and runtime not prepared')
class ModelRegression(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.bundle=load_bundle(bundle_path);cat=cls.bundle['catalogs']['seoultech-csv-test']
  cls.snap=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',target_role=None)
 def case(self,goal):return recommend_with_trace(dict(self.snap,career_goal=goal),self.bundle)
 def test_natural_data_analysis(self):
  r,t=self.case('사용자 행동 데이터를 분석해 서비스 개선에 기여하고 싶어요')
  self.assertEqual(r['status'],'ok');self.assertIn('data_analysis',[x['skill_id'] for x in r['goal_skills']])
 def test_image_goal_and_mobile_combination(self):
  for goal in ('사진 속 물체를 구별하는 인공지능 모델을 만들고 싶어요','모바일 앱에 이미지 인식 기능을 넣고 싶습니다'):
   r,t=self.case(goal);self.assertIn('computer_vision',[x['skill_id'] for x in r['goal_skills']])
 def test_api_context(self):
  r,t=self.case('모바일 앱에서 사용할 REST API를 설계하는 일을 하고 싶습니다')
  self.assertIn('api_design',[x['skill_id'] for x in r['goal_skills']]);self.assertNotIn('mobile',[x['skill_id'] for x in r['goal_skills']])
 def test_ab_test_context(self):
  r,t=self.case('웹 서비스의 A/B 테스트 결과를 분석하고 싶어요')
  self.assertIn('data_analysis',[x['skill_id'] for x in r['goal_skills']]);self.assertNotIn('software_testing',[x['skill_id'] for x in r['goal_skills']])
 def test_mobile_exclusion(self):
  r,t=self.case('모바일 앱이 아닌 웹사이트를 만들고 싶어요')
  self.assertEqual(r['status'],'ok');self.assertIn('mobile',t['matching']['excluded_skills']);self.assertNotIn('csv-row-054',[x['course_id'] for x in r['courses']])
 def test_model_deployment_does_not_invent_courses(self):
  r,t=self.case('인공지능 모델 연구가 아니라 모델을 서비스에 배포하고 싶어요')
  self.assertEqual(r['status'],'no_match');self.assertEqual(t['status_reason'],'no_linked_courses')
if __name__=='__main__':unittest.main()
