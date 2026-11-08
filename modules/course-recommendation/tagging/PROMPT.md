# 단일 구조화 분석 요청

과목명과 확인된 학교 원문(있으면), 표준 skill_id 사전을 입력받는다. 원문과 출처가 있으면 항목별로 `school_source`와 원문 출처를 기록하고, 제목에서만 추정한 항목은 `title_inference`와 제목 출처를 기록한다. 원래 제목과 행 ID는 그대로 둔다. 짧은 예상 학습 항목마다 `id`, `text`, `object`, `action`, `source_type`, `source`를 기록하고, 각 태그 후보는 사전에 있는 `skill_id`와 근거 항목 ID 배열을 연결한다. 불확실하거나 범위가 넓은 제목은 빈 목록과 보류 이유를 기록한다. 사전에 없는 개념은 `dictionary_candidates`에만 기록한다. 제목에서 특정 언어, SQL, 프레임워크, 선수조건, 강의 주차 또는 실제 강의 내용을 단정하지 않는다. confidence나 coverage를 추정하지 않는다. 모든 결과는 `unreviewed` 또는 `held`로 출력한다. `sample.json`의 구조를 따른다. 원문 자료를 얻었다고 주장하지 않는다.
