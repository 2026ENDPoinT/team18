"""Real local API/SQLite for roadmap-results.mjs; all Gemini entry points forbidden."""
from contextlib import closing
import os
from pathlib import Path
import socket
import tempfile
from unittest.mock import Mock

storage = tempfile.TemporaryDirectory(prefix='team18-results-ui-')
os.environ.update(PYTHON_DOTENV_DISABLED='1', ROADMAP_DB_BACKEND='sqlite',
    ROADMAP_DB_PATH=str(Path(storage.name) / 'test.db'), ROADMAP_FILE_STORAGE_PATH=str(Path(storage.name) / 'files'),
    ROADMAP_AUTO_SEED_DEV='0', ROADMAP_APP_ORIGIN='http://localhost:3000', ROADMAP_INSECURE_LOCAL_COOKIE='1',
    ROADMAP_OCR_PROVIDER='none', GEMINI_API_KEY='', GOOGLE_API_KEY='', RENDER='false', ROADMAP_AI_COOLDOWN_SECONDS='0')

# Prevent accidental outbound calls even if a provider is reintroduced.
original_connect = socket.socket.connect

def local_connect(sock, address):
    if isinstance(address, tuple) and address[0] not in ('localhost', '127.0.0.1', '::1'):
        raise AssertionError('External network forbidden in UI regression')
    return original_connect(sock, address)

socket.socket.connect = local_connect
from roadmap_scenario import RoadmapAPI, DB_COURSE, C, fake_roadmap
from app.main import app
from api import dependencies
from api.routes import activities, job_skill_analysis
from api.domain import COOKIE, Problem
from repositories.plans import connect
from repositories.roadmaps import RoadmapRepository
from services import gemini_roadmap, course_reasons, gemini_jobs
from services.roadmap_generation import capture_basis, model_input, validate_result

case = RoadmapAPI()
case.setUp()
with closing(connect()) as db:
    sentence = 'SQL을 활용한 데이터 조회 및 집계를 학습한다.'
    db.execute('UPDATE catalog_courses SET description_text=? WHERE catalog_id=? AND course_id=?', (sentence, C, DB_COURSE))
    db.execute('INSERT INTO catalog_course_keywords(catalog_id,course_id,keyword,keyword_role,evidence_text) VALUES(?,?,?,?,?)', (C, DB_COURSE, 'SQL', 'learning', sentence))
case.jobs()
with closing(connect()) as db:
    basis = capture_basis(db, db.execute('SELECT * FROM roadmap_inputs WHERE request_id=?', (case.rid,)).fetchone())
    store = RoadmapRepository(db)
    legacy = store.create(case.rid, basis)
    store.finish(case.rid, legacy['run_id'], validate_result(fake_roadmap(model_input(basis)), basis))
    store.update_progress(legacy['run_id'], 'task-1', True, 0)
    db.commit()

spies = {}
for module, function in ((gemini_roadmap, 'generate_roadmap'), (course_reasons, 'generate_course_reasons'),
                         (gemini_jobs, '_generate'), (job_skill_analysis, 'job_skill_analysis')):
    spy = Mock(side_effect=AssertionError('Unexpected Gemini call: ' + function))
    setattr(module, function, spy)
    spies[function] = spy
state = {'activity_failure': False}

def catalog(db, **kwargs):
    if state['activity_failure']:
        raise Problem(503, 'activity_source_unavailable', 'Synthetic activity failure')
    return [], {'status': 'success', 'source': 'contestkorea', 'kind': 'competition', 'collected': 0}

activities.load_catalog = activities.load_contestkorea_catalog = catalog
dependencies.APP_ORIGIN = os.environ.get('ROADMAP_UI_ORIGIN', 'http://localhost:15133')
from app import main
main.APP_ORIGIN = dependencies.APP_ORIGIN

@app.get('/api/results-test-fixture')
def fixture():
    return {'request_id': case.rid, 'legacy_id': legacy['run_id'], 'cookie': case.client.cookies.get(COOKIE),
            'calls': {key: spy.call_count for key, spy in spies.items()}}

@app.post('/api/results-test-state')
def change_state(body: dict):
    state.update(activity_failure=bool(body.get('activity_failure')))
    if body.get('remove_job_snapshot'):
        # Keep old snapshots: change the goal so there is no matching analysis.
        with closing(connect()) as db:
            db.execute('UPDATE roadmap_inputs SET career_goal=?,input_revision=input_revision+1 WHERE request_id=?',
                       ('SQL 학습을 새롭게 시작하고 싶어요.', case.rid))
    return state

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('ROADMAP_UI_PORT', '18133')))
    finally:
        case.doCleanups()
        storage.cleanup()
