"""Reproducible provisional name-only profiles for the supplied CSV, never production data."""
import csv, hashlib, json, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]; source=list((root/'data').glob('*.csv'))
if len(source)!=1: sys.exit('Expected exactly one source CSV in data/')
source=source[0]
expected='9b511b63700f29e89c51c7662d4ae2736b72ba67b6400d03d3f50dea8dc6f16e'
if hashlib.sha256(source.read_bytes()).hexdigest()!=expected: sys.exit('CSV changed; review all row mappings before reuse')
out=root/'artifacts'/'seoultech-data'; out.mkdir(parents=True,exist_ok=True)
with source.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
if len(rows)!=68: sys.exit('Expected 68 source rows; review the mapping before reuse')
items=[
('programming','프로그래밍','변수, 조건문, 반복문, 함수로 프로그램을 작성한다',['코딩']),
('object_oriented','객체지향 프로그래밍','객체와 클래스에 기반하여 소프트웨어를 설계하고 구현한다',['객체지향']),
('data_structures','자료구조','자료를 저장하고 처리하는 자료구조를 이해하고 사용한다',[]),
('algorithms','알고리즘','문제를 해결하는 알고리즘의 설계와 분석',['알고리즘']),
('sql','SQL','관계형 데이터베이스에서 SQL을 사용해 데이터 조회와 변경을 수행한다',['에스큐엘']),
('databases','데이터베이스','데이터베이스의 구조와 데이터 관리 원리를 이해한다',[]),
('operating_systems','운영체제','프로세스와 메모리 등 운영체제의 원리를 이해한다',[]),
('networks','컴퓨터 네트워크','컴퓨터 네트워크의 데이터 통신 원리를 이해한다',['네트워크']),
('software_engineering','소프트웨어공학','소프트웨어 개발과 설계 및 유지보수 원리를 이해한다',[]),
('web_development','웹 개발','웹 애플리케이션을 개발하는 프로그래밍 능력',['웹 프로그래밍']),
('data_analysis','데이터 분석','데이터를 분석하고 패턴과 의미를 찾는다',['데이터분석']),
('statistics','확률과 통계','확률과 랜덤 변수의 수학적 원리를 이해한다',['확률']),
('linear_algebra','선형대수','벡터와 행렬 및 선형변환을 이해한다',[]),
('machine_learning','기계학습','데이터에서 학습하는 기계학습 모델의 원리와 활용',['머신러닝','machine learning']),
('ai','인공지능','인공지능의 기본 개념과 문제 해결 방법을 이해한다',['AI']),
('security','정보보안','컴퓨터 시스템과 정보 보호의 원리를 이해한다',['보안','사이버보안']),
('computer_vision','컴퓨터 비전','이미지와 영상의 시각 정보를 컴퓨터로 처리한다',['영상처리']),
('natural_language','자연어 처리','자연어 텍스트를 컴퓨터로 분석하고 처리한다',['자연어처리','NLP']),
('embedded','임베디드 시스템','임베디드 장치에서 실행되는 소프트웨어를 이해하고 개발한다',['임베디드']),
('systems_programming','시스템 프로그래밍','운영체제와 상호작용하는 시스템 소프트웨어를 작성한다',[]),
('computer_architecture','컴퓨터 구조','프로세서와 컴퓨터 시스템의 구성과 작동을 이해한다',[]),
('cryptography','암호','정보 보호를 위한 암호 알고리즘의 원리를 이해한다',['암호학']),
('graphics','컴퓨터 그래픽스','컴퓨터를 이용한 그래픽 이미지의 표현과 처리',[]),
('mobile','모바일 프로그래밍','모바일 장치를 위한 응용 프로그램을 작성한다',['모바일']),
('discrete_math','이산수학','컴퓨터 과학에 사용되는 이산적인 수학 구조를 이해한다',[]),
('reinforcement_learning','강화학습','보상에 따라 행동을 선택하는 강화학습의 개념을 이해한다',['reinforcement learning']),
('data_mining','데이터 마이닝','데이터에서 패턴이나 유용한 정보를 발견하는 방법을 이해한다',['데이터마이닝']),
('big_data_processing','빅데이터 처리','대규모 데이터를 처리하고 관리하는 방법을 이해한다',['빅데이터처리']),
('digital_logic','디지털 논리','디지털 회로와 논리 연산의 기본 원리를 이해한다',['디지털논리']),
('formal_languages','형식 언어','형식적으로 정의한 언어와 문법을 이해한다',['형식언어']),
('automata','오토마타','계산 모형으로서 오토마타의 원리를 이해한다',['automata']),
('programming_language_theory','프로그래밍 언어론','프로그래밍 언어의 구조와 의미를 이해한다',[]),
('compiler','컴파일러','프로그래밍 언어를 변환하는 컴파일러의 구조와 원리를 이해한다',['컴파일러구조']),
('unix','유닉스 시스템','유닉스 계열 시스템의 사용과 동작을 이해한다',['유닉스','Unix']),
('data_communication','데이터 통신','컴퓨터와 장치 사이의 데이터 전송 원리를 이해한다',['데이터통신']),
('open_source','오픈소스 소프트웨어','공개된 소스코드에 기반한 소프트웨어의 개념을 이해한다',['오픈소스']),
('iot','사물인터넷','네트워크로 연결된 사물과 장치의 기본 개념을 이해한다',['IoT']),
('blockchain','블록체인','분산된 블록 기록을 이용하는 기술의 기본 개념을 이해한다',[]),
('game_programming','게임 프로그래밍','게임의 동작과 규칙을 프로그램으로 구현한다',['게임프로그래밍']),
('software_design','소프트웨어 설계','소프트웨어의 구조와 구성 요소를 설계한다',[]),
('software_testing','소프트웨어 테스트','소프트웨어의 동작을 검증하고 오류를 찾는다',['테스트']),

]
skills=[dict(skill_id=i,name=n,description=d,aliases=a) for i,n,d,a in items]
def role(id,name,aliases,description,priorities): return dict(role_id=id,name=name,aliases=aliases,description=description,skills=[dict(skill_id=k,priority=v) for k,v in priorities])
roles=[
role('backend','백엔드 개발자',['백엔드'],'서버 애플리케이션과 데이터베이스를 설계하고 개발한다',[('programming',3),('databases',3),('networks',2),('software_engineering',2),('operating_systems',2)]),
role('data_analyst','데이터 분석가',['데이터 애널리스트'],'데이터를 분석해 패턴을 발견하고 의사결정을 돕는다',[('data_analysis',3),('statistics',3),('databases',2),('programming',2)]),
role('ml_engineer','머신러닝 엔지니어',['기계학습 엔지니어'],'기계학습 모델을 개발하고 활용하는 엔지니어',[('machine_learning',3),('programming',3),('linear_algebra',2),('statistics',2)]),
role('security_engineer','보안 엔지니어',['보안 전문가'],'컴퓨터와 네트워크 시스템의 보안을 분석하고 보호한다',[('security',3),('networks',2),('operating_systems',2),('cryptography',2)])]
# Explicit row-level mappings inferred only from the supplied names; no claim about actual syllabus.
assign={1:'programming',2:'programming',3:'',4:'',5:'discrete_math',6:'object_oriented',7:'object_oriented',8:'operating_systems',9:'operating_systems',10:'statistics',11:'statistics',12:'data_structures',13:'data_structures',14:'computer_architecture',15:'computer_architecture',16:'',17:'',18:'networks',19:'data_analysis',20:'systems_programming',21:'computer_vision',22:'operating_systems',23:'security',24:'',25:'machine_learning',26:'machine_learning',27:'',28:'',29:'',30:'natural_language',31:'embedded',32:'',33:'',34:'embedded',35:'cryptography',36:'programming',37:'programming',38:'linear_algebra',39:'linear_algebra',40:'',41:'',42:'databases',43:'databases',44:'algorithms',45:'web_development',46:'networks',47:'systems_programming',48:'ai',49:'machine_learning',50:'machine_learning',51:'software_engineering',52:'software_engineering',53:'graphics',54:'mobile',55:'security',56:'computer_architecture',57:'web_development',58:'programming',59:'',60:'',61:'',62:'',63:'',64:'',65:'software_engineering',66:'data_analysis',67:'security',68:'data_analysis'}
# Specific tags are limited to concepts present in the title.
assign.update({8:'unix',9:'unix',14:'digital_logic',15:'digital_logic',16:'formal_languages',17:'formal_languages',25:'reinforcement_learning',26:'reinforcement_learning',27:'programming_language_theory',28:'programming_language_theory',34:'iot',40:'open_source',41:'open_source',46:'data_communication',58:'game_programming',61:'blockchain',62:'compiler',66:'data_mining',68:'big_data_processing'})
assert set(assign)==set(range(1,len(rows)+1))
ids=[f'csv-row-{i:03}' for i in range(1,len(rows)+1)]
# Additional broad connections are tentative name-based hypotheses, not syllabus evidence.
# Omitted courses remain deferred; no tag is added merely to reach the five-tag cap.
secondary={
    6:['programming'], 7:['programming'],
    8:['operating_systems'], 9:['operating_systems'],
    12:['algorithms'], 13:['algorithms'],
    14:['computer_architecture'], 15:['computer_architecture'],
    16:['automata'], 17:['automata'],
    19:['statistics'], 20:['programming','operating_systems'],
    21:['ai'], 25:['machine_learning','ai'], 26:['machine_learning','ai'],
    30:['ai'], 31:['programming'], 34:['embedded','networks'], 35:['security'],
    44:['data_structures'], 45:['programming'], 46:['networks'],
    47:['unix','programming','operating_systems'],
    49:['ai'], 50:['ai'],
    51:['software_design','software_testing'], 52:['software_design','software_testing'],
    53:['programming'], 54:['programming'], 57:['programming'], 58:['programming'],
    62:['programming_language_theory'], 65:['software_design','software_testing'],
    66:['data_analysis','machine_learning'], 68:['data_analysis'],
}
profiles=[]
for i, tag in assign.items():
    if not tag: continue
    extra=[skill for skill in secondary.get(i,[]) if skill != tag]
    tags=[dict(skill_id=tag,coverage=1.0)] + [dict(skill_id=skill,coverage=0.5) for skill in extra]
    if len(tags)>5 or len({t['skill_id'] for t in tags})!=len(tags): raise ValueError('invalid tags')
    profiles.append(dict(course_id=ids[i-1],source_type='name_inferred',review_status='unreviewed',skills=tags))
