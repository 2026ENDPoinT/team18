# 강의 추천 모듈 (개발 중)

`recommend_courses(input_snapshot, semantic_bundle, limit=5)`는 기존 서비스에 의존하지 않는 내부 진입점이다. 고정된 스냅샷을 받아 모델을 한 번 실행하고 역량별 가중합으로 현재 목록의 과목 ID를 반환한다. 별도 서버는 없다. 모델과 데이터가 아직 준비되지 않아 운영 배포가 가능한 완성본은 아니다.

- `course_recommendation/`: 공개 함수, 점수 계산, ONNX 인코더와 묶음 검사.
- `data/`: 저장소의 **가상 개발용** 목록을 이용한 샘플 계약, 역량·직무·과목 태그와 미검증 설정. 실제 교육과정이 아니다.
- `config/`: 설정 안내. 실제 설정은 묶음의 `config.json`에 포함한다.
- `scripts/`: 모델 변환, 묶음 및 벡터 생성, 단독 실행과 고정 벡터 데모.
- `tests/`: 모델 없이 실행하는 로직 테스트.
- `artifacts/`: 로컬에서 생성하는 모델·토크나이저·배포 묶음. 대용량 생성물이라 Git에서 제외한다. 운영에는 검토한 묶음을 배포 시스템으로 전달한다.

## 데이터 준비 및 검토

현재 사전은 실행 예제용 역량 6개, 직무 1개에 불과하다. 저장소의 목록 A 6개 과목 중 5개 이름만으로 추정한 태그는 전부 `unreviewed`이며, 내용이 불명확한 프로젝트 실습은 보류했다. 실제 강의 설명, 검토 근거, 직무 공개 자료 및 버전은 확보되지 않았다. 이 파일을 실제 추천에 사용하면 안 된다. 운영 전 실제 목록 전체와 원문을 확보하고 표준 사전 60~100개와 직무 8~12개를 검토해 작성한다. 설명에 근거한 태그는 `source_type: description` 및 각 태그의 근거를 기록하고, 이름 추론은 별도로 표시한다. 미검토 태그를 검토 완료로 표시하지 않는다. `course_ids`는 목록 전체이며 태깅 보류 과목은 `profiles`에서 생략한다. 목록의 버전과 ID는 서비스에서 고정한 값과 같아야 한다. 동일 과목의 언어별 행은 목록의 `equivalent_course_groups`에 ID 배열로 명시한다. 각 배열의 첫 ID가 선호 표시 대상이며, 같은 ID는 여러 그룹에 속할 수 없다. 그룹은 추천에서 한 번만 나오고 어느 구성원을 이수해도 전체가 제외된다. 이름만으로 같은 과목인지 자동 판정하지 않는다.

`config.json`의 임계값은 모두 예시이며 검증된 값이 아니다. 직무표와 0.6/0.4 혼합 비율도 초기 가설이다. 한국어 예시를 학습·점검으로 분리하고, 사람의 적합성 판단에 대해 역량 정밀도, 상위 5개 적합도, 과목명 검색 대비 및 모호·범위 밖 목표의 강제 추천률을 비교한 후 확정해야 한다. 복잡한 부정·상충 표현은 현재 규칙이 완전하지 않으므로 운영 전 추가 검증이 필요하다. 원본과 양자화 모델의 결과도 비교한다.

## 설치, 모델 및 묶음 준비

