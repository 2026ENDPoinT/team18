# 강의 추천 모듈

고정된 과목 목록과 이수 선택, 진로 문장을 받아 관련 과목을 추천하는 독립 Python 모듈이다. small 인코더를 요청당 최대 한 번 실행한다. 별도 서버·UI는 없다. 과목 태그와 직무표는 미검토 실험 자료이며 운영 배포용으로 승인되지 않았다.

## 자료 위치

- `data/`의 서울과기대 과목 CSV는 사용자 제공 원천이다. `seoultech_2026_catalog.json`은 68개 임시 `csv-row` ID, 16개 확인된 한영 그룹과 기존 태그의 기준 매핑이다. `seoultech_2026_skills.json`은 41개 표준 역량 사전이다. 원천에 강의 개요와 실제 DB ID는 없다. 나머지 `data/` 파일은 가상 개발용 예제다.
- `tagging/full-catalog/`는 전체 52개 프로필의 제목 기반 후보 JSON, 사람 검토 CSV, 차이·무결성 자료와 [검토 안내](tagging/full-catalog/REVIEW.md)다. 확인된 강의자료가 아니며 모두 `unreviewed`다. `tagging/sample.json`은 아래 최신 비교 실행에 사용된 별도 두 과목 샘플이다.
- `artifacts/model/`은 현재 사용할 FP32 E5-small ONNX 모델·토크나이저·사전 벡터·44개 실험 역량·5개 직무·기존 과목 태그·설정·manifest의 일관된 단일 묶음이다. 모델 revision은 `614241f622f53c4eeff9890bdc4f31cfecc418b3`이다. `encoder.onnx`와 `tokenizer.json`은 인코더 구성이고 `lookup_vectors.npz`, 사전·직무·과목·설정 JSON과 `manifest.json`은 이 인코더와 함께 검증되는 실행 묶음이다. 소형 실험 묶음이지 운영 기본 승격이 아니다. `artifacts/seoultech-data/rows.json`은 원천 CSV의 행 ID 대응을 담은 실행용 파생 파일이다.
- `evaluation/career-goals/`의 100개 개발 입력과 200개 초안은 미검토 자료다. [최신 비교 실행](evaluation/career-goals/runs/20261108T054152Z-db17025d/report.md)은 기존/개선 해석과 기존/두 과목 후보 태그의 네 조합을 한 실행에 기록한다. 해당 실행은 전체 과목 후보에 대한 평가가 아니다. 실행 기록의 코드 해시는 폴더 경로 변경 이전의 코드 상태를 가리킨다.
- `course_recommendation/`, `scripts/`, `tests/`는 추천 로직과 준비·검증 코드다. `artifacts/`는 대용량 재생성물·환경·임시 출력을 담으며 Git에서 제외한다. 원천·후보·검토 자료는 제외하지 않는다.

## 실행 및 검증

저장소 루트에서 로컬 Python 3.12 환경이 준비된 경우:

```sh
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/seoultech-2026/run.py
modules/course-recommendation/artifacts/.venv/bin/python -m unittest discover -s modules/course-recommendation/tests -v
cd modules/course-recommendation
python3 tagging/full-catalog/manage.py audit
python3 tagging/full-catalog/manage.py export
python3 tagging/full-catalog/manage.py convert --experimental --output artifacts/full-catalog-candidate/course_profiles.json
```

변환 출력은 새로운 실험 파일이어야 하며 기존 파일을 덮어쓰지 않는다. [실험 coverage 설정](tagging/full-catalog/coverage_experiment.json)의 핵심 1.0 / 보조 0.5는 계산 가정이지 실제 학습 비중이 아니다. 출력 manifest에 설정과 후보 해시를 기록한다. 운영 자동 승격 경로는 없다. 검토 CSV의 수정·메모는 JSON에 자동 반영되지 않는다. 검토자가 항목 근거, 검토자·메모를 JSON에 반영하고 추론 검토와 학교 자료 확인 상태를 구분한다.

묶음을 재생성하려면 `pip install -r requirements-build.txt` 후 모듈 폴더에서 다음을 실행한다. 현재 실행 묶음의 인코더와 토크나이저를 사용하며 원천 행 매핑과 실험 데이터를 먼저 재생성한다. 출력은 기존 묶음과 다른 경로여야 한다.

```sh
python evaluation/seoultech-2026/prepare.py
python evaluation/seoultech-2026/prepare_experimental.py
python scripts/build_bundle.py --model artifacts/model --data artifacts/seoultech-data-experimental --output artifacts/rebuilt-bundle --version seoultech-rebuilt
```

모델이 없으면 `scripts/prepare_model.py --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3 --output <새 모델 경로>`로 고정 revision을 개발 환경에서 준비한다. 모델 다운로드는 실행 시 하지 않는다. 벡터는 같은 모델·토크나이저로 생성해야 한다. manifest 해시·사전 ID와 벡터 순서·목록과 동일 과목 그룹을 로드 시 검사한다. 필요 시 중간 모델과 재생성 데이터를 제거할 수 있다.

`evaluation/career-goals/run_followup.py`는 네 조합의 보고서·CSV·추적·요약을 한 실행으로 생성한다. `diagnose.py --weights '{"data_analysis":1,"statistics":1}'`는 목표 역량 직접 주입을 진단한다. 사람의 검토 라벨이 없으면 정확도·추천 적합도를 계산하지 않는다. 평가 입력과 라벨은 결과와 구분해 보존한다.

## 호출 계약과 제한

`load_bundle(path)`를 시작할 때 한 번 호출하고 `recommend_courses(snapshot, bundle, limit=5)`에 재사용한다. 스냅샷의 목록 ID·버전과 전체 과목 ID, 이수 선택, 선택 검토 상태가 묶음과 일치해야 한다. 동일 그룹의 어느 과목을 이수해도 그룹 전체를 제외한다. 적합한 결과가 없으면 `no_match`, 목록이나 모델 오류면 `unavailable`이며 256토큰 초과는 입력 오류다. 호출자가 목록과 이수 선택의 소유권·revision을 검증하고 스냅샷을 고정해야 한다. 반환 점수는 검증용이며 수강 가능성이나 역량 평가가 아니다.

## 2026-11-08 정리

원천 CSV, ID·그룹 기준, 41개 사전, 전체 구조화 후보와 검토 파일, 평가 입력, 테스트, 현재 FP32 묶음 및 같은 실행의 최신 네 조합 결과를 보존했다. 동일 FP32 모델 복제본, 미채택 INT8 묶음, 다운로드 캐시, 이전 실행·추적·벤치마크 결과와 재생성 가능한 데이터 복제본을 삭제했다. 최신 비교 재현에 필요한 두 과목 샘플과 이전 해석기는 평가 입력·비교 코드로 남겼다. 로컬 `.venv`는 현재 실행 및 모델 재생성 의존성이라 남겼다. 과거 검토 요청서는 별도 검토 문맥으로 남겼으며 그 수치는 현재 품질 평가가 아니다. 리뷰 라벨은 확인되지 않았다.
