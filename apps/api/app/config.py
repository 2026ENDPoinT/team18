"""Runtime configuration. No cloud credentials or external services are required."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get('ROADMAP_DB_PATH', ROOT / 'var' / 'roadmap.sqlite3'))
APP_ORIGIN = os.environ.get('ROADMAP_APP_ORIGIN', 'http://localhost:3000').rstrip('/')
SECURE_COOKIE = os.environ.get('ROADMAP_INSECURE_LOCAL_COOKIE') != '1'
# Reserved for a future document-storage provider; P1 does not read or write files here.
FILE_STORAGE_PATH = Path(os.environ.get('ROADMAP_FILE_STORAGE_PATH', ROOT / 'var' / 'files'))

API_HOST = os.environ.get('ROADMAP_API_HOST', '127.0.0.1')
API_PORT = int(os.environ.get('ROADMAP_API_PORT', '8000'))
