# 공모전·대외활동 추천 검증

## 개인화 추천 이유 개선 2026년 11월 14일

선정된 활동에 대해 진로 관련성, 확인된 개인 수행 경험의 활용, 활동에서 얻을 경험을 2~3문장으로 설명하도록 `activity-personal-reasons-v2`를 적용했다. 권장 길이는 100~200자이며 검증 허용 범위는 80~260자다. 추천 점수·순서·후보 선정, 카드 배치와 CSS는 변경하지 않았다. 운영 DB와 기존 사용자·로드맵 이력은 수정하지 않았다.

### 생성과 저장 흐름

기존 `roadmap_batch.run → _execute_activity_reasons → attach_reasons(generate=True)` 연결을 유지하고 실제 API 통합 테스트로 실행을 확인했다. 최대 12개의 선정 후보 중 상세 과제와 결과물 근거가 있는 활동만 한 번의 Gemini 구조화 JSON 요청에 포함한다. 재시도는 하지 않으며 기존 `ai_guard`의 소유자별 동시 실행·쿨다운·사용량 제한을 그대로 적용한다. 캐시 적중은 추가 사용량을 소비하지 않는다.

`career`, `experience`, `expected` 문장과 원문 인용, 경험 ID를 먼저 검증한 뒤 하나의 문단으로 합친다. 확인된 관련 경험이 없으면 `career`와 `expected`의 2문장만 작성한다. Gemini가 근거를 충분히 설명할 수 없으면 동일한 JSON 구조에서 `sentences=[]`로 보류할 수 있다. 이 결과는 AI 개인화 문장으로 표시하지 않는다.

검증된 구조화 결과와 공급자 실패는 `ai_requests.result_json`에 저장되고, 카드 문단·근거·상태는 `roadmap_runs.result_json.activity_recommendations`에 저장된다. GET 조회는 생성하지 않는다. 같은 입력과 근거의 명시적 재생성도 캐시를 재사용한다. 목표·확인 경험·본문·모델·이유 버전이 바뀌면 새로운 캐시 기준을 사용하며 기존 이력은 보존한다.

### 근거 검증과 화면 상태

- Gemini 입력에서 미확인·팀 수행·경험 없음 항목을 개인 경험으로 전달하지 않는다. 사용자가 수정한 경험은 수정된 수행 내용과 개인 기여 범위를 사용한다. 직무 비교는 사용자 확인 상태의 항목만 포함한다.
- 제목·분야만으로 과제를 만들지 않는다. 상세 필드가 있어도 과제 또는 결과물 근거가 없거나 미정·부정된 내용이면 생성 대상에서 제외한다.
- 각 문장의 인용이 해당 공고 원문에 연속해서 존재하는지 확인한다. 메타데이터의 기술명을 본문 과제 근거로 사용할 수 없고, 부정 문장을 잘라 긍정 과제로 바꿀 수도 없다.
- 수행 방법의 공통점과 명시된 기술·결과물 용어를 검사한다. 공고 내용을 과거 프로젝트 경험으로 바꾸거나, 과거 사용 기술을 공고 요구사항으로 바꾸면 거부한다. 자유 문장의 모든 의미를 형식적으로 증명하는 검증은 아니며, 인식하지 못한 수행 방법이나 모호한 근거는 보수적으로 보류될 수 있다.
- `reason_source=gemini`, `reason_status=generated`는 ‘내 진로에 도움이 되는 이유’로 표시한다. fallback은 `needs_verification`, `generation_failed`, `not_generated`로 나누고 ‘추천 근거 확인 필요’로 표시한다. 과거 제목 나열 fallback도 개인화 문장처럼 보여 주지 않는다.

### 검증 결과

아래 A~E는 가상 사용자·공고 자료와 **모의 Gemini 응답**을 사용했다. SDK 호출 인터페이스, 서버 검증, 실제 DB 저장, API 재조회까지 검사했지만 Gemini의 실제 생성 품질을 검증한 결과는 아니다.

