"""Local-only fault gates for real browser -> API -> PostgreSQL -> Storage REST.

Requires the disposable DB prepared by test_documents_postgres.py. Storage and
Auth are synthetic; no hosted service or billable OCR is contacted. State lives
in a caller-created temporary directory so SIGKILL/restart preserves evidence.
"""
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import json
import os
import sys
import time

from postgres_test_safety import validate_reset_target

url = validate_reset_target(os.environ.get('ROADMAP_TEST_POSTGRES_URL', ''), os.environ)
root = Path(os.environ['DOCUMENT_RECOVERY_TEST_ROOT']).resolve()
if not str(root).startswith('/private/tmp/team18-recovery-browser-'):
    raise SystemExit('A disposable test directory is required')
os.environ.update(PYTHON_DOTENV_DISABLED='1', ROADMAP_DB_BACKEND='postgres', ROADMAP_DATABASE_URL=url,
    ROADMAP_POSTGRES_DOCUMENTS_ENABLED='1', ROADMAP_AUTO_SEED_DEV='0', ROADMAP_APP_ORIGIN='http://localhost:15115',
    ROADMAP_OCR_PROVIDER='none', RENDER='false')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app import main
from api.routes import documents as routes
from providers.document_storage import LocalDocumentStorage, SupabaseDocumentStorage
from repositories.documents import DocumentRepository
from worker import documents as worker
from postgres_auth_fixture import PostgresTestAuth

auth = PostgresTestAuth().start()
user_file = root / 'user.txt'
if user_file.exists():
    user = user_file.read_text(); auth.users.add(user)
else:
    user = auth.headers()['Authorization'].removeprefix('Bearer '); user_file.write_text(user)


def gate(stage):
    (root / ('entered-' + stage)).touch()
    deadline = time.monotonic() + 45
    while not (root / ('release-' + stage)).exists():
        if time.monotonic() > deadline: raise TimeoutError('test gate timed out')
        time.sleep(.02)


files = LocalDocumentStorage(root / 'objects')


class StorageREST(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, status, data):
        self.send_response(status); self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if '/bucket/' in self.path: return self.reply(200, b'{"public":false}')
        key = self.path.rsplit('/', 1)[-1]
        try: content = files.read(key)
        except FileNotFoundError: return self.reply(404, b'{"statusCode":"404"}')
        self.reply(200, b'{}' if '/info/' in self.path else content)
    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        key = self.path.rsplit('/', 1)[-1]
        if data == b'gate:storage': gate('storage')
        files.save(key, data)
        self.reply(200, b'{}')
    def do_DELETE(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        for key in body['prefixes']: files.delete(key)
        self.reply(200, b'[]')


http = ThreadingHTTPServer(('127.0.0.1', 0), StorageREST)
Thread(target=http.serve_forever, daemon=True).start()
storage = SupabaseDocumentStorage('https://synthetic-storage.invalid', 'sb_secret_synthetic', 'private-test')
# Test-only loopback transport; exercise the actual private-bucket, POST, GET,
# exact-key DELETE and deletion verification code without a cloud account.
storage.url = f'http://127.0.0.1:{http.server_port}/storage/v1'
real_save = storage.save


def save(key, data, mime):
    if data == b'gate:reservation': gate('reservation')
    real_save(key, data, mime)


storage.save = save
routes.get_storage = worker.get_storage = lambda: storage
routes.request_work = lambda: None  # Recovery must work through the lifespan worker.
worker.UPLOAD_LEASE_SECONDS = routes.UPLOAD_LEASE_SECONDS = 3
worker.LEASE_SECONDS = 3
real_create = DocumentRepository.create


def create(self, key, rid, filename, *args):
    if filename == 'before-db.txt': gate('db')
    return real_create(self, key, rid, filename, *args)


DocumentRepository.create = create
real_extract = worker.extract


def extract(extension, data, **kwargs):
    if data == b'gate:ocr': gate('ocr')
    return real_extract(extension, data, **kwargs)


worker.extract = extract


class SyntheticOCR:
    def detect(self, data):
        assert data.startswith(b'\x89PNG')
        gate('ocr-service')
        return {'text': '제가 Python으로 프로젝트 API를 구현했습니다.', 'segments': []}


real_ocr = worker.DocumentOCR


def document_ocr(row, token, check, provider=None):
    # Exercise the real durable OCR ledger/cache; only the external Google call
    # is replaced. Injected providers cannot instantiate a Google API client.
    return real_ocr(row, token, check, provider=SyntheticOCR())


worker.DocumentOCR = document_ocr


@main.app.get('/__test__/config')
def config(): return {'user': user}


@main.app.post('/__test__/new-user')
def new_user():
    global user
    user = auth.headers()['Authorization'].removeprefix('Bearer ')
    user_file.write_text(user)
    return {'user': user}


@main.app.get('/__test__/scan')
def scan():
    from fastapi.responses import Response
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'unit'))
    from test_document_ocr import pdf
    return Response(pdf(['scan']), media_type='application/pdf')


@main.app.get('/__test__/audit/{rid}')
def audit(rid: str):
    with closing(worker.connect()) as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM document_upload_reservations WHERE request_id=?', (rid,)).fetchall()]
        documents = [dict(row) for row in DocumentRepository(db).list_active(rid)]
        units = [dict(row) for row in db.execute('''SELECT u.status FROM document_ocr_units u
            JOIN project_documents d ON d.document_id=u.document_id WHERE d.request_id=?''', (rid,)).fetchall()]
    return {'uploads': rows, 'documents': documents,
            'ocr_units': units,
            'objects': [row['storage_key'] for row in rows if files.path(row['storage_key']).exists()]}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(main.app, host='127.0.0.1', port=18095)
