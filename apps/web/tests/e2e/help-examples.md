# Page help screenshots and browser regression

`apps/web/public/help/*.png` contains eight distinct captures of `#main-content` in the actual `apps/web` application, made in Chromium at a 1440×900 viewport. These are not rendered mockups or generated illustrations. Each image was visually inspected. The same fictional student, 민서, is used throughout: 한빛대학교 (예시) 컴퓨터공학과, a data-analysis goal, two completed courses, and an event-registration project. The help dialog explicitly labels the school, document, analysis and recommendation as fictional examples.

The disposable `apps/api/tests/integration/help_ui_server.py` runs the real plan/document/course/experience/roadmap APIs and SQLite repository. Its external-network block prevents calls to production services. Authentication, AI generation, job postings and the activity catalog use deterministic fixtures; the uploaded TXT parser and persistence are real. No production credentials or student data are used. The original provider boundaries stay unchanged in production code.

To reproduce, install the normal web and API development dependencies, start the fixture server, and start Next with:

```sh
NEXT_TELEMETRY_DISABLED=1 ROADMAP_API_ORIGIN=http://127.0.0.1:18083 NEXT_PUBLIC_SUPABASE_URL=https://job-skills-test.supabase.co NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=test-key npm run dev -- --hostname 127.0.0.1 --port 15102
```

From the repository root, use an installed Playwright module and Chromium executable:

```sh
CAPTURE_HELP=1 PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/help-flow.mjs
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/help-flow.mjs
node --experimental-vm-modules --test apps/web/tests/unit/*.test.mjs
```

For a production build, set `ROADMAP_API_ORIGIN` to the intended HTTPS API origin; production configuration deliberately rejects an unset or HTTP origin. The isolated build check used `https://api.example.test` and test Supabase configuration without calling those hosts.

The capture pass writes the images. The second pass loads all eight images from the application and exercises native dialog dismissal, focus containment/return, images fitted to the dialog without zoom controls, preserved drafts/selections/tabs, image-error recovery, input save retries, full desktop/mobile workflows, goal-only activities, document skip and zero selected courses. It also injects changed metadata into saved/partial responses to check that removed rendering areas stay absent. Both passes use 1440×900 and 390×844.

`p5-flow.mjs` is a compatibility entry for the maintained `intake-flow.mjs`; the earlier unauthenticated P5 contract is retired.

Other maintained regressions: `intake-flow.mjs` with `intake_ui_server.py`, `explore-flow.mjs` with `explore_ui_server.py`, and `review-fixes.mjs` with `review_fixes_ui_server.py`. `roadmaps.mjs` and `tests/browser/activities.mjs` are browser-only API fixtures. An actual external-provider end-to-end check is separate from these tests.

## Verification scope

- Real local UI and API: anonymous plan creation/resume, department catalog reads (zero/one/multiple), delayed-response protection, TXT upload/extraction, course selection and confirmation, zero-course confirmation, experience answer persistence, career PATCH, saved roadmap reads and task progress. SQLite contains only disposable test data.
- Browser-controlled failure cases: network save failure/retry, changed metadata, image 404/retry and provider-error rendering. Concurrent plan/course changes use the real API conflict checks.
- Simulated external services: Supabase sessions/OAuth responses, Gemini outputs, Google Vision OCR results, Himalayas postings and ContestKorea activities. No live external-provider success claim is made. OCR orchestration and document parsing still run through the real API.
- Regression suites: `help-flow`, `intake-flow` (also the `p5-flow` entry), `explore-flow`, `navigation-no-dashboard`, `review-fixes`, `guest-flow`, `stepup-ui`, `roadmaps`, and `tests/browser/activities.mjs`.
- Unit checks include eight distinct PNG assets and safe student-facing error messages. API regression checks cover project experience, job-skill analysis and roadmap integrations.

The main help flow runs both 1440×900 and 390×844. The intake regression additionally checks 320px layout, real 409 conflicts, upload/OCR orchestration and extracted-text modal focus return. The help test inspects closed disclosures as well as visible text so removed internal metadata cannot reappear merely by expanding a section.

## Current desktop UI regression

The course help example uses the small fictional catalog from `help_ui_server.py`
and shows the four year tables in the selection confirmation dialog.

With the same fixture API and Next server running, check the current desktop flow:

```sh
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/ui-polish.mjs
```

