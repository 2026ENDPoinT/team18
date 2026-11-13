# 과목별 고정 추천 문구 전환 — 2026-11-14

추천 이유를 `catalog_courses.recommendation_reason TEXT`에 저장하고, API가 이 문자열을 그대로 반환하도록 변경했다. 추천 후보 계산, 순서, 이수·대체과목 제외, 강의 원문 근거 및 다른 AI 기능은 유지한다. 운영 Supabase는 과목 자료만 읽기 전용으로 대조했으며 이번 작업에서 운영 쓰기나 배포는 수행하지 않았다.

## 1. 대상과 데이터 확인

- 대상: 서울과학기술대학교 컴퓨터공학과 2026 교육과정 `seoultech-cse-2026-major-v1`.
- 운영 Supabase 조회 결과 **68개 행**. 저장소의 두 과목 fixture와 ID/이름/학수번호/권장 학년·학기 및 강의 개요 해시가 모두 일치했다. 사용자 테이블은 운영에서 조회하지 않았다.
- 작성 문구 **68개**, 빈 문구 **0개**, 서로 다른 문자열 **68개**. SQLite와 임시 PostgreSQL에 각각 68/68개 저장 및 원문 일치를 검증했다. 운영 문구 등록은 아래 배포 절차로 적용해야 한다.
- 기존 한·영 동일 과목 묶음은 유지한다. `course_groups.canonical_id()`가 정하는 한국어 대표 ID로 조회한다. 결과에 영문 ID만 있는 경우도 동일하다. 임의로 전달된 `member_course_ids`나 과목명으로 다른 문구를 빌리지 않는다.
- `강화학습`과 `Reinforcement Learning`의 등록 개요는 지능형 소프트웨어를 설명한다. 보상·정책 학습을 임의로 추가하지 않고 확보된 개요에 맞췄다. `코업프로젝트(1)/(2)`는 인턴 이수 인정용 과목이므로 별도 설계·구현 수업으로 묘사하지 않았다.

## 2. 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `apps/api/app/data/seoultech_cse_2026_recommendation_reasons.json` | catalog ID와 68개 course ID, 검수용 이름·학수번호, 개별 고정 문구 |
| `apps/api/migrations/013_course_recommendation_reasons.sql` | SQLite 컬럼 추가 및 기존 대상 행의 새 컬럼만 UPDATE |
| `supabase/migrations/20261113230604_course_recommendation_reasons.sql` | CLI가 생성한 PostgreSQL 마이그레이션. 컬럼 추가, 68개 행 및 ID·이름·학수번호 검증, 문구 UPDATE |
| `apps/api/app/scripts/seed_course_reasons.py` | 명시적 seed 적용·검증, 두 SQL 파일 재현용 renderer. 시작 시 호출되지 않음 |
| `supabase/checks/course_recommendation_reasons.sql` | 운영 적용 후 읽기 전용 확인 쿼리 |
| `apps/api/app/repositories/courses.py` | catalog ID와 course ID 목록으로 표시 문구 일괄 조회 |
| `apps/api/app/services/course_reasons.py` | Gemini 프롬프트·생성·검증 제거, DB 응답 투영 및 메타데이터. 다른 AI가 사용하는 `experience_input` 보존 |
| `apps/api/app/services/roadmap_batch.py` | 추천 이유 AI guard/cache 호출을 DB 조회로 대체, 새 결과에 고정 문구 저장 |
| `apps/api/app/repositories/roadmaps.py` | 기존 이력 조회 시 표시 필드만 DB 문구로 대체 |
| `apps/api/app/api/routes/recommendations.py` | 기존 추천 계산 후 DB 문구 적용 |
| `apps/api/app/api/routes/roadmaps.py` | 기존 course-reasons 응답 구조를 유지하며 DB 출처 반환 |
| `apps/web/src/features/roadmap/resultPresentation.mjs`, `useCourseReasons.js` | 고정 문구 우선 표시. DB에 문구가 없다고 명시된 경우 옛 AI 문구 재사용 방지 |
| `apps/api/tests/unit/test_course_reasons.py`, `test_roadmap_batch_partial.py` | 제거된 AI 문구 규약 대신 고정 문구·안전한 대체 안내 검증 |
| `apps/api/tests/integration/test_course_reason_data.py`, `fixed_course_reasons_scenario.py` | 데이터·마이그레이션·API·이력·캐시·완료 기록·AI 무호출 검증 |
| `apps/api/tests/integration/test_course_reasons_api.py`, `course_reasons_scenario.py`, `catalog_ranking_scenario.py`, `roadmap_batch_scenario.py`, `roadmap_batch_postgres_scenario.py` | 새 계약과 기존 순위/다른 AI 회귀 검증. 기존 `personalized_course_reasons_scenario.py`는 고정 문구 시나리오로 교체 |
| `apps/api/tests/integration/roadmap_results_ui_server.py`, `apps/web/tests/e2e/course-reasons.mjs`, `roadmap-results.mjs`, `apps/web/tests/unit/course-reasons.test.mjs` | 실제 Next UI, 실제 API와 SQLite 및 합성 응답 기반 화면 검증 |

