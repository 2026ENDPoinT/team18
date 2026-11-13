"""Disposable real API/SQLite/files/parser server for document-upload E2E."""
import os
from pathlib import Path
import sys
import tempfile
import time

temporary = tempfile.TemporaryDirectory(prefix='team18-document-upload-ui-')
os.environ.update(PYTHON_DOTENV_DISABLED='1', ROADMAP_DB_BACKEND='sqlite',
    ROADMAP_DB_PATH=str(Path(temporary.name) / 'test.db'),
    ROADMAP_FILE_STORAGE_PATH=str(Path(temporary.name) / 'files'),
    ROADMAP_AUTO_SEED_DEV='0', ROADMAP_APP_ORIGIN='http://localhost:15115',
    ROADMAP_INSECURE_LOCAL_COOKIE='1', ROADMAP_OCR_PROVIDER='none', RENDER='false')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.main import app
from api.routes import documents
from providers.document_storage import LocalDocumentStorage
from worker import documents as worker


class TestStorage(LocalDocumentStorage):
    failed_once = False
    def save(self, key, data):
        time.sleep(.25)  # Make per-file pending UI observable.
        if data == b'UPLOAD_FAIL_ONCE' and not self.failed_once:
            self.failed_once = True
            raise OSError('fixed one-time storage failure')
        super().save(key, data)


storage = TestStorage()
documents.get_storage = lambda: storage
worker.get_storage = lambda: storage
real_extract = worker.extract


def extract(extension, data, **kwargs):
    if data == b'EXTRACTION_FAIL':
        raise ValueError('fixed extraction failure')
    return real_extract(extension, data, **kwargs)


worker.extract = extract

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(app, host='127.0.0.1', port=18095)
    finally:
        temporary.cleanup()
