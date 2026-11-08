# 서울과기대 목록 준비

원천 CSV는 `data/`에 있으며 설명과 실제 과목 ID는 없다. 68행의 `csv-row-NNN` 임시 ID와 16개 한영 그룹은 `data/seoultech_2026_catalog.json`에 보존한다. 해당 프로필의 태그는 제목 기반 미검토 가설이다. 전체 구조화 후보와 검토 자료는 `tagging/full-catalog/`에 있다.

`prepare.py`는 원천 해시와 행 수를 확인하고 재생성 가능한 시험 데이터를 `artifacts/seoultech-data/`에 만든다. `prepare_experimental.py`는 그 자료를 바탕으로 별도 실험 사전과 직무표를 만든다. 현재 FP32 실행 묶음은 `artifacts/model/`이며 운영 승인된 자료가 아니다. 현재 묶음으로 스모크 검사를 실행하려면 `python evaluation/seoultech-2026/run.py`를 사용한다.
