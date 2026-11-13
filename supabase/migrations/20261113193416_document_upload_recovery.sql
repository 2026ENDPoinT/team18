-- Additive. Drain requests from the old API before deploying the new worker.
-- Existing documents and legacy reservations remain unchanged.
ALTER TABLE public.document_upload_reservations
 ADD COLUMN upload_id text,
 ADD COLUMN content_sha256 text,
 ADD COLUMN upload_lease_token text;
CREATE UNIQUE INDEX document_upload_reservations_idempotency
 ON public.document_upload_reservations(request_id, upload_id);
-- Existing RLS / server-only grants are deliberately preserved.
