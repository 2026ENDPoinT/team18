import json, sys, unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
from course_recommendation import recommend_courses, InputTooLong
class Encoder:
    def __init__(self): self.calls=0
    def encode(self, text): self.calls+=1; return [1.,0.]
class Tests(unittest.TestCase):
    def setUp(self):
        read=lambda n:json.loads((root/'data'/n).read_text())
        self.s=read('sample_input.json'); self.e=Encoder()
        self.b=dict(bundle_version='fixture',dimension=2,skills=read('skills.json'),roles=read('roles.json'),catalogs=read('course_profiles.json'),config=read('config.json'),encoder=self.e,skill_vectors=[[0.,1.]]*6,role_vectors=[[0.,1.]])
    def test_snapshot_filter_and_one_inference(self):
        result=recommend_courses(self.s,self.b)
        self.assertEqual(result['status'],'ok'); self.assertEqual(self.e.calls,1)
        ids=[c['course_id'] for c in result['courses']]
        self.assertNotIn(self.s['completed_course_ids'][0],ids); self.assertTrue(set(ids)<=set(self.s['course_ids']))
        self.assertEqual(result['selection_review_status'],'unconfirmed')
        other=dict(self.s,completed_course_ids=[ids[0]])
        self.assertNotIn(ids[0],[x['course_id'] for x in recommend_courses(other,self.b)['courses']])
    def test_no_match_and_unavailable(self):
        self.s['target_role']=None; self.s['career_goal']='우주 여행'
        self.assertEqual(recommend_courses(self.s,self.b)['status'],'no_match')
        self.s['catalog_version']='mismatch'
        self.assertEqual(recommend_courses(self.s,self.b)['status'],'unavailable')
        self.assertEqual(self.e.calls,1)
    def test_no_padding_and_role_exclusion(self):
        self.s['career_goal']='백엔드 말고 음악'; self.s['target_role']=None
        self.assertEqual(recommend_courses(self.s,self.b)['status'],'no_match')
    def test_encoder_failure_and_length(self):
        class Failure:
            def encode(self,t): raise RuntimeError('model failed')
        self.b['encoder']=Failure(); self.assertEqual(recommend_courses(self.s,self.b)['status'],'unavailable')
        class Long:
            def encode(self,t): raise InputTooLong()
        self.b['encoder']=Long()
        with self.assertRaises(InputTooLong): recommend_courses(self.s,self.b)
    def test_alias_with_korean_particle_and_identifier_boundary(self):
        self.s['target_role']=None; self.s['career_goal']='SQL을 배우고 싶어요'
        self.assertEqual(recommend_courses(self.s,self.b)['goal_skills'][0]['skill_id'],'sql')
        from course_recommendation.core import _match
        self.assertFalse(_match('JavaScript', 'Java'))
        self.assertTrue(_match('백엔드를 배우고 싶어요', '백엔드'))
    def test_equivalent_courses_are_deduplicated_and_completion_shared(self):
        catalog = self.b['catalogs'][self.s['catalog_id']]
        a, b = self.s['course_ids'][2:4]
        catalog['equivalent_course_groups'] = [[a, b]]
        # Give both alternatives identical relevant tags.
        profiles = {p['course_id']: p for p in catalog['profiles']}
        profiles[b]['skills'] = list(profiles[a]['skills'])
        self.s['completed_course_ids'] = []
        courses = [c['course_id'] for c in recommend_courses(self.s,self.b)['courses']]
        self.assertIn(a,courses); self.assertNotIn(b,courses)
        for completed in (a,b):
            self.s['completed_course_ids'] = [completed]
            courses = [c['course_id'] for c in recommend_courses(self.s,self.b)['courses']]
            self.assertNotIn(a,courses); self.assertNotIn(b,courses)
    def test_bad_equivalence_groups_are_unavailable(self):
        catalog = self.b['catalogs'][self.s['catalog_id']]
        ids = self.s['course_ids']
        for groups in ([[ids[0], 'missing']], [[ids[0], ids[1]],[ids[1], ids[2]]], [[ids[0],ids[0]]]):
            catalog['equivalent_course_groups'] = groups
            self.assertEqual(recommend_courses(self.s,self.b)['status'],'unavailable')
    def test_experimental_snapshot_and_single_inference(self):
        self.b['config']['interpretation_version']='experimental-v2'
        original=self.s
        class MutatingEncoder:
            calls=0
            def encode(inner,text):
                inner.calls+=1
                original['completed_course_ids'][:]=original['course_ids'][:]
                return [1.,0.]
        encoder=MutatingEncoder();self.b['encoder']=encoder
        result=recommend_courses(self.s,self.b)
        self.assertEqual(encoder.calls,1);self.assertEqual(result['status'],'ok')
        self.assertTrue(result['courses'])
    def test_experimental_exclusion_survives_role_and_users_are_isolated(self):
        self.b['config']['interpretation_version']='experimental-v2'
        self.s['career_goal']='SQL 말고 백엔드';self.s['target_role']='백엔드'
        catalog=self.b['catalogs'][self.s['catalog_id']];a,b=self.s['course_ids'][2:4]
        catalog['equivalent_course_groups']=[[a,b]]
        for completed in (a,b):
            r=recommend_courses(dict(self.s,completed_course_ids=[completed]),self.b)
            self.assertNotIn('sql',[x['skill_id'] for x in r['goal_skills']])
            self.assertFalse({a,b}&{x['course_id'] for x in r['courses']})
        other=recommend_courses(dict(self.s,completed_course_ids=[]),self.b)
        self.assertIn(a,[x['course_id'] for x in other['courses']])
    def test_experimental_failure_distinction(self):
        self.b['config']['interpretation_version']='experimental-v2'
        self.s['career_goal']='우주 여행';self.s['target_role']=None
        self.assertEqual(recommend_courses(self.s,self.b)['status'],'no_match')
        self.s['catalog_version']='bad'
        self.assertEqual(recommend_courses(self.s,self.b)['status'],'unavailable')
    def test_partial_membership_rejected(self):
        self.s['course_ids'].pop(); self.assertEqual(recommend_courses(self.s,self.b)['status'],'unavailable')
if __name__=='__main__': unittest.main()
