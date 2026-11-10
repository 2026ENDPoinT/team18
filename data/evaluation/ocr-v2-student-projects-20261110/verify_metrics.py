"""Recompute saved CER with independent stdlib DP; audit every aggregation and fact decision."""
import argparse, collections, hashlib, importlib.util, json, statistics, unicodedata
from pathlib import Path
BASE=Path(__file__).resolve().parent
from score_facts import score_facts, STATES

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s,ws):
    s=unicodedata.normalize('NFC',s);return ''.join(c for c in s if not c.isspace()) if ws else s

def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):nxt.append(min(row[j]+1,nxt[-1]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]

def preflight():
    manifest=json.loads((BASE/'qa/draft_manifest.json').read_text());n=0
    for s in manifest:
        facts=json.loads((BASE/s['facts']).read_text());scores=score_facts((BASE/s['ground_truth']).read_text(),facts)
        assert all(x['state']=='preserved' for x in scores),(s['id'],[x for x in scores if x['state']!='preserved']);n+=len(scores)
    fixture=json.loads((BASE/'key_facts/p01_intro.json').read_text());f=fixture['roles'][0]
    assert score_facts('나는 예약 화면과 관리자 승인 기능을 개발했다.',{'technology':[],'roles':[f],'metrics':[]})[0]['state']=='mislinked'
    metric=fixture['metrics'][0]
    def state(t):return score_facts(t,{'technology':[],'roles':[],'metrics':[metric]})[0]['state']
    assert state('예약 API p95 180ms → 420ms로 증가')=='mislinked'
    assert state('예약 API p95 420ms → 180ms로 증가')=='mislinked'
    assert state('예약 API p95\n420ms\n180ms')=='indeterminate'
    assert state('420ms와 180ms를 측정했다.')=='indeterminate'
    print(json.dumps({'reference_self_checks':n,'semantic_negative_probes':5,'passed':True}));return

def verify(out):
    manifest=json.loads((BASE/'manifest.json').read_text());summary=json.loads((out/'summary.json').read_text());env=json.loads((out/'environment.json').read_text())
    assert sha(BASE/'manifest.json')==env['manifest_sha256']
    for f,h in manifest['tracked_assets'].items():assert sha(BASE/f)==h,f
    rows=summary['samples'];assert len(rows)==len(manifest['samples'])==36
    manifest_by={s['id']:s for s in manifest['samples']};assert {r['id'] for r in rows}==set(manifest_by)
    facts_count=0
    for r in rows:
        s=manifest_by[r['id']]
        for k in ['image','ground_truth','facts','reading_order']:assert sha(BASE/s[k])==s[k+'_sha256']
        pred=(out/r['prediction']).read_text();assert sha(out/r['prediction'])==r['prediction_sha256']
        ir=json.loads((out/'inference_records'/f"{r['id']}.json").read_text());assert r['status']==ir['status'] and r['seconds']==ir['seconds']
        if r['status']!='error':assert ir['raw_return']==[[1,pred]]
        gt=(BASE/s['ground_truth']).read_text()
        for k,ws in [('with_whitespace',False),('without_whitespace',True)]:
            a,b=norm(gt,ws),norm(pred,ws);d=distance(a,b);m=r[k]
            assert d==m['errors']==m['insertions']+m['deletions']+m['substitutions']
            assert len(a)==m['reference_characters'] and len(b)==m['prediction_characters'] and m['cer']==d/len(a)
        expected=score_facts(pred,json.loads((BASE/s['facts']).read_text()));assert expected==r['fact_scores'];facts_count+=len(expected)
        for f in expected:
            if f['category'] in ['roles','metrics'] and f['state'] in ['mislinked','indeterminate']:assert f['evidence'] and f['evidence'] in pred
    groups={'all_inputs':rows,'introduction':[r for r in rows if r['format']=='introduction'],'slides':[r for r in rows if r['format']=='slide']}
    groups.update({layout:[r for r in rows if r['layout']==layout] for layout in {r['layout'] for r in rows}})
    groups.update({pid:[r for r in rows if r['project_id']==pid] for pid in {r['project_id'] for r in rows}})
    for key,subset in groups.items():
        agg=summary['groups'][key];assert agg['evaluation_pages']==len(subset)
        assert agg['median_seconds']==statistics.median(r['seconds'] for r in subset if r['status']!='error')
        for metric in ['with_whitespace','without_whitespace']:
            errors=sum(r[metric]['errors'] for r in subset);chars=sum(r[metric]['reference_characters'] for r in subset)
            assert agg[metric]['errors']==errors and agg[metric]['reference_characters']==chars and agg[metric]['cer']==errors/chars
        for cat in ['technology','roles','metrics']:
            fs=[f for r in subset for f in r['fact_scores'] if f['category']==cat];counts={s:sum(f['state']==s for f in fs) for s in STATES}
            assert agg[cat]['states']==counts and agg[cat]['total']==len(fs) and agg[cat]['success']==counts['preserved']
    previous=BASE.parent/'ocr-v2-20261110'
    assert all(sha(previous/p)==h for p,h in env['previous_evaluation_file_hashes'].items())
    repo=BASE.parents[2];assert all(sha(repo/p)==h for p,h in env['source_hashes'].items())
    result={'all_passed':True,'verified_pages':36,'independent_CER_DP_checks':72,'verified_fact_decisions':facts_count,'verified_groups':len(groups),'input_prediction_and_rubric_hashes_verified':True,'previous_evaluation_unchanged':True,'service_code_and_models_unchanged':True,'fact_verification_note':'rerun frozen deterministic scorer and audit aggregation/evidence; not an independent human semantic validation'}
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=BASE/'results');p.add_argument('--preflight',action='store_true');a=p.parse_args();preflight() if a.preflight else verify(a.results)