version=hashlib.sha256(source.read_bytes()).hexdigest()
# Korean first is the display preference, not a claim that either section is available.
pairs=[(1,2),(3,4),(6,7),(8,9),(10,11),(12,13),(14,15),(16,17),(26,25),(27,28),(36,37),(38,39),(40,41),(42,43),(49,50),(51,52)]
groups=[[ids[a-1],ids[b-1]] for a,b in pairs]
# Equivalent language variants must retain identical provisional tags.
profile_map={p['course_id']:p['skills'] for p in profiles}
for group in groups:
    if profile_map.get(group[0]) != profile_map.get(group[1]): raise ValueError('equivalent course tags differ')
catalog={'seoultech-csv-test':{'version':version,'course_ids':ids,'profiles':profiles,'equivalent_course_groups':groups}}
config={'skill_threshold':0.9,'role_threshold':0.9,'role_margin':0.05,'course_threshold':0.01}
for name,obj in [('skills.json',skills),('roles.json',roles),('course_profiles.json',catalog),('config.json',config),('rows.json',[dict(course_id=id,**row) for id,row in zip(ids,rows)])]: (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
skill_names={item['skill_id']:item['name'] for item in skills}
with (out/'course_tags_review.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f); writer.writerow(['course_id','교과목명','검토상태','태그 (coverage)'])
    for i,row in enumerate(rows):
        tags=profile_map.get(ids[i],[])
        writer.writerow([ids[i],row['교과목명'],'미검토' if tags else '보류', ' / '.join(f"{skill_names[t['skill_id']]} [{t['skill_id']}] ({t['coverage']})" for t in tags)])
print(f'CSV SHA-256 {version}; {len(rows)} rows; {len(profiles)} tagged; {len(rows)-len(profiles)} deferred; {len(skills)} skills, {len(roles)} roles; output {out}')