| 사례 | 입력 | 확인 결과 |
| --- | --- | --- |
| A | 데이터 분석 목표, Python 처리·시각화 경험, 환경 공공데이터 분석·제출 과제 | 3문장, 기존 처리 경험을 환경 데이터 분석에 연결 |
| B | 백엔드 개발 목표, REST API 구현 경험, API 설계·구현 및 서비스·설명서 제출 | 3문장, API 경험과 서비스 구현 연결 |
| C | 인공지능 연구 목표, 머신러닝 학습·평가 코드 작성 경험, 모델 개발·평가·제출 | 3문장, 사용자가 확인한 개인 수행 범위만 사용 |
| D | 데이터 분석 목표, 확인된 프로젝트 없음, 상세 분석·제출 과제 | 2문장, 과거 경험을 만들지 않음 |
| E | 데이터 분석 목표, 제목만 있는 공고 | Gemini 호출 0회, 추천 근거 확인 필요 |

A~D의 문단은 서로 다르며 원문 인용과 함께 저장·재조회 후 그대로 유지된다. C의 기존 프로젝트 분석이 개인 기여를 확정하지 못하는 경우에는 테스트에서 사용자 수정 API로 개인 수행을 명시적으로 확인했다. 단순 확인 답변으로 불명확한 기여 범위를 자동 승격하지 않는다.

- API 전체 검사: **676개 통과, 63개 건너뜀, 기존 실패 1개**, 추가 subtest 30개 통과. 실패는 이번 변경과 무관한 `test_manual_workflow_uses_shared_docker_entrypoint`이며 현재 HEAD에도 `.github/workflows/collect-activities.yml`이 없어 발생한다. 워크플로를 임의로 생성하지 않았다.
- 별도 TLS 로컬 PostgreSQL 17 컨테이너: **28개 통과**. 로드맵 생성, A~E, `ai_requests`의 1회 사용량·구조화 결과, `roadmap_runs`의 문단·근거 저장, 이력 보존, 캐시·동시 요청·실패·사용량 제한을 검사했다. 운영 PostgreSQL 검증은 아니다.
- 프론트 단위: **53개 통과**. Next.js 프로덕션 빌드 성공.
- 데스크톱 브라우저: 저장된 문단, fallback/과거 결과 구분, 탭·새로고침·포커스에서 생성 요청 없음, 기존 메타데이터·링크 유지 확인. API는 고정 응답으로 대체했으므로 운영 E2E가 아니다. 모바일 변경은 없다.
- 실제 Gemini: **미검증**. 현재 실행 환경에 `GEMINI_API_KEY`가 없으며 실제 API를 호출하지 않았다.

모의 응답 A의 검증·저장 문장:

> 기후·환경 공공데이터를 분석하는 과제로, 데이터 분석가에게 필요한 분석 과정을 연습할 수 있습니다. 기존 Python 데이터 처리 경험을 환경 데이터 분석에 적용해 볼 수 있습니다. 분석 결과를 설명하는 제출물을 작성하며 결과를 전달하는 프로젝트 경험으로 넓힐 수 있습니다.

재현 명령은 저장소 루트 기준이다. 활성 Python 환경에 API 테스트 의존성을 설치해야 한다.

```sh
PYTHONPATH=apps/api:apps/api/app python -m pytest apps/api/tests/unit apps/api/tests/integration -q
node --experimental-vm-modules --test apps/web/tests/unit/*.test.mjs
```

실제 Gemini 검증은 키를 환경변수로 설정한 후 아래 파일만 명시적으로 실행한다. 가상 A~D 입력으로 최대 4회 호출하고 E는 호출하지 않는다. 인메모리 SQLite의 호출 제한·캐시만 사용하며 운영 DB에 연결하지 않는다. 성공 시 실제 문장과 근거를 pytest 임시 폴더의 `actual-gemini-activity-reasons.json`에 남기고 출력한다.

```sh
GEMINI_LIVE_TEST=1 PYTHONPATH=apps/api:apps/api/app python -m pytest \
  apps/api/tests/integration/test_activity_reasons_live.py -q -s
```

## 이전 검증 기록 2026년 11월 12일

아래 내용은 당시 구현과 운영 검증 기록이며, 추천 이유 생성·표시의 현재 동작은 위 내용을 따른다.

기준: 시작 시 `git fetch origin main` 완료. `HEAD`와 `origin/main` 모두 `8e500645d51e793a98bc025142f6f4bac9f55b3a`였다.

## 코드와 자동 검증

`GET /api/roadmap-inputs/{request_id}/activities`는 기존 `owned_context`와 계획 소유권 검사를 사용한다. 진로 목표만 필수이며 문서, 희망 직무, 직무 분석, 생성된 로드맵은 필요하지 않다. 현재 유효한 확인 경험과 명시적으로 경험 없음이라고 답한 보완 후보가 있으면 추가로 활용한다. 학생 입력은 서버에서만 매칭하며 공급자에게 보내지 않는다. 학생 조회에서 Gemini나 외부 공고 수집을 호출하지 않는다. 수집 저장소 마이그레이션은 별도 적용한다.

