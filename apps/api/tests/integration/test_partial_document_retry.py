"""Partial document retries preserve OCR billing protection and confirmation rules."""
from unittest.mock import Mock
from pathlib import Path
import sys

from providers.google_vision_ocr import OCRError
from services.document_ocr import retry_policy
from worker import documents as worker
from test_document_uploads import listing, service, upload

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'unit'))
from test_document_ocr import docx


def test_confirmed_partial_document_can_be_reprocessed_without_repeating_failed_ocr(service):
    client, path, storage = service
    response = upload(client, path, 'project-partial.docx', docx(text=True))
    assert response.status_code == 201
    document_id = response.json()['document']['document_id']
    provider = Mock(detect=Mock(side_effect=OCRError('ocr_timeout')))
    assert worker.run_once(storage, ocr_provider=provider)

    data = listing(client, path)
    first = data['documents'][0]
    assert first['extraction_status'] == 'partial' and first['extraction_error_code'] == 'ocr_timeout'
    assert first['retry_available'] is True
    extraction = client.get(f'{path}/{document_id}/extractions/1').json()
    assert extraction['extracted_text']
    confirm = client.post(f'{path}/{document_id}/extractions/1/confirmation', json={
        'expected_input_revision': data['input_revision'],
    })
    assert confirm.status_code == 200
    confirmed = listing(client, path)
    assert confirmed['documents'][0]['partial_confirmed_at']
    assert confirmed['documents'][0]['retry_available'] is True

    retry = client.post(f'{path}/{document_id}/retry-extraction', json={
        'expected_input_revision': confirmed['input_revision'],
    })
    assert retry.status_code == 202 and retry.json()['extraction_revision'] == 2
    assert worker.run_once(storage, ocr_provider=provider)
    current = listing(client, path)['documents'][0]
    assert current['extraction_status'] == 'partial' and current['partial_confirmed_at'] is None
    assert client.get(f'{path}/{document_id}/extractions/2').json()['extracted_text'] == extraction['extracted_text']
    assert provider.detect.call_count == 1  # The failed unit was not sent to OCR again.


def test_unread_and_pending_documents_keep_existing_retry_limits():
    unavailable = {'available': False, 'reason': 'ocr_disabled'}
    assert not retry_policy({'extraction_status': 'pending', 'extraction_error_code': None}, unavailable)['retry_available']
    assert not retry_policy({'extraction_status': 'needs_ocr', 'extraction_error_code': 'ocr_timeout'}, unavailable)['retry_available']
