"""Runtime configuration. No cloud credentials or external services are required."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get('ROADMAP_DB_PATH', ROOT / 'var' / 'roadmap.sqlite3'))
APP_ORIGIN = os.environ.get('ROADMAP_APP_ORIGIN', 'http://localhost:3000').rstrip('/')
SECURE_COOKIE = os.environ.get('ROADMAP_INSECURE_LOCAL_COOKIE') != '1'
# Private local document storage; replace its adapter for other storage providers.
FILE_STORAGE_PATH = Path(os.environ.get('ROADMAP_FILE_STORAGE_PATH', ROOT / 'var' / 'files'))

API_HOST = os.environ.get('ROADMAP_API_HOST', '127.0.0.1')
API_PORT = int(os.environ.get('ROADMAP_API_PORT', '8000'))

MAX_DOCUMENT_BYTES = int(os.environ.get('ROADMAP_MAX_DOCUMENT_BYTES', str(10 * 1024 * 1024)))
MAX_DOCUMENTS = int(os.environ.get('ROADMAP_MAX_DOCUMENTS', '10'))
