import copy, csv, importlib.util, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('catalog_manage', ROOT/'tagging/full-catalog/manage.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class FullCatalog(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.doc,cls.cats,cls.skills,cls.cat,cls.digest,cls.rows=m.inputs()
 def test_catalog_and_csv(self):
  self.assertTrue(m.val(self.doc,self.cat,self.skills,self.digest,self.rows));self.assertEqual(m.audit_csv(self.doc),52)
 def test_missing_duplicate_group_and_skill(self):
  for mutation in ('missing','duplicate','group','skill','evidence','importance'):
   d=copy.deepcopy(self.doc)
   if mutation=='missing': d['profiles'].pop()
   if mutation=='duplicate': d['profiles'].append(copy.deepcopy(d['profiles'][0]))
   if mutation=='group': d['profiles'][0]['courses'].pop()
   if mutation=='skill': d['profiles'][0]['tag_candidates'][0]['skill_id']='not_a_skill'
   if mutation=='evidence': d['profiles'][0]['tag_candidates'][0]['learning_item_ids']=['missing']
   if mutation=='importance': d['profiles'][0]['tag_candidates'][0]['importance']='unknown'
   with self.subTest(mutation=mutation), self.assertRaises((AssertionError,KeyError)):
    m.val(d,self.cat,self.skills,self.digest,self.rows)
 def test_conversion_is_separate_and_experimental(self):
  cfg=m.read(m.HERE/'coverage_experiment.json')
  with self.assertRaises(ValueError): m.convert(self.doc,self.cats,cfg,False)
  result=m.convert(self.doc,self.cats,cfg,True)[self.doc['catalog_id']]
  self.assertEqual(len(result['profiles']),58)
  self.assertTrue(all(p['review_status']=='unreviewed' for p in result['profiles']))
  self.assertTrue(all(t['coverage'] in (0.5,1.0) for p in result['profiles'] for t in p['skills']))
  self.assertTrue(all(t['coverage'] is None for p in self.doc['profiles'] for t in p['tag_candidates']))
