import copy, importlib.util, json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tagging'))
from course_recommendation.interpret import interpret
from pipeline import validate,convert
class Followup(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  d=ROOT/'artifacts/model'
  if not d.exists(): raise unittest.SkipTest('local experimental data unavailable')
  cls.skills=json.loads((d/'skills.json').read_text());cls.roles=json.loads((d/'roles.json').read_text());cls.catalogs=json.loads((d/'course_profiles.json').read_text());cls.draft=json.loads((ROOT/'tagging/sample.json').read_text())
 def test_contrast_and_exclusion(self):
  for s,expected in [('데이터 분석보다 서버 개발에 관심', 'backend'),('데이터 분석보다는 백엔드에 관심','backend')]:
   m=interpret(s,self.skills,self.roles);self.assertIn(expected,m['positive_roles']);self.assertNotIn('data_analysis',m['positive_skills']);self.assertIn('data_analysis',m['blocked_direct'])
  m=interpret('데이터 분석보다 우주여행에 관심',self.skills,self.roles);self.assertTrue(m['ambiguous'])
  for text,sid in [('게임 개발은 원하지 않고 보안 공부','game_programming'),('암호 이론은 빼고 웹 취약점을 점검','cryptography'),('통계 분석은 하지 않고 데이터를 저장','statistics')]:
   self.assertIn(sid,interpret(text,self.skills,self.roles)['excluded_skills'])
 def test_context(self):
  self.assertNotIn('api_design',interpret('API와 연결하고 화면을 개발',self.skills,self.roles)['positive_skills'])
  self.assertIn('api_design',interpret('API를 설계하고 제공',self.skills,self.roles)['positive_skills'])
  m=interpret('웹 취약점을 찾아 고치기',self.skills,self.roles);self.assertTrue({'security','web_development'}<=set(m['positive_skills']))
  m=interpret('게임을 만들고 데이터도 분석',self.skills,self.roles);self.assertTrue({'game_programming','data_analysis'}<=set(m['positive_skills']))
 def test_tags_and_gate(self):
  self.assertTrue(validate(self.draft,self.catalogs,self.skills))
  with self.assertRaises(ValueError): convert(self.draft,self.catalogs,self.skills)
  draft=copy.deepcopy(self.draft);draft['courses'][0]['tag_candidates'][0]['skill_id']='invented'
  with self.assertRaises(ValueError): validate(draft,self.catalogs,self.skills)
  draft=copy.deepcopy(self.draft);draft['courses'][0]['course_id']='missing'
  with self.assertRaises(ValueError): validate(draft,self.catalogs,self.skills)
  changed=convert(self.draft,self.catalogs,self.skills,True);self.assertNotEqual(changed,self.catalogs)
 def test_generated_artifacts_consistent(self):
  import csv
  for run in (ROOT/'evaluation/career-goals/runs').glob('*'):
   if not run.is_dir(): continue
   summary=json.loads((run/'summary.json').read_text());rid=summary['metadata']['run_id']
   with (run/'results.csv').open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
   traces=[json.loads(x) for x in (run/'traces.jsonl').read_text().splitlines()]
   self.assertTrue(all(x['run_id']==rid for x in rows+traces));self.assertEqual(len(rows),len(traces))
   for key,counts in summary['status_counts'].items():
    parser,tags=key.split('/');subset=[x for x in rows if x['parser']==parser and x['tags']==tags]
    for status,count in counts.items():self.assertEqual(sum(x['status']==status for x in subset),count)
