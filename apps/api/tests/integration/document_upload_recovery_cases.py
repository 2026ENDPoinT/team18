"""Shared SQLite/PostgreSQL fault injection against the real API/repository."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Event
from unittest.mock import patch
import time
import uuid

from repositories.documents import DocumentRepository
from repositories.postgres import StorageUnavailable


def verify_recovery(client, routes, worker, storage):
    headers = {'Origin': 'http://localhost:3000'}
    rid = client.post('/api/roadmap-inputs', headers=headers).json()['request_id']
    path = f'/api/roadmap-inputs/{rid}/documents'
    def state(*ids):
        response = client.get(path, params={'upload_ids': ','.join(ids)})
        assert response.status_code == 200, response.text
        return response.json()
    def send(name, upload_id, content=b'project', revision=None):
        revision = state()['input_revision'] if revision is None else revision
        return client.post(path, headers={**headers, 'Idempotency-Key': upload_id},
            data={'expected_input_revision': str(revision)}, files={'file': (name, content)})
    def fresh(): return str(uuid.uuid4())
    def expire(key, age=-1):
        with closing(worker.connect()) as db:
            db.execute('UPDATE document_upload_reservations SET expires_at=? WHERE storage_key=?', (worker.later(age), key))
    def reservation(upload_id):
        with closing(worker.connect()) as db:
            return dict(DocumentRepository(db).upload_by_id(rid, upload_id))
    def clean():
        while worker.cleanup_reservation(storage): pass
    def save(key, content):
        if routes.DB_BACKEND == 'postgres': storage.save(key, content, 'text/plain; charset=utf-8')
        else: storage.save(key, content)
    def exists(key):
        try: storage.read(key); return True
        except (OSError, KeyError): return False

    entered, release = Event(), Event()
    real_save = storage.save
    def slow_save(*args):
        entered.set()
        assert release.wait(10)
        return real_save(*args)
    first = fresh()
    with patch.object(storage, 'save', slow_save), ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(send, 'live.txt', first)
        try:
            assert entered.wait(5)
            current = state(first)
            assert current['documents'] == []
            assert current['uploads'][0]['status'] == 'uploading'
            assert send('live.txt', first, revision=0).status_code == 202
            assert send('live.txt', first, b'different', revision=0).json()['error'] == 'idempotency_conflict'
            assert send('LIVE.TXT', fresh(), revision=0).json()['error'] == 'duplicate_filename'
            clean()
            assert reservation(first)['cleanup_attempts'] == 0
        finally: release.set()
        result = future.result()
        assert result.status_code == 201, result.text
    did = result.json()['document']['document_id']
    before = state(first)
    repeated = send('live.txt', first, revision=0)
    assert repeated.status_code == 200 and repeated.json()['document']['document_id'] == did
    assert state()['input_revision'] == before['input_revision']
    assert state(first)['uploads'][0]['status'] == 'registered'
    assert len(state()['documents']) == 1

    # Defensive cleanup with inconsistent legacy metadata never deletes a DB key.
    with closing(worker.connect()) as db:
        db.execute('UPDATE document_upload_reservations SET committed_at=NULL,expires_at=? WHERE storage_key=?', (worker.later(-1), did))
    clean()
    assert exists(did)
    assert state(first)['uploads'][0]['status'] == 'registered'
    with closing(worker.connect()) as db: DocumentRepository(db).finish_reservation(did, worker.timestamp())

    if routes.DB_BACKEND == 'postgres':
        # A lost COMMIT acknowledgement is different from a rollback. The
        # error-path release and later cleanup must preserve the committed file.
        from repositories.postgres import PostgresConnection
        real_commit = PostgresConnection.commit
        ambiguous_id = fresh()
        def ambiguous_commit(db):
            created = db.execute('''SELECT 1 FROM project_documents d JOIN document_upload_reservations r
                ON r.storage_key=d.storage_key WHERE r.request_id=? AND r.upload_id=?''', (rid, ambiguous_id)).fetchone()
            real_commit(db)
            if created: raise StorageUnavailable('injected lost COMMIT response')
        with patch.object(PostgresConnection, 'commit', ambiguous_commit):
            # Explicit revision avoids injecting a failure into a preceding GET.
            result = send('commit-response.txt', ambiguous_id, revision=before['input_revision'])
        assert result.status_code == 503, result.text
        committed_key = reservation(ambiguous_id)['storage_key']
        clean(); assert exists(committed_key)
        repeated = send('commit-response.txt', ambiguous_id, revision=0)
        assert repeated.status_code == 200 and repeated.json()['document']['document_id'] == committed_key

    for stage in ('before_storage', 'after_storage', 'before_db'):
        upload_id = fresh()
        def failing_save(*args):
            if stage == 'after_storage': real_save(*args)
            raise OSError('injected Storage failure')
        target = patch.object(DocumentRepository, 'create', side_effect=StorageUnavailable('injected DB failure')) if stage == 'before_db' else patch.object(storage, 'save', failing_save)
        with target:
            failed = send(stage + '.txt', upload_id)
        assert failed.status_code == 503, failed.text
        failed_key = reservation(upload_id)['storage_key']
        assert state(upload_id)['uploads'][0]['status'] == 'interrupted'
        assert send(stage + '.txt', upload_id).json()['error'] == 'upload_expired'
        clean()
        assert not exists(failed_key) and exists(did)
        # Late ambiguous Storage completion is removed by the retained tombstone.
        save(failed_key, b'late bytes')
        with closing(worker.connect()) as db:
            db.execute('UPDATE document_upload_reservations SET cleanup_lease_until=? WHERE storage_key=?', (worker.later(-1), failed_key))
        clean()
        assert not exists(failed_key)
        assert send(stage + '.txt', fresh()).status_code == 201

    # Longer-than-initial-lease Storage I/O remains valid through server renewal.
    entered.clear(); release.clear(); live = fresh()
    with patch.object(worker, 'UPLOAD_LEASE_SECONDS', .3), patch.object(routes, 'UPLOAD_LEASE_SECONDS', .3), patch.object(storage, 'save', slow_save), ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(send, 'heartbeat.txt', live)
        try:
            assert entered.wait(5)
            time.sleep(.7)
            assert state(live)['uploads'][0]['status'] == 'uploading'
            clean()
        finally: release.set()
        assert future.result().status_code == 201

    # Expiry fences an old writer; it cannot commit after a cleaner claims it.
    entered.clear(); release.clear(); old = fresh()
    with patch.object(storage, 'save', slow_save), ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(send, 'fenced.txt', old)
        try:
            assert entered.wait(5)
            key = reservation(old)['storage_key']; expire(key)
            clean()
            assert state(old)['uploads'][0]['status'] == 'interrupted'
        finally: release.set()
        assert future.result().json()['error'] == 'upload_expired'
    with closing(worker.connect()) as db:
        assert not DocumentRepository(db).has_storage_key(key)
        db.execute('UPDATE document_upload_reservations SET cleanup_lease_until=? WHERE storage_key=?', (worker.later(-1), key))
    clean(); assert not exists(key)

    # A dead process's reservations neither hold names nor capacity. Active
    # reservations do hold the tenth slot. No explicit cleanup request required.
    dead = fresh(); dead_key = fresh()
    with closing(worker.connect()) as db:
        DocumentRepository(db).reserve_upload(dead_key, rid, worker.timestamp(), worker.later(-1), 'dead.txt', dead, 'digest', fresh())
    assert state(dead)['uploads'][0]['status'] == 'interrupted'
    assert send('dead.txt', fresh()).status_code == 201
    while len(state()['documents']) < 9:
        assert send(f"fill-{len(state()['documents'])}.txt", fresh()).status_code == 201
    entered.clear(); release.clear()
    with patch.object(storage, 'save', slow_save), ThreadPoolExecutor(max_workers=2) as pool:
        last = pool.submit(send, 'tenth.txt', fresh())
        try:
            assert entered.wait(5)
            assert send('overflow.txt', fresh()).json()['error'] == 'file_limit'
        finally: release.set()
        assert last.result().status_code == 201
    assert len(state()['documents']) == 10
    assert send('eleventh.txt', fresh()).json()['error'] == 'file_limit'

    # New worker instance resumes abandoned extraction and cleanup without HTTP.
    with closing(worker.connect()) as db:
        db.execute("UPDATE project_documents SET extraction_lease_token='dead-worker',extraction_lease_until=? WHERE request_id=? AND extraction_status='pending'", (worker.later(-1), rid))
    stop, thread = worker.start_worker()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with closing(worker.connect()) as db:
                unfinished = db.execute("SELECT count(*) AS n FROM project_documents WHERE request_id=? AND extraction_status='pending'", (rid,)).fetchone()['n']
                cleaned = DocumentRepository(db).upload_by_id(rid, dead)['cleanup_attempts']
            if unfinished == 0 and cleaned: break
            time.sleep(.05)
        assert unfinished == 0 and cleaned
    finally: stop.set(); thread.join(5)
    assert all(d['extraction_status'] == 'ready' for d in state()['documents'])

    # Tombstones are bounded; registered documents remain forever untouched.
    expire(dead_key, -8 * 86400)
    with closing(worker.connect()) as db:
        db.execute('UPDATE document_upload_reservations SET cleanup_lease_until=? WHERE storage_key=?', (worker.later(-1), dead_key))
    clean()
    with closing(worker.connect()) as db:
        assert DocumentRepository(db).upload_by_id(rid, dead) is None
    assert exists(did) and len(state()['documents']) == 10
    print('upload recovery: identity, leases, interruption, cleanup, capacity, restart passed')