기존 작업 폴더에 있던 문서 업로드·결과 목록 페이지 나누기·스타일 변경은 이 작업의 수정 목록에서 제외했다. `services/course_recommendations.py`의 순위 알고리즘과 `course_groups.py`의 묶음 규칙은 수정하지 않았다.

## 3. 데이터 흐름과 캐시

```text
독립 수강 추천 API
  기존 추천 계산/기존 순서/이수·대체과목 제외
    → CourseRepository.recommendation_reasons(catalog_id, 대표 course IDs)
      → recommendation_reason / reason / personalization_reason 동일 문자열 반환

새 전체 로드맵
  기존 병렬 계산 → DB 문구 조회 → 새 결과 저장 → run_payload의 표시 투영

저장된 로드맵 / 이전 결과 / course-reasons
  권한·상태·문서 근거 제한 확인 → 저장된 후보 및 기존 묶음 규칙 적용
    → 저장된 run.catalog_id로 DB 조회 → 표시 문구와 메타데이터만 대체
      → React의 기존 추천 이유 위치에 표시
```

조회는 현재 사용자 프로필의 catalog ID가 아닌 **해당 결과에 연결된 catalog ID**를 쓴다. `result_json`, `basis_json`, 기존 `ai_requests`, 완료 기록은 조회 때문에 수정되지 않는다. 새 고정 문구는 `description_text`, `course_evidence`, `keyword_evidence`, 페이지 및 근거 필드와 별개이며 그 필드들은 보존된다.

등록 문구는 공백까지 그대로 반환한다. NULL·빈 문자열·미등록 catalog/course ID에는 `추천 근거 확인 필요`를 반환한다. 대표 행이 누락되었다고 영문 행이나 이름이 같은 다른 교육과정의 문구로 대체하지 않는다.

버전은 `catalog-fixed-reasons-v1`. 출처는 전체 등록 시 `catalog_fixed`, 혼합이면 `catalog_fixed_with_fallback`, 모두 미등록이면 `safe_fallback`; provider는 `database` 또는 안전 안내만 있는 경우 `server`다. course-reasons의 `reasons[].course_id`, `personalization_reason`, `evidence_ids` 형식은 유지한다. `evidence_ids=[]`는 고정 편집 문구가 생성된 근거 ID를 인용하지 않는다는 뜻이다.

추천 이유 생성용 Gemini 호출, 프롬프트, `guarded_call(operation='course_reasons')` 및 해당 AI 캐시 조회를 제거했다. 과거 캐시는 삭제하지 않고 사용 경로를 끊었다. 새 문구는 순위·로드맵의 basis 해시에 포함하지 않는다. 문구만 수정했을 때 기존 로드맵을 재사용하고 `is_stale=false`가 유지되는 테스트가 있다. 직무 분석, 프로젝트 분석, 역량 비교, 활동 추천 설명 및 개인화 로드맵 생성 모듈은 변경하지 않았다.

## 4. API 응답 예시

다음은 표시 관련 필드만 발췌한 예시다. 실제 course ID는 그대로다.

변경 전에는 저장된 AI 문구 또는 강의 내용에서 추출한 문장이 표시될 수 있었다.

```json
{
  "course_id": "stcse-2026-ac66832f2c533c700dde1354",
  "reason": "관련성을 추가로 확인할 교육과정 내용: ...",
  "personalization_reason": "학생 목표와 경험에 연결한 AI 생성 문구"
}
```

변경 후 독립 추천과 저장 결과의 과목 항목:

```json
{
  "course_id": "stcse-2026-ac66832f2c533c700dde1354",
  "recommendation_reason": "본 강좌에서는 데이터를 체계적으로 구성하고 여러 응용에서 공유하기 위한 데이터베이스의 기본 개념을 소개하고, 중복을 줄이는 데이터 구성과 효율적인 운영 및 관리 방법을 학습한다.",
  "reason": "본 강좌에서는 데이터를 체계적으로 구성하고 여러 응용에서 공유하기 위한 데이터베이스의 기본 개념을 소개하고, 중복을 줄이는 데이터 구성과 효율적인 운영 및 관리 방법을 학습한다.",
  "personalization_reason": "본 강좌에서는 데이터를 체계적으로 구성하고 여러 응용에서 공유하기 위한 데이터베이스의 기본 개념을 소개하고, 중복을 줄이는 데이터 구성과 효율적인 운영 및 관리 방법을 학습한다.",
  "reason_source": "catalog_fixed",
  "reason_provider": "database",
  "reason_version": "catalog-fixed-reasons-v1"
}
```

course-reasons 응답:

```json
{
  "run_id": "기존-run-id",
  "reasons": [{
    "course_id": "stcse-2026-ac66832f2c533c700dde1354",
    "personalization_reason": "본 강좌에서는 데이터를 체계적으로 구성하고 여러 응용에서 공유하기 위한 데이터베이스의 기본 개념을 소개하고, 중복을 줄이는 데이터 구성과 효율적인 운영 및 관리 방법을 학습한다.",
    "evidence_ids": []
  }],
  "source": "catalog_fixed",
  "provider": "database",
  "reason_version": "catalog-fixed-reasons-v1"
}
```

