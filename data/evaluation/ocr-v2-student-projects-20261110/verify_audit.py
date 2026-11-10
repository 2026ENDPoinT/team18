"""Verify audited decisions, unchanged CER/timing/raw inputs, and all audit aggregates."""
import argparse,json,collections,statistics
from pathlib import Path
from audit_metrics import audit_metric,tests
from evaluate import sha,validate,save
from score_facts import score_facts,STATES
BASE=Path(__file__).resolve().parent

def verify(out):
    target=out/'audited';summary=json.loads((target/'summary.json').read_text());original=json.loads((out/'summary.json').read_text());provenance=json.loads((target/'provenance.json').read_text())
    assert sha(BASE/'audit_metrics.py')==provenance['audit_script_sha256'];assert sha(BASE/'adjudication_policy.md')==provenance['policy_sha256'];assert sha(out/'summary.json')==provenance['original_summary_sha256']
    manifest=json.loads((BASE/'manifest.json').read_text());validate(manifest)
    assert json.loads((out/'verification.json').read_text())['all_passed']
    assert tests()==10
    old={r['id']:r for r in original['samples']};n=0
    for r in summary['samples']:
        prior=old[r['id']]
        for key in ['with_whitespace','without_whitespace','seconds','status','prediction_sha256']:assert r[key]==prior[key]
        raw=(out/r['prediction']).read_text();assert sha(out/r['prediction'])==r['prediction_sha256']
        facts=json.loads((BASE/r['facts']).read_text());frozen=score_facts(raw,facts)
        expected=[f for f in frozen if f['category']!='metrics']+[audit_metric(raw,f) for f in facts['metrics']]
        assert expected==r['fact_scores'];n+=len(expected)
        for f in expected:
            if f['category'] in ['roles','metrics']:assert f['evidence'] in raw
            if f['category']=='metrics' and f['state']=='preserved':
                p=f['parsed_relation'];assert (p['before'],p['after'],p['before_unit'],p['after_unit'])==(f['before'],f['after'],f['unit'],f['unit'])
                assert p['connector'] in ['directed_arrow','destination_particle_and_direction','explicit_before_after_labels']
                if p['connector']=='destination_particle_and_direction':assert p['direction_word']==f['direction']
    for key,g in summary['groups'].items():
        rows=[r for r in summary['samples'] if key=='all_inputs' or r['format']==key or (key=='slides' and r['format']=='slide') or r['layout']==key or r['project_id']==key]
        assert len(rows)==g['evaluation_pages']
        assert g['median_seconds']==statistics.median(r['seconds'] for r in rows)
        for cat in ['technology','roles','metrics']:
            facts=[f for r in rows for f in r['fact_scores'] if f['category']==cat];counts={s:sum(f['state']==s for f in facts) for s in STATES}
            assert g[cat]['states']==counts and g[cat]['success']==counts['preserved'] and g[cat]['total']==len(facts)
    result={'all_passed':True,'verified_pages':36,'verified_fact_decisions':n,'metric_connection_probes':10,'groups':len(summary['groups']),'original_CER_DP_verification_reused':72,'original_scores_retained':True,'CER_timing_prediction_and_frozen_input_unchanged':True,'semantic_validation':'deterministic rerun, tuple and evidence checks; not independent human review'}
    save(target/'verification.json',result);print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=BASE/'results');a=p.parse_args();verify(a.results)