Result의 다섯 번째 탭에 카드·로딩·빈 결과·실패·부분 실패를 연결했다. 활동 로더는 로드맵 조회와 독립적이며 같은 계획/입력 버전의 응답을 최대 5분, 마감 시각 이내에서 재사용한다. 탭을 떠나도 컴포넌트를 유지하고, 포커스/분 단위 확인/입력 변경/명시적 재시도로 다시 판정한다. 기존 방향키·Home·End 탭 동작과 테마를 사용한다.

공통 공고는 PostgreSQL의 누적 후보에서 읽는다. 운영자가 수동으로 수집하며 학생 조회는 외부 사이트에 접속하지 않는다. 실패 시 마지막 성공 자료를 유지한다. 콘테스트코리아는 공모전의 학문•과학•IT와 아이디어•건축•창업, 대외활동의 교육 • 강연 • 멘토링 • 세미나와 전시 • 박람 • 행사 • 축제 분야에서 접수 중·예정이면서 대학생·누구나 참가가 확인된 공고만 저장하고 동일 본문은 날짜별로 중복 저장하지 않는다. 개인화 응답은 `Cache-Control: no-store`다. [운영 안내](contestkorea-server-collection.md)

접수 중·예정 공고를 추천하고, 예정 카드에는 시작일과 상태 배지를 표시한다. 접수 시작 시각에도 캐시가 만료된다. 접수 기간은 한국 시간으로 재판정하고 날짜 마감은 당일을 포함한다. 명시된 시각, 연말을 넘는 기간, 상시 접수를 처리한다. 연도·자격이 불명확하거나 추가 참가 조건이 표시된 공고는 제외한다. 원문 제목/분야에 없는 기술 사용 의무를 만들지 않으며 낮은 관련성의 공고로 결과 수를 채우지 않는다.

관련성 판정은 정의된 직무·활동·역량 표현으로 제한한다. 목표의 임의 단어가 겹치는 우회 경로는 제거했으며 일반어 또는 프로젝트 소재 일치만으로는 선정하지 않는다. 분석·개발 등 수행 분야가 확인된 목표에서 환경·건축 같은 소재만 겹치는 경우도 제외한다. 제목·분야와, 제공된 경우에만 `description_text` 본문을 검사한다. 현재 Basic DEMO 어댑터는 본문을 제공하지 않으므로 본문을 추정하거나 추가 수집하지 않는다. 점수에 반영된 각 근거를 `evidence`와 화면용 `reasons`에 함께 기록한다. 고정 회귀 입력에서는 쇼핑 숏폼 부업 강의·자전거 대행진을 제외하고, 공공데이터 활용 경진대회·자전거 수요 데이터 분석 경진대회를 유지한다.

고정 표본 결과:

| 학생 목표 | 추천 순서 | 근거 |
| --- | --- | --- |
| 데이터 분석가 | 공공데이터 분석 경진대회 → 소비자 데이터 분석과 마케팅 아이디어 공모전 | 입력 목표와 제목의 데이터 표현 |
| 마케팅 지망생 | 브랜드 마케팅 기획 공모전 → 소비자 데이터 분석과 마케팅 아이디어 공모전 → SNS 홍보 서포터즈 | 입력 목표와 제목의 마케팅·SNS 표현 |

자동 검증: API 108개 통과, 1개 건너뜀(기존 선택적 Gemini 실호출 테스트), 프론트 단위 23개 통과, Next.js 프로덕션 빌드 성공. API 검증에는 이번 활동 추천 53개, 기존 한영 과목 16쌍·이수 선택·수강 추천·로드맵·외부 fixture 회귀가 포함된다.

```sh
ROADMAP_DB_BACKEND=sqlite PYTHONPATH=apps/api/app apps/api/.venv/bin/python -m pytest \
  apps/api/tests/unit/test_activity_recommendations.py \
  apps/api/tests/integration/test_activities_api.py \
  apps/api/tests/unit/test_course_groups.py \
  apps/api/tests/unit/test_course_recommendations.py \
  apps/api/tests/unit/test_roadmap_generation.py \
  apps/api/tests/integration/test_course_equivalence_api.py \
  apps/api/tests/integration/test_p4_external.py -q -rs
node --experimental-vm-modules --test apps/web/tests/unit/*.test.mjs
cd apps/web
ROADMAP_API_ORIGIN=https://endpoint-team18.onrender.com npm run build
```

