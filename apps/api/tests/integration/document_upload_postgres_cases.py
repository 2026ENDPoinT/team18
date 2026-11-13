"""Extra real PostgreSQL concurrency cases, called by the isolated PG scenario."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import psycopg


def verify_upload_registration(client, store, routes, url, root):
    headers = {'Origin': 'http://localhost:3000'}
    rid = client.post('/api/roadmap-inputs', headers=headers).json()['request_id']
    path = f'/api/roadmap-inputs/{rid}/documents'
    def upload(name, content=b'text', revision=0):
        return client.post(path, headers=headers, data={'expected_input_revision': str(revision)}, files={'file': (name, content)})

    # Store the first request slowly while the second commits first. The plan
    # lock is released during Storage I/O, and reserved names/counts remain held.
    entered, release = Event(), Event()
    original_save = store.save
    def save(key, data, mime):
        if data == b'slow':
            entered.set()
            assert release.wait(10)
        original_save(key, data, mime)

    with patch.object(routes, 'request_work', lambda: None), patch.object(store, 'save', save):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(upload, 'Z-first.txt', b'slow')
            try:
                assert entered.wait(10)
                duplicate = upload('z-FIRST.TXT')
                assert duplicate.status_code == 409, duplicate.text
                assert duplicate.json()['error'] == 'duplicate_filename'
                assert duplicate.json()['filename'] == 'z-FIRST.TXT'
                second = upload('A-second.txt')
                assert second.status_code == 201, second.text
                third = upload('M-third.txt', revision=1)
                assert third.status_code == 201, third.text
            finally:
                release.set()
            first_result = first.result()
            assert first_result.status_code == 201, first_result.text
    saved = client.get(path).json()['documents']
    assert [d['original_filename'] for d in saved] == ['Z-first.txt', 'A-second.txt', 'M-third.txt']
    assert [d['position'] for d in saved] == [1, 2, 3]
    assert saved[0]['created_at'] < saved[1]['created_at'] < saved[2]['created_at']

    # A failed upload immediately releases its reservation, while cleanup still
    # retains the storage key to catch late/ambiguous objects.
    with patch.object(routes, 'request_work', lambda: None):
        store.fail = True
        failed = upload('retry.txt', revision=client.get(path).json()['input_revision'])
        store.fail = False
        assert failed.status_code == 503
        retried = upload('retry.txt', revision=client.get(path).json()['input_revision'])
        assert retried.status_code == 201, retried.text

        # Concurrent distinct reservations cannot exceed the remaining slots.
        entered.clear(); release.clear()
        with patch.object(routes, 'MAX_DOCUMENTS', 5), patch.object(store, 'save', save):
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = pool.submit(upload, 'last-slot.txt', b'slow', client.get(path).json()['input_revision'])
                try:
                    assert entered.wait(10)
                    blocked = upload('overflow.txt', revision=client.get(path).json()['input_revision'])
                    assert blocked.status_code == 422 and blocked.json()['error'] == 'file_limit'
                finally:
                    release.set()
                assert pending.result().status_code == 201

    # Rehearse the additive migration with a pre-existing nameless reservation.
    # The transaction rolls back; historical documents and extraction FKs stay.
    with psycopg.connect(url) as db:
        before = db.execute('SELECT count(*) FROM project_documents').fetchone()[0]
        extractions = db.execute('SELECT count(*) FROM document_extractions').fetchone()[0]
        db.execute('ALTER TABLE document_upload_reservations DROP COLUMN original_filename')
        db.execute("INSERT INTO document_upload_reservations(storage_key, request_id, created_at, expires_at) VALUES ('legacy-reservation', %s, now(), now())", (rid,))
        db.execute((root / 'supabase/migrations/20261113191643_document_upload_filenames.sql').read_text())
        assert db.execute("SELECT original_filename FROM document_upload_reservations WHERE storage_key='legacy-reservation'").fetchone()[0] is None
        assert db.execute('SELECT count(*) FROM project_documents').fetchone()[0] == before
        assert db.execute('SELECT count(*) FROM document_extractions').fetchone()[0] == extractions
        assert db.execute("SELECT relrowsecurity FROM pg_class WHERE oid='public.document_upload_reservations'::regclass").fetchone()[0]
        for role in ('anon', 'authenticated'):
            assert not db.execute("SELECT has_table_privilege(%s, 'public.document_upload_reservations', 'select,insert,update,delete')", (role,)).fetchone()[0]
        db.rollback()

    # Rehearse the recovery migration against populated pre-migration tables.
    # Roll back the rehearsal; no registered document/extraction may be changed.
    with psycopg.connect(url) as db:
        before = db.execute('SELECT count(*) FROM project_documents').fetchone()[0]
        extractions = db.execute('SELECT count(*) FROM document_extractions').fetchone()[0]
        db.execute('ALTER TABLE document_upload_reservations DROP COLUMN upload_id, DROP COLUMN content_sha256, DROP COLUMN upload_lease_token')
        db.execute("INSERT INTO document_upload_reservations(storage_key,request_id,created_at,expires_at) VALUES ('recovery-legacy',%s,now(),now())", (rid,))
        db.execute((root / 'supabase/migrations/20261113193416_document_upload_recovery.sql').read_text())
        assert db.execute("SELECT upload_id,content_sha256,upload_lease_token FROM document_upload_reservations WHERE storage_key='recovery-legacy'").fetchone() == (None, None, None)
        assert db.execute('SELECT count(*) FROM project_documents').fetchone()[0] == before
        assert db.execute('SELECT count(*) FROM document_extractions').fetchone()[0] == extractions
        assert db.execute("SELECT relrowsecurity FROM pg_class WHERE oid='public.document_upload_reservations'::regclass").fetchone()[0]
        for role in ('anon', 'authenticated'):
            assert not db.execute("SELECT has_table_privilege(%s, 'public.document_upload_reservations', 'select,insert,update,delete')", (role,)).fetchone()[0]
        db.rollback()
