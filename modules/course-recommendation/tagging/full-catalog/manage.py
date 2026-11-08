"""Export, audit and convert the authoritative full-catalog draft."""
import argparse, collections, copy, csv, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from course_recommendation.legacy import validate_equivalence_groups

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def inputs():
 doc=read(HERE/'profiles.json'); cats=read(ROOT/'data/seoultech_2026_catalog.json'); skills=read(ROOT/'data/seoultech_2026_skills.json'); cat=cats[doc['catalog_id']]
 source=ROOT/doc['profiles'][0]['source']['file']; digest=hashlib.sha256(source.read_bytes()).hexdigest()
 with source.open(encoding='utf-8-sig',newline='') as f: raw=list(csv.DictReader(f))
 rows={f'csv-row-{i:03}':r['교과목명'] for i,r in enumerate(raw,1)}
 return doc,cats,skills,cat,digest,rows

def val(doc,cat,skills,digest,rows):
 assert doc['catalog_version']==cat['version']==digest
 assert set(rows)==set(cat['course_ids']); validate_equivalence_groups(cat)
 allowed={s['skill_id'] for s in skills}; seen=[]; ids=[]
 expected={frozenset(g) for g in cat['equivalent_course_groups']}; actual=set()
 for p in doc['profiles']:
  assert p['catalog_id']==doc['catalog_id'] and p['catalog_version']==digest
  assert p['source']['sha256']==digest and p['source']['type'] in ('title','mixed','school_source')
  assert p['review_status'] in ('unreviewed','inference_reviewed','source_verified')
  if p['review_status']!='unreviewed': assert p['reviewer'] and p['review_notes']
  ids.append(p['profile_id']); group=[x['course_id'] for x in p['courses']];seen+=group
  assert group and all(rows.get(c['course_id'])==c['title'] for c in p['courses'])
  if len(group)>1: actual.add(frozenset(group))
  itemmap={x['id']:x for x in p['learning_items']};assert len(itemmap)==len(p['learning_items'])
  for item in itemmap.values():
   assert all(item.get(k) for k in ('text','object','action','source','source_type'))
   assert item['source_type'] in ('title_inferred','school_source')
   if item['source_type']=='school_source': assert item.get('source')
  tagids=[]
  for t in p['tag_candidates']:
   assert t['skill_id'] in allowed and t['importance'] in ('core','supporting') and t['rationale']
   assert t['learning_item_ids'] and set(t['learning_item_ids'])<=itemmap.keys()
   assert t.get('coverage') is None or (p['review_status']!='unreviewed' and t['coverage'] in (0.5,1.0))
   if p['review_status']=='source_verified': assert all(itemmap[i]['source_type']=='school_source' for i in t['learning_item_ids'])
   tagids.append(t['skill_id'])
  assert len(tagids)==len(set(tagids))
  if not tagids: assert p['hold_reason'] and p['required_material']
 assert len(ids)==len(set(ids)) and len(seen)==len(set(seen)) and set(seen)==set(rows)
 assert actual==expected
 # Terms in title may justify a named technology; manually review any flagged content.
 suspect=['Python','JavaScript','SQL','React','Django','TensorFlow','선수조건','주차별','숙련도']
 flags=[]
 for p in doc['profiles']:
  title=' '.join(c['title'] for c in p['courses'])
  for item in p['learning_items']:
   for term in suspect:
    if term.lower() in item['text'].lower() and term.lower() not in title.lower(): flags.append((p['profile_id'],term))
 assert not flags, flags
 return True

