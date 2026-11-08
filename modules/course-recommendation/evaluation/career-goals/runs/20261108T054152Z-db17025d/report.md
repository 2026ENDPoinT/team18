# 후속 2×2 실험

실행 ID: 20261108T054152Z-db17025d  
생성 시각: 2026-11-08T05:41:52.078544+00:00  
코드 상태 SHA-256: 2378989b6553bdc16b317ed9e561ecdaa4c94433762388808cc4a2b71c18088b  
모델 / 토크나이저: 8eed52b853530f371bf8a9a97554ab74d024b9af407c60f9171585746c424bf4 / cd98e5698b201ba914efb8c18b6709fa8735ab71dcad8d2b431e52e8bf68d932  
설정: 5e06e39a968c4b689e51920e1ae3ec982ed30b028c40147c02a50c8db28a463e  
평가셋: 4e5265f94c601c21699b097dc70f5cd710a590599e2e64d8989054fdd0ebcee5  
묶음 해시 및 후보 해시: summary.json 참조

same v2 engine, model, vocabulary, role table, filters and thresholds; previous vs follow-up interpreter; baseline vs partial candidate replacement; existing shared-tag coverage retained; new tags experimental 0.5

검토 라벨이 없어 정확도·추천 적합도·제외 위반율은 계산 불가. 상태 건수는 품질 지표가 아니다.

## 상태 건수
- previous/existing: {'ok': 44, 'no_match': 56}; 사유: {'matched': 44, 'no_skill_candidates': 49, 'unresolved_exclusion': 5, 'no_linked_courses': 1, 'unresolved_choice': 1}
- previous/candidate: {'ok': 44, 'no_match': 56}; 사유: {'matched': 44, 'no_skill_candidates': 49, 'unresolved_exclusion': 5, 'no_linked_courses': 1, 'unresolved_choice': 1}
- improved/existing: {'ok': 48, 'no_match': 52}; 사유: {'matched': 48, 'no_skill_candidates': 49, 'no_linked_courses': 1, 'unresolved_choice_or_comparison': 1, 'parser_unresolved_exclusion': 1}
- improved/candidate: {'ok': 48, 'no_match': 52}; 사유: {'matched': 48, 'no_skill_candidates': 49, 'no_linked_courses': 1, 'unresolved_choice_or_comparison': 1, 'parser_unresolved_exclusion': 1}

태그 후보로 과목 목록이 달라진 입력 ID: {"previous": ["G039", "G040"], "improved": ["G039", "G040"]}

