# Non-AI MVP 진행 상태

## P0 완료 범위

- 빈 디렉터리만 있던 저장소에 Next.js 웹앱과 Python 표준 라이브러리 기반 상태 확인 API를 구성했다. AI 키와 DB 연결은 필요하지 않다.
- `/`, `/input/basic`, `/input/documents`, `/input/courses`, `/input/review`, `/result`와 결과 5개 탭을 구현했다. 최신 목업의 흰색·회색 서비스 화면을 기준으로 했으며 목업 편집·시연 도구는 제외했다.
- 진로·학업 입력은 브라우저 메모리에만 유지한다. 새로고침 시 사라지며 저장 성공으로 표시하지 않는다. 문서 업로드와 과목 선택은 비활성화했다.
- API 공통 요청 및 오류 처리 기반과 `GET /api/health`를 마련했다. 이 API는 DB 연결 상태를 나타내지 않는다.

## 확인한 자료와 구조

README, `docs/FOLDER_STRUCTURE.md`, 기획서, 학생 입력 데이터 명세 ver.3, `docs/mockups/career-roadmap-mockup 2.html`, `docs/career-roadmap-system-map.html`을 확인했다. 저장소 및 상위 경로에서 AGENTS.md를 찾지 못했다. 기존에는 실행 코드, 의존성 설정, 기준 데이터 및 DB 스키마가 없었다. 기존 `apps/web`, `apps/api` 구조를 사용한다. 폴더 구조 문서는 Next.js와 Python 계층을 제안하지만 특정 백엔드 프레임워크는 확정하지 않았다.

## 아직 구현하지 않은 기능

영구 저장 및 DB, 계정·인증, 학교·학과·과목 기준 데이터와 이수 확인, 파일 업로드·추출, 분석 확인, AI 호출, 로드맵 생성, 외부 자료 수집과 추천은 구현하지 않았다. 결과는 빈 상태만 표시한다. P1 작업은 포함하지 않는다.

## 실행 및 검증

실행 방법은 저장소 README 참고. 검증 결과는 작업 완료 후 아래에 기록한다.

- `npm run build`: 성공, 6개 경로 정적 생성 확인.
- `npm run check` 및 `python3 -m py_compile apps/api/app/main.py`: 통과.
- 프로덕션 웹 서버와 API 실행 후 6개 경로 HTTP 200, `/api/health` 정상 응답 및 미존재 API 404 확인.
- Brave 헤드리스 브라우저에서 6개 화면의 주요 문구, 결과 5개 탭 전환 및 선택 상태, 기본 정보 화면의 모바일 너비(390px) 가로 넘침 여부 확인.
