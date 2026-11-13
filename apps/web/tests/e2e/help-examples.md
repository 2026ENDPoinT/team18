# Page help examples and browser regression

The eight `apps/web/public/help/*.png` images are captures of the actual Next.js
application with fictional student data. They are refreshed by `help-flow.mjs`,
not drawn mockups. Desktop captures use a 1440×900 viewport: seven capture
`#main-content` (including its full height), and `courses.png` captures the
viewport with the course confirmation dialog open. Help dialogs load the same
images on desktop and mobile.

The examples follow one student, 민서: 한빛대학교 (예시) 컴퓨터공학과, an
event-registration data-analysis goal, two completed courses, and a project
using React, SQL and Python. A teammate owns the Docker work. The dialog labels
all school, document and recommendation content as fictional.

## Reproduce

Install the normal API and web development dependencies. From the repository
root, start the disposable API:

```sh
apps/api/.venv/bin/python apps/api/tests/integration/help_ui_server.py
```

Start Next in `apps/web` with test configuration (browser origin is
`http://localhost:15102`):

```sh
NEXT_TELEMETRY_DISABLED=1 ROADMAP_API_ORIGIN=http://127.0.0.1:18083 NEXT_PUBLIC_SUPABASE_URL=https://job-skills-test.supabase.co NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=test-key npm run dev -- --hostname 127.0.0.1 --port 15102
```

Use an installed Playwright module and Chromium executable. Run from the
repository root, first capturing and then checking the new images through the
actual question-mark buttons:

```sh
CAPTURE_HELP=1 PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/help-flow.mjs
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/help-flow.mjs
node --test apps/web/tests/unit/help-assets.test.mjs
```

Set `HELP_CAPTURE_IDS` to comma-separated help IDs to refresh a subset. Omit it
to refresh all eight. The scenario still runs in full. Diagnostic screenshots
are written to `/tmp/team18-help-artifacts/`.

## Current examples (2026-11-14)

| Help ID | Captured state |
| --- | --- |
| `basic` | Saved goal and target role, with the selected school/department collapsed |
| `documents` | Uploaded project document after extraction is complete |
| `courses` | Four year tables in the confirmation dialog, with two selected courses |
| `review` | Saved React correction, SQL uncertainty, Python no-experience answer, and current selected-answer styling |
| `result-roadmap` | 결과 요약, four current tabs, 재분석, saved courses/skills/activities |
| `result-courses` | Current catalog recommendation text and expanded database learning content |
| `result-skills` | Data Analyst job analysis, SQL demand and the student's project comparison |
| `result-activities` | Saved personalized participation reason, eligibility, deadline and original link |

The review footer now starts generation with **로드맵 만들기**. The scenario
checks this first saved result, explicitly runs **직무 분석 실행**, then uses
**재분석** to save the comparison with the course and activity recommendations.
Tab order is **결과 요약 → 수강 후보 → 직무 역량 비교 → 공모전·대외활동**.
The result examples include no retired execution-task controls.

Course explanations come from the fixture's current catalog text. Activity
reason AI output is a deterministic fixture, but evidence validation and saving
run through the real service. Missing job analysis on initial generation is a
valid state; the final captured result contains the explicitly requested job
analysis and saved activity reason.

## Verification scope

On 2026-11-14, the capture and image-validation passes both passed at the two
viewport sizes below. The eight-image asset test and `git diff --check` also passed.

Both capture and validation passes run at 1440×900 and 390×844. The validation
pass opens all eight question-mark dialogs and checks image loading, image fit,
Escape/close dismissal, focus containment and return, and unchanged drafts,
course selections and selected result tabs. Opening help, switching result tabs
and reloading must not save inputs or start another analysis.

The scenario also checks basic-save and course-confirmation retries, document
extraction and its text dialog, persisted experience corrections, career edits,
changed internal metadata, image 404/retry, document skip, zero selected courses,
goal-only activities, and the document API error state. Asset checks require
eight distinct PNGs with readable source dimensions and alternative text.

The API uses a fresh temporary SQLite database and temporary document storage.
Plan creation, input persistence, parsing, course selection, experience answers,
recommendation filtering and saved result bundles use real local routes.
Authentication, AI responses, job postings and activity catalogs are fixtures;
external networking is blocked by the fixture server. These runs do not verify
live providers or change production data.

Other feature-specific scripts in this directory are separate regressions;
their results are not implied by a successful help refresh. Avoid using older
capture entry points to overwrite these assets without checking their scenario
and labels against the current application.