## 사례 (실행 결과 자동 생성)
- G018 / existing: ok (matched); web_development | programming | software_engineering; 웹프로그래밍 [csv-row-045] | 고급웹프로그래밍 [csv-row-057] | 프로그래밍입문(1) [csv-row-001] | 프로그래밍입문(2) [csv-row-036] | 객체지향프로그래밍언어 [csv-row-006]
- G018 / candidate: ok (matched); web_development | programming | software_engineering; 웹프로그래밍 [csv-row-045] | 고급웹프로그래밍 [csv-row-057] | 프로그래밍입문(1) [csv-row-001] | 프로그래밍입문(2) [csv-row-036] | 객체지향프로그래밍언어 [csv-row-006]
- G031 / existing: ok (matched); computer_vision | ai; 컴퓨터비전 [csv-row-021] | 인공지능개론 [csv-row-048] | 강화학습 [csv-row-026] | 자연어처리 [csv-row-030] | 기계학습 [csv-row-049]
- G031 / candidate: ok (matched); computer_vision | ai; 컴퓨터비전 [csv-row-021] | 인공지능개론 [csv-row-048] | 강화학습 [csv-row-026] | 자연어처리 [csv-row-030] | 기계학습 [csv-row-049]
- G036 / existing: ok (matched); computer_vision | ai; 컴퓨터비전 [csv-row-021] | 인공지능개론 [csv-row-048] | 강화학습 [csv-row-026] | 자연어처리 [csv-row-030] | 기계학습 [csv-row-049]
- G036 / candidate: ok (matched); computer_vision | ai; 컴퓨터비전 [csv-row-021] | 인공지능개론 [csv-row-048] | 강화학습 [csv-row-026] | 자연어처리 [csv-row-030] | 기계학습 [csv-row-049]
- G042 / existing: ok (matched); security | web_development; 정보보호론 [csv-row-023] | 컴퓨터보안 [csv-row-055] | 사이버보안 [csv-row-067] | 차세대암호알고리즘 [csv-row-035] | 웹프로그래밍 [csv-row-045]
- G042 / candidate: ok (matched); security | web_development; 정보보호론 [csv-row-023] | 컴퓨터보안 [csv-row-055] | 사이버보안 [csv-row-067] | 차세대암호알고리즘 [csv-row-035] | 웹프로그래밍 [csv-row-045]
- G077 / existing: ok (matched); data_analysis | game_programming; 데이터분석 [csv-row-019] | 게임프로그래밍 [csv-row-058] | 데이터마이닝 [csv-row-066] | 빅데이터처리 [csv-row-068]
- G077 / candidate: ok (matched); data_analysis | game_programming; 데이터분석 [csv-row-019] | 게임프로그래밍 [csv-row-058] | 데이터마이닝 [csv-row-066] | 빅데이터처리 [csv-row-068]
- G082 / existing: ok (matched); data_analysis; 데이터분석 [csv-row-019] | 데이터마이닝 [csv-row-066] | 빅데이터처리 [csv-row-068]
- G082 / candidate: ok (matched); data_analysis; 데이터분석 [csv-row-019] | 데이터마이닝 [csv-row-066] | 빅데이터처리 [csv-row-068]
- G083 / existing: ok (matched); databases | sql; 데이터베이스 [csv-row-042]
- G083 / candidate: ok (matched); databases | sql; 데이터베이스 [csv-row-042]
- G084 / existing: ok (matched); security; 정보보호론 [csv-row-023] | 컴퓨터보안 [csv-row-055] | 사이버보안 [csv-row-067] | 차세대암호알고리즘 [csv-row-035]
- G084 / candidate: ok (matched); security; 정보보호론 [csv-row-023] | 컴퓨터보안 [csv-row-055] | 사이버보안 [csv-row-067] | 차세대암호알고리즘 [csv-row-035]
- G086 / existing: ok (matched); databases | programming | networks | operating_systems | software_engineering; 프로그래밍입문(1) [csv-row-001] | 프로그래밍입문(2) [csv-row-036] | 데이터베이스 [csv-row-042] | 시스템프로그래밍 [csv-row-020] | 유닉스프로그래밍 [csv-row-047]
- G086 / candidate: ok (matched); databases | programming | networks | operating_systems | software_engineering; 프로그래밍입문(1) [csv-row-001] | 프로그래밍입문(2) [csv-row-036] | 데이터베이스 [csv-row-042] | 시스템프로그래밍 [csv-row-020] | 유닉스프로그래밍 [csv-row-047]
- G087 / existing: ok (matched); security | web_development; 정보보호론 [csv-row-023] | 컴퓨터보안 [csv-row-055] | 사이버보안 [csv-row-067] | 차세대암호알고리즘 [csv-row-035] | 웹프로그래밍 [csv-row-045]
- G087 / candidate: ok (matched); security | web_development; 정보보호론 [csv-row-023] | 컴퓨터보안 [csv-row-055] | 사이버보안 [csv-row-067] | 차세대암호알고리즘 [csv-row-035] | 웹프로그래밍 [csv-row-045]
- G090 / existing: ok (matched); databases; 데이터베이스 [csv-row-042]
- G090 / candidate: ok (matched); databases; 데이터베이스 [csv-row-042]

## 태그 차이
[{"course_id": "csv-row-021", "title": "컴퓨터비전", "before": [{"skill_id": "computer_vision", "coverage": 1.0}, {"skill_id": "ai", "coverage": 0.5}], "after": [{"skill_id": "computer_vision", "coverage": 1.0}]}]

G087에서 암호 역량은 제외되지만 보안 태그로 암호 과목이 추천될 수 있다. 공유 기초 과목까지 일괄 제거하지 않기 때문에 과목 수준 제외 정책과 검토된 근거가 필요하다.

제목 기반 수작업 샘플 두 과목만 교체했다. 기존 공통 태그 coverage는 유지하며 신규 태그가 있으면 0.5라는 실험 가정을 적용한다. 실제 학습 비중이나 강의계획서 검증이 아니다. 결과 차이와 적절성은 사람의 검토가 필요하다.