This uses a 1280×720 desktop viewport, plus 390×844 for filtered bulk selection.
It checks required-field feedback, whole-row
toggling, year/semester selection limited to visible search results, reversals while saving,
reload persistence, dialog focus restoration, ordered result navigation, and reuse
of the saved result without fetching result history or starting another analysis.

With the same servers, `navigation-no-dashboard.mjs` checks the sidebar, saved
result link, legacy `/dashboard` redirect, result navigation and resume/retry:

```sh
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/navigation-no-dashboard.mjs
```

For a focused bulk-selection regression, run `course_groups_ui_server.py` with
Next on port 15101 pointing to its API on port 18082, then run:

```sh
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/course-bulk-selection.mjs
```

This uses the grouped catalog and disposable SQLite to verify the `데` search
across years and semesters, partial and complete selection, disabled empty
groups, selected-only filtering, queued saves, hidden selections and reload on
desktop and mobile. The fixture server accepts `COURSE_API_PORT` and
`COURSE_WEB_ORIGIN` to run on different ports.

## Document actions

Run `document_upload_ui_server.py` and Next on port 15115 pointing to its API on
port 18095, then run:

```sh
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/document-page-actions.mjs
```

This checks partial extraction confirmation and retry, the empty/uploaded/failed
document states, and the footer button layout at desktop and mobile widths.

## Basic information summary and save flow

Run `apps/api/tests/integration/basic_ui_server.py` instead of the help fixture
server to test the school/department disclosure. It adds a second fictional
school, multiple catalogs and a department without a catalog to the same real
local API/SQLite setup. Use the Next command above, then run:

```sh
CAPTURE_HELP=1 PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/basic-form.mjs
```

This updates only `public/help/basic.png` from the actual collapsed desktop UI.
Both 1440×900 and 390×844 exercise first visit, selection and collapse, reopening
with selected values, school change without losing the career draft, catalog
reset/automatic attachment, saved catalog restoration, delayed catalog responses,
catalog retry, required-goal focus, save-in-flight navigation blocking, refresh
restoration, school-free saving and both destinations, 503 retry and real 409
conflict handling. The help dialog preserves the draft and returns focus.

Captures and the verification report are written to the ignored
`apps/web/test-results/basic-form/` directory: `desktop-collapsed.png`,
`mobile-expanded.png` (390×844 viewport), `mobile-expanded-full.png` (the entire
scrollable page at that viewport width), and `report.json`. The example uses a
fictional student's running-record analysis goal; no production data is changed.

The result starts with 실행 로드맵 and has four tabs; the retired 준비 상태 tab
and its example are removed. To refresh only the result examples, set
`HELP_CAPTURE_IDS=result-roadmap,result-skills,result-courses,result-activities`
when running `CAPTURE_HELP=1` with `help-flow.mjs`.

## Result overview and retained details

`/result` and `/result?tab=roadmap` open the execution overview. The title and
help button are followed immediately by the four URL-backed tabs. The basic card
shows the saved target role and goal; school/department are intentionally omitted
from the result overview. The lower cards show the first three saved course
recommendations (in server order), the saved analyzed role, and up to three
activities. The course tab retains the full filtered list and learning evidence.
Current completed/reviewed-equivalent course IDs are excluded from both lists.
Below the overview, the execution steps show completion criteria and let the
student save task progress. Old `?tab=readiness` links open this same view.

Visits, tab changes, focus and reload only read saved resources. Activity GETs
read stored catalogs; these paths do not invoke a collector or AI provider.

Run against `help_ui_server.py` and the local Next configuration above:

```sh
CAPTURE_HELP=1 PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node apps/web/tests/e2e/result-overview.mjs
```

This refreshes the four result help PNGs and checks 1440×900 and 390×844 in
Chromium: heading/tab order, active underline, left/right/Home/End keys,
reload/back restoration, the legacy dashboard redirect, activity original links,
per-tab help and focus restoration, independent loading/empty/error states,
goal-only activities, explicit generation/regeneration, saved completion and
historical runs. It saves `프로그래밍 기초` as completed via the real API, and
asserts that the distinct recommended `데이터베이스` and its API reason appear.
External source navigation uses an intercepted destination to verify the exact
returned URL without depending on a fictional example's remote availability.

Captures and actual local API responses are in the ignored
`apps/web/test-results/result-overview/` directory: `result-1440.png`,
`result-390.png`, their `-full.png` versions, `api-responses.json`, and `report.json`.
External authentication, AI output and provider catalogs remain test fixtures;
plan/course persistence and recommendation filtering run through the real API.
