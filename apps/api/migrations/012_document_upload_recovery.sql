CREATE TABLE document_upload_reservations (
 storage_key TEXT PRIMARY KEY,
 request_id TEXT NOT NULL REFERENCES roadmap_inputs(request_id),
 created_at TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 committed_at TEXT,
 original_filename TEXT,
 upload_id TEXT,
 content_sha256 TEXT,
 upload_lease_token TEXT,
 cleanup_lease_token TEXT,
 cleanup_lease_until TEXT,
 cleanup_attempts INTEGER NOT NULL DEFAULT 0 CHECK (cleanup_attempts >= 0),
 cleanup_error_code TEXT,
 UNIQUE(request_id, upload_id)
);
CREATE INDEX document_upload_reservations_request ON document_upload_reservations(request_id, expires_at);
CREATE INDEX document_upload_reservations_cleanup ON document_upload_reservations(expires_at, cleanup_lease_until);
