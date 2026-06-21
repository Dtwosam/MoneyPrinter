-- Post-RC Lane 2: repeatable evidence-window identity for memory rows.
ALTER TABLE printer_memory_windows ADD COLUMN snapshot_start_id INTEGER;
ALTER TABLE printer_memory_windows ADD COLUMN snapshot_end_id INTEGER;
ALTER TABLE printer_memory_windows ADD COLUMN window_start_at TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN window_end_at TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN cycle_id TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN source_reference TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN evidence_role TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN evidence_fingerprint TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN evidence_identity_hash TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN evidence_difference_reason TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN duplicate_guard_status TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN memory_diversity_label TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN concentration_audit_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_memory_windows_evidence_identity
    ON printer_memory_windows (evidence_identity_hash);

CREATE INDEX IF NOT EXISTS idx_memory_windows_target_evidence
    ON printer_memory_windows (token_id, pair_id, window_kind, snapshot_start_id, snapshot_end_id, evidence_role);
