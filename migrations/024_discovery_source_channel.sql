-- Post-RC Discovery Source Diversity Sprint A: source channel metadata on discovery candidates.
ALTER TABLE printer_discovery_candidates ADD COLUMN source_channel TEXT;
ALTER TABLE printer_discovery_candidates ADD COLUMN source_channel_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_discovery_candidates_source_channel
    ON printer_discovery_candidates (source_channel);
