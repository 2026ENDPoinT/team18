"""Create grouped, unreviewed candidate labels; not an independent audited test set."""
import csv
from pathlib import Path
# Each seed stays together across both halves; all labels require human review.
seeds=[
('positive','웹 프론트엔드 화면 개발','web_development',''),('positive','서버 API 설계','api_design',''),('positive','컴퓨터 네트워크 원리','networks',''),('positive','운영체제 메모리 관리','operating_systems',''),('positive','자료구조 설계','data_structures',''),('positive','알고리즘 분석','algorithms',''),('positive','데이터베이스 관리','databases',''),('positive','컴퓨터 그래픽스','graphics',''),('positive','확률과 랜덤 변수','statistics',''),('positive','선형대수','linear_algebra',''),
('indirect','영상을 해석하는 컴퓨터 프로그램','computer_vision',''),('indirect','기계가 문장을 처리하는 기술','natural_language',''),('indirect','센서가 달린 연결 기기','iot',''),('indirect','데이터에서 유용한 패턴 찾기','data_mining',''),('indirect','프로그램을 기계어로 변환하는 과정','compiler',''),('indirect','장치에서 실행되는 소프트웨어','embedded',''),('indirect','파일과 프로세스 관리','operating_systems',''),('indirect','데이터를 이용한 행동 예측','machine_learning',''),('indirect','보상을 통한 행동 학습','reinforcement_learning',''),('indirect','프로그램 구조 설계','software_design',''),
('negative','모바일 앱이 아닌 웹사이트 개발','web_development','mobile'),('negative','프론트엔드 말고 백엔드 서버','api_design',''),('negative','웹 개발을 제외하고 네트워크 원리','networks','web_development'),('negative','그래픽스가 아닌 데이터베이스 관리','databases','graphics'),('negative','기계학습 말고 정보보안','security','machine_learning'),('negative','운영체제 대신 알고리즘 분석','algorithms','operating_systems'),('negative','인공지능이 아닌 이산수학','discrete_math','ai'),('negative','프로그래밍을 제외하고 통계','statistics','programming'),('negative','모바일 개발 말고 컴퓨터 그래픽스','graphics','mobile'),('negative','보안이 아닌 자료구조','data_structures','security'),
('comparison','웹 개발보다 네트워크','networks',''),('comparison','통계보다는 데이터 분석','data_analysis',''),('comparison','프로그래밍보다 알고리즘','algorithms',''),('comparison','운영체제보다 데이터베이스','databases',''),('comparison','모바일보다 웹 개발','web_development',''),
('complex','알고리즘과 자료구조를 함께','algorithms|data_structures',''),('complex','컴퓨터 그래픽스와 선형대수를 함께','graphics|linear_algebra',''),('complex','네트워크와 보안을 함께','networks|security',''),('complex','기계학습과 확률을 함께','machine_learning|statistics',''),('complex','데이터베이스와 웹 개발을 함께','databases|web_development',''),
('ambiguous','보안과 웹 개발 중 아직 결정을 못한 상태','', ''),('ambiguous','기계학습과 데이터 분석 중 어느 쪽을 선택할지 모르는 상태','',''),('ambiguous','소프트웨어 분야의 막연한 직업','',''),('ambiguous','좋아하는 전공 분야가 무엇인지 모르는 상황','',''),('ambiguous','아직 직무를 정하지 않은 대학생의 진로','',''),
('out_of_scope','서양 고전 음악 연주','',''),('out_of_scope','제과점에서 빵을 만드는 제빵사','',''),('out_of_scope','해양 생물 관찰 연구','',''),('out_of_scope','건축물 내부 인테리어 디자인','',''),('out_of_scope','전문 운동선수 훈련','','')]
assert len(seeds)==50
out=Path(__file__).resolve().parent/'draft_200.csv'
with out.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['id','split','group_id','sentence','type','allowed_skills','excluded_skills','decision','course_relevance_json','evidence','review_status'])
 for index,(kind,subject,allowed,excluded) in enumerate(seeds):
  split='adjustment' if index%2==0 else 'holdout_candidate'
  if kind in ('ambiguous','out_of_scope'):
   texts=[f'{subject}에 관심이 있어요.',f'저는 {subject}을 생각하고 있습니다.',f'제 목표는 {subject}입니다.',f'{subject}에 대해 고민하고 있어요.']
  else:
   texts=[f'{subject} 분야에 관심이 있어요.',f'저는 {subject} 분야를 공부하고 싶습니다.',f'진로 목표는 {subject}입니다.',f'{subject} 관련 일을 하고 싶어요.']
  for j,text in enumerate(texts):
   w.writerow([f'N{index*4+j+1:03}',split,f'group-{index+1:02}',text,kind,allowed,excluded,'defer' if kind in ('ambiguous','out_of_scope') else 'recommend','', '자동 작성된 초안; 사람의 검토 필요','draft'])
print('200 draft examples; 100 adjustment and 100 holdout candidates, grouped by intent')
