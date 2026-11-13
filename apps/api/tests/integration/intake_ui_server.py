"""Disposable intake browser QA: real routes/SQLite/catalog, fake Google OCR only.

Run: python tests/integration/intake_ui_server.py
Next dev: ROADMAP_API_ORIGIN=http://127.0.0.1:18083, port 15103.
Browser auth uses the same synthetic Supabase session as stepup-ui.mjs.
"""
from contextlib import closing
from datetime import date
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch

with tempfile.TemporaryDirectory(prefix='team18-intake-ui-') as tmp:
    os.environ.update(PYTHON_DOTENV_DISABLED='1', ROADMAP_DB_BACKEND='sqlite',
        ROADMAP_DB_PATH=str(Path(tmp) / 'ui.db'), ROADMAP_FILE_STORAGE_PATH=str(Path(tmp) / 'files'),
        ROADMAP_AUTO_SEED_DEV='0', ROADMAP_APP_ORIGIN=os.environ.get('UI_TEST_ORIGIN', 'http://localhost:15103'),
        ROADMAP_INSECURE_LOCAL_COOKIE='1', ROADMAP_OCR_PROVIDER='google_vision',
        GOOGLE_APPLICATION_CREDENTIALS='/nonexistent/intake-test.json',
        GEMINI_API_KEY='', SUPABASE_URL='', SUPABASE_SECRET_KEY='', RENDER='false')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'unit'))
    from app.main import app
    from repositories.plans import connect, migrate
    from test_document_ocr import pdf, docx, TEXT
    from fastapi.responses import Response
    from google.cloud import vision
    import uvicorn

    vision.ImageAnnotatorClient = Mock(side_effect=AssertionError('No paid Google calls in QA'))
    migrate()
    fixture = json.loads((Path(__file__).parents[1] / 'fixtures' / 'seoultech_cse_2026_catalog.json').read_text())
    with closing(connect()) as db:
        db.execute('INSERT INTO universities VALUES(?,?,1)', ('seoultech', '서울과학기술대학교'))
        for did, name in [('seoultech-cse', '컴퓨터공학과'), ('qa-none', '목록 없는 검증 학과'), ('qa-many', '복수 목록 검증 학과')]:
            db.execute('INSERT INTO departments VALUES(?,?,?,1)', (did, 'seoultech', name))
        db.execute('INSERT INTO universities VALUES(?,?,1)', ('qa-university', '검증용 다른 학교'))
        db.execute('INSERT INTO departments VALUES(?,?,?,1)', ('qa-other', 'qa-university', '다른 학교 학과'))
        for cid, did, year in [('seoultech-cse-2026-major-v1', 'seoultech-cse', date.today().year),
                               ('qa-previous', 'qa-many', date.today().year - 1),
                               ('qa-current', 'qa-many', date.today().year),
                               ('qa-future', 'qa-many', date.today().year + 1)]:
            db.execute('INSERT INTO course_catalogs VALUES(?,?,?,?,?,?,?,?,?,NULL,1)',
                (cid, did, year, f'{year}학년도 검증 목록', '변경된 출처 안내 문자열: 68개 행 비노출 검증',
                 'complete', '변경된 출처 이름', None, '2099-12-31T00:00:00Z'))
        for row in fixture['courses']:
            db.execute('INSERT INTO courses(course_id,university_id,canonical_name) VALUES(?,?,?)',
                (row['course_id'], 'seoultech', row['course_name']))
            db.execute('INSERT INTO catalog_courses(catalog_id,course_id,course_name,course_code,credits,category,recommended_year,recommended_term) VALUES(?,?,?,?,?,?,?,?)',
                ('seoultech-cse-2026-major-v1', *(row[k] for k in ['course_id','course_name','course_code','credits','category','recommended_year','recommended_term'])))
        db.commit()

    @app.get('/api/intake-qa/scan.pdf')
    def scan(): return Response(pdf(['scan']), media_type='application/pdf')

    @app.get('/api/intake-qa/image.docx')
    def image_doc(): return Response(docx(images=True, text=True), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    provider = Mock(detect=Mock(return_value={'text': TEXT, 'segments': []}))
    with patch('services.document_ocr.availability', return_value=None), patch('services.document_ocr.GoogleVisionOCR', return_value=provider):
        uvicorn.run(app, host='127.0.0.1', port=18083)
