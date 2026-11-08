"""One run produces all comparison artifacts with common immutable provenance."""
import copy,csv,datetime,hashlib,json,sys,uuid
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(root)); sys.path.insert(0,str(root/'tagging'))
from pipeline import load,convert
from course_recommendation import load_bundle
from course_recommendation.engine import recommend_with_trace
from course_recommendation.interpret import interpret
from course_recommendation.interpret_v2 import interpret as previous
from course_recommendation.bundle import digest
p=Path(__file__).resolve().parent; bundle_path=root/'artifacts/model'
b=load_bundle(bundle_path); draft=load(root/'tagging/sample.json'); new=convert(draft,b['catalogs'],b['skills'],True)
rows=load(root/'artifacts/seoultech-data/rows.json'); names={r['course_id']:r['교과목명'] for r in rows}
with (p/'career_goals_100.csv').open(encoding='utf-8-sig',newline='') as f: goals=list(csv.DictReader(f))
code_files=[root/'course_recommendation'/x for x in ('interpret.py','interpret_v2.py','engine.py','legacy.py','bundle.py')]+[Path(__file__),root/'tagging/pipeline.py']
h=hashlib.sha256()
for f in code_files: h.update(str(f.relative_to(root)).encode()); h.update(bytes.fromhex(digest(f)))
now=datetime.datetime.now(datetime.timezone.utc); rid=now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
meta={'run_id':rid,'generated_at':now.isoformat(),'code_state_sha256':h.hexdigest(),'model_sha256':b['bundle_hashes']['encoder.onnx'],'tokenizer_sha256':b['bundle_hashes']['tokenizer.json'],'bundle_hashes':b['bundle_hashes'],'config_sha256':b['bundle_hashes']['config.json'],'eval_set_sha256':digest(p/'career_goals_100.csv'),'candidate_sha256':digest(root/'tagging/sample.json'),'conditions':'same v2 engine, model, vocabulary, role table, filters and thresholds; previous vs follow-up interpreter; baseline vs partial candidate replacement; existing shared-tag coverage retained; new tags experimental 0.5'}
out=p/'runs'/rid; out.mkdir(parents=True)
cat=b['catalogs']['seoultech-csv-test']; snap=dict(catalog_id='seoultech-csv-test',catalog_version=cat['version'],course_ids=cat['course_ids'],completed_course_ids=[],selection_review_status='unconfirmed',target_role=None)
results=[]; traces=[]
for goal in goals:
 for parser,fn in [('previous',previous),('improved',interpret)]:
  for tags in ('existing','candidate'):
   bb=dict(b); bb['catalogs']=b['catalogs'] if tags=='existing' else new
   result,trace=recommend_with_trace(dict(snap,career_goal=goal['희망_진로_예시']),bb,interpreter=fn)
   if result['status']=='unavailable': raise RuntimeError((goal['id'],trace['status_reason']))
   results.append({'run_id':rid,'generated_at':meta['generated_at'],'code_state_sha256':meta['code_state_sha256'],'model_sha256':meta['model_sha256'],'tokenizer_sha256':meta['tokenizer_sha256'],'config_sha256':meta['config_sha256'],'eval_set_sha256':meta['eval_set_sha256'],'candidate_sha256':meta['candidate_sha256'],'bundle_hashes':json.dumps(meta['bundle_hashes'],sort_keys=True),'id':goal['id'],'parser':parser,'tags':tags,'status':result['status'],'reason':trace['status_reason'],'skills':' | '.join(x['skill_id'] for x in result['goal_skills']),'courses':' | '.join(names[x['course_id']]+' ['+x['course_id']+']' for x in result['courses'])})
   traces.append({'run_id':rid,'metadata':meta,'id':goal['id'],'parser':parser,'tags':tags,'trace':trace})
with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
with (out/'traces.jsonl').open('w',encoding='utf-8') as f:
 for t in traces: f.write(json.dumps(t,ensure_ascii=False)+'\n')
counts={f'{parser}/{tags}':dict(Counter(r['status'] for r in results if r['parser']==parser and r['tags']==tags)) for parser in ('previous','improved') for tags in ('existing','candidate')}
reasons={f'{parser}/{tags}':dict(Counter(r['reason'] for r in results if r['parser']==parser and r['tags']==tags)) for parser in ('previous','improved') for tags in ('existing','candidate')}
oldp={x['course_id']:x for x in cat['profiles']}; newp={x['course_id']:x for x in new['seoultech-csv-test']['profiles']}
diff=[{'course_id':cid,'title':names[cid],'before':oldp.get(cid,{}).get('skills',[]),'after':newp.get(cid,{}).get('skills',[])} for cid in sorted(set(oldp)|set(newp)) if oldp.get(cid,{}).get('skills',[])!=newp.get(cid,{}).get('skills',[])]
changes={}
for parser in ('previous','improved'):
 existing={r['id']:r for r in results if r['parser']==parser and r['tags']=='existing'}
 candidate={r['id']:r for r in results if r['parser']==parser and r['tags']=='candidate'}
 changes[parser]=[gid for gid in existing if existing[gid]['courses']!=candidate[gid]['courses']]
summary={'changed_course_lists':changes,'metadata':meta,'status_counts':counts,'reason_counts':reasons,'tag_diff':diff,'reviewed_quality_metrics':None,'reviewed_quality_reason':'No reviewed labels; precision, relevance and exclusion violation rates cannot be computed.'}
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
lines=['# 후속 2×2 실험', '', f'실행 ID: {rid}  ',f'생성 시각: {now.isoformat()}  ',f'코드 상태 SHA-256: {h.hexdigest()}  ',f'모델 / 토크나이저: {meta["model_sha256"]} / {meta["tokenizer_sha256"]}  ',f'설정: {meta["config_sha256"]}  ',f'평가셋: {meta["eval_set_sha256"]}  ',f'묶음 해시 및 후보 해시: summary.json 참조', '',meta['conditions'], '', '검토 라벨이 없어 정확도·추천 적합도·제외 위반율은 계산 불가. 상태 건수는 품질 지표가 아니다.', '', '## 상태 건수']
for key,v in counts.items(): lines.append(f'- {key}: {v}; 사유: {reasons[key]}')
lines += ['', '태그 후보로 과목 목록이 달라진 입력 ID: '+json.dumps(changes,ensure_ascii=False), '', '## 사례 (실행 결과 자동 생성)']
for gid in ('G018','G031','G036','G042','G077','G082','G083','G084','G086','G087','G090'):
 for r in results:
  if r['id']==gid and r['parser']=='improved': lines.append(f'- {gid} / {r["tags"]}: {r["status"]} ({r["reason"]}); {r["skills"]}; {r["courses"]}')
lines+=['','## 태그 차이',json.dumps(diff,ensure_ascii=False), '', 'G087에서 암호 역량은 제외되지만 보안 태그로 암호 과목이 추천될 수 있다. 공유 기초 과목까지 일괄 제거하지 않기 때문에 과목 수준 제외 정책과 검토된 근거가 필요하다.', '', '제목 기반 수작업 샘플 두 과목만 교체했다. 기존 공통 태그 coverage는 유지하며 신규 태그가 있으면 0.5라는 실험 가정을 적용한다. 실제 학습 비중이나 강의계획서 검증이 아니다. 결과 차이와 적절성은 사람의 검토가 필요하다.']
(out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(out)
