"""Validate structured drafts and explicitly convert reviewed or experimental candidates."""
import argparse, json, copy
from pathlib import Path

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def validate(doc, catalogs, skills):
    if not all(doc.get(k) for k in ('generation_version','dictionary_version','bundle_version')): raise ValueError('versions required')
    allowed={s['skill_id'] for s in skills}; seen=set(); claimed_groups=set()
    for r in doc['courses']:
        cat=catalogs[r['catalog_id']]; cid=r['course_id']; key=(r['catalog_id'],cid)
        if key in seen or cid not in cat['course_ids']: raise ValueError('duplicate or unknown course: '+str(key))
        seen.add(key)
        for group in cat.get('equivalent_course_groups',[]):
            if cid in group:
                group_key=(r['catalog_id'],tuple(group))
                if group_key in claimed_groups: raise ValueError('duplicate equivalent group analysis')
                claimed_groups.add(group_key)
        if not r.get('source') or 'dictionary_candidates' not in r: raise ValueError('source and dictionary candidates required')
        if not r['original_title'] or r['review_status'] not in ('unreviewed','inference_reviewed','source_verified','held'): raise ValueError('invalid title/status')
        if r['review_status']=='held' and not r.get('hold_reason'): raise ValueError('hold requires reason')
        items={x['id']:x for x in r['learning_items']}
        if len(items)!=len(r['learning_items']): raise ValueError('duplicate learning item')
        for item in items.values():
            if item['source_type'] not in ('title_inference','school_source') or not all(item.get(k) for k in ('text','object','action','source')): raise ValueError('invalid learning item')
        tags=set()
        for tag in r['tag_candidates']:
            sid=tag['skill_id']
            if sid not in allowed or sid in tags or not tag['learning_item_ids'] or not set(tag['learning_item_ids'])<=items.keys(): raise ValueError('invalid tag or evidence')
            tags.add(sid)
            if tag.get('coverage') not in (None,0.5,1.0): raise ValueError('invalid coverage')
            if r['review_status']=='unreviewed' and tag.get('coverage') is not None: raise ValueError('unreviewed coverage')
            if r['review_status']=='source_verified' and any(items[i]['source_type']!='school_source' for i in tag['learning_item_ids']): raise ValueError('source verification requires school evidence')
    return True

def convert(doc, catalogs, skills, experimental=False):
    validate(doc,catalogs,skills); out=copy.deepcopy(catalogs)
    for r in doc['courses']:
        if r['review_status']=='held': continue
        if not experimental and r['review_status'] not in ('inference_reviewed','source_verified'): raise ValueError('unreviewed candidate cannot enter reviewed output')
        cat=out[r['catalog_id']]; ids=[r['course_id']]
        for group in cat.get('equivalent_course_groups',[]):
            if r['course_id'] in group: ids=group; break
        tags=[]
        for t in r['tag_candidates']:
            coverage=t.get('coverage')
            if coverage is None:
                if not experimental: raise ValueError('reviewed coverage required')
                coverage=0.5 # explicit sensitivity assumption, never written back to draft
            tags.append({'skill_id':t['skill_id'],'coverage':coverage})
        for cid in ids:
            existing=next((p for p in cat['profiles'] if p['course_id']==cid),None)
            if existing:
                old={t['skill_id']:t['coverage'] for t in existing['skills']}
                if experimental:
                    for t in tags:
                        if t['skill_id'] in old: t['coverage']=old[t['skill_id']]
                existing['skills']=copy.deepcopy(tags)
                existing['review_status']='unreviewed' if experimental else r['review_status']
            elif tags: cat['profiles'].append({'course_id':cid,'source_type':'name_inferred','review_status':'unreviewed' if experimental else r['review_status'],'skills':copy.deepcopy(tags)})
    if not experimental and any(p.get('review_status') not in ('inference_reviewed','source_verified') for cat in out.values() for p in cat['profiles']): raise ValueError('unreviewed baseline profiles cannot enter reviewed output')
    return out

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['validate','convert']); p.add_argument('--input',required=True); p.add_argument('--catalog',required=True); p.add_argument('--skills',required=True); p.add_argument('--output'); p.add_argument('--experimental',action='store_true'); a=p.parse_args()
    d,c,s=load(a.input),load(a.catalog),load(a.skills); validate(d,c,s)
    if a.command=='convert':
        if not a.output: p.error('--output required')
        if a.experimental and 'artifacts' not in Path(a.output).resolve().parts: p.error('experimental output must be under artifacts')
        save(a.output,convert(d,c,s,a.experimental))
    print('valid')
if __name__=='__main__': main()
