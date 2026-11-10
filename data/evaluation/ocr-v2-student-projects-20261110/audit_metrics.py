"""Post-inference scoring audit. Never changes frozen inputs, predictions, or original scores.
Corrects unit tokenization and recognizes explicit direction words / before-after labels.
"""
import argparse, collections, csv, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from evaluate import aggregate, validate, sha, save
from score_facts import compact, mapped, excerpt
BASE=Path(__file__).resolve().parent
NUMBER=r'([0-9]+(?:\.[0-9]+)?)'
UNIT=r'(건/s|[A-Za-z]+|%)'
PAIR=NUMBER+UNIT

def audit_metric(raw,f):
    original,text,indices=mapped(raw);label=compact(f['name']);positions=[m.start() for m in re.finditer(re.escape(label),text)]
    candidates=[]
    def add(pos,end,groups,connector,direction=None):
        b,u1,a,u2=groups
        parsed={'metric':f['name'],'before':b,'after':a,'before_unit':u1,'after_unit':u2,'connector':connector,'direction_word':direction}
        okay=(b,a,u1,u2)==(f['before'],f['after'],f['unit'],f['unit']) and (direction is None or direction==f['direction'])
        candidates.append({'state':'preserved' if okay else 'mislinked','parsed_relation':parsed,'evidence':excerpt(original,indices,pos,end),'reason':'metric, ordered values, exact units, and explicit directional grammar or before/after labels form a connected fact'})
    for pos in positions:
        tail=text[pos+len(label):]
        m=re.match(r'^[:：]?'+PAIR+r'(?:→|⇒|->|에서)'+PAIR,tail)
        if m:
            end=pos+len(label)+m.end();suffix=text[end:end+16];dm=re.match(r'(?:(?:으)?로)?(증가|감소)',suffix)
            add(pos,end+(dm.end() if dm else 0),m.groups(),'directed_arrow',dm.group(1) if dm else None)
        # Explicit destination particle + directional verb is stronger than merely finding two numbers.
        m=re.match(r'^[:：]?'+PAIR+PAIR+r'(?:으)?로(증가|감소)',tail)
        if m:add(pos,pos+len(label)+m.end(),m.groups()[:4],'destination_particle_and_direction',m.group(5))
    # Line-local labels: each label must be followed immediately by its own value/unit.
    # The unique known metric scope must precede them. Other prose between the two pairs is allowed.
    before=list(re.finditer(r'개선전'+PAIR,text));after=list(re.finditer(r'개선후'+PAIR,text))
    scope_end=min([x.start() for x in before+after],default=0)
    if len(before)==len(after)==1 and positions and any(p<scope_end for p in positions):
        b,a=before[0],after[0]
        if b.end()<=a.start() and a.end()-b.start()<350:
            # A second distinct metric name would make the scope ambiguous.
            projects=json.loads((BASE/'sources/projects.json').read_text())
            mentioned={compact(p['metric']) for p in projects if compact(p['metric']) in text[:a.end()]}
            if mentioned=={label}:
                pos=max(p for p in positions if p<scope_end)
                add(pos,a.end(),(*b.groups(),*a.groups()),'explicit_before_after_labels')
    if not candidates:
        old={'state':'indeterminate' if positions else 'missing','parsed_relation':None,'evidence':raw,'reason':'no complete connected metric relation; numerical presence alone is insufficient'}
        return {**f,'category':'metrics',**old}
    chosen=next((c for c in candidates if c['state']=='mislinked'),None) or candidates[0]
    return {**f,'category':'metrics',**chosen}

def tests():
    f=json.loads((BASE/'key_facts/p01_intro.json').read_text())['metrics'][0]
    probes=[('예약 API p95 420ms → 180ms','preserved'),('예약 API p95 420ms 180ms로 감소','preserved'),('예약 API p95 420ms 180ms','indeterminate'),('420ms 180ms로 감소','missing'),('예약 API p95 420ms → 180s','mislinked'),('예약 API p95 180ms → 420ms','mislinked'),('예약 API p95 420ms 180ms로 증가','mislinked'),('예약 API p95 420ms → 180ms\n예약 API p95\n감소한 결과','preserved'),('예약 API p95\n개선 전\n420ms\n관련 설명\n개선 후\n180ms','preserved'),('예약 API p95\n개선 전\n180ms\n개선 후\n420ms','mislinked')]
    for text,state in probes:assert audit_metric(text,f)['state']==state,(text,audit_metric(text,f))
    return len(probes)

def audit(out):
    target=out/'audited';assert not target.exists(),'Do not overwrite an audit.'
    manifest=json.loads((BASE/'manifest.json').read_text());validate(manifest)
    probe_count=tests();summary=json.loads((out/'summary.json').read_text());changes=[]
    for r in summary['samples']:
        raw=(out/r['prediction']).read_text()
        updated=[]
        for old in r['fact_scores']:
            if old['category']!='metrics':updated.append(old);continue
            original=json.loads((BASE/r['facts']).read_text())['metrics'][0]
            new=audit_metric(raw,original)
            assert new['evidence'] in raw
            updated.append(new);changes.append({'page':r['id'],'fact_id':old['id'],'original_state':old['state'],'audited_state':new['state'],'original_parsed_relation':old['parsed_relation'],'audited_relation':new['parsed_relation'],'evidence':new['evidence'],'reason':new['reason']})
        r['fact_scores']=updated
    rows=summary['samples'];groups={'all_inputs':rows,'introduction':[r for r in rows if r['format']=='introduction'],'slides':[r for r in rows if r['format']=='slide']}
    groups.update({key:[r for r in rows if r['layout']==key] for key in sorted({r['layout'] for r in rows})});groups.update({key:[r for r in rows if r['project_id']==key] for key in sorted({r['project_id'] for r in rows})})
    summary['groups']={k:aggregate(v) for k,v in groups.items()};target.mkdir()
    save(target/'summary.json',summary);save(target/'metric_adjudications.json',changes)
    for r in rows:
        assert sha(out/r['prediction'])==r['prediction_sha256']
    with (target/'fact_scores.jsonl').open('w',encoding='utf-8') as f:
        for r in rows:
            for fact in r['fact_scores']:f.write(json.dumps({'page':r['id'],**fact},ensure_ascii=False)+'\n')
    save(target/'provenance.json',{'stage':'post-inference scoring audit; not preregistered parser','created_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_manifest_sha256':sha(BASE/'manifest.json'),'original_summary_sha256':sha(out/'summary.json'),'audit_script_sha256':sha(BASE/'audit_metrics.py'),'policy_sha256':sha(BASE/'adjudication_policy.md'),'changed_decisions':sum(c['original_state']!=c['audited_state'] for c in changes),'metric_facts_reviewed':len(changes),'negative_and_positive_probes':probe_count,'ground_truth_images_predictions_unchanged':True,'external_LLM_calls':0})
    validate(manifest)
    print(json.dumps(summary['groups']['all_inputs'],ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=BASE/'results');a=p.parse_args();audit(a.results)
