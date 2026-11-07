# 대학생 개인화 진로 로드맵

P4 로컬 웹앱입니다. Node.js 20.9 이상과 Python 3이 필요합니다. 별도의 AI 키나 DB 서비스는 필요하지 않습니다.

먼저 API 가상환경과 문서 파싱 라이브러리를 설치합니다.

```sh
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -r apps/api/requirements.txt
```

과목 화면에 사용할 가상 개발용 기준 데이터를 한 번 적재합니다. 실제 대학이나 교육과정 자료가 아닙니다.

```sh
python3 apps/api/app/scripts/seed_dev.py
```

이후 터미널 두 개에서 각각 실행합니다.

```sh
ROADMAP_INSECURE_LOCAL_COOKIE=1 apps/api/.venv/bin/python apps/api/app/main.py
```

```sh
cd apps/web
npm ci
npm run dev
```

http://localhost:3000 에서 새 계획을 만들거나 이어서 작성할 수 있습니다. 최초 실행 시 `apps/api/var/roadmap.sqlite3`에 마이그레이션이 적용됩니다. 입력은 이 파일에 보관되므로 삭제하지 않으면 서버 재시작 후에도 유지됩니다. 세션은 30일 동안 유효하며 쿠키 삭제·만료 시 해당 세션의 계획에 다시 접근할 수 없습니다.

## 설정

| 환경변수 | 기본값 | 용도 |
|---|---|---|
| `ROADMAP_DB_PATH` | `apps/api/var/roadmap.sqlite3` | SQLite DB 파일 위치 |
| `ROADMAP_API_HOST` / `ROADMAP_API_PORT` | `127.0.0.1` / `8000` | API 바인드 주소와 포트 |
| `ROADMAP_API_ORIGIN` | `http://127.0.0.1:8000` | Next.js의 서버 측 API 프록시 대상. Next 빌드·실행 환경에 설정 |
| `ROADMAP_APP_ORIGIN` | `http://localhost:3000` | 쓰기 요청의 허용 Origin. 브라우저에서 접근하는 정확한 출처와 일치해야 함 |
| `ROADMAP_INSECURE_LOCAL_COOKIE` | 미설정 | 로컬 HTTP 테스트에서만 `1`로 설정. 기본 쿠키에는 Secure 속성이 적용됨 |
| `ROADMAP_FILE_STORAGE_PATH` | `apps/api/var/files` | 비공개 원본 파일 저장 경로 |
| `ROADMAP_MAX_DOCUMENT_BYTES` / `ROADMAP_MAX_DOCUMENTS` | `10485760` / `10` | 파일당 바이트와 계획당 문서 개수 제한 |
| `ROADMAP_PROXY_MAX_BODY_BYTES` | `11534336` | Next.js 프록시 본문 상한. 파일 크기 제한과 multipart 여유를 합친 값 이상으로 설정 |

세션 토큰은 서버가 안전한 난수로 만들고 DB에는 해시만 저장하므로 별도 서명 비밀키는 사용하지 않습니다. 향후 필요한 비밀은 환경의 비밀 저장소에서 주입하고 저장소에 커밋하지 않습니다. 운영 HTTPS에서는 `ROADMAP_INSECURE_LOCAL_COOKIE`를 설정하지 않습니다. 현재 서버와 SQLite는 로컬 개발용이며 클라우드용 DB 어댑터, 마이그레이션, 파일 저장소, HTTPS 및 배포 구성을 별도로 마련해야 합니다. DB 접근은 `apps/api/app/repositories/p1.py`, 환경 설정은 `apps/api/app/config.py`, 웹 API 주소는 `apps/web/next.config.mjs`에 분리되어 있습니다.

