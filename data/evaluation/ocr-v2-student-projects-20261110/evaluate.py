"""Run the real LocalOCR defaults; image-only inference, then score saved outputs."""
import argparse, collections, csv, hashlib, importlib.metadata, importlib.util, json, os, platform, statistics, subprocess, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
BASE=Path(__file__).resolve().parent;REPO=BASE.parents[2];OLD=BASE.parent/'ocr-v2-20261110'
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('previous_evaluator',OLD/'evaluate.py');previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
score=previous.score
from score_facts import score_facts, STATES

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,text=True).strip()
def inventory(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in str(p)}
def validate(manifest):
    for f,h in manifest['tracked_assets'].items():assert sha(BASE/f)==h,f
    for s in manifest['samples']:
        for k in ['image','ground_truth','facts','reading_order']:assert sha(BASE/s[k])==s[k+'_sha256'],(s['id'],k)

def aggregate(rows):
    r=previous.aggregate(rows);r['independent_projects']=len({x['project_id'] for x in rows});r['evaluation_pages']=len(rows)
    for category in ['technology','roles','metrics']:
        facts=[f for x in rows for f in x['fact_scores'] if f['category']==category]
        counts={s:sum(f['state']==s for f in facts) for s in STATES}
        r[category]={'success':counts['preserved'],'total':len(facts),'rate':counts['preserved']/len(facts) if facts else None,'states':counts}
    return r

