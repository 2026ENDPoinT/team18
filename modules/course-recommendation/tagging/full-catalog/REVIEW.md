# 전 과목 태깅 검토 안내

원천 68행, 확인된 동일 과목 16그룹, 고유 프로필 52개. 후보 있음 43개 / 보류 9개 (각각 58행 / 10행).

초안은 제목과 일반적인 학문 의미를 바탕으로 Codex가 직접 작성했다. 외부 모델이나 학교 강의계획서는 사용하지 않았다. title_inferred는 사실 확인이 아닌 추정이다. 핵심/보조는 태그 관계이지 학습 비중이 아니다.

기존 임시 태그와 비교: 프로필 기준 추가 0개, 제거 32개, 공통 태그 핵심/보조 변경 1개. 상세는 tag_diff.csv. 기존 coverage 1.0/0.5를 비교용 핵심/보조로 해석했으며 기존 태그도 미검토다.

## 보류
- 컴퓨터공학개론 [csv-row-003], Introduction to Computer Engineering [csv-row-004]: 표준 사전에 개론을 표현할 역량이 없어 태깅 보류; 필요: 강의계획서, 강의 개요와 학습 목표
- 캡스톤디자인(1) [csv-row-024]: 캡스톤의 프로젝트 주제와 수행 활동은 제목으로 특정할 수 없음; 필요: 강의계획서, 강의 개요와 학습 목표
- 현장실습(1) [csv-row-029]: 현장실습의 기관·업무가 확인되지 않음; 필요: 강의계획서, 강의 개요와 학습 목표
- 코업(1) [csv-row-032]: 코업의 기관·직무와 학습 목표가 확인되지 않음; 필요: 강의계획서, 강의 개요와 학습 목표
- 코업프로젝트(1) [csv-row-033]: 코업 프로젝트의 주제·활동이 확인되지 않음; 필요: 강의계획서, 강의 개요와 학습 목표
- 캡스톤디자인(2) [csv-row-059]: 캡스톤의 프로젝트 주제와 수행 활동은 제목으로 특정할 수 없음; 필요: 강의계획서, 강의 개요와 학습 목표
- 현장실습(3) [csv-row-060]: 현장실습의 기관·업무가 확인되지 않음; 필요: 강의계획서, 강의 개요와 학습 목표
- 코업(2) [csv-row-063]: 코업의 기관·직무와 학습 목표가 확인되지 않음; 필요: 강의계획서, 강의 개요와 학습 목표
- 코업프로젝트(2) [csv-row-064]: 코업 프로젝트의 주제·활동이 확인되지 않음; 필요: 강의계획서, 강의 개요와 학습 목표

## 핵심·보조 태그 분포 (프로필 기준)
- core:ai: 1
- core:algorithms: 1
- core:automata: 1
- core:big_data_processing: 1
- core:blockchain: 1
- core:compiler: 1
- core:computer_architecture: 1
- core:computer_vision: 1
- core:cryptography: 1
- core:data_analysis: 1
- core:data_communication: 1
- core:data_mining: 1
- core:data_structures: 1
- core:databases: 1
- core:digital_logic: 1
- core:discrete_math: 1
- core:embedded: 1
- core:formal_languages: 1
- core:game_programming: 1
- core:graphics: 1
- core:iot: 1
- core:linear_algebra: 1
- core:machine_learning: 1
- core:mobile: 1
- core:natural_language: 1
- core:networks: 1
- core:object_oriented: 1
- core:open_source: 1
- core:operating_systems: 1
- core:programming: 2
- core:programming_language_theory: 1
- core:reinforcement_learning: 1
- core:security: 3
- core:software_engineering: 2
- core:statistics: 1
- core:systems_programming: 2
- core:unix: 1
- core:web_development: 2
- supporting:data_analysis: 1
- supporting:unix: 1

사전 확장 후보: {"컴퓨터공학 개론": 1, "데이터 모델링": 1}

## 검토 방법

review.csv에서 학습 내용과 대상·행동, 태그의 적절성, 누락과 보류 사유를 검토한다. 수정 태그와 메모 열은 검토 의견 수집용이며 JSON에 자동 반영되지 않는다. 검토자가 근거와 함께 profiles.json을 수정하고 reviewer·review_notes를 채운 뒤, 추론의 타당성을 검토했으면 inference_reviewed, 항목별 학교 원문과 출처를 확인했으면 source_verified로 바꾼다. 학교 자료가 없는 항목을 학교 확인으로 표시하지 않는다. 검토 후 export와 audit를 다시 실행한다. 실험 변환의 coverage는 별도 설정의 가정이다.

자동 검사는 ID, 그룹, 태그 및 학습 항목 연결, CSV 재읽기와 일부 근거 없는 기술명 패턴을 확인한다. 기술명 목록 검사는 완전하지 않으며 학교 자료를 대신하지 않는다.
