import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from course_recommendation.interpret import interpret, occurrences

skills=[{'skill_id':i,'name':name,'aliases':aliases} for i,name,aliases in [
 ('mobile','모바일 프로그래밍',['모바일']),('web','웹 개발',['웹사이트']),('programming','프로그래밍',[]),
 ('security','보안',[]),('ai','인공지능',['AI']),('database','데이터베이스',[]),('network','네트워크',[]),
 ('statistics','통계',[]),('algorithms','알고리즘',[]),('graphics','컴퓨터 그래픽스',['그래픽스']),
 ('software_testing','소프트웨어 테스트',['테스트']),('data_analysis','데이터 분석',[]),('api_design','API 설계',['API']),('model_deployment','모델 배포',[])]]
class InterpretationTests(unittest.TestCase):
 def test_thirty_minimal_pairs(self):
  # Each pair has the same two concepts and the same surface form except the excluded side.
  concepts=[('모바일','mobile','웹사이트','web'),('프로그래밍','programming','보안','security'),('데이터베이스','database','네트워크','network'),('통계','statistics','알고리즘','algorithms'),('그래픽스','graphics','인공지능','ai'),('보안','security','통계','statistics'),('웹사이트','web','데이터베이스','database'),('네트워크','network','프로그래밍','programming'),('인공지능','ai','알고리즘','algorithms'),('알고리즘','algorithms','그래픽스','graphics')]
  patterns=['{a} 말고 {b}를 배우고 싶어요','{a}가 아닌 {b}를 배우고 싶어요','{a}를 제외하고 {b}를 배우고 싶어요']
  for a,aid,b,bid in concepts:
   for fmt in patterns:
    for first,first_id,second,second_id in ((a,aid,b,bid),(b,bid,a,aid)):
     with self.subTest(pattern=fmt,first=first):
      r=interpret(fmt.format(a=first,b=second),skills,[])
      self.assertIn(first_id,r['excluded_skills']);self.assertIn(second_id,r['positive_skills']);self.assertNotIn(second_id,r['excluded_skills'])
 def test_comparison_addition_and_ambiguity(self):
  r=interpret('보안보다 프로그래밍을 배우고 싶어요',skills,[])
  self.assertNotIn('security',r['excluded_skills']);self.assertIn('programming',r['positive_skills'])
  r=interpret('보안뿐 아니라 프로그래밍도 배우고 싶어요',skills,[])
  self.assertFalse(r['ambiguous']);self.assertEqual(set(r['positive_skills']),{'security','programming'})
  self.assertTrue(interpret('프로그래밍을 할지 보안을 할지 아직 고민 중이에요',skills,[])['ambiguous'])
 def test_unknown_negative_and_role_scope(self):
  roles=[{'role_id':'frontend','name':'프론트엔드 개발자','aliases':['프론트엔드']},{'role_id':'backend','name':'백엔드 개발자','aliases':['백엔드']}]
  r=interpret('프론트엔드 말고 백엔드 개발자가 되고 싶어요',skills,roles)
  self.assertIn('frontend',r['excluded_roles']); self.assertIn('backend',r['positive_roles']); self.assertFalse(r['ambiguous'])
  self.assertTrue(interpret('백엔드와 프론트엔드 모두 싫은데 개발자가 되고 싶어요',skills,roles)['ambiguous'])
 def test_context(self):
  api=interpret('모바일 앱에서 사용할 REST API를 설계하는 목표',skills,[])
  self.assertIn('mobile',api['blocked_direct']); self.assertIn('api_design',api['positive_skills'])
  screen=interpret('서버 API를 연결하는 모바일 화면 개발',skills,[])
  self.assertIn('mobile',screen['positive_skills']); self.assertNotIn('mobile',screen['blocked_direct'])
  ab=interpret('A/B 테스트 결과 분석',skills,[])
  self.assertIn('software_testing',ab['blocked_direct']); self.assertIn('data_analysis',ab['positive_skills'])
  self.assertFalse(occurrences('JavaScript','Java'));self.assertTrue(occurrences('Java를','Java'))
if __name__=='__main__': unittest.main()