def summarize(out,manifest):
    rows=[]
    for s in manifest['samples']:
        run=json.loads((out/'inference_records'/f"{s['id']}.json").read_text())
        pred=(out/run['prediction']).read_text();gt=(BASE/s['ground_truth']).read_text();facts=json.loads((BASE/s['facts']).read_text())
        row={**s,**run,'with_whitespace':score(gt,pred),'without_whitespace':score(gt,pred,True),'fact_scores':score_facts(pred,facts)}
        save(out/'sample_scores'/f"{s['id']}.json",row);rows.append(row)
    groups={'all_inputs':rows,'introduction':[x for x in rows if x['format']=='introduction'],'slides':[x for x in rows if x['format']=='slide']}
    for layout in sorted({r['layout'] for r in rows}):groups[layout]=[r for r in rows if r['layout']==layout]
    for project in sorted({r['project_id'] for r in rows}):groups[project]=[r for r in rows if r['project_id']==project]
    summary={'groups':{k:aggregate(v) for k,v in groups.items()},'samples':rows};save(out/'summary.json',summary)
    fields=['id','project_id','layout','status','seconds','cer','cer_no_space','errors','reference_characters','technology_success','technology_total','roles_success','roles_total','metrics_success','metrics_total']
    with (out/'scores.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:
            ag=aggregate([r]);w.writerow({**{k:r[k] for k in fields[:5]},'cer':r['with_whitespace']['cer'],'cer_no_space':r['without_whitespace']['cer'],**{k:r['with_whitespace'][k] for k in ['errors','reference_characters']},**{c+'_'+k:ag[c][k] for c in ['technology','roles','metrics'] for k in ['success','total']}})
    with (out/'fact_scores.jsonl').open('w',encoding='utf-8') as f:
        for r in rows:
            for fact in r['fact_scores']:f.write(json.dumps({'page':r['id'],**fact},ensure_ascii=False)+'\n')
    return summary

def run(out):
    assert not out.exists(),f'Refusing to overwrite: {out}'
    manifest=json.loads((BASE/'manifest.json').read_text());validate(manifest)
    before=inventory(OLD);tracked_before=git('diff','--binary','HEAD')
    paths=[REPO/'ai/local/ocr.py',REPO/'ai/intake.py',REPO/'ai/workflow.py',REPO/'ai/gemini/roadmap.mjs']
    paths+=sorted((REPO/'ai/models/ocr-v2').rglob('*'))+sorted((REPO/'ai/models/ocr-detector').rglob('*'))
    paths=[p for p in paths if p.is_file()];hashes={str(p.relative_to(REPO)):sha(p) for p in paths}
    for d in ['predictions','inference_records','sample_scores']:(out/d).mkdir(parents=True)
    metadata={'commit':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'started_at_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':sha(BASE/'manifest.json'),'python':sys.version,'os':platform.platform(),'hardware':previous.hardware(),'cpu_count':os.cpu_count(),'source_hashes':hashes,'previous_evaluation_file_hashes':before,'settings':{'model':'local','orientation':'auto','layout':'rows','crop_padding':0},'package_versions':{p:importlib.metadata.version(p) for p in ['torch','torchvision','transformers','pillow','numpy','opencv-python-headless','pypdfium2','rapidfuzz']},'timing':'PNG bytes in memory -> extract(png, bytes) -> return; single trial, no scoring or model load in page latency','input_isolation':'Only PNG bytes are passed to LocalOCR. Reference/fact content is read by summarize after all inference. No PDF text layer exists.'}
    oldenv=json.loads((OLD/'results/environment.json').read_text());metadata['previous_comparison']={k:{'old':oldenv.get(k),'current':metadata.get(k)} for k in ['commit','settings','package_versions']};metadata['changed_source_or_model_files']={p:{'old':oldenv['source_hashes'].get(p),'current':v} for p,v in hashes.items() if oldenv['source_hashes'].get(p)!=v}
    t=time.perf_counter();import torch
    sys.path.insert(0,str(REPO/'ai'));from local.ocr import LocalOCR
    metadata['import_seconds']=time.perf_counter()-t;torch.set_num_threads(2);torch.set_num_interop_threads(1)
    metadata.update(torch_threads=torch.get_num_threads(),torch_interop_threads=torch.get_num_interop_threads(),cuda_available=torch.cuda.is_available(),mps_available=torch.backends.mps.is_available())
    t=time.perf_counter()
    try:engine=LocalOCR('local')
    except Exception:
        metadata.update(model_load_seconds=time.perf_counter()-t,load_error=traceback.format_exc());save(out/'environment.json',metadata);raise
    metadata.update(model_load_seconds=time.perf_counter()-t,device=engine.device,detector_class=type(engine.dm).__name__,recognizer_class=type(engine.rm).__name__)
    assert (engine.orientation,engine.layout,engine.crop_padding)==('auto','rows',0)
    t=time.perf_counter();metadata['warmup_output']=engine.extract('png',(OLD/'qa/warmup.png').read_bytes());metadata['warmup_seconds']=time.perf_counter()-t
    save(out/'environment.json',metadata);print(json.dumps({'event':'loaded','device':engine.device,'seconds':metadata['model_load_seconds']}),flush=True)
    for s in manifest['samples']:
        image_bytes=(BASE/s['image']).read_bytes();error=None
        if engine.device=='cuda':torch.cuda.synchronize()
        t=time.perf_counter()
        try:
            pages=engine.extract('png',image_bytes)
            if engine.device=='cuda':torch.cuda.synchronize()
            seconds=time.perf_counter()-t;assert len(pages)==1
            pred=pages[0][1];status='success' if pred.strip() else 'empty'
        except Exception:seconds=time.perf_counter()-t;error=traceback.format_exc();pred='';status='error';pages=None
        path=out/'predictions'/f"{s['id']}.txt";path.write_text(pred,encoding='utf-8')
        record={'id':s['id'],'status':status,'seconds':seconds,'error':error,'prediction':str(path.relative_to(out)),'prediction_sha256':sha(path),'raw_return':pages}
        save(out/'inference_records'/f"{s['id']}.json",record);print(json.dumps({'event':'sample','id':s['id'],'status':status,'seconds':seconds}),flush=True)
    metadata['inference_finished_at_utc']=datetime.now(timezone.utc).isoformat()
    summary=summarize(out,manifest)
    validate(manifest);assert before==inventory(OLD);assert tracked_before==git('diff','--binary','HEAD');assert hashes=={str(p.relative_to(REPO)):sha(p) for p in paths}
    metadata.update(source_unchanged_after_run=True,previous_evaluation_unchanged=True,frozen_inputs_unchanged=True,finished_at_utc=datetime.now(timezone.utc).isoformat());save(out/'environment.json',metadata)
    print(json.dumps({'event':'complete',**summary['groups']['all_inputs']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=BASE/'results');a=p.parse_args();run(a.output.resolve())