로컬 Chromium 브라우저 회귀도 통과했다. API를 고정 응답으로 대체하여 로드맵 조회 실패 상태에서도 목표만으로 활동 표시, 키보드 탭 이동, 조회 재사용, 부분/빈/전체/네트워크 오류 구분, 원문 링크 새 창 이동, 모바일 390px 레이아웃을 검사했다. 이 검사는 운영 E2E가 아니다. 스크립트는 `apps/web/tests/browser/activities.mjs`이고 Playwright가 필요하다. 테스트 빌드에는 `NEXT_PUBLIC_SUPABASE_URL=https://team18-test.supabase.co`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=fixture-public-key`를 사용하고 `next start -H 127.0.0.1 -p 3100`으로 실행한다. 이 테스트 설정을 운영에 적용하지 않는다.

## 실제 공급자 응답

서버 환경변수 `CONTESTKOREA_API_KEY`로 두 종류를 실제 조회했다. 키와 인증 요청 URL은 보고서·로그·브라우저 응답에 넣지 않는다. 키 없이 가상 공고로 대체하는 경로는 없다. `urllib` 전송은 리다이렉트를 따르지 않고, 오류는 고정 코드로 바꾼다.

실제 응답은 `[{"resultcode":"1","resultmsg":"성공","Data":[...]}]`이며 분야 코드는 `STR_BCODE`다. 공고의 `STR_MEETCODE`, `STR_MEETING`, `STR_MENU`, `STR_HOST`, `STR_TARGET`, `STR_DATE1`, `STR_URL` 7개 필드를 확인했다. 같은 분야 응답에도 다른 종류의 홍보 공고가 포함되어 원문 링크의 `Txt_gbn`으로 구분을 보정한다.

| 조회 | 분야 수 | 종류별 ID 중복 제거 후 | 실패 분야/파싱 실패/기간 원문 확인 실패 |
| --- | ---: | ---: | ---: |
| 공모전 `int_gbn=1` | 10 | 95 | 0 / 0 / 0 |
| 대외활동 `int_gbn=2` | 7 | 68 | 0 / 0 / 0 |

합친 고유 공고는 163건이다. 데모는 분야별 최근 등록 10건 표본이므로 전체 모집 목록이나 종류별 최종 추천 수를 의미하지 않는다.

중요한 실제 계약 차이: `STR_DATE1`은 `11.07~11.16`처럼 연도가 없다. 공고 ID나 현재 연도로 연도를 추정하지 않는다. 같은 `str_no`의 콘테스트코리아 공개 상세 페이지 접수기간 표에서 `2026.11.07 ~ 2026.11.16`을 확인하고, 양 끝 월·일이 API와 일치할 때만 `verified_period`로 사용한다. 원 API 기간도 보존·표시한다. 원문 조회 실패·불일치는 현재 접수 중으로 판단하지 않는다.

실제 표본을 매칭한 결과 데이터 분석가는 1건, 마케팅 지망생은 6건이었다. 예를 들어 데이터 목표에는 [2026년 공공데이터 활용 경진대회](https://www.contestkorea.com/sub/view.php?Txt_gbn=1&Txt_bcode=031410001&str_no=202611020029), 마감 `2026-12-01`이 추천됐다. 마케팅 목표에는 [2027년 경주시 SNS 알리미 모집](https://www.contestkorea.com/sub/view.php?Txt_gbn=2&Txt_bcode=040710001&str_no=202610300024), 마감 `2026-11-13`이 포함됐다. 추천 수는 현재 날짜·공고 갱신에 따라 달라진다.

Render 또는 키가 있는 로컬 환경에서 재검증:

```sh
python app/scripts/external_collect.py contestkorea
```

이 명령은 PostgreSQL 설정에서도 fixture용 SQLite 테이블이나 마이그레이션을 사용하지 않는다. 두 `sources.status`, 분야 수, 정규화 필드와 `verified_period`를 확인한다. 부분 실패도 종료 코드 1이다. 기존 `init-fixtures/enqueue/work` 경로는 자동 테스트용으로 유지한다.

## 배포 사이트 E2E

사용자 승인 후 구현 커밋 [`98c47a34bc67d41448a8978334de2185c2adf31c`](https://github.com/biabio0503/endpoint_team18/commit/98c47a34bc67d41448a8978334de2185c2adf31c)을 `main`에 반영했다. [Vercel 자동 배포](https://vercel.com/leejunsuks-projects/web/FjNXmJ5QRaqk8cD5hmK42aCJNtP5)는 성공 상태이며, Render OpenAPI의 새 `/api/roadmap-inputs/{rid}/activities` 경로와 실제 추천 응답으로 백엔드 반영을 확인했다.

2026-11-12 01:17 KST부터 운영 [Vercel 사이트](https://web-seven-xi-rblasxflsf.vercel.app/)에서 Chromium E2E를 실행하여 **통과**했다. 원본 응답을 대체하거나 네트워크를 모킹하지 않았다. 별도 게스트에 진로 목표만 저장한 테스트 계획을 만들고, 시작 화면의 ‘이어서 작성’으로 같은 저장 계획을 다시 열었다. 이 계획에는 문서·희망 직무·직무 분석·생성된 로드맵이 없다. 사용자의 기존 개인 계획을 검사한 것은 아니다.

| 확인 항목 | 운영 결과 |
| --- | --- |
| 기존 저장 계획 열기 | ‘이어서 작성’ 후 동일 계획 ID와 저장 목표 확인 |
| 활동 탭 | End 키로 이동, 실제 추천 카드·목표·입력 버전 표시 |
| 데이터 분석가 | 1건, 첫 추천은 공공데이터 활용 경진대회, 마감 2026-12-01 |
| 마케팅 지망생 | 목표 수정·저장 후 재열기, 6건, 첫 추천은 경주시 SNS 알리미, 마감 2026-11-13 |
| 추천 근거 | 학생 목표와 공고 제목에서 확인된 표현을 화면에서 검증 |
| 공모전 원문 보기 | 새 창의 `str_no`, 제목, 연도 포함 접수기간 일치 |
| 대외활동 원문 보기 | 새 창의 `str_no`, 제목, 연도 포함 접수기간 일치 |
| 탭 왕복·창 포커스 | 추가 활동 요청 없이 컴포넌트 응답 재사용 |
| 서버 공통 캐시 | 두 목표 모두 공모전·대외활동 `cache_hit=true`, 최초 수집 시각 유지 |
| 공급자 상태 | 두 종류 모두 `success`, 95건/68건, 실패 분야·파싱·기간 확인 실패 0 |

공개 공고 정보와 검증 결과만 남긴 [운영 E2E 증거](audits/activity-recommendations-2026-11-12/deployed-e2e.json)를 보존했다. 키·인증 토큰·테스트 계획 ID는 포함하지 않는다. 첫 원문 검사에서는 브라우저 새 창의 주소가 정해지기 전 검사하여 자동화가 실패했고, 실제 원문 URL 이동 완료를 기다리도록 검사만 수정한 뒤 두 목표 모두 통과했다. 서비스 코드는 이 재검증 과정에서 변경하지 않았다.

운영 한계: 공통 캐시가 비어 있으면 분야별 API와 공개 원문의 연도 확인 때문에 첫 조회가 오래 걸릴 수 있다. 캐시는 프로세스별이므로 서버 재시작·확장 후 다시 수집한다. 데모 표본과 보수적 자격 필터 때문에 적합한 공고가 있어도 추천 0건일 수 있다. 원문의 상세 참가 조건은 학생이 최종 확인해야 한다.

## 데이콘·데이커 DB 후보 추가 (2026-11-12)

기존 `/activities` 응답에는 이제 PostgreSQL의 최신 성공 수집 스냅샷도 같은 추천 함수로 평가해 포함한다. 학생 요청에서 데이콘·데이커 사이트나 Playwright를 호출하지 않는다. 신청 기간은 대회 진행 기간과 별도로 원문에서 확인하며 조회 시점에 다시 마감을 판정한다. 참가 자격을 확정하지 못한 후보는 제외한다. 출처는 `source`/`source_label`, 원문은 `url`, 마감은 `deadline_label`, 학생 목표와 공고의 연결 근거는 기존 `reasons`/`evidence`에 담긴다. 수집 실패 때 이전 성공본을 사용하며 콘테스트코리아는 계속 제공한다. [서버 수집 운영 인수인계](dacon-server-collection.md)를 참고한다.
