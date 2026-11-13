"""Real API/storage/parser regression tests for per-file upload registration."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from api.routes import documents as routes
from providers.document_storage import LocalDocumentStorage
from repositories import plans
from repositories.documents import DocumentRepository
from worker import documents as worker

ORIGIN = {'Origin': 'http://localhost:3000'}
FIXTURES = Path(__file__).resolve().parents[4] / 'docs/test-files'


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(plans, 'DB_PATH', tmp_path / 'documents.db')
    monkeypatch.setattr(main, 'start_worker', lambda: None)
    storage = LocalDocumentStorage(tmp_path / 'files')
    monkeypatch.setattr(routes, 'get_storage', lambda: storage)
    monkeypatch.setattr(worker, 'get_storage', lambda: storage)
    with TestClient(main.app, headers=ORIGIN) as client:
        rid = client.post('/api/roadmap-inputs').json()['request_id']
        yield client, f'/api/roadmap-inputs/{rid}/documents', storage


def upload(client, path, name, content=b'project text', revision=None):
    if revision is None:
        revision = client.get(path).json()['input_revision']
    return client.post(path, data={'expected_input_revision': str(revision)}, files={'file': (name, content)})


def listing(client, path):
    data = client.get(path).json()
    assert [d['position'] for d in data['documents']] == list(range(1, len(data['documents']) + 1))
    return data


def test_formats_order_extraction_delete_and_reupload(service):
    client, path, storage = service
    names = ['project-ready.pdf', 'project-ready.docx', 'project-ready.txt']
    for name in names:
        assert upload(client, path, name, (FIXTURES / name).read_bytes()).status_code == 201
    before = listing(client, path)['documents']
    assert [d['original_filename'] for d in before] == names
    while worker.run_once(storage):
        pass
    after = listing(client, path)['documents']
    assert [d['document_id'] for d in after] == [d['document_id'] for d in before]
    assert all(d['extraction_status'] == 'ready' for d in after)
    for doc in after:
        assert client.get(f"{path}/{doc['document_id']}/extractions/1").json()['extracted_text']
    assert client.request('DELETE', path + '/' + after[1]['document_id'], json={
        'expected_input_revision': listing(client, path)['input_revision']}).status_code == 200
    assert upload(client, path, names[1], (FIXTURES / names[1]).read_bytes()).status_code == 201
    assert [d['original_filename'] for d in listing(client, path)['documents']] == [names[0], names[2], names[1]]


def test_case_insensitive_duplicates_pending_and_repeated_selection(service):
    client, path, _ = service
    assert upload(client, path, 'Report.TXT').status_code == 201
    for name in ['Report.TXT', 'report.txt', 'REPORT.txt']:
        result = upload(client, path, name, b'different content and size')
        assert result.status_code == 409
        assert result.json()['error'] == 'duplicate_filename'
        assert result.json()['filename'] == name
        assert name in result.json()['message']
    assert upload(client, path, 'new.txt').status_code == 201
    assert len(listing(client, path)['documents']) == 2


def test_concurrent_duplicate_only_one_saved(service):
    client, path, _ = service
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda name: upload(client, path, name, revision=0), ['Same.txt', 'same.TXT', 'SAME.txt']))
    assert sorted(r.status_code for r in responses) == [201, 409, 409]
    assert all(r.status_code == 201 or r.json()['error'] == 'duplicate_filename' for r in responses)
    assert len(listing(client, path)['documents']) == 1


def test_names_scoped_to_owned_request(service):
    client, path, _ = service
    assert upload(client, path, 'report.txt').status_code == 201
    rid = client.post('/api/roadmap-inputs').json()['request_id']
    assert upload(client, f'/api/roadmap-inputs/{rid}/documents', 'report.txt').status_code == 201
    with TestClient(main.app, headers=ORIGIN) as other:
        rid = other.post('/api/roadmap-inputs').json()['request_id']
        assert other.get(path).status_code == 404
        assert upload(other, f'/api/roadmap-inputs/{rid}/documents', 'report.txt').status_code == 201


def test_storage_failure_does_not_register_or_block_retry(service, monkeypatch):
    client, path, storage = service
    save = storage.save
    def fail_one(key, data):
        if data == b'fail':
            raise OSError('fixed storage failure')
        save(key, data)
    monkeypatch.setattr(storage, 'save', fail_one)
    assert upload(client, path, 'first.txt').status_code == 201
    assert upload(client, path, 'retry.txt', b'fail').status_code == 503
    assert upload(client, path, 'last.txt').status_code == 201
    assert [d['original_filename'] for d in listing(client, path)['documents']] == ['first.txt', 'last.txt']
    assert upload(client, path, 'retry.txt').status_code == 201


def test_existing_count_size_and_content_validation(service, monkeypatch):
    client, path, _ = service
    policy = listing(client, path)['upload_policy']
    assert policy == {'max_files': 10, 'max_file_bytes': 10485760, 'extensions': ['pdf', 'docx', 'txt', 'md', 'markdown']}
    for name, content in [('image.png', b'bad'), ('binary.txt', b'\xff'), ('empty.txt', b''), ('fake.pdf', b'not a pdf')]:
        assert upload(client, path, name, content).status_code == 422
    monkeypatch.setattr(routes, 'MAX_DOCUMENT_BYTES', 16)
    assert upload(client, path, 'limit.txt', b'x' * 16).status_code == 201
    assert upload(client, path, 'large.txt', b'x' * 17).status_code == 413
    for n in range(9):
        assert upload(client, path, f'{n}.txt').status_code == 201
    assert upload(client, path, 'extra.txt').json()['error'] == 'file_limit'
    assert len(listing(client, path)['documents']) == 10


@pytest.mark.parametrize('filename', ['README.md', 'PROJECT.MD', 'report.markdown'])
def test_markdown_upload_extraction_and_retry(service, filename):
    client, path, storage = service
    text = '# 프로젝트 기록\n\n## 본인 역할\n- Python으로 **데이터 정제**를 구현했습니다.\n\n```python\nprint("완료")\n```\n\n[결과](https://example.com/report)\n'
    response = upload(client, path, filename, text.encode('utf-8-sig'))
    assert response.status_code == 201
    doc = response.json()['document']
    assert doc['original_filename'] == filename
    assert doc['mime_type'] == 'text/plain; charset=utf-8'
    for revision in (1, 2):
        while worker.run_once(storage):
            pass
        current = listing(client, path)
        assert current['analysis_eligible']
        assert current['documents'][0]['extraction_status'] == 'ready'
        extracted = client.get(f"{path}/{doc['document_id']}/extractions/{revision}").json()
        assert extracted['extracted_text'] == text
        assert extracted['segments'] == [{'start': 0, 'end': len(text), 'paragraph': 1}]
        if revision == 1:
            assert client.post(f"{path}/{doc['document_id']}/retry-extraction", json={
                'expected_input_revision': current['input_revision']}).status_code == 202


@pytest.mark.parametrize('extension', ['md', 'markdown'])
@pytest.mark.parametrize('content', [b'', b'\xff', b'hello\x00world', b'hello\x01world', b'%PDF-1.4', b'PK\x03\x04'])
def test_invalid_markdown_is_rejected_before_registration(service, extension, content):
    client, path, _ = service
    response = upload(client, path, f'invalid.{extension}', content)
    assert response.status_code == 422
    assert response.json()['error'] == 'invalid_file'
    assert listing(client, path)['documents'] == []


def test_existing_tied_timestamps_stable_and_new_registration_monotonic(service):
    client, path, _ = service
    rid = path.split('/')[3]
    at = '2099-01-01T00:00:00.000000+00:00'
    with closing(plans.connect()) as db:
        repo = DocumentRepository(db)
        for key in ['bbbbbbbb-0000-4000-8000-000000000000', 'aaaaaaaa-0000-4000-8000-000000000000']:
            repo.create(key, rid, key + '.txt', 'text/plain; charset=utf-8', 1, at)
    before = listing(client, path)['documents']
    assert before[0]['document_id'].startswith('a')
    assert upload(client, path, 'new.txt').status_code == 201
    after = listing(client, path)['documents']
    assert after[:2] == before
    assert after[2]['created_at'] > at