Python 환경에 `pip install -r modules/course-recommendation/requirements-build.txt`를 실행한다. 운영에는 `requirements.txt`만 필요하다. Python 및 플랫폼에 맞는 패키지 지원 여부를 먼저 확인한다. 모델 다운로드는 개발 환경에서만 수행한다. 다음의 `REVISION`에는 [모델 저장소](https://huggingface.co/intfloat/multilingual-e5-small)에서 확인한 **40자리 커밋 SHA**를 넣는다. 로컬 동작 확인에 사용한 revision은 `614241f622f53c4eeff9890bdc4f31cfecc418b3`이다.

```sh
python modules/course-recommendation/scripts/prepare_model.py --revision REVISION --output modules/course-recommendation/artifacts/model
python modules/course-recommendation/scripts/build_bundle.py --model modules/course-recommendation/artifacts/model --data modules/course-recommendation/data --output modules/course-recommendation/artifacts/bundle --version demo-v1
python modules/course-recommendation/scripts/run.py --bundle modules/course-recommendation/artifacts/bundle --input modules/course-recommendation/data/sample_input.json
```

양자화 후보는 다른 모델 디렉터리에 `prepare_model.py`의 `--int8`로 만들고, 그 모델로 묶음의 벡터를 다시 생성한다. 추론 및 인덱스에 동일한 모델과 토크나이저를 사용한다. 빌드 시 모델·토크나이저·데이터·벡터 해시, 모델 revision, ID 순서, 차원 및 전처리가 manifest에 기록되며 로드 시 검사한다. 앱 시작 시 다운로드하거나 변환하지 않는다. 파일 해시는 우발적 불일치 확인용이며 신뢰할 수 있는 배포 경로를 대체하지 않는다.

의존성이나 모델 없이 점수 계산 흐름만 보려면 다음을 실행한다. 고정 가짜 벡터를 쓰므로 의미 기반 품질 검증이 아니다.

```sh
python3 modules/course-recommendation/scripts/demo_fixture.py
python3 -m unittest discover -s modules/course-recommendation/tests -v
```

## 호출 계약과 연결

`load_bundle(path)`를 프로세스 시작 시 한 번 호출한다. 초기화가 실패하면 서비스에서 추천 상태를 `unavailable`로 저장해야 한다. 반환된 묶음을 재사용하며 세션의 추론은 잠금으로 직렬화된다. 동기 인코딩을 비동기 웹 이벤트 루프에서 직접 실행하지 않는다. 다중 worker의 모델 복제 여부를 배포에서 확인한다.

스냅샷에는 `career_goal`, 선택적인 `target_role`, `catalog_id`, `catalog_version`, 해당 목록 전체 `course_ids`, 이수 선택 true만 담은 `completed_course_ids`, `selection_review_status` (`confirmed`, `partial`, `unconfirmed`)가 필요하다. 목록 확인 정책·소유권·revision 검증과 스냅샷 고정은 호출자의 책임이다. ID와 목록 버전이 다르면 `unavailable`; 계산 성공 후 적합한 결과가 없으면 `no_match`; 결과가 있으면 `ok`다. 256토큰을 초과하면 `InputTooLong`을 발생시켜 입력 수정을 요청한다. 반환되는 `goal_skills`, `courses`의 score는 내부 검증용이며 추천 이유나 능력 평가가 아니다. 결과 이름은 고정된 DB 행에서만 조회한다.

이 저장소에는 로드맵 실행 API, 스냅샷과 `roadmap_runs` 저장 흐름이 아직 없다. 실제 과목 자료 검증 후 해당 흐름이 구현되면 인증·소유권·revision을 검증한 생성 서비스에서 같은 읽기 시점의 스냅샷을 만들고 이 함수를 호출해 결과를 저장해야 한다. 저장 시 입력 revision 변경을 다시 확인해야 한다. 현재 서비스 연결이나 결과 저장은 구현·검증되지 않았다. 문서 삭제 정책 및 전체 로드맵 실패 정책도 정해야 한다.

## 배포 평가

실제 목록 검토와 한국어 품질 평가 외에 목표 CPU/RAM에서 원본·양자화 모델별 로드 후 RSS, cold start, 첫 요청, warm p50/p95, 동시 대기 및 최대 RSS를 측정한다. 로컬 macOS ARM64/Python 3.12에서 FP32 변환과 실제 추론을 확인했다. 세 문장의 토큰 ID는 원본과 같았고 임베딩 코사인 유사도는 모두 0.999999 이상이었다. 샘플 추천은 가상 자료를 사용했으며, 부하·추천 품질은 측정하지 않았다. 별칭 규칙만으로 의미 추천을 대체하지 않는다. 모델 사용법은 [E5 모델 카드](https://huggingface.co/intfloat/multilingual-e5-small), ONNX 변환과 풀링에 관한 [Sentence Transformers 문서](https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html)를 참고한다.

## 2026-11-08 한국어 해석 실험

이전 `seoultech-test-v4` 묶음과 공개 함수의 기존 기본 동작을 유지한다. 별도로 만든 `seoultech-experimental-v1` 묶음에서만 `config.json`의 `interpretation_version: experimental-v2`가 적용된다. 이는 미검토 실험이며 운영 기본 설정으로 승인된 모델이 아니다. API는 여전히 `recommend_courses(snapshot, bundle)`이고, 개발·평가 전용 `course_recommendation.engine.recommend_with_trace`는 `(결과, 추적)`을 반환한다. 추적에는 원문 대신 정규화된 문장 기준 별칭 위치와 입력 ID, 후보, 가중치, 사유, 묶음 해시가 기록된다. 추적을 수집하는 곳에서는 입력 ID와 위치 데이터도 적절히 보호한다. 일반 운영 로그는 남기지 않는다.

다음 명령은 이미 위에서 설명한 모델 준비 후 저장소 루트에서 실행한다. 이 프로젝트에서는 테스트한 Python 3.12 가상환경을 `artifacts/.venv`에 만들었다. 단계별 세부 내용과 제약은 [실험 보고서](evaluation/career-goals/실험_결과_및_검토.md)를 참조한다.

```sh
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/seoultech-2026/prepare.py
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/seoultech-2026/prepare_experimental.py
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/scripts/build_bundle.py --model modules/course-recommendation/artifacts/model --data modules/course-recommendation/artifacts/seoultech-data-experimental --output modules/course-recommendation/artifacts/seoultech-bundle-experimental --version seoultech-experimental-v1
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/career-goals/compare_experimental.py
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/career-goals/diagnose.py --weights '{"data_analysis":1,"statistics":1}'
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/career-goals/evaluate.py --split adjustment
modules/course-recommendation/artifacts/.venv/bin/python -m unittest discover -s modules/course-recommendation/tests -v
```

`evaluate.py`는 기본적으로 조정용 후보만 실행하고 `review_status=reviewed` 라벨만 품질 지표에 포함한다. 초안 전체를 검증된 정답처럼 계산하지 않는다. 평가 입력과 ID 분할, 직무·완료 스냅샷이 원래 요구에 맞는지 사람이 검토해야 한다. `course_relevance_json`에는 `{"csv-row-001": 1}` 형식의 등급을 작성할 수 있다. 추적 결과는 입력 원문을 포함하지 않지만 위치와 식별자를 포함하므로 보관·공유 시 주의한다.

INT8 후보는 별도 `prepare_model.py --int8`로 만들고 그 최종 ONNX 인코더로 새 묶음을 생성한다. FP32 벡터를 INT8 query에 재사용하지 않는다. 로컬 벤치마크는 `evaluation/benchmarks/run.py --bundle <묶음 경로>`로 실행한다. 프로세스 생성부터 준비까지의 시간은 별도 자식 프로세스로 측정하며 다운로드는 포함하지 않는다. 목표 환경의 CPU·메모리 제한을 적용하지 않은 로컬 수치와 운영 환경 수치를 혼동하지 않는다.
