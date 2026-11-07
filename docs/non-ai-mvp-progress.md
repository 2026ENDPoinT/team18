# Non-AI MVP 진행 상태

## P1 완료 범위

- 서버가 익명 세션을 발급하고 토큰의 SHA-256 해시와 만료 시각을 저장한다. 쿠키는 HttpOnly·SameSite=Strict이며 Secure가 기본값이다. 로컬 HTTP에서만 명시적으로 Secure를 끌 수 있다. 쓰기 요청은 허용 Origin도 검사한다.
- `POST /api/roadmap-inputs`, `GET /api/roadmap-inputs/resume`, `GET /api/roadmap-inputs/{request_id}`, `PATCH /api/roadmap-inputs/{request_id}`를 구현했다. 브라우저는 Next.js의 `/api` 프록시를 사용한다. `GET /api/reference`는 선택 가능한 학교·학과·목록 기준 자료를 제공한다.
- 계획 생성·이어 쓰기와 기본 정보 저장·복원을 DB와 연결했다. 데이터 접근마다 세션 소유자를 확인하고, 잘못된 입력은 422, 오래된 입력 버전은 409로 처리한다. 실제 변경이 있을 때만 전체 버전을 올리고, 학교·학과·목록 변경 시 선택 버전 증가와 확인 해제를 함께 수행한다.
- 최초 마이그레이션 `apps/api/migrations/001_p1.sql`은 `session_owners`, `roadmap_inputs`, `universities`, `departments`, `course_catalogs`를 만든다. SQLite 어댑터와 실행 환경 설정은 분리했다. 실제 기준 데이터는 제공되지 않아 목록이 비어 있다.
- 사용자 입력, 저장 중·완료·실패·충돌 상태는 API 응답을 반영한다. 저장되지 않은 변경은 별도로 안내한다.

## P0 및 확인한 자료

6개 화면과 결과 5탭, 공통 화면 구성 및 API 호출 기반을 유지했다. README, 폴더 구조 문서, 최신 시스템 맵, 학생 입력 데이터 명세 ver.3, 기존 코드와 P0 진행 기록을 확인했다. 저장소와 상위 경로에서 AGENTS.md는 찾지 못했다.

## 검증

- `npm run build`, `npm run check`, Python 컴파일 확인.
- HTTP 통합 테스트: 세션별 조회·수정 차단, Origin 검증, 입력·관계 오류, NULL과 0, 변경 없는 저장, 충돌과 동시 수정, DB 재열기 확인.
- Brave 헤드리스: 계획 없음, 생성·저장, 새로고침 복원, 이어 쓰기 및 쿠키 속성 확인.
- 별도 API 프로세스를 종료하고 같은 SQLite 파일로 재시작한 후 저장된 계획과 버전 복원 확인.

## P2 인계 및 미구현

`course_catalogs`, 계획의 목록 ID, 선택 버전 및 확인 필드는 향후 과목 목록·이수 토글을 위한 확장 지점이다. 기준 데이터 수집·등록, 과목 테이블과 토글 저장·확인 API는 P2 범위다. 문서 업로드·파일 저장, 계정·로그인, AI 분석, 결과 생성과 추천도 미구현이다. 30일 세션 만료나 쿠키 삭제 후 계정 기반 복구는 제공하지 않는다.

현재 SQLite와 표준 라이브러리 HTTP 서버는 로컬 환경을 위한 구현이다. 클라우드 DB·파일 저장소를 사용할 때는 어댑터와 해당 DB 마이그레이션 및 운영 구성이 별도로 필요하며 실제 배포는 수행하지 않았다. API 주소·DB 경로·파일 저장소 예약 경로·Origin·쿠키 및 실행 설정은 환경변수로 분리했다. P1은 별도 비밀키 없이 무작위 세션 토큰을 발급한다.
