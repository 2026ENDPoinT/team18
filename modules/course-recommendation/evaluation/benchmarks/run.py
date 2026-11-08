"""Local benchmark; process readiness is measured from script entry, excludes download."""
import time
START=time.perf_counter()
import argparse, concurrent.futures, hashlib, importlib.metadata, json, os, platform, resource, subprocess, sys, threading
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from course_recommendation import load_bundle,recommend_courses
p=argparse.ArgumentParser();p.add_argument('--bundle',default=str(root/'artifacts/model'));p.add_argument('--iterations',type=int,default=5);p.add_argument('--output',default=str(root/'artifacts/local_benchmark.json'));a=p.parse_args()
bp=Path(a.bundle)
child_code="import sys; sys.path.insert(0,sys.argv[1]); from course_recommendation import load_bundle; x=load_bundle(sys.argv[2]); print('READY',flush=True)"
start_child=time.perf_counter()
child=subprocess.Popen([sys.executable,'-c',child_code,str(root),str(bp)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
line=child.stdout.readline(); process_ready_ms=(time.perf_counter()-start_child)*1000
if line.strip()!='READY': raise SystemExit('Readiness subprocess failed: '+child.stderr.read())
child.wait(timeout=120)
main_start=time.perf_counter();b=load_bundle(bp); ready=time.perf_counter()-main_start; cat=b['catalogs']['seoultech-csv-test']
snap=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',target_role=None)
def rss():
 try:return int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip())*1024
 except Exception:return None
loaded=rss(); gate=threading.Lock(); original=b['encoder']
class Timed:
 def __init__(self, inner):self.inner=inner;self.local=threading.local()
 def encode(self,t):
  start=time.perf_counter()
  with gate:
   acquired=time.perf_counter(); v=self.inner.encode(t); end=time.perf_counter()
  self.local.timings=(acquired-start,end-acquired)
  return v
enc=Timed(original);b['encoder']=enc
texts={'short':'백엔드 개발자가 되고 싶습니다','medium':'데이터 분석과 시각화를 활용해 사용자 행동을 이해하고 서비스 개선에 기여하고 싶습니다','long':'소프트웨어 개발과 데이터 분석을 함께 배우고 싶습니다. '*18}
def one(goal):
 start=time.perf_counter(); result=recommend_courses(dict(snap,career_goal=goal),b);end=time.perf_counter()
 queue,infer=getattr(enc.local,'timings',(None,None));enc.local.timings=(None,None)
 return {'total_ms':(end-start)*1000,'queue_ms':queue*1000 if queue is not None else None,'inference_ms':infer*1000 if infer is not None else None,'status':result['status']}
def pct(vals,p):
 vals=sorted(x for x in vals if x is not None)
 return vals[min(len(vals)-1,round((len(vals)-1)*p))] if vals else None
first=one(texts['short']); warm={}
for key,text in texts.items():
 tokens=len(original.tokenizer.encode('query: '+text).ids)
 if tokens>256: warm[key]={'tokens':tokens,'skipped':'over 256 token input limit'};continue
 samples=[one(text) for _ in range(a.iterations)]
 warm[key]={'tokens':tokens,'n':len(samples),'p50_ms':pct([x['total_ms'] for x in samples],.5),'p95_ms':pct([x['total_ms'] for x in samples],.95)}
concurrency={}
for n in (1,2,4,8):
 samples=[]
 for _ in range(a.iterations):
  with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool: samples.extend(pool.map(one,[texts['medium']]*n))
 concurrency[str(n)]={'n':len(samples),'queue_p50_ms':pct([x['queue_ms'] for x in samples],.5),'queue_p95_ms':pct([x['queue_ms'] for x in samples],.95),'inference_p50_ms':pct([x['inference_ms'] for x in samples],.5),'inference_p95_ms':pct([x['inference_ms'] for x in samples],.95),'total_p50_ms':pct([x['total_ms'] for x in samples],.5),'total_p95_ms':pct([x['total_ms'] for x in samples],.95),'errors':sum(x['status']=='unavailable' for x in samples),'timeouts':'not configured'}
try: cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
except Exception: cpu=platform.processor()
try: physical_ram=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True).strip())
except Exception: physical_ram=None
manifest=json.loads((bp/'manifest.json').read_text())
maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform!='darwin': maxrss*=1024
result={'scope':'local process only; no target CPU/RAM limits imposed; process spawn to ready includes Python startup and excludes model download; a measurement, not a deployment guarantee','os':platform.platform(),'cpu':cpu,'logical_cpu_count':os.cpu_count(),'cpu_quota':'not measured','physical_ram_bytes':physical_ram,'ram_limit':'not configured','python':platform.python_version(),'packages':{x:importlib.metadata.version(x) for x in ('numpy','onnxruntime','tokenizers')},'model_revision':manifest['model_revision'],'bundle_version':manifest['bundle_version'],'file_sha256':manifest['sha256'],'model_bytes':(bp/'encoder.onnx').stat().st_size,'session_count':1,'onnx_threads':1,'cache':'none','process_spawn_to_ready_ms':process_ready_ms,'bundle_load_ms':ready*1000,'rss_after_load_bytes':loaded,'max_rss_bytes':maxrss,'first_request':first,'warm_by_token_length':warm,'concurrency':concurrency}
Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Saved',a.output)
