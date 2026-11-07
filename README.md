# 대학생 개인화 진로 로드맵

P0 스켈레톤 웹앱입니다. AI 키와 DB 없이 실행할 수 있습니다. Node.js 20.9 이상과 Python 3이 필요합니다.

터미널 두 개에서 각각 실행합니다.

```sh
python3 apps/api/app/main.py
```

```sh
cd apps/web
npm ci
npm run dev
```

브라우저에서 http://localhost:3000 을 엽니다. API 상태는 http://localhost:3000/api/health 에서 확인합니다. 프로덕션 빌드는 `apps/web`에서 `npm run build`, 실행은 `npm start`입니다.

입력값은 화면 이동 중에만 메모리에 유지됩니다. 새로고침 또는 탭을 닫으면 사라지며, 서버·DB에 저장되지 않습니다. 업로드, 과목 기준 자료, 분석 및 추천은 아직 제공하지 않습니다. 상세 상태는 [진행 문서](docs/non-ai-mvp-progress.md)를 참고하세요.
