"""Run the batch scenarios only against the explicitly authorized disposable local DB."""
import os
from pathlib import Path
import sys
import unittest
import psycopg
from postgres_test_safety import validate_reset_target

url = validate_reset_target(os.environ.get('ROADMAP_TEST_POSTGRES_URL', ''), os.environ)
root = Path(__file__).resolve().parents[4]
with psycopg.connect(url, hostaddr='127.0.0.1', autocommit=True) as db:
    if db.info.dbname != 'team18_document_test' or db.execute("SELECT to_regnamespace('supabase_migrations')").fetchone()[0] is not None:
        raise SystemExit('Refusing to reset a non-test or Supabase database.')
    db.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
    db.execute('CREATE SCHEMA IF NOT EXISTS auth; CREATE TABLE IF NOT EXISTS auth.users(id uuid PRIMARY KEY)')
    db.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
    END $$""")
    for migration in sorted((root / 'supabase/migrations').glob('*.sql')):
        with db.transaction(): db.execute(migration.read_text())

os.environ.update(ROADMAP_DB_BACKEND='postgres', ROADMAP_DATABASE_URL=url,
                  ROADMAP_INSECURE_LOCAL_COOKIE='1', ROADMAP_APP_ORIGIN='http://localhost:3000')
from roadmap_batch_scenario import BatchAPI
from activity_reasons_scenario import ActivityReasonAPI
from fixed_course_reasons_scenario import FixedReasonAPI

suite = unittest.TestSuite(BatchAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(BatchAPI) if name.startswith('test_batch_'))
suite.addTests(ActivityReasonAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(ActivityReasonAPI) if name.startswith('test_activity_'))
suite.addTests(FixedReasonAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(FixedReasonAPI) if name.startswith('test_fixed_'))
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
