# 프로젝트 문서 업로드 중단과 새로고침 복구

2026년 11월 14일 검증. 새로고침 후 문서 목록과 업로드 큐를 서버 상태에 맞춰 복구한다. 등록이 완료된 문서는 성공으로 표시하고, 유효한 서버 예약은 진행 상태로 표시한다. 브라우저에만 있던 파일은 업로드 중단으로 표시해 원본 재선택을 안내한다. 최대 10개 제한과 기존 선택·드롭·중복 차단·등록 순서·삭제·OCR 기능을 유지한다.

운영 DB와 Storage는 변경하지 않았다. 아래 PostgreSQL 마이그레이션을 먼저 적용하고 API와 프론트엔드를 배포해야 운영에 반영된다.

## 원인과 수정 전 재현

기준 커밋은 `812143a80d596f84ce6b7cf90fc70beba49edaab`이다. GitHub `2026ENDPoinT/team18`의 `main` 워커 파일을 조회해 로컬 코드와 일치함을 확인했다.

기존 흐름은 `File → 메모리 큐 → multipart 전체 수신/검증 → PostgreSQL 예약 → Storage 저장 → 문서/추출 행 생성 → 응답 → BackgroundTasks`였다.

- 큐의 `File`은 React 메모리에만 있었다. 서버 예약과 연결되는 클라이언트 요청 ID가 없고 목록 API는 등록 문서만 반환했다. 업로드 요청 직후 새로고침한 실제 Brave 재현에서는 문서 0개, 큐 0개, 재선택 안내 0개였다. 따라서 이 커밋에서 “파일명 큐가 새로고침 후 그대로 유지됨” 자체는 재현되지 않았다. 등록되지 않은 파일을 서버 상태와 대조하거나 재선택하도록 복구하지 못하는 문제는 재현됐다.
- 예약이 생성된 뒤 프로세스가 종료되면 15분간 예약이 이름과 개수를 차지했다. 정상 진행 여부를 알리는 heartbeat가 없었다. 만료된 예약은 원래도 개수 쿼리에서 제외됐으므로 영구적인 개수 점유로 일반화할 수는 없다.
- Storage 저장과 DB 등록은 별개 작업이다. 그 사이 중단되면 예약과 파일만 남으며, 응답 유실 시 클라이언트가 등록 성공을 요청 ID로 확인할 수 없었다.
- `main.py`는 SQLite에서만 워커를 시작했다. PostgreSQL의 복구는 후속 요청의 제한된 `BackgroundTasks` 실행에 의존했다. 실제로 요청이 없으면 DB의 pending 작업과 예약 정리가 재개되지 않았다.
- 기존 `loop()`를 PostgreSQL에서 그대로 실행하면 `SupabaseDocumentStorage.old_keys`가 없어 `AttributeError`가 발생했다. 이 오류가 추출 처리까지 막는 구조도 별도로 재현했다.

## 새로고침 후 상태와 API 계약

`POST /api/roadmap-inputs/{rid}/documents`는 선택한 파일마다 생성한 UUID를 `Idempotency-Key` 헤더로 받는다. `(request_id, upload_id)` 유일 인덱스와 파일명·SHA-256 검증으로 같은 요청이 다른 파일로 바뀌는 것을 차단한다. 다른 계획의 동일 ID는 독립된 요청이다.

| 상황 | 응답 및 표시 |
| --- | --- |
| 새 등록 완료 | 201, 문서 ID와 upload_id 반환 |
| 같은 요청이 이미 등록됨 | 200, 기존 문서 반환, 개수와 input_revision 증가 없음 |
| 같은 요청의 서버 작업이 진행 중 | 202, 진행 상태 반환, Storage 재전송 없음 |
| 같은 ID에 다른 파일 | 409 idempotency_conflict |
| 같은 요청이 만료됨 | 409 upload_expired, 파일 재선택으로 새로운 요청 생성 |
| 등록 후 사용자가 문서를 삭제함 | 동일 요청 재전송은 410, 원본 재선택은 새 요청 |

