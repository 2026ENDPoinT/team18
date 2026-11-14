-- Self-reported experience is independent of document evidence and its answers.
CREATE TABLE manual_skill_experiences (
 snapshot_id TEXT NOT NULL REFERENCES job_skill_snapshots(snapshot_id) ON DELETE CASCADE,
 skill_key TEXT NOT NULL,
 input_revision INTEGER NOT NULL,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,skill_key)
);
