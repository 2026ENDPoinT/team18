# Page help screenshots and browser regression

`apps/web/public/help/*.png` contains ten distinct captures of `#main-content` in the actual `apps/web` application, made in Chromium at a 1440×900 viewport. These are not rendered mockups or generated illustrations. Each image was visually inspected. The same fictional student, 민서, is used throughout: 한빛대학교 (예시) 컴퓨터공학과, a data-analysis goal, two completed courses, and an event-registration project. The help dialog explicitly labels the school, document, analysis and recommendation as fictional examples.

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

The capture pass writes the images. The second pass loads all ten images from the application and exercises native dialog dismissal, focus containment/return, zoom, preserved drafts/selections/tabs, image-error recovery, input save retries, full desktop/mobile workflows, goal-only activities, document skip and zero selected courses. It also injects changed metadata into saved/partial responses to check that removed rendering areas stay absent. Both passes use 1440×900 and 390×844.

`p5-flow.mjs` is a compatibility entry for the maintained `intake-flow.mjs`; the earlier unauthenticated P5 contract is retired.

Other maintained regressions: `intake-flow.mjs` with `intake_ui_server.py`, `explore-flow.mjs` and `dashboard-flow.mjs` with `explore_ui_server.py`, and `review-fixes.mjs` with `review_fixes_ui_server.py`. `roadmaps.mjs` and `tests/browser/activities.mjs` are browser-only API fixtures. An actual external-provider end-to-end check is separate from these tests.

## Verification scope

- Real local UI and API: anonymous plan creation/resume, department catalog reads (zero/one/multiple), delayed-response protection, TXT upload/extraction, course selection and confirmation, zero-course confirmation, experience answer persistence, career PATCH, saved roadmap reads and task progress. SQLite contains only disposable test data.
- Browser-controlled failure cases: network save failure/retry, changed metadata, image 404/retry and provider-error rendering. Concurrent plan/course changes use the real API conflict checks.
- Simulated external services: Supabase sessions/OAuth responses, Gemini outputs, Google Vision OCR results, Himalayas postings and ContestKorea activities. No live external-provider success claim is made. OCR orchestration and document parsing still run through the real API.
- Regression suites: `help-flow`, `intake-flow` (also the `p5-flow` entry), `explore-flow`, `dashboard-flow`, `review-fixes`, `guest-flow`, `stepup-ui`, `roadmaps`, and `tests/browser/activities.mjs`.
- Unit checks: 38 web tests, including ten distinct PNG assets and safe student-facing error messages. API regression checks: 19 tests across project experience, job-skill analysis and roadmap integrations. Frontend production build also completes.

The main help flow runs both 1440×900 and 390×844. The intake regression additionally checks 320px layout, real 409 conflicts, upload/OCR orchestration and extracted-text modal focus return. The help test inspects closed disclosures as well as visible text so removed internal metadata cannot reappear merely by expanding a section.

## Current desktop UI regression

The course help example uses the small fictional catalog from `help_ui_server.py`
and shows the four year tables in the selection confirmation dialog.

With the same fixture API and Next server running, check the current desktop flow:

```sh
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs P5_BROWSER=/path/to/chromium node apps/web/tests/e2e/ui-polish.mjs
```

This uses a 1280×720 desktop viewport. It checks required-field feedback, whole-row
toggling, year/semester selection, search-hidden selections, reversals while saving,
reload persistence, dialog focus restoration, ordered result navigation, and reuse
of the saved result without fetching result history or starting another analysis.
