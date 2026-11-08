"""Human-authored title-inference draft; source strings below are the actual analyses."""
import csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
# Each item is (object, action, concrete inferred learning content); each tag is
# (existing skill ID, core/supporting, 1-based evidence indices, review rationale).
D={
1:([('프로그램과 명령','작성','간단한 프로그램의 명령을 작성한다'),('프로그램의 실행 흐름','이해','명령이 실행되는 흐름을 이해한다')],[('programming','core',[1,2],'프로그래밍 입문이라는 제목의 직접 주제')],[]),
3:([('컴퓨터공학의 주요 분야','개관','컴퓨터공학의 주요 분야를 개관한다'),('컴퓨터 시스템과 소프트웨어','이해','컴퓨터 시스템과 소프트웨어의 역할을 살핀다')],[],['컴퓨터공학 개론']),
5:([('이산적 수학 구조','이해','이산적 대상의 수학적 표현을 이해한다'),('명제와 논리','분석','명제와 논리적 관계를 분석한다')],[('discrete_math','core',[1,2],'이산수학이라는 제목의 직접 주제')],[]),
6:([('객체와 클래스','이해','객체와 클래스의 개념을 이해한다'),('객체 사이의 관계','구현','객체 사이의 관계를 프로그램으로 표현한다')],[('object_oriented','core',[1,2],'객체지향 언어의 직접 주제')],[]),
8:([('유닉스 시스템','이해','유닉스 시스템의 구성과 동작을 이해한다'),('유닉스 환경의 파일과 프로세스','이해','유닉스 환경에서 파일과 프로세스의 역할을 살핀다')],[('unix','core',[1,2],'제목에 명시된 유닉스 시스템')],[]),
10:([('확률과 사건','계산','사건의 확률을 표현하고 계산한다'),('확률변수와 분포','이해','확률변수와 그 분포를 이해한다')],[('statistics','core',[1,2],'확률과 확률변수의 기초를 다룸')],[]),
12:([('자료구조','비교','자료를 조직하는 여러 구조를 비교한다'),('자료의 저장과 접근','이해','자료구조에서 저장과 접근 방법을 이해한다')],[('data_structures','core',[1,2],'자료구조 자체가 제목의 주제')],[]),
14:([('논리 연산과 논리회로','이해','디지털 논리 연산과 회로를 이해한다'),('디지털 시스템','구성','논리 요소로 구성된 디지털 시스템을 살핀다')],[('digital_logic','core',[1,2],'제목에 디지털 논리와 시스템이 명시됨')],[]),
16:([('형식 문법과 언어','이해','형식 문법과 언어의 표현을 이해한다'),('오토마타와 언어','분석','오토마타가 언어를 인식하는 관계를 분석한다')],[('formal_languages','core',[1,2],'형식 언어가 제목에 명시됨'),('automata','core',[2],'오토마타가 제목에 명시됨')],[]),
18:([('컴퓨터 네트워크','이해','컴퓨터 간 네트워크의 구성과 통신을 이해한다'),('네트워크 통신','분석','네트워크에서 정보가 전달되는 방식을 살핀다')],[('networks','core',[1,2],'컴퓨터 네트워크가 직접 주제')],[]),
19:([('데이터','분석','데이터를 살펴보고 특징과 패턴을 분석한다'),('분석 결과','해석','데이터 분석 결과의 의미를 해석한다')],[('data_analysis','core',[1,2],'데이터 분석이 직접 주제')],[]),
20:([('시스템 소프트웨어','구현','시스템과 상호작용하는 소프트웨어 구현을 살핀다'),('시스템 자원','이해','프로그램에서 시스템 자원을 다루는 원리를 이해한다')],[('systems_programming','core',[1,2],'시스템 프로그래밍이 직접 주제')],[]),
21:([('이미지와 영상','처리','이미지와 영상의 시각 정보를 처리하는 방법을 살핀다'),('시각 정보','분석','시각 정보에서 특징을 분석하는 원리를 이해한다')],[('computer_vision','core',[1,2],'컴퓨터비전이 직접 주제')],[]),
22:([('프로세스와 스레드','이해','운영체제의 실행 단위와 관리 원리를 이해한다'),('메모리와 자원','관리','운영체제가 메모리와 자원을 관리하는 방식을 살핀다')],[('operating_systems','core',[1,2],'운영체제의 기본 관리 대상')],[]),
23:([('정보와 시스템의 위협','분석','정보와 시스템에 대한 위협을 살핀다'),('정보 보호 원리','이해','정보를 보호하는 기본 원리를 이해한다')],[('security','core',[1,2],'정보보호론의 직접 주제')],[]),
26:([('행동과 보상','이해','행동에 따른 보상을 이용하는 학습 개념을 이해한다'),('상태와 행동 선택','분석','상태에 따른 행동 선택과 결과를 분석한다')],[('reinforcement_learning','core',[1,2],'강화학습이 직접 주제')],[]),
27:([('프로그래밍 언어의 구문','분석','프로그래밍 언어의 구문 구조를 살핀다'),('프로그래밍 언어의 의미','이해','언어 구성 요소의 의미를 이해한다')],[('programming_language_theory','core',[1,2],'프로그래밍언어론이 직접 주제')],[]),
30:([('자연어 텍스트','분석','자연어 텍스트의 구조와 정보를 분석한다'),('자연어 데이터','처리','자연어를 컴퓨터로 처리하는 방법을 살핀다')],[('natural_language','core',[1,2],'자연어처리가 직접 주제')],[]),
31:([('임베디드 장치의 소프트웨어','이해','임베디드 장치에서 동작하는 소프트웨어의 특성을 이해한다'),('장치와 소프트웨어','구현','장치 환경에 맞는 소프트웨어 구현을 살핀다')],[('embedded','core',[1,2],'임베디드 소프트웨어가 직접 주제')],[]),
34:([('연결된 사물과 장치','이해','네트워크로 연결된 장치의 역할을 이해한다'),('사물 간 데이터 교환','분석','사물과 서비스 사이의 데이터 교환을 살핀다')],[('iot','core',[1,2],'사물인터넷이 직접 주제')],[]),
35:([('암호 알고리즘','이해','정보 보호에 쓰이는 암호 알고리즘의 원리를 이해한다'),('암호 기법','비교','암호 기법의 특성을 비교한다')],[('cryptography','core',[1,2],'암호 알고리즘이 제목에 명시됨')],[]),
36:([('프로그램과 명령','작성','프로그램의 명령을 작성한다'),('프로그램 구성','이해','프로그램을 구성하는 요소와 실행 흐름을 살핀다')],[('programming','core',[1,2],'프로그래밍 입문이라는 직접 주제')],[]),
38:([('벡터와 행렬','연산','벡터와 행렬의 연산을 이해한다'),('선형 변환','분석','선형 변환과 그 표현을 분석한다')],[('linear_algebra','core',[1,2],'선형대수의 기본 대상')],[]),
40:([('오픈소스 소프트웨어','이해','공개된 소스에 기반한 소프트웨어의 개념을 이해한다'),('공개 소스와 협업','분석','공개 소스의 활용과 협업 방식을 살핀다')],[('open_source','core',[1,2],'오픈소스 소프트웨어가 직접 주제')],[]),
42:([('데이터와 관계','구조화','데이터와 관계를 구조화하는 방법을 이해한다'),('데이터의 저장과 조회','이해','데이터베이스에서 데이터의 저장과 조회 개념을 살핀다')],[('databases','core',[1,2],'데이터베이스의 기본 개념')],['데이터 모델링']),
44:([('알고리즘','설계','문제를 해결하는 절차를 설계한다'),('알고리즘의 자원 사용','분석','알고리즘의 실행 비용을 분석한다')],[('algorithms','core',[1,2],'알고리즘 자체가 직접 주제')],[]),
45:([('웹 애플리케이션','구현','웹에서 동작하는 프로그램의 구현을 살핀다'),('웹 요청과 응답','이해','웹에서 정보가 전달되는 기본 구조를 이해한다')],[('web_development','core',[1,2],'웹 프로그래밍이 직접 주제')],[]),
46:([('데이터 전송','이해','장치 사이 데이터 전송의 기본 원리를 이해한다'),('통신 방식','비교','데이터 통신 방식의 특성을 비교한다')],[('data_communication','core',[1,2],'데이터통신이 직접 주제')],[]),
47:([('유닉스 환경의 프로그램','구현','유닉스 환경에서 동작하는 프로그램을 작성한다'),('유닉스 시스템 자원','이해','프로그램이 유닉스 시스템 자원과 상호작용하는 방식을 살핀다')],[('systems_programming','core',[1,2],'유닉스 환경의 시스템 프로그래밍'),('unix','supporting',[1,2],'유닉스가 제목에 명시된 실행 환경')],[]),
48:([('인공지능의 문제 해결','이해','인공지능의 기본 문제 해결 개념을 이해한다'),('인공지능 접근법','비교','인공지능 문제를 다루는 접근법을 살핀다')],[('ai','core',[1,2],'인공지능 개론이 직접 주제')],[]),
49:([('데이터와 학습 모델','이해','데이터로부터 모델이 학습하는 원리를 이해한다'),('학습 결과','평가','학습 모델의 결과를 평가하는 개념을 살핀다')],[('machine_learning','core',[1,2],'기계학습이 직접 주제')],[]),
51:([('소프트웨어 개발 과정','이해','소프트웨어 개발 과정의 주요 활동을 이해한다'),('소프트웨어 품질','관리','소프트웨어 품질을 관리하는 원리를 살핀다')],[('software_engineering','core',[1,2],'소프트웨어공학이 직접 주제')],[]),
53:([('그래픽 이미지','표현','컴퓨터에서 그래픽 이미지를 표현하는 원리를 이해한다'),('시각 장면','생성','시각 장면을 컴퓨터로 생성하는 방법을 살핀다')],[('graphics','core',[1,2],'컴퓨터그래픽스가 직접 주제')],[]),
54:([('모바일 응용 프로그램','구현','모바일 환경에서 동작하는 응용 프로그램을 구현한다'),('모바일 장치 환경','이해','모바일 장치 환경의 특성을 살핀다')],[('mobile','core',[1,2],'모바일 프로그래밍이 직접 주제')],[]),
55:([('컴퓨터 시스템의 위협','분석','컴퓨터 시스템에 대한 보안 위협을 분석한다'),('시스템 보호','이해','컴퓨터 시스템을 보호하는 원리를 이해한다')],[('security','core',[1,2],'컴퓨터보안이 직접 주제')],[]),
56:([('프로세서와 메모리','이해','컴퓨터 시스템의 주요 구성 요소와 역할을 이해한다'),('컴퓨터 시스템 구조','분석','구성 요소의 상호작용을 분석한다')],[('computer_architecture','core',[1,2],'컴퓨터 시스템의 구조가 직접 주제')],[]),
57:([('웹 애플리케이션','구현','웹 애플리케이션의 구성과 구현을 살핀다'),('웹 프로그램 구조','분석','웹 프로그램의 구조와 구성 요소를 분석한다')],[('web_development','core',[1,2],'고급 웹프로그래밍이 직접 주제')],[]),
58:([('게임의 규칙과 동작','구현','게임의 규칙과 동작을 프로그램으로 구현한다'),('게임 프로그램 구조','이해','게임 프로그램의 구성 요소를 이해한다')],[('game_programming','core',[1,2],'게임 프로그래밍이 직접 주제')],[]),
61:([('블록과 분산 기록','이해','블록으로 연결된 분산 기록의 개념을 이해한다'),('블록체인 기록의 검증','분석','분산된 기록을 검증하는 원리를 살핀다')],[('blockchain','core',[1,2],'블록체인이 직접 주제')],[]),
62:([('컴파일러의 구성','이해','원시 언어를 변환하는 컴파일러의 구조를 이해한다'),('프로그램 변환 단계','분석','프로그램을 다른 표현으로 변환하는 단계를 살핀다')],[('compiler','core',[1,2],'컴파일러구조가 직접 주제')],[]),
65:([('소프트웨어 개발 과정','분석','소프트웨어 개발 과정의 활동과 관계를 분석한다'),('소프트웨어 품질과 유지보수','이해','소프트웨어 품질과 유지보수의 원리를 살핀다')],[('software_engineering','core',[1,2],'고급 소프트웨어공학이 직접 주제')],[]),
66:([('데이터의 패턴','발견','데이터에서 반복되는 패턴과 정보를 발견한다'),('발견된 패턴','해석','데이터에서 찾은 패턴의 의미를 해석한다')],[('data_mining','core',[1,2],'데이터마이닝이 직접 주제'),('data_analysis','supporting',[2],'발견한 데이터 패턴의 해석과 관련')],[]),
67:([('사이버 환경의 위협','분석','사이버 환경의 보안 위협을 살핀다'),('정보 시스템 보호','이해','정보 시스템을 보호하는 원리를 이해한다')],[('security','core',[1,2],'사이버보안이 직접 주제')],[]),
68:([('대규모 데이터','처리','대규모 데이터를 처리하는 방법을 이해한다'),('대규모 데이터 처리 구조','분석','데이터 규모에 따른 처리 구조의 특성을 살핀다')],[('big_data_processing','core',[1,2],'빅데이터처리가 직접 주제')],[]),
}
HELD={24:'캡스톤의 프로젝트 주제와 수행 활동은 제목으로 특정할 수 없음',29:'현장실습의 기관·업무가 확인되지 않음',32:'코업의 기관·직무와 학습 목표가 확인되지 않음',33:'코업 프로젝트의 주제·활동이 확인되지 않음',59:'캡스톤의 프로젝트 주제와 수행 활동은 제목으로 특정할 수 없음',60:'현장실습의 기관·업무가 확인되지 않음',63:'코업의 기관·직무와 학습 목표가 확인되지 않음',64:'코업 프로젝트의 주제·활동이 확인되지 않음'}
def main():
 if (OUT/'profiles.json').exists(): raise SystemExit('profiles.json already exists; preserve authoritative reviewed data')
 source=next((ROOT/'data').glob('*.csv')); source_bytes=source.read_bytes(); version=hashlib.sha256(source_bytes).hexdigest()
 with source.open(encoding='utf-8-sig',newline='') as f: raw=list(csv.DictReader(f))
 cat=json.loads((ROOT/'data/seoultech_2026_catalog.json').read_text())['seoultech-csv-test']
 if len(raw)!=68 or version!=cat['version']: raise ValueError('source version mismatch')
 groups=cat['equivalent_course_groups']; mapping={cid:g for g in groups for cid in g}; used=set(); profiles=[]
 stamp=datetime.now(timezone.utc).isoformat()
 for idx,row in enumerate(raw,1):
  cid=f'csv-row-{idx:03d}'
  if cid in used: continue
  group=mapping.get(cid,[cid]); used.update(group); representative=group[0]; n=int(representative[-3:]); titles=[{'course_id':x,'title':raw[int(x[-3:])-1]['교과목명']} for x in group]
  if n not in D and n not in HELD: raise ValueError('unanalysed '+representative)
  items,tags,expansion=D.get(n,([],[],[])); learning=[{'id':f'L{i}', 'text':text,'object':obj,'action':action,'source_type':'title_inferred','source':'과목명: '+titles[0]['title']} for i,(obj,action,text) in enumerate(items,1)]
  candidates=[{'skill_id':sid,'importance':importance,'learning_item_ids':[f'L{x}' for x in ids], 'rationale':reason,'coverage':None} for sid,importance,ids,reason in tags]
  profiles.append({'profile_id':'profile-'+representative,'catalog_id':'seoultech-csv-test','catalog_version':version,'courses':titles,'source':{'type':'title','file':str(source.relative_to(ROOT)),'sha256':version,'actual_description':None},'learning_items':learning,'tag_candidates':candidates,'dictionary_candidates':expansion,'uncertainty':'제목에 근거한 추정이며 실제 강의 내용과 학습 비중은 확인되지 않음','hold_reason':HELD.get(n) or ('표준 사전에 개론을 표현할 역량이 없어 태깅 보류' if not tags else None),'required_material':'강의계획서, 강의 개요와 학습 목표' if not tags else '강의 개요와 학습 목표', 'review_status':'unreviewed','reviewer':None,'review_notes':None})
 doc={'schema_version':'full-catalog-v1','generation':{'method':'Codex가 제목과 일반적 학문 의미를 바탕으로 직접 작성; 외부 모델 및 외부 자료 미사용','version':'manual-full-v1','generated_at':stamp},'dictionary_version':'seoultech-2026-41-skill-v1','catalog_id':'seoultech-csv-test','catalog_version':version,'profiles':profiles}
 (OUT/'profiles.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('profiles',len(profiles),'source rows',len(used),'held',sum(not x['tag_candidates'] for x in profiles))
if __name__=='__main__': main()