`GET .../documents?upload_ids=<UUID 목록>`은 하나의 DB 스냅샷으로 `documents`, `uploads`, `input_revision`을 반환한다. 등록 문서에는 `upload_id`를 포함한다. `uploads`에는 해당 계획의 현재 유효한 예약과 조회한 ID의 최종 상태를 포함한다. 조회 ID는 최대 100개이며 소유권 검사는 기존과 동일하다.

브라우저는 탭별·계획별 sessionStorage에 요청 ID, 파일명, 크기만 보관한다. 파일 바이트는 저장하지 않는다. 새로고침 시 서버 조회가 완료될 때까지 상태를 확인하고 다음과 같이 처리한다.

| 서버 확인 결과 | 복구 |
| --- | --- |
| 동일 upload_id 문서 존재 | 큐 항목을 제거하고 실제 등록 문서 및 추출 상태 표시 |
| 유효한 업로드 예약 존재 | 서버에서 업로드 중으로 표시 |
| 예약 만료 또는 서버에 요청 없음 | 업로드 중단과 파일 다시 선택 버튼 표시 |
| 서버 조회 실패 | 확인 실패 안내 후 재조회, 업로드 성공으로 추정하지 않음 |

페이지가 보이는 동안 3초마다 목록을 갱신한다. 서버에서 뒤늦게 등록이 끝나는 경우도 반영된다. 로컬 메타데이터를 자동 업로드에 넣지 않으며, 실제 `File`이 있는 현재 페이지의 대기 파일만 전송한다. 파일명만으로 성공을 추정하지 않는다. 등록 문서와 큐는 기존 카드 안의 서로 다른 표에 표시한다.

