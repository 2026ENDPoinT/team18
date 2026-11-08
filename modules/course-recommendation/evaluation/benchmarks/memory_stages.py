"""Local process RSS snapshots; run once per strategy on the same bundle."""
import argparse, hashlib, json, os, resource, subprocess, sys, time
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--hash-mode',choices=['whole','stream'],required=True);a=p.parse_args(); bundle=Path(a.bundle)
def snap(name):
 return {'stage':name,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
s=[snap('process_start')]; start=time.perf_counter();h=hashlib.sha256()
with (bundle/'encoder.onnx').open('rb') as f:
 if a.hash_mode=='whole': h.update(f.read())
 else:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
s.append(snap('model_hash_complete'))
from course_recommendation.bundle import read, Encoder
manifest=read(bundle/'manifest.json'); data=[read(bundle/n) for n in ('skills.json','roles.json','course_profiles.json','config.json')]
s.append(snap('dictionary_loaded'))
enc=Encoder(bundle,manifest['dimension']);s.append(snap('model_loaded_before_first_inference'))
enc.encode('query: 서버 개발을 배우고 싶다');s.append(snap('first_inference_complete'))
print(json.dumps({'hash_mode':a.hash_mode,'model_hash':h.hexdigest(),'snapshots':s,'elapsed_seconds':time.perf_counter()-start,'platform':sys.platform,'note':'local process only; peak units platform-dependent; no target server limits'},indent=2))
