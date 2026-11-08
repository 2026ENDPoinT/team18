"""Build vectors using the exact deployment encoder, with hashes and explicit row IDs."""
import argparse, json, shutil, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from course_recommendation.bundle import Encoder, digest, load_bundle
import numpy as np
p=argparse.ArgumentParser(); p.add_argument('--model',required=True); p.add_argument('--data',required=True); p.add_argument('--output',required=True); p.add_argument('--version',required=True); a=p.parse_args()
model,data,out=map(Path,(a.model,a.data,a.output)); out.mkdir(parents=True,exist_ok=True)
for name in ('encoder.onnx','tokenizer.json'): shutil.copyfile(model/name,out/name)
for name in ('skills.json','roles.json','course_profiles.json','config.json'): shutil.copyfile(data/name,out/name)
skills=json.loads((out/'skills.json').read_text()); roles=json.loads((out/'roles.json').read_text())
encoder=Encoder(out,384)
def vectors(items): return np.asarray([encoder.encode('passage: '+x['name']+' '+x['description']) for x in items],dtype=np.float32).reshape(-1,384)
np.savez_compressed(out/'lookup_vectors.npz', skills=vectors(skills), roles=vectors(roles))
files=('encoder.onnx','tokenizer.json','skills.json','roles.json','course_profiles.json','config.json','lookup_vectors.npz')
manifest={'bundle_version':a.version,'model_revision':(model/'model_revision.txt').read_text().strip(),'dimension':384,'preprocessing':'e5 query/passage, attention-mask mean, L2, max 256','skill_ids':[x['skill_id'] for x in skills],'role_ids':[x['role_id'] for x in roles],'sha256':{name:digest(out/name) for name in files}}
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
load_bundle(out)
print('Validated bundle:',out)