원본 파일의 자동 재전송은 구현하지 않았다. 향후 이를 제공하려면 브라우저에서 바이트를 복구할 수 있는 Blob 저장/파일 접근 권한과 서버 업로드 오프셋·완료 검증을 함께 설계해야 한다. Supabase의 [resumable uploads](https://supabase.com/docs/guides/storage/uploads/resumable-uploads)는 별도 검토 대상이다.

## 예약과 파일 보호

multipart 전체 수신과 파일 검증이 끝난 후에만 예약한다. 계획 행 잠금으로 중복 이름·등록 순서·개수 검사를 직렬화하고 Storage I/O 전에는 트랜잭션을 종료한다. SQLite도 같은 예약 흐름을 사용한다.

새 예약은 120초 lease와 서버 전용 token을 갖는다. 살아 있는 업로드 작업이 최대 20초 간격으로 lease를 갱신한다. 브라우저 연결이 끊어져도 서버에 도착한 파일의 저장·등록은 계속 진행할 수 있다. 프로세스가 죽으면 heartbeat가 사라지고 예약이 만료된다. 만료된 lease는 다시 살릴 수 없으며 정리 작업은 token을 무효화해 늦은 등록을 차단한다.

개수는 삭제되지 않은 등록 문서 수와 아직 등록되지 않은 유효 예약 수의 합이다. 실패한 예약은 가능한 즉시 해제하고, DB 장애로 해제할 수 없으면 lease 만료로 개수에서 빠진다. 다른 계획의 예약은 이 개수에 포함하지 않는다.

실패 경로에서 Storage 파일을 바로 삭제하지 않는다. DB COMMIT은 성공했으나 응답만 유실됐을 수 있기 때문이다. 별도 DB 연결에서 등록 여부를 확인하며 예약을 해제한다. 정리 워커는 만료된 정확한 예약 키만 선택하고, 예약 행을 잠근 상태에서 실제 문서 참조를 다시 검사한 뒤 파일을 지운다. 등록된 문서 키는 예약 메타데이터가 잘못되어 있어도 삭제 대상에서 제외된다.

Storage 저장 후 DB 등록 전에 실패한 파일은 안전하게 정리하는 방식을 선택했다. 이 경우 완료로 표시하지 않고 사용자에게 원본 재선택을 안내한다. 새로 등록된 파일과 실패한 이전 시도의 키가 달라 서로 영향을 주지 않는다.

늦게 도착한 Storage 응답을 처리하기 위해 실패 예약은 정리 후에도 하루 간격으로 확인한다. 만료 후 7일이 지난 실패 예약은 마지막 Storage 삭제가 성공하고 문서 참조가 없는 경우에만 제거한다. 정리 실패는 60초 후 재시도한다. 완료된 요청 ID는 멱등성과 삭제된 문서의 재생성 방지를 위해 보존한다.

PostgreSQL 문서 기능이 활성화되면 FastAPI lifespan에서 상시 워커를 시작한다. 새 프로세스는 DB의 pending 문서와 만료된 작업 lease를 다시 claim한다. `FOR UPDATE SKIP LOCKED`와 완료 token/revision 검사, 기존 OCR 기록 재사용을 유지한다. 요청 기반 작업은 보조 수단으로 남고 상시 워커와 프로세스 내 실행 잠금을 공유한다. Supabase 정리는 버킷 전체 스캔을 하지 않는다. 정리 실패가 문서 추출을 막지 않도록 처리도 분리했다.

프로세스가 실행되지 않는 호스팅 절전 시간에는 작업이 진행되지 않는다. 재기동 시 복구되지만 절전 중 즉시 완료를 보장하려면 상시 실행 환경이 필요하다.

## 검증 결과

실제 Brave와 Next.js → FastAPI → 로컬 PostgreSQL 17을 사용했다. Storage는 실제 `SupabaseDocumentStorage`의 HTTP 요청·비공개 버킷 확인·삭제 검증을 로컬 REST fixture로 연결했다. 운영 Supabase Storage와 Google API는 호출하지 않았다. OCR 테스트는 스캔 PDF 렌더링, DB OCR 예약/결과 저장을 실행하고 외부 Google 응답만 합성했다.

| 번호 | 시점 | 결과 |
| --- | --- | --- |
| 1 | POST 시작 직후, API 도착 전 새로고침 | 서버 문서 없음, 중단 및 재선택 안내 |
| 2 | 예약 생성 직후 새로고침 | 실제 서버 진행 표시, 최초 lease 시간을 넘겨도 heartbeat 유지, 한 번 등록 |
| 3 | Storage 요청 중 새로고침 | 예약 유지, 저장 완료 후 문서 동기화 |
| 4 | Storage 저장 완료 후 DB 등록 전 SIGKILL | 재시작 후 해당 고아 파일 정리, 중단 표시, 재선택 성공 |
| 5 | DB 등록 후 응답 전달 전 새로고침 | 기존 문서 1개 복구, 원본 파일 보존 |
| 6 | 문서 추출 및 스캔 PDF OCR 중 새로고침 | pending 유지 후 완료, OCR 처리 기록 1개 |
| 7 | 여러 파일 중간에 새로고침 | 등록 완료·서버 진행·미전송 파일을 구분, 미전송 파일만 재선택 |
| 8 | 업로드 중 API 종료 및 재시작 | 죽은 예약 만료, 재등록 성공; 추출 작업도 새 워커가 브라우저 요청 없이 재개 |
| 9 | 중단 후 같은 파일 재선택 | 문서·원본 각각 1개, 중복 없음 |
| 10 | 9개 등록 상태에서 10번째 업로드 중단 | 유효 예약은 마지막 자리 점유, 만료 후 자리 반환, 10개 성공·11개 차단 |

추가 PostgreSQL/API 검증은 같은 ID 동시 요청, 다른 내용의 ID 재사용, Storage 오류, DB 등록 오류, COMMIT 응답 유실, 늦은 파일 생성, 만료 writer와 정리 경합, 7일 정리, 기존 문서 보호, 소유권과 다른 계획 격리를 포함한다. 신규 마이그레이션을 기존 문서·추출·예약이 있는 DB에 적용하고 데이터 개수, RLS, anon/authenticated 권한이 유지되는 것도 검증했다.

- 중단 브라우저 시나리오 10개 및 추가 OCR 시나리오 통과.
- 기존 업로드 브라우저 시나리오 8개 통과: 다중 선택, 드롭, 중복 이름, 순서, 삭제/재등록, 실패 격리, 크기/개수 제한, 응답 유실.
- 업로드·OCR 관련 SQLite 테스트 67개 통과, PostgreSQL 전용 4개 제외.
- PostgreSQL 문서 통합 시나리오 통과. 별도 PostgreSQL OCR 테스트 52개 통과.
- 프론트엔드 큐 테스트 3개 통과. 전체 프론트엔드 단위 테스트 및 Next.js 빌드 통과.
- 전체 API 실행은 620개 통과, 61개 제외, 기존 실패 2개. 수정 전 사본에서도 동일하게 실패한 테스트는 `test_fastapi.py`의 오래된 OpenAPI 경로 목록과 `test_dacon.py`의 존재하지 않는 `collect-activities.yml` 참조다.

## 변경 파일

| 파일 | 역할 |
| --- | --- |
| `apps/web/src/features/intake/Documents.js` | 서버 상태 조회, 큐/문서 구분, 중단 안내 |
| `apps/web/src/features/intake/useDocumentUploads.js` | 업로드 ID, 실파일 큐 처리, 재선택·상태 동기화 |
| `apps/web/src/features/intake/documentUploadQueue.mjs` | 메타데이터 저장과 서버 기준 복구 |
| `apps/web/src/features/intake/documents.css` | 별도 큐 표가 불필요하게 늘어나는 것 방지 |
| `apps/api/app/api/routes/documents.py` | 상태 조회, 멱등 업로드, 안전한 실패 처리 |
| `apps/api/app/repositories/documents.py` | 예약·lease·조회·정리 쿼리와 문서 보호 |
| `apps/api/app/worker/documents.py` | 업로드 heartbeat, 정리, PostgreSQL 상시 복구 |
| `apps/api/app/providers/document_storage.py` | 파일 저장과 DB 등록/정리 책임 명시; 기존 비공개 REST 동작 유지 |
| `apps/api/app/main.py` | PostgreSQL 문서 워커 시작 |
| 두 마이그레이션 및 관련 API·브라우저·큐·OCR 테스트 | 아래 적용 및 회귀 검증 |

## 마이그레이션과 배포 절차

PostgreSQL은 `supabase/migrations/20261113193416_document_upload_recovery.sql`을 별도 적용한다. CLI가 생성한 파일명이며 기존 파일명 예약 마이그레이션 `20261113191643_document_upload_filenames.sql`이 선행되어야 한다. 추가되는 것은 nullable `upload_id`, `content_sha256`, `upload_lease_token`과 유일 인덱스다. 기존 문서/사용자 행 변경이나 삭제, 공개 권한 추가는 없다. SQLite는 `apps/api/migrations/012_document_upload_recovery.sql`을 앱 시작 시 적용한다.

1. 기존 업로드 요청을 drain하고 이전 API/워커를 종료한다. 새 정리 규칙과 이전 writer를 섞어서 운영하지 않는다.
2. 변경 전 문서·추출·예약 수를 기록하고 위 마이그레이션을 한 트랜잭션으로 적용한다. 운영 자동 마이그레이션이나 DB 초기화는 하지 않는다.
3. 아래 읽기 전용 쿼리로 컬럼·인덱스·권한과 기존 문서/추출 수를 비교한다.
4. API를 배포하고 `ROADMAP_POSTGRES_DOCUMENTS_ENABLED=1` 상태에서 워커 시작을 확인한다. 프론트엔드를 배포한다.
5. staging 전용 계획으로 9개+진행 예약, 응답 유실, 프로세스 재시작, 기존 문서 읽기를 확인한다. 실제 호스팅 중단·프록시와 hosted Storage 연동 검증은 이 단계에서 수행한다.

```sql
SELECT count(*) FROM public.project_documents;
SELECT count(*) FROM public.document_extractions;
SELECT count(*) FROM public.document_upload_reservations;
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='public' AND table_name='document_upload_reservations'
  AND column_name IN ('upload_id','content_sha256','upload_lease_token');
SELECT indexdef FROM pg_indexes
WHERE schemaname='public' AND indexname='document_upload_reservations_idempotency';
SELECT relrowsecurity FROM pg_class
WHERE oid='public.document_upload_reservations'::regclass;
SELECT role_name, has_table_privilege(role_name,
  'public.document_upload_reservations','select,insert,update,delete')
FROM (VALUES ('anon'),('authenticated')) AS roles(role_name);
```

RLS는 true, 두 공개 역할의 테이블 권한은 false여야 한다. 롤백 시에도 요청을 drain한 뒤 애플리케이션만 이전 버전으로 돌리고 추가 컬럼/인덱스는 유지한다. 검증 없이 컬럼이나 기존 문서를 삭제하지 않는다.

## 테스트 재실행

기존 `tests/integration/postgres_test_safety.py`가 localhost의 `team18_document_test`와 명시적인 reset opt-in을 요구한다. 운영 연결 문자열을 이 명령에 사용하지 않는다. TLS를 지원하는 일회용 PostgreSQL을 준비한다.

```sh
cd apps/api
python -m pytest tests/integration/test_document_uploads.py tests/integration/test_document_upload_recovery.py -q
ROADMAP_TEST_POSTGRES_URL=postgresql://USER:PASSWORD@127.0.0.1:PORT/team18_document_test \
ROADMAP_ALLOW_TEST_DB_RESET=1 python -m pytest tests/integration/test_documents_postgres.py -q
PYTHONPATH=app ROADMAP_OCR_TEST_BACKEND=postgres \
ROADMAP_TEST_POSTGRES_URL=postgresql://USER:PASSWORD@127.0.0.1:PORT/team18_document_test \
ROADMAP_ALLOW_TEST_DB_RESET=1 python -m pytest tests/unit/test_document_ocr.py tests/unit/test_ocr_preflight.py tests/unit/test_ocr_budget_boundaries.py -q
```

브라우저 검증은 `apps/web`에서 Next를 `:15115`로 실행하고 `ROADMAP_API_ORIGIN=http://127.0.0.1:18095`, 합성 `NEXT_PUBLIC_SUPABASE_URL=https://job-skills-test.supabase.co`, 합성 publishable key를 설정한다. `document-upload-recovery.mjs`가 별도 테스트 API를 실행/종료하므로 해당 포트에 다른 API가 없어야 한다. 실행 전 위 PostgreSQL 통합 테스트로 로컬 스키마를 준비한다.

```sh
cd apps/web
node --experimental-vm-modules --test tests/unit/*.test.mjs
ROADMAP_TEST_POSTGRES_URL=postgresql://USER:PASSWORD@127.0.0.1:PORT/team18_document_test \
ROADMAP_ALLOW_TEST_DB_RESET=1 DOCUMENT_TEST_PYTHON=/path/to/test/python \
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/browser \
node tests/e2e/document-upload-recovery.mjs
```

스크립트가 출력하는 임시 디렉터리에 API 로그, 결과 JSON과 화면 캡처를 남긴다. 테스트 fixture의 3초 lease는 검증 속도를 위한 설정이며 운영 lease는 120초다. 기존 UX 검증은 `document_upload_ui_server.py`와 `tests/e2e/document-uploads.mjs`를 사용한다.