`apps/web`에서 `npm run build`, `npm start`로 프로덕션 빌드를 확인할 수 있습니다. 백엔드 통합 테스트는 저장소 루트에서 `apps/api/.venv/bin/python -m unittest discover -s apps/api/tests/integration -p 'test_*.py' -v`로 실행합니다. 제공된 학교·학과·과목은 직접 만든 가상 개발용 데이터입니다. 문서 업로드와 일반 텍스트 추출을 사용할 수 있습니다. AI 분석은 준비 중입니다. [진행 문서](docs/non-ai-mvp-progress.md)를 참고하세요.

## 문서 처리

PDF, DOCX, UTF-8 TXT를 계획당 최대 10개, 파일당 최대 10MiB까지 업로드할 수 있습니다. PDF는 최대 100페이지, DOCX는 압축 해제 크기 30MiB와 1,000개 항목까지 허용합니다. 추출 텍스트는 최대 100만 문자이며 잘린 경우 일부 추출로 표시합니다. 이 제한들은 처리 안전을 위한 로컬 기본값입니다.

원본은 `ROADMAP_FILE_STORAGE_PATH` 아래 서버가 만든 식별자 이름으로 비공개 저장하고, 텍스트·위치와 버전은 SQLite에 보관합니다. 서버 시작 시 함께 실행되는 로컬 워커가 대기 작업과 삭제 정리를 처리하며, 중단된 작업은 lease 만료 후 재개합니다. 이미지·스캔의 OCR은 제공하지 않습니다. 일부 문서에서 이미지, 머리글·바닥글, 각주나 포함 개체 등은 읽히지 않을 수 있으며 확인된 제한은 화면에 표시합니다. 문서를 삭제하면 즉시 목록에서 제외하고 원본과 추출 이력을 정리합니다. 정리 실패는 기록되어 재시도합니다.

## 외부 자료 수집: 내부 fixture 검증

현재 실제 채용·공모전·대외활동 출처와 접근 정책은 정해지지 않았습니다. 연결된 운영 사이트와 네트워크 수집 기능은 없으며, 다음 명령은 가상 도메인 `fixtures.invalid`과 저장소 안의 가상 데이터만 사용합니다. 사용자 화면이나 공개 API에서 수집을 실행하지 않습니다.

```sh
apps/api/.venv/bin/python apps/api/app/scripts/external_collect.py init-fixtures
apps/api/.venv/bin/python apps/api/app/scripts/external_collect.py enqueue fixture-jobs --fixture-set v1 --job-key example-1
apps/api/.venv/bin/python apps/api/app/scripts/external_collect.py work --drain
apps/api/.venv/bin/python apps/api/app/scripts/external_collect.py inspect fixture-jobs
```

`enqueue`가 반환한 작업 ID는 `status <작업 ID>`로 조회하고, 실패 또는 부분 작업은 `retry <작업 ID>`로 다시 대기시킨 뒤 `work`를 실행합니다. 같은 출처·작업 키·범위의 재등록은 기존 작업을 반환하며, 같은 키에 다른 범위를 사용하면 거부합니다. `work`는 기본적으로 한 건, `--drain`은 대기 중인 전체 작업을 처리하고 실패한 작업이 있으면 종료 코드 1을 반환합니다. 실행 중 중단된 작업은 120초 점유 기한이 지난 뒤 다음 `work`에서 다시 처리됩니다.

다른 fixture 출처는 `fixture-activities`, `fixture-pdf`입니다. `fixture-jobs`의 `--fixture-set`은 `v1`, `v2`, `empty`, `partial`, `failure`를 지원합니다. PDF는 페이지별 일반 텍스트만 추출하며 명시 필드를 자동 분류하지 않아 작업 상태가 부분 확보로 남습니다. HTML fixture는 제목·문단·목록 태그의 명시 필드만 보관합니다. fixture 원문은 건당 2MiB, 작업당 100건으로 제한하고 PDF는 100페이지까지 읽습니다. 기한·시간대나 조건이 불명확하면 추정하지 않습니다. 실제 출처를 연결하려면 해당 기관의 공식 접근 방식과 이용 조건·범위·요청 제한을 확인하고 별도 어댑터와 설정을 구현해야 합니다.
