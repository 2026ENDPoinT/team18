"""Reviewed data parity and idempotent migrations on disposable databases only."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from scripts.seed_course_reasons import apply, load_data, migration_sql, seed_sql, verify
from repositories.courses import CourseRepository

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = json.loads((ROOT / 'apps/api/tests/fixtures/seoultech_cse_2026_course_evidence.json').read_text())
PG_MIGRATION = ROOT / 'supabase/migrations/20261113230604_course_recommendation_reasons.sql'
SQLITE_MIGRATION = ROOT / 'apps/api/migrations/013_course_recommendation_reasons.sql'


def populate(db, catalog):
    for c in FIXTURE:
        db.execute('INSERT INTO catalog_courses(catalog_id,course_id,course_name,course_code,description_text) VALUES(?,?,?,?,?)',
                   (catalog, c['course_id'], c['course_name'], c['course_code'], c['description_text']))
    db.execute('INSERT INTO catalog_courses(catalog_id,course_id,course_name,course_code,description_text) VALUES(?,?,?,?,?)',
               ('other', FIXTURE[0]['course_id'], FIXTURE[0]['course_name'], 'other', 'unrelated description'))


def snapshot(db):
    return [dict(r) for r in db.execute('SELECT catalog_id,course_id,course_name,course_code,description_text FROM catalog_courses ORDER BY catalog_id,course_id')]


def test_authored_data_exact_mapping_and_checked_in_sql():
    data = load_data()
    assert len(data['courses']) == len(FIXTURE) == 68
    assert [(r['course_id'], r['course_name'], r['course_code']) for r in data['courses']] == [
        (r['course_id'], r['course_name'], r['course_code']) for r in FIXTURE]
    assert len({r['recommendation_reason'] for r in data['courses']}) == 68
    assert SQLITE_MIGRATION.read_text() == migration_sql()
    assert PG_MIGRATION.read_text() == migration_sql(postgres=True)


def test_sqlite_upgrade_and_seed_preserve_other_columns_and_repeat_safely(tmp_path, monkeypatch):
    from repositories import plans
    monkeypatch.setattr(plans, 'DB_PATH', tmp_path / 'test.db')
    plans.migrate()
    with closing(plans.connect()) as db:
        # Recreate just the pre-upgrade catalog shape for an existing installation.
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('DROP TABLE catalog_courses')
        db.execute('CREATE TABLE catalog_courses(catalog_id text,course_id text,course_name text,course_code text,description_text text,PRIMARY KEY(catalog_id,course_id))')
        populate(db, load_data()['catalog_id'])
        db.execute("DELETE FROM schema_migrations WHERE name='013_course_recommendation_reasons.sql'")
        before = snapshot(db)
    plans.migrate()
    plans.migrate()
    with closing(plans.connect()) as db:
        assert verify(db) == 68
        assert snapshot(db) == before
        assert apply(db) == apply(db) == 68
        assert snapshot(db) == before
        assert db.execute("SELECT recommendation_reason FROM catalog_courses WHERE catalog_id='other'").fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM schema_migrations WHERE name='013_course_recommendation_reasons.sql'").fetchone()[0] == 1
        db.execute("UPDATE catalog_courses SET course_code='changed' WHERE course_id=? AND catalog_id=?", (FIXTURE[0]['course_id'], load_data()['catalog_id']))
        with pytest.raises(ValueError, match='no update applied'):
            apply(db)


def test_postgres_migration_seed_and_sqlite_lookup_parity():
    url = os.environ.get('COURSE_TEST_DATABASE_URL')
    if not url:
        pytest.skip('disposable PostgreSQL URL not configured')
    parsed = urlsplit(url)
    assert parsed.hostname in ('localhost', '127.0.0.1') and parsed.path == '/team18_course_test' and not parsed.query
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from repositories.postgres import PostgresConnection
    schema = 'fixed_reasons_' + uuid4().hex
    with psycopg.connect(url, autocommit=True, row_factory=dict_row, hostaddr='127.0.0.1') as pg:
        pg.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            pg.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            pg.execute('CREATE TABLE catalog_courses(catalog_id text,course_id text,course_name text,course_code text,description_text text,PRIMARY KEY(catalog_id,course_id))')
            db = PostgresConnection(pg, psycopg.Error)
            populate(db, load_data()['catalog_id'])
            before = snapshot(db)
            migration = PG_MIGRATION.read_text().replace('public.', schema + '.')
            pg.execute(migration)
            pg.execute(migration)
            assert verify(db) == apply(db) == apply(db) == 68
            assert snapshot(db) == before
            sqlite = sqlite3.connect(':memory:'); sqlite.row_factory = sqlite3.Row
            with closing(sqlite):
                sqlite.execute('CREATE TABLE catalog_courses(catalog_id text,course_id text,course_name text,course_code text,description_text text,PRIMARY KEY(catalog_id,course_id))')
                populate(sqlite, load_data()['catalog_id'])
                sqlite.executescript(SQLITE_MIGRATION.read_text())
                ids = [c['course_id'] for c in FIXTURE]
                assert CourseRepository(db).recommendation_reasons(load_data()['catalog_id'], ids) == CourseRepository(sqlite).recommendation_reasons(load_data()['catalog_id'], ids)
            # Drift aborts the whole statement rather than silently updating 67 rows.
            pg.execute("UPDATE catalog_courses SET course_code='changed' WHERE catalog_id=%s AND course_id=%s", (load_data()['catalog_id'], FIXTURE[0]['course_id']))
            pg.execute('UPDATE catalog_courses SET recommendation_reason=NULL')
            with pytest.raises(psycopg.Error, match='differ from the reviewed'):
                pg.execute(migration)
            assert pg.execute('SELECT count(*) n FROM catalog_courses WHERE recommendation_reason IS NOT NULL').fetchone()['n'] == 0
        finally:
            pg.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