def csvrows(doc):
 def j(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'))
 for p in doc['profiles']:
  yield {'profile_id':p['profile_id'],'course_ids':j([c['course_id'] for c in p['courses']]),'course_titles':j([c['title'] for c in p['courses']]),'learning_content':j([x['text'] for x in p['learning_items']]),'learning_objects':j([x['object'] for x in p['learning_items']]),'learning_actions':j([x['action'] for x in p['learning_items']]),'core_tags':j([t['skill_id'] for t in p['tag_candidates'] if t['importance']=='core']),'supporting_tags':j([t['skill_id'] for t in p['tag_candidates'] if t['importance']=='supporting']),'evidence_type':j([x['source_type'] for x in p['learning_items']] or ['title_inferred']),'uncertainty_hold':p['uncertainty']+((' / 보류: '+p['hold_reason']+' / 필요: '+p['required_material']) if p['hold_reason'] else ''),'dictionary_candidates':j(p['dictionary_candidates']),'review_status':p['review_status'],'reviewer_corrections':'','reviewer_notes':''}

def export(doc):
 rows=list(csvrows(doc)); path=HERE/'review.csv'
 if path.exists():
  with path.open(encoding='utf-8-sig',newline='') as f: old={r['profile_id']:r for r in csv.DictReader(f)}
  for row in rows:
   for key in ('reviewer_corrections','reviewer_notes'):
    row[key]=old.get(row['profile_id'],{}).get(key,'')
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return path

def audit_csv(doc):
 with (HERE/'review.csv').open(encoding='utf-8-sig',newline='') as f: actual=list(csv.DictReader(f))
 expected=list(csvrows(doc));assert len(actual)==len(expected)
 for a,e in zip(actual,expected):
  for k,v in e.items():
   if k not in ('reviewer_corrections','reviewer_notes'): assert a[k]==v,(a['profile_id'],k)
 return len(actual)

def diff(doc,cat):
 old={p['course_id']:p for p in cat['profiles']}; lines=[]
 for p in doc['profiles']:
  cid=p['courses'][0]['course_id']; prior={t['skill_id']:('core' if t['coverage']==1 else 'supporting') for t in old.get(cid,{}).get('skills',[])}
  new={t['skill_id']:t['importance'] for t in p['tag_candidates']}
  lines.append({'profile_id':p['profile_id'],'course_ids':' | '.join(c['course_id'] for c in p['courses']),'titles':' | '.join(c['title'] for c in p['courses']),'added':' | '.join(sorted(new.keys()-prior.keys())),'removed':' | '.join(sorted(prior.keys()-new.keys())),'importance_changed':' | '.join(f'{k}:{prior[k]}->{new[k]}' for k in sorted(prior.keys()&new.keys()) if prior[k]!=new[k])})
 return lines

def report(doc,cat,rows):
 diffs=diff(doc,cat)
 with (HERE/'tag_diff.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(diffs[0]));w.writeheader();w.writerows(diffs)
 counts=collections.Counter((t['importance'],t['skill_id']) for p in doc['profiles'] for t in p['tag_candidates'])
 held=[p for p in doc['profiles'] if not p['tag_candidates']]
 checks={'source_rows':len(rows),'profiles':len(doc['profiles']),'equivalent_groups':len(cat['equivalent_course_groups']),'tagged_profiles':len(doc['profiles'])-len(held),'held_profiles':len(held),'tagged_rows':sum(len(p['courses']) for p in doc['profiles'] if p['tag_candidates']),'held_rows':sum(len(p['courses']) for p in held),'added_tags':sum(len(x['added'].split(' | ')) for x in diffs if x['added']),'removed_tags':sum(len(x['removed'].split(' | ')) for x in diffs if x['removed']),'importance_changes':sum(len(x['importance_changed'].split(' | ')) for x in diffs if x['importance_changed']),'tag_distribution':{f'{kind}:{sid}':n for (kind,sid),n in sorted(counts.items())},'dictionary_candidates':dict(collections.Counter(x for p in doc['profiles'] for x in p['dictionary_candidates'])),'csv_rows_checked':audit_csv(doc),'status':'passed','limits':'기술명 탐지는 정해진 단어 목록만 자동 검사; 내용 타당성은 사람의 검토가 필요'}
 write(HERE/'audit.json',checks)
 lines=['# 전 과목 태깅 검토 안내','',f"원천 {checks['source_rows']}행, 확인된 동일 과목 {checks['equivalent_groups']}그룹, 고유 프로필 {checks['profiles']}개. 후보 있음 {checks['tagged_profiles']}개 / 보류 {checks['held_profiles']}개 (각각 {checks['tagged_rows']}행 / {checks['held_rows']}행).",'','초안은 제목과 일반적인 학문 의미를 바탕으로 Codex가 직접 작성했다. 외부 모델이나 학교 강의계획서는 사용하지 않았다. title_inferred는 사실 확인이 아닌 추정이다. 핵심/보조는 태그 관계이지 학습 비중이 아니다.','',f"기존 임시 태그와 비교: 프로필 기준 추가 {checks['added_tags']}개, 제거 {checks['removed_tags']}개, 공통 태그 핵심/보조 변경 {checks['importance_changes']}개. 상세는 tag_diff.csv. 기존 coverage 1.0/0.5를 비교용 핵심/보조로 해석했으며 기존 태그도 미검토다.",'','## 보류']
 for p in held: lines.append('- '+', '.join(c['title']+' ['+c['course_id']+']' for c in p['courses'])+': '+p['hold_reason']+'; 필요: '+p['required_material'])
 lines+=['','## 핵심·보조 태그 분포 (프로필 기준)']
 for k,v in checks['tag_distribution'].items(): lines.append(f'- {k}: {v}')
 lines+=['','사전 확장 후보: '+json.dumps(checks['dictionary_candidates'],ensure_ascii=False),'','## 검토 방법','', 'review.csv에서 학습 내용과 대상·행동, 태그의 적절성, 누락과 보류 사유를 검토한다. 수정 태그와 메모 열은 검토 의견 수집용이며 JSON에 자동 반영되지 않는다. 검토자가 근거와 함께 profiles.json을 수정하고 reviewer·review_notes를 채운 뒤, 추론의 타당성을 검토했으면 inference_reviewed, 항목별 학교 원문과 출처를 확인했으면 source_verified로 바꾼다. 학교 자료가 없는 항목을 학교 확인으로 표시하지 않는다. 검토 후 export와 audit를 다시 실행한다. 실험 변환의 coverage는 별도 설정의 가정이다.','', '자동 검사는 ID, 그룹, 태그 및 학습 항목 연결, CSV 재읽기와 일부 근거 없는 기술명 패턴을 확인한다. 기술명 목록 검사는 완전하지 않으며 학교 자료를 대신하지 않는다.']
 (HERE/'REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 return checks

def convert(doc,cats,config,experimental):
 if not experimental: raise ValueError('운영 승격 경로 없음: 검토 및 운영 승인 후 별도 준비 필요')
 cat=copy.deepcopy(cats[doc['catalog_id']]);cat['profiles']=[]
 for p in doc['profiles']:
  if not p['tag_candidates']: continue
  tags=[{'skill_id':t['skill_id'],'coverage':config['coverage_by_importance'][t['importance']]} for t in p['tag_candidates']]
  for c in p['courses']: cat['profiles'].append({'course_id':c['course_id'],'source_type':'name_inferred','review_status':'unreviewed','skills':copy.deepcopy(tags)})
 return {doc['catalog_id']:cat}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['export','audit','convert']);parser.add_argument('--experimental',action='store_true');parser.add_argument('--output');a=parser.parse_args()
 doc,cats,skills,cat,digest,rows=inputs();val(doc,cat,skills,digest,rows)
 if a.command=='export': print(export(doc))
 if a.command=='audit': print(json.dumps(report(doc,cat,rows),ensure_ascii=False,indent=2))
 if a.command=='convert':
  if not a.experimental or not a.output: parser.error('별도 실험용 --experimental --output 필요')
  path=Path(a.output).resolve(); art=(ROOT/'artifacts').resolve()
  if not path.is_relative_to(art) or path.exists(): parser.error('artifacts 아래의 새 파일만 허용')
  cfg=read(HERE/'coverage_experiment.json'); result=convert(doc,cats,cfg,True);path.parent.mkdir(parents=True,exist_ok=True);write(path,result)
  write(str(path)+'.manifest.json',{'candidate_sha256':hashlib.sha256((HERE/'profiles.json').read_bytes()).hexdigest(),'config_sha256':hashlib.sha256((HERE/'coverage_experiment.json').read_bytes()).hexdigest(),'conversion_version':cfg['version'],'experimental':True,'assumption':cfg['description'],'catalog_version':doc['catalog_version']});print(path)
if __name__=='__main__': main()
