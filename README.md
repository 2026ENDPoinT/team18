# 대학생 개인화 진로 로드맵

P2 로컬 웹앱입니다. Node.js 20.9 이상과 Python 3이 필요합니다. 별도의 AI 키나 DB 서비스는 필요하지 않습니다.

과목 화면에 사용할 가상 개발용 기준 데이터를 한 번 적재합니다. 실제 대학이나 교육과정 자료가 아닙니다.

```sh
python3 apps/api/app/scripts/seed_dev.py
```

이후 터미널 두 개에서 각각 실행합니다.

```sh
ROADMAP_INSECURE_LOCAL_COOKIE=1 python3 apps/api/app/main.py
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
| `ROADMAP_FILE_STORAGE_PATH` | `apps/api/var/files` | 향후 문서 저장을 위한 예약 설정. P1에서는 사용하지 않음 |

세션 토큰은 서버가 안전한 난수로 만들고 DB에는 해시만 저장하므로 별도 서명 비밀키는 사용하지 않습니다. 향후 필요한 비밀은 환경의 비밀 저장소에서 주입하고 저장소에 커밋하지 않습니다. 운영 HTTPS에서는 `ROADMAP_INSECURE_LOCAL_COOKIE`를 설정하지 않습니다. 현재 서버와 SQLite는 로컬 개발용이며 클라우드용 DB 어댑터, 마이그레이션, 파일 저장소, HTTPS 및 배포 구성을 별도로 마련해야 합니다. DB 접근은 `apps/api/app/repositories/p1.py`, 환경 설정은 `apps/api/app/config.py`, 웹 API 주소는 `apps/web/next.config.mjs`에 분리되어 있습니다.

`apps/web`에서 `npm run build`, `npm start`로 프로덕션 빌드를 확인할 수 있습니다. 백엔드 통합 테스트는 저장소 루트에서 `python3 -m unittest discover -s apps/api/tests/integration -p 'test_*.py' -v`로 실행합니다. 제공된 학교·학과·과목은 직접 만든 가상 개발용 데이터입니다. 문서 업로드와 분석은 준비 중입니다. [진행 문서](docs/non-ai-mvp-progress.md)를 참고하세요.
