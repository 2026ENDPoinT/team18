from unittest.mock import patch

from test_document_uploads import service
from api.routes import documents as routes
from worker import documents as worker
from document_upload_recovery_cases import verify_recovery


def test_upload_recovery_faults(service):
    client, _, storage = service
    with patch.object(routes, 'request_work', lambda: None):
        verify_recovery(client, routes, worker, storage)