## 5. 운영 적용 순서

1. 대상 DB와 기존 migration 이력을 읽기 전용으로 확인한다. 아래 SQL을 적용할 대상은 위 catalog의 68개 행이 있는 기존 DB다. 새 스키마만 있는 DB는 migration이 컬럼을 만들고 종료하므로, 교육과정 import 후 명시적 seed를 실행해야 한다.
2. 기존 선행 migration이 이미 적용된 상태에서 **`20261113230604_course_recommendation_reasons.sql` 하나를 추가 적용**한다. 컬럼 추가와 문구 UPDATE가 같은 migration 트랜잭션에서 수행되도록 한다. 대상이 일부만 있거나 ID/이름/학수번호가 다르면 PostgreSQL은 예외로 중단한다.
3. `supabase/checks/course_recommendation_reasons.sql`의 결과가 **68 / 68 / 0**, 누락 목록 0행인지 확인한다. `seed_course_reasons.py --check`로 원문까지 정확히 검증할 수도 있다.
4. 백엔드를 배포한 뒤 프론트엔드를 배포한다. DB 컬럼보다 먼저 새 백엔드를 배포하면 조회가 실패하므로 이 순서를 지킨다.
5. 새 추천, 기존 저장 결과 GET, course-reasons POST에서 문구와 `source/provider/version`을 확인한다. 결과 조회나 탭 재진입으로 추천 이유 AI 요청이 생기지 않는지 확인한다.

