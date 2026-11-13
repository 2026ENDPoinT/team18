"""Validate/apply reviewed catalog prose, or render the versioned migration SQL.

This is an explicit data maintenance command, never a server startup hook.
Only recommendation_reason changes; the caller owns the transaction.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
DATA_PATH = APP / 'data/seoultech_cse_2026_recommendation_reasons.json'


def load_data():
    data = json.loads(DATA_PATH.read_text())
    rows = data['courses']
    if len(rows) != 68 or len({row['course_id'] for row in rows}) != len(rows):
        raise ValueError('Expected 68 distinct reviewed course IDs')
    if any(not row['recommendation_reason'].startswith('본 강좌에서는 ') for row in rows):
        raise ValueError('Missing reviewed explanation')
    return data


def validate_catalog(db, data):
    actual = {row['course_id']: (row['course_name'], row['course_code']) for row in db.execute(
        'SELECT course_id,course_name,course_code FROM catalog_courses WHERE catalog_id=?', (data['catalog_id'],))}
    expected = {row['course_id']: (row['course_name'], row['course_code']) for row in data['courses']}
    if actual != expected:
        raise ValueError('Catalog IDs/names/codes differ from the 68 reviewed rows; no update applied')


def apply(db):
    data = load_data()
    validate_catalog(db, data)
    for row in data['courses']:
        db.execute('UPDATE catalog_courses SET recommendation_reason=? WHERE catalog_id=? AND course_id=?',
                   (row['recommendation_reason'], data['catalog_id'], row['course_id']))
    return verify(db)


def verify(db):
    data = load_data()
    validate_catalog(db, data)
    actual = {row['course_id']: row['recommendation_reason'] for row in db.execute(
        'SELECT course_id,recommendation_reason FROM catalog_courses WHERE catalog_id=?', (data['catalog_id'],))}
    expected = {row['course_id']: row['recommendation_reason'] for row in data['courses']}
    if actual != expected:
        raise ValueError('Stored explanations do not exactly match the reviewed seed')
    return len(actual)


def seed_sql(*, postgres=False):
    """Render literal, reviewable values; both backends consume identical text."""
    data = load_data()
    def literal(value):
        return "'" + value.replace("'", "''") + "'"
    rows = ',\n'.join('  (' + ', '.join(literal(row[key]) for key in
        ('course_id', 'course_name', 'course_code', 'recommendation_reason')) + ')' for row in data['courses'])
    table = 'public.catalog_courses' if postgres else 'catalog_courses'
    return f'''WITH authored(course_id, course_name, course_code, reason) AS (VALUES
{rows}
)
UPDATE {table} AS cc SET recommendation_reason = authored.reason
FROM authored
WHERE cc.catalog_id = {literal(data['catalog_id'])}
  AND cc.course_id = authored.course_id
  AND cc.course_name = authored.course_name AND cc.course_code = authored.course_code;
'''


def migration_sql(*, postgres=False):
    header = '-- Generated from app/data/seoultech_cse_2026_recommendation_reasons.json.\n-- Updates only the new display column; no catalog rows or history are replaced.\n'
    if not postgres:
        # SQLite schema_migrations owns one-time ALTER; the UPDATE is repeatable.
        return header + 'ALTER TABLE catalog_courses ADD COLUMN recommendation_reason TEXT;\n' + seed_sql()
    return header + '''ALTER TABLE public.catalog_courses ADD COLUMN IF NOT EXISTS recommendation_reason text;
DO $$
DECLARE
  target_count integer;
  updated_count integer;
BEGIN
  SELECT count(*) INTO target_count FROM public.catalog_courses
    WHERE catalog_id = 'seoultech-cse-2026-major-v1';
  -- A clean installation may import the catalog later and run the explicit seed.
  IF target_count = 0 THEN RETURN; END IF;
  IF target_count <> 68 THEN
    RAISE EXCEPTION 'Expected 68 reviewed catalog rows, found %; no data updated', target_count;
  END IF;
''' + seed_sql(postgres=True) + '''  GET DIAGNOSTICS updated_count = ROW_COUNT;
  IF updated_count <> 68 THEN
    RAISE EXCEPTION 'Catalog IDs/names/codes differ from the reviewed 68 rows; no data updated';
  END IF;
END $$;
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true', help='Read-only exact catalog/seed verification')
    group.add_argument('--apply', action='store_true', help='Update only existing reviewed rows')
    group.add_argument('--render', choices=('sqlite', 'postgres'), help='Print migration SQL without connecting')
    args = parser.parse_args()
    if args.render:
        print(migration_sql(postgres=args.render == 'postgres'), end='')
    else:
        from repositories.plans import connect
        with closing(connect()) as db:
            db.execute('BEGIN')
            try:
                count = apply(db) if args.apply else verify(db)
                db.commit()
            except Exception:
                db.execute('ROLLBACK')
                raise
        print(f'Verified {count}/68 fixed course explanations')
