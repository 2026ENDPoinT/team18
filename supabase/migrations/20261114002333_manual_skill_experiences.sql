-- Backend-only, authorized through the owning roadmap's existing lock/check.
CREATE TABLE public.manual_skill_experiences (
 snapshot_id TEXT NOT NULL REFERENCES public.job_skill_snapshots(snapshot_id) ON DELETE CASCADE,
 skill_key TEXT NOT NULL,
 input_revision INTEGER NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL,
 PRIMARY KEY(snapshot_id,skill_key)
);
ALTER TABLE public.manual_skill_experiences ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.manual_skill_experiences FROM PUBLIC, anon, authenticated;