설치된 Supabase CLI 3.0.0의 `--help`로 확인한 명령 예시다. CLI v3는 원격 대상을 명시해야 한다. [공식 v3 변경 안내](https://supabase.com/changelog/supabase-cli-v3), [마이그레이션 안내](https://supabase.com/docs/guides/deployment/database-migrations)를 참고한다.

```sh
supabase migration list --remote=htuttclopxaiyhgcakkj
supabase db push --remote=htuttclopxaiyhgcakkj --skip-vault --dry-run
# dry-run에서 이번 파일만 추가 적용됨을 확인한 후 실행
supabase db push --remote=htuttclopxaiyhgcakkj --skip-vault
```

dry-run에 다른 미적용 이력이 나오거나 이력이 맞지 않으면 원인을 확인한다. 이 작업을 적용하기 위해 운영 `reset`, `repair`, 기존 이력 수정, `--include-all`, 전체 seed 재적재를 실행하지 않는다. CLI로 관리 중인 운영 DB에는 검토된 migration 경로로 적용한다. 수동 SQL 관리 환경에서 파일을 실행한다면 운영자가 기존 배포 절차에 따라 단일 트랜잭션으로 실행하고 이력 정책을 확인해야 한다.

SQLite는 기존 `repositories.plans.migrate()`가 013 파일을 한 번 적용한다. 같은 migrate 명령을 반복해도 `schema_migrations` 때문에 ALTER가 다시 실행되지 않는다. 원시 SQLite ALTER 파일을 임의로 두 번 실행하는 방식은 사용하지 않는다. 데이터만 다시 적용할 필요가 있을 때는 아래 명시적 seed가 중복 없이 UPDATE한다.

```sh
# 환경변수는 적용할 DB에 맞게 운영 절차로 설정한다. 비밀값을 코드나 문서에 넣지 않는다.
python apps/api/app/scripts/seed_course_reasons.py --check
python apps/api/app/scripts/seed_course_reasons.py --apply
python apps/api/app/scripts/seed_course_reasons.py --check
```

위 seed는 먼저 전체 68개 ID·이름·학수번호가 맞는지 검사하고 새 컬럼만 수정한다. 가상 개발 과목은 대상이 아니므로 기존 `seed_dev.py`는 변경하지 않았다. 서버 시작 시 문구를 생성하거나 매번 UPDATE하는 동작도 추가하지 않았다. 향후 문구 수정은 새 데이터 버전과 새 migration으로 관리하고 적용된 과거 migration 파일은 수정하지 않는다. 롤백이 필요하면 앱 버전을 먼저 복구하고 추가 컬럼과 데이터는 보존한다.

## 6. 검증 결과

- 운영 확인: 과목 reference 68개를 읽기 전용 대조. 운영 사용자 데이터·키·유료 Gemini API는 테스트에 사용하지 않음. 운영 적용 및 배포는 미실행.
- 전체 Python 회귀: **691 passed, 64 skipped, 1 failed**, 추가 subtest 30개 통과. 실패는 기존 `tests/unit/test_dacon.py::test_manual_workflow_uses_shared_docker_entrypoint`가 저장소에 없는 `.github/workflows/collect-activities.yml`을 요구하기 때문이며 HEAD에도 해당 파일이 없다. 이번 범위 밖의 수집 workflow는 추가하지 않았다. skipped는 외부 서비스/별도 환경을 요구하는 기존 조건부 검사이며 성공으로 계산하지 않았다.
- SQLite/PostgreSQL 데이터 검사: **4 passed**. 68개 ID 매핑, 정확한 원문 동등성, 반복 적용, 다른 컬럼 보존, catalog 불일치 시 중단, 기존 PostgreSQL 순위 조회 검증.
- PostgreSQL API: 임시 PostgreSQL 17 + TLS 컨테이너에서 전체 Supabase migration과 기존 로드맵/활동 시나리오 및 새 고정 문구 API 시나리오 통과. pytest wrapper **1 passed**이며 내부 unittest를 실제 실행한다.
- 프론트엔드 단위 검사: **56 passed**. 합성 환경변수와 격리된 소스 복사본에서 Next.js 프로덕션 빌드 성공(9개 정적 페이지 생성).
- 브라우저: 실제 Next UI에서 고정 문구가 옛 AI 필드보다 우선함, 안전 안내, 과거 결과, 완료 과목 숨김, 새로고침, 탭 반복, 원문 근거 펼침, 데스크톱/모바일 가로 넘침 없음 확인. 해당 화면 동작에서 course-reasons 및 AI 요청 없음.
- 실제 HTTP + SQLite + Next 통합: 새 생성, 기존 이력 조회, 과거 완료 기록 보존, 누락 분석/활동 오류 처리, 새로고침과 탭, 모바일 검증 통과. 금지한 Gemini 진입점 호출 횟수 **0**.
- 추천 회귀: 기존 31개 목표 표현을 포함한 catalog/ranking/equivalence 시나리오를 유지하며 모든 표시 문구가 DB 원문과 같음을 추가 검증했다. 같은 이름의 다른 catalog, 미등록 ID, 임의 member ID, 영문 대표 후보, NULL/빈 문구, 남아 있는 AI 캐시 및 과거 JSON을 별도로 검사했다.
- 테스트는 임시 저장소와 합성 사용자·문서 및 mocked AI를 사용했다. 문서/분석 제한 및 소유권 확인은 그대로 유지했다.

재현 명령(환경에 맞는 Python과 테스트 전용 URL 지정):

```sh
(cd apps/api && PYTHON_DOTENV_DISABLED=1 GEMINI_API_KEY='' GOOGLE_API_KEY='' python -m pytest -q)
node --experimental-vm-modules --test apps/web/tests/unit/*.test.mjs
# COURSE_TEST_DATABASE_URL: localhost의 /team18_course_test 전용
python -m pytest -q apps/api/tests/integration/test_course_reason_data.py apps/api/tests/integration/test_course_ranking_postgres.py
# ROADMAP_TEST_POSTGRES_URL: localhost의 /team18_document_test 전용, ROADMAP_ALLOW_TEST_DB_RESET=1 필요
# 위 이름의 폐기 가능한 테스트 DB에서만 실행. 운영 URL 사용 금지.
(cd apps/api && python -m pytest -q tests/integration/test_roadmap_batch_postgres.py)
```

## 7. 전체 고정 문구

아래 68개 행은 버전 관리 JSON과 동일한 문자열이다. 모든 행의 catalog ID는 `seoultech-cse-2026-major-v1`이다. 한·영 묶음 과목도 DB 행은 각각 유지하며 실제 표시에는 한국어 대표 행을 쓴다.

| 과목명 | course_id | 학수번호 | recommendation_reason |
|---|---|---|---|
| Data Structure | stcse-2026-104870f5ca28eed690bf2b2c | 109831 | 본 강좌에서는 자료구조와 알고리즘 분석의 기본 개념을 소개하고, 데이터의 저장과 빠른 갱신 및 조회를 위한 구조와 처리 방법을 학습한다. |
| Database | stcse-2026-56e5e2a1aedbfd4d2e87404c | 109834 | 본 강좌에서는 데이터의 불필요한 중복을 줄이고 여러 응용에서 공유할 수 있는 데이터베이스의 구성 원리를 소개하며, 효율적인 운영 방법과 데이터베이스 관리 시스템을 학습한다. |
| Digital Logic and Systems | stcse-2026-f91a4d5f545eb2689570039a | 109843 | 본 강좌에서는 디지털 시스템의 논리 설계에 필요한 기본 이론을 소개하고, 계산과 데이터 처리에 사용되는 논리 회로의 설계 원리를 학습한다. |
| Formal Language and Automata Theory | stcse-2026-be2a757b0389cbe8547079bf | 109838 | 본 강좌에서는 정규문법과 문맥자유문법을 비롯한 형식언어의 체계를 소개하고, 유한 오토마타와 튜링 기계 등 계산 모형 및 문법과 계산 복잡도의 관계를 학습한다. |
| Introduction to Computer Engineering | stcse-2026-754b943b19ec581ef0d0435c | 109815 | 본 강좌에서는 정보기술과 컴퓨터공학의 기본 개념을 소개하고, 컴퓨터 구조와 주변장치, 소프트웨어, 하드웨어, 네트워크 및 보안의 기초를 학습한다. |
| Introduction to Programming 1 | stcse-2026-fe99517e2472f51c862aaa83 | 109416 | 본 강좌에서는 프로그래밍과 C 언어의 기초를 소개하고, 절차적 프로그래밍을 바탕으로 문제의 해결 과정을 표현하고 구현하는 방법을 학습한다. |
| Introduction to Programming 2 | stcse-2026-88d0f3dc417dbe933f136a32 | 109417 | 본 강좌에서는 C++ 언어의 기본 문법과 객체지향 프로그래밍의 요소를 소개하고, 캡슐화와 상속 및 다형성을 활용하는 방법을 학습한다. |
| Linear Algebra | stcse-2026-a98c7b9423b33b3f650290fd | 109829 | 본 강좌에서는 공학에서 사용하는 벡터와 행렬 및 다차원 공간의 수학적 이론을 소개하고, 이를 바탕으로 복잡한 시스템을 설계하고 분석하는 원리를 학습한다. |
| Machine Learning | stcse-2026-f5bc8d16a7f2317e1ba1527b | 109509 | 본 강좌에서는 데이터로부터 예측 모형을 학습하는 기계학습 알고리즘을 소개하고, 회귀와 분류 및 심층 신경망을 이용한 이미지와 시계열 데이터 처리 방법을 학습한다. |
| Object Oriented Programming Language | stcse-2026-b579434322f827bb66cda07e | 109817 | 본 강좌에서는 자바 언어의 문법과 객체지향 개념을 소개하고, 그래픽 사용자 인터페이스와 다중 스레드 및 네트워크 기능을 활용한 응용프로그램 작성 방법을 학습한다. |
| Open Source Software | stcse-2026-4d9f7a444f10e18d93e335aa | 109833 | 본 강좌에서는 오픈소스 프로젝트의 개발 참여와 공개 및 관리 방식을 소개하고, 관련 도구와 수치 프로그래밍을 통해 오픈소스 소프트웨어의 개발 과정을 학습한다. |
| Probability and Random Variables | stcse-2026-dc20b8bf14ae041933c8be7b | 109830 | 본 강좌에서는 확률변수와 확률 과정의 기본 개념을 소개하고, 모멘트와 가우스 과정 및 푸아송 과정의 특성과 선형 시스템 해석에 활용하는 방법을 학습한다. |
| Programming Language Theory | stcse-2026-da40ea10da7e10eb80353a02 | 109836 | 본 강좌에서는 프로그래밍 언어의 주요 구성 요소와 설계 개념을 소개하고, 다양한 언어의 특성을 비교하고 평가하는 방법을 학습한다. |
| Reinforcement Learning | stcse-2026-6ca7d9e1c99caaff4c4c4972 | 109510 | 본 강좌에서는 데이터로부터 상황을 인지하고 학습하며 추론하는 지능형 소프트웨어를 소개하고, 이를 구현하는 데 활용되는 인공지능과 분산처리 등 관련 기술의 개념과 방법을 학습한다. |
| Software Engineering | stcse-2026-9788e8552c077d7a145ee121 | 109835 | 본 강좌에서는 효율적인 소프트웨어 시스템 개발을 위한 소프트웨어공학의 개념을 소개하고, 소프트웨어 프로세스와 애자일 방식 및 명세 작성부터 시스템 개선까지의 개발 활동을 학습한다. |
| Unix System | stcse-2026-2833fdb8a1ebba3eab96ee62 | 109819 | 본 강좌에서는 유닉스 운영체제의 기본 구성과 명령어를 소개하고, 계층적 파일 구조와 셸 프로그래밍 및 사용자와 시스템의 관리 방법을 학습한다. |
| 강화학습 | stcse-2026-7e87cf985c3d2799c69b7e10 | 109845 | 본 강좌에서는 다양한 데이터의 인지와 학습 및 추론을 통해 정보를 얻는 지능형 소프트웨어의 개념을 소개하고, 인공지능과 분산처리 등 이를 실현하는 소프트웨어 기술을 학습한다. |
| 객체지향프로그래밍언어 | stcse-2026-46e14bb5a291da1228563e90 | 109816 | 본 강좌에서는 자바를 활용한 객체지향 프로그래밍의 개념을 소개하고, 그래픽 사용자 인터페이스와 다중 스레드 및 네트워크 기능을 포함한 응용프로그램 개발 방법을 학습한다. |
| 게임프로그래밍 | stcse-2026-ca8439d01ecaf7d52fc71ab8 | 109504 | 본 강좌에서는 게임 디자인과 기획 및 개발 과정의 기본 개념을 소개하고, 게임 엔진을 활용한 콘텐츠 구성과 스크립팅 및 사용자 인터페이스 구현 방법을 학습한다. |
| 고급소프트웨어공학 | stcse-2026-63c4005c7ca97e9df70781e4 | 109506 | 본 강좌에서는 소프트웨어 개발을 지원하는 도구의 설계와 개발 원리를 심화하여 학습하고, 이러한 도구를 소프트웨어 개발 과정에 적용하는 방법을 다룬다. |
| 고급웹프로그래밍 | stcse-2026-09e8a685af936cdae6a62808 | 109481 | 본 강좌에서는 동적인 웹 환경의 설계와 개발에 필요한 프로그래밍 기법을 소개하고, 클라이언트와 서버 측의 처리 및 모바일 웹 구현에 활용되는 방법을 학습한다. |
| 기계학습 | stcse-2026-14b7c8e1ca22230501a521cf | 109078 | 본 강좌에서는 데이터에 기반한 예측 모형과 기계학습 알고리즘의 개념을 소개하고, 지도학습의 회귀와 분류 및 신경망을 활용한 이미지와 시계열 데이터 처리 방법을 학습한다. |
| 데이터마이닝 | stcse-2026-35d7bec97616b2d91eb5aaf0 | 109507 | 본 강좌에서는 데이터에서 유용한 패턴을 찾는 데이터마이닝의 기본 개념을 소개하고, 분류와 군집화, 차원 축소 및 이상치 탐지 기법과 적용 방법을 학습한다. |
| 데이터베이스 | stcse-2026-ac66832f2c533c700dde1354 | 109341 | 본 강좌에서는 데이터를 체계적으로 구성하고 여러 응용에서 공유하기 위한 데이터베이스의 기본 개념을 소개하고, 중복을 줄이는 데이터 구성과 효율적인 운영 및 관리 방법을 학습한다. |
| 데이터분석 | stcse-2026-25258933948dfe017f5d0566 | 109076 | 본 강좌에서는 데이터과학을 위한 데이터분석의 개념을 소개하고, 데이터분석에 적용할 수 있는 알고리즘과 방법론 및 모형을 학습한다. |
| 데이터통신 | stcse-2026-699927f1b2ea20409790730a | 109360 | 본 강좌에서는 원격으로 정보를 교환하는 데이터통신의 기본 원리와 표준 모델을 소개하고, 물리계층과 데이터링크 계층의 동작 및 유무선 통신 시스템의 기초를 학습한다. |
| 디지털논리및시스템 | stcse-2026-ea5538d5f483450918b884f9 | 109842 | 본 강좌에서는 디지털 컴퓨터와 디지털 기기의 기초가 되는 논리 설계 개념을 소개하고, 디지털 소자의 동작 원리와 논리 게이트의 활용 방법을 학습한다. |
| 모바일프로그래밍 | stcse-2026-811eb258200dc12bf1e75add | 109038 | 본 강좌에서는 모바일 환경의 메모리와 처리 성능 및 프로그램 인터페이스의 특성을 소개하고, 이러한 환경에서 동작하는 모바일 프로그램의 구성과 개발 방법을 학습한다. |
| 블록체인 | stcse-2026-a28f2996733ccdb826e16e4b | 109086 | 본 강좌에서는 블록체인의 기반이 되는 암호 기술과 분산 장부의 개념을 소개하고, 합의 알고리즘과 분산 네트워크 및 디지털 암호화폐의 동작 원리와 응용을 학습한다. |
| 빅데이터처리 | stcse-2026-007079f732bd4e519b888581 | 109840 | 본 강좌에서는 대규모 데이터에서 의미를 추출하기 위한 처리와 분석의 개념을 소개하고, 분산 데이터 처리 및 기계학습 알고리즘을 활용한 분석 방법을 학습한다. |
| 사물인터넷 | stcse-2026-fb8c7673de0606e23c5ef679 | 109505 | 본 강좌에서는 사물인터넷 시스템에 사용되는 무선통신 기술의 개념과 특성을 소개하고, 다양한 통신 기술을 사물인터넷 환경에 적용하는 방법을 학습한다. |
| 사이버보안 | stcse-2026-9e3185d350ffb5e1409461d8 | 109512 | 본 강좌에서는 사이버공간의 보안 위협과 대응 체계를 소개하고, 암호학과 네트워크 및 운영체제 보안의 기초와 인공지능·공급망·클라우드 보안의 주요 개념을 학습한다. |
| 선형대수학 | stcse-2026-7275dc0a727f55aa354afb0c | 109073 | 본 강좌에서는 벡터와 행렬 및 다차원 공간의 수학적 개념을 소개하고, 컴퓨터공학에서 다루는 시스템을 표현하고 분석하는 데 필요한 선형대수의 원리를 학습한다. |
| 소프트웨어공학 | stcse-2026-73b45f859b8e6a6c0773c397 | 109130 | 본 강좌에서는 소프트웨어의 효율적인 개발과 개선을 위한 공학적 접근을 소개하고, 개발 프로세스와 애자일 방식 및 소프트웨어 명세부터 시스템 발전까지의 과정을 학습한다. |
| 시스템프로그래밍 | stcse-2026-e7d7ea1f3fd682a4ed273e96 | 109077 | 본 강좌에서는 소프트웨어가 컴퓨터 시스템에서 동작하는 원리와 데이터 표현 방법을 소개하고, 프로세서의 동작과 어셈블리 프로그래밍의 기초를 학습한다. |
| 알고리즘 | stcse-2026-93a891ff706ed4a28b5d3350 | 109180 | 본 강좌에서는 다양한 문제 해결에 사용되는 알고리즘의 기능과 처리 과정을 소개하고, 알고리즘의 복잡도를 분석하여 효율적인 해결 방법을 설계하는 기법을 학습한다. |
| 오픈소스소프트웨어 | stcse-2026-85cfe65884f69e499cf31d05 | 109075 | 본 강좌에서는 오픈소스 소프트웨어의 개발 방식과 프로젝트 공개 및 관리 과정을 소개하고, 개발에 필요한 도구와 수치 프로그래밍의 활용 방법을 학습한다. |
| 운영체제 | stcse-2026-1a8398f8e4420e8c3c79a958 | 109200 | 본 강좌에서는 컴퓨터 하드웨어와 자원을 관리하는 운영체제의 기본 개념을 소개하고, 프로세스와 처리장치, 메모리 및 저장장치의 관리 원리를 학습한다. |
| 웹프로그래밍 | stcse-2026-8a60e5062fa47ed86365d396 | 109261 | 본 강좌에서는 웹에서 정보를 구성하고 표현하는 프로그래밍의 기본 개념을 소개하고, 웹 문서의 구조와 스타일 및 동작을 구현하여 웹사이트를 만드는 방법을 학습한다. |
| 유닉스시스템 | stcse-2026-4bbca78a9437bde5b42ee872 | 109818 | 본 강좌에서는 다중 사용자와 다중 작업을 지원하는 유닉스 운영체제의 특성을 소개하고, 파일 시스템과 명령어 및 셸을 활용한 시스템 사용과 관리 방법을 학습한다. |
| 유닉스프로그래밍 | stcse-2026-46904f11df0388aba7c0854a | 109482 | 본 강좌에서는 유닉스 환경의 시스템 호출과 라이브러리를 활용하는 프로그래밍 기법을 소개하고, 파일 시스템과 프로세스, 프로세스 간 통신 및 시그널의 처리 방법을 학습한다. |
| 이산수학 | stcse-2026-34248fd9b3ef9e2615c83b6e | 109255 | 본 강좌에서는 컴퓨터의 수학적 구조를 이해하기 위한 이산수학의 기본 개념을 소개하고, 논리와 집합, 관계, 그래프 및 트리 등의 이론을 학습한다. |
| 인공지능개론 | stcse-2026-c6787119c1c6ad2c44038386 | 109844 | 본 강좌에서는 인공지능과 인공신경망의 기초 이론을 소개하고, 다양한 신경망 구조와 학습 방법 및 패턴 인식과 컴퓨터비전 등에 적용하는 원리를 학습한다. |
| 임베디드소프트웨어 | stcse-2026-0dd581a6be9e12008c70f9ba | 109484 | 본 강좌에서는 임베디드 시스템과 운영체제의 기본 개념을 소개하고, 리눅스 환경에서 임베디드 소프트웨어를 개발하고 운영하는 방법을 학습한다. |
| 자료구조 | stcse-2026-c80f43e507d33cfbb13fbda1 | 109220 | 본 강좌에서는 데이터를 효율적으로 저장하고 처리하기 위한 자료구조의 기본 개념을 소개하고, 다양한 자료구조의 표현 방식과 이를 조작하는 알고리즘을 학습한다. |
| 자연어처리 | stcse-2026-5c72f35075debf5b8946dad9 | 109083 | 본 강좌에서는 인간의 언어를 컴퓨터로 처리하는 자연어처리의 기본 개념을 소개하고, 형태소 분석과 품사 부착 및 구문 분석 등 언어 구조를 분석하는 방법을 학습한다. |
| 정보보호론 | stcse-2026-179217ec84465a70097a0ccc | 109820 | 본 강좌에서는 정보의 훼손과 변조 및 유출을 방지하기 위한 정보보호의 기본 개념을 소개하고, 암호 시스템과 해시 함수, 전자서명 및 공개키 기반구조의 원리와 응용을 학습한다. |
| 차세대암호알고리즘 | stcse-2026-2ccb89db9b283489630f3483 | 109511 | 본 강좌에서는 현대 암호와 차세대 암호알고리즘의 이론을 소개하고, 경량암호와 동형암호 및 양자내성암호의 개념과 암호 모듈의 설계 및 분석 방법을 학습한다. |
| 캡스톤디자인(1) | stcse-2026-338f28ac1b06d540385dc9b6 | 109113 | 본 강좌에서는 전공 분야의 주제를 선정하여 팀 프로젝트를 수행하는 과정을 다루고, 문제 분석과 설계, 개발 및 테스트를 통해 종합적인 설계 방법을 학습한다. |
| 캡스톤디자인(2) | stcse-2026-f241c24f5fe43751c08e35f8 | 109114 | 본 강좌에서는 전공 지식을 활용한 팀 프로젝트의 수행 과정을 다루고, 설계와 구현, 검증 및 결과 정리와 발표 방법을 학습한다. |
| 컴파일러구조 | stcse-2026-120a2ef090f8acfa5afedcbc | 109270 | 본 강좌에서는 프로그램을 다른 언어로 번역하는 컴파일러의 구조를 소개하고, 어휘·구문·의미 분석과 중간 코드 생성 및 코드 최적화와 생성 원리를 학습한다. |
| 컴퓨터공학개론 | stcse-2026-830c26afb9ddfed87a0d35a5 | 109814 | 본 강좌에서는 컴퓨터의 구성과 동작에 관한 기본 개념을 소개하고, 하드웨어와 소프트웨어, 입출력 및 네트워크 등 컴퓨터 시스템의 주요 원리를 학습한다. |
| 컴퓨터그래픽스 | stcse-2026-04d6457b335d4ef1c76157cc | 109029 | 본 강좌에서는 데이터를 영상과 도형으로 표현하는 컴퓨터그래픽스의 기본 개념을 소개하고, 그래픽 알고리즘과 프로그래밍 및 영상 처리의 원리를 학습한다. |
| 컴퓨터네트워크 | stcse-2026-e68db1068b8a28ed1c5cd2f4 | 109032 | 본 강좌에서는 컴퓨터 간 통신과 네트워크의 기본 구조를 소개하고, 근거리망과 광역망의 통신 규약 및 흐름제어와 네트워크 분석 방법을 학습한다. |
| 컴퓨터보안 | stcse-2026-c7bff9c06301ce9e3608bf20 | 109285 | 본 강좌에서는 컴퓨터보안의 기본 이론과 응용을 소개하고, 접근제어와 악성 소프트웨어 및 서비스거부공격에 대한 대응과 디지털 포렌식의 개념을 학습한다. |
| 컴퓨터비전 | stcse-2026-ab2867eb0e4ccf82554869b2 | 109079 | 본 강좌에서는 디지털 영상으로부터 정보를 이해하는 컴퓨터비전의 기본 개념을 소개하고, 인간의 시각 체계가 수행하는 작업을 공학적으로 분석하고 자동화하는 방법을 학습한다. |
| 컴퓨터시스템구조 | stcse-2026-190f14679a6e2be9cb9c7759 | 109343 | 본 강좌에서는 컴퓨터시스템의 구성과 명령어 처리 과정을 소개하고, 명령어 집합과 주소지정 방식, 연산장치, 데이터 경로 및 제어장치의 동작 원리를 학습한다. |
| 코업(1) | stcse-2026-6fbe1947d15411b9c769afdd | 109500 | 본 강좌에서는 전공과 관련된 기업의 현장 업무에 참여하여 학업에서 다룬 이론과 실제 업무를 연결하고, 현장 활동의 수행 내용과 결과를 정리하는 과정을 학습한다. |
| 코업(2) | stcse-2026-f1b3a94ec0a5b1053302673d | 109502 | 본 강좌에서는 전공 관련 기업의 업무를 현장에서 경험하고, 업무 수행 과정에서 이론을 적용하는 방법과 활동 결과를 보고서로 정리하는 과정을 다룬다. |
| 코업프로젝트(1) | stcse-2026-6a40784a44de2bb50a5006ee | 109501 | 본 강좌에서는 코업 교과목과 연계하여 한 학기 동안 수행한 전일제 인턴 활동을 이수 기록으로 확인하는 과정을 다룬다. |
| 코업프로젝트(2) | stcse-2026-8038a33af19c7e0812f9c0ae | 109503 | 본 강좌에서는 코업 이수에 연계된 전일제 인턴 활동의 수행 기록을 확인하고, 학기 동안의 현장 참여를 이수 내역으로 남기는 과정을 다룬다. |
| 프로그래밍언어론 | stcse-2026-fdb71c9884eaa0e2a3ea1d54 | 109324 | 본 강좌에서는 여러 프로그래밍 언어의 설계 목적과 기본 개념을 소개하고, 언어의 구성과 특성을 비교·분석하여 활용 가능성을 평가하는 방법을 학습한다. |
| 프로그래밍입문(1) | stcse-2026-f489b01929ee28951fa7d25b | 109003 | 본 강좌에서는 C 언어를 중심으로 프로그래밍의 기본 개념을 소개하고, 절차적인 문제 해결 과정을 프로그램으로 작성하고 구현하는 방법을 학습한다. |
| 프로그래밍입문(2) | stcse-2026-72952814843d7a0be199d034 | 109004 | 본 강좌에서는 C++를 활용한 객체지향 프로그래밍의 기본 개념을 소개하고, 객체와 클래스, 캡슐화, 상속 및 다형성을 이용한 문제 해결 방법을 학습한다. |
| 현장실습(1) | stcse-2026-48f0c34a50a8cf78772900b8 | 109024 | 본 강좌에서는 산업 현장의 기술 현황과 실제 업무를 접하고, 현장에서 활용되는 기술을 익혀 업무상의 문제를 해결하는 방법을 학습한다. |
| 현장실습(3) | stcse-2026-0f058f380d819419dfc049ca | 109044 | 본 강좌에서는 산업체의 기술과 업무 수행 과정을 현장에서 살펴보고, 실제 업무에 필요한 기술을 적용하여 문제를 해결하는 과정을 학습한다. |
| 형식언어및오토마타 | stcse-2026-dd1ad00cc7f9f4753f8c7cd8 | 109084 | 본 강좌에서는 형식언어와 문법체계의 기본 개념을 소개하고, 유한 오토마타와 푸시다운 오토마타 및 튜링 기계의 원리와 계산 복잡도의 관계를 학습한다. |
| 확률및랜덤변수 | stcse-2026-8abca03565bd409781fbe044 | 109074 | 본 강좌에서는 불규칙 신호를 이해하기 위한 확률변수와 확률 과정의 개념을 소개하고, 모멘트와 주요 확률 과정의 특성 및 선형 시스템 해석에 적용하는 방법을 학습한다. |
