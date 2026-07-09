-- V2-2S: Cross-batch selection cooldown rotation state.
-- Records the last-selected batch and evidence fingerprint per (token_mint, pair_address).
-- Used by token-level and pair-level selection cooldown checks (V2-2R design, Rules 1 and 2).
-- No scores, ranking, confidence, or weighted logic is stored or implied.

CREATE TABLE IF NOT EXISTS printer_selection_rotation_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_mint TEXT NOT NULL,
    pair_address TEXT NOT NULL,
    last_selected_batch_id TEXT,
    last_selected_batch_seq INTEGER,
    last_selected_at TEXT,
    last_evidence_fingerprint_json TEXT,
    selection_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(token_mint, pair_address)
);

CREATE INDEX IF NOT EXISTS idx_rotation_state_token_mint
    ON printer_selection_rotation_state (token_mint);

CREATE INDEX IF NOT EXISTS idx_rotation_state_pair_address
    ON printer_selection_rotation_state (pair_address);
