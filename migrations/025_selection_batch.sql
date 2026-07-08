-- V2-2C: Selection-batch persistence layer.
-- Stores memory-diet selection batches and per-candidate batch items including
-- bucket assignment, selection/rejection reasons, same-token/new-pair
-- classification, cooldown/reopen state, and candidate-universe metadata.
-- No scoring, ranking, confidence, or weighted logic is stored or implied.

CREATE TABLE IF NOT EXISTS printer_selection_batches (
    id INTEGER PRIMARY KEY,
    batch_id TEXT NOT NULL UNIQUE,
    batch_status TEXT NOT NULL DEFAULT 'ASSEMBLED'
        CHECK (batch_status IN ('ASSEMBLED', 'REJECTED', 'PENDING_PROOF')),
    window_kind TEXT NOT NULL DEFAULT 'WINDOW_15M',
    candidate_pool_total INTEGER NOT NULL DEFAULT 0,
    selected_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    unavailable_or_unclassified_count INTEGER NOT NULL DEFAULT 0,
    pool_summary_json TEXT,
    pool_diversity_notes TEXT,
    pool_quality_notes TEXT,
    operator_approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_selection_batches_batch_id
    ON printer_selection_batches (batch_id);

CREATE INDEX IF NOT EXISTS idx_selection_batches_status
    ON printer_selection_batches (batch_status);

CREATE INDEX IF NOT EXISTS idx_selection_batches_created_at
    ON printer_selection_batches (created_at);

CREATE TABLE IF NOT EXISTS printer_selection_batch_items (
    id INTEGER PRIMARY KEY,
    batch_id TEXT NOT NULL,
    item_status TEXT NOT NULL DEFAULT 'UNCLASSIFIED'
        CHECK (item_status IN ('SELECTED', 'REJECTED', 'UNCLASSIFIED')),
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT NOT NULL,
    pair_address TEXT NOT NULL,
    chain TEXT NOT NULL DEFAULT 'solana',
    primary_bucket TEXT,
    bucket_name TEXT,
    asset_class TEXT,
    asset_class_reason TEXT,
    behavior_context_labels TEXT,
    selection_reason TEXT,
    rejection_reason TEXT,
    tracking_lane TEXT,
    lane_rationale TEXT,
    source_name TEXT,
    source_channel TEXT,
    source_request_id INTEGER,
    source_response_id INTEGER,
    discovery_candidate_id INTEGER,
    same_token_new_pair INTEGER NOT NULL DEFAULT 0,
    same_token_new_pair_classification TEXT,
    operator_approved INTEGER NOT NULL DEFAULT 0,
    manual_override_reason TEXT,
    selected_at TEXT,
    cooldown_reopened INTEGER NOT NULL DEFAULT 0,
    cooldown_reopen_reason TEXT,
    candidate_metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (batch_id) REFERENCES printer_selection_batches (batch_id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens (id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs (id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests (id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses (id),
    FOREIGN KEY (discovery_candidate_id) REFERENCES printer_discovery_candidates (id)
);

CREATE INDEX IF NOT EXISTS idx_selection_batch_items_batch_id
    ON printer_selection_batch_items (batch_id);

CREATE INDEX IF NOT EXISTS idx_selection_batch_items_item_status
    ON printer_selection_batch_items (item_status);

CREATE INDEX IF NOT EXISTS idx_selection_batch_items_token_mint
    ON printer_selection_batch_items (token_mint);

CREATE INDEX IF NOT EXISTS idx_selection_batch_items_primary_bucket
    ON printer_selection_batch_items (primary_bucket);

CREATE INDEX IF NOT EXISTS idx_selection_batch_items_tracking_lane
    ON printer_selection_batch_items (tracking_lane);

CREATE INDEX IF NOT EXISTS idx_selection_batch_items_same_token_new_pair
    ON printer_selection_batch_items (same_token_new_pair);
