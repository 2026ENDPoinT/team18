-- Additive: preserve existing documents, extraction links and old reservations.
-- Deploy before the API, after draining uploads from the old API version.
-- New uploads serialize name/count checks on their owning roadmap_inputs row.
-- No uniqueness constraint on historical documents: existing duplicates remain
-- readable/deletable, while new active duplicates are rejected atomically.
ALTER TABLE public.document_upload_reservations ADD COLUMN original_filename text;
