CREATE TABLE IF NOT EXISTS printer_safety_rug_snapshots (
    id INTEGER PRIMARY KEY,
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    captured_at TEXT NOT NULL,
    liquidity_usd REAL,
    liquidity_locked INTEGER CHECK (liquidity_locked IN (0, 1) OR liquidity_locked IS NULL),
    liquidity_lock_source TEXT,
    liquidity_lock_until TEXT,
    holder_count INTEGER,
    top_holder_percent REAL,
    top_5_holder_percent REAL,
    top_10_holder_percent REAL,
    creator_percent REAL,
    mint_authority_present INTEGER CHECK (mint_authority_present IN (0, 1) OR mint_authority_present IS NULL),
    freeze_authority_present INTEGER CHECK (freeze_authority_present IN (0, 1) OR freeze_authority_present IS NULL),
    update_authority_present INTEGER CHECK (update_authority_present IN (0, 1) OR update_authority_present IS NULL),
    transfer_fee_present INTEGER CHECK (transfer_fee_present IN (0, 1) OR transfer_fee_present IS NULL),
    blacklist_function_present INTEGER CHECK (blacklist_function_present IN (0, 1) OR blacklist_function_present IS NULL),
    honeypot_like_behavior INTEGER CHECK (honeypot_like_behavior IN (0, 1) OR honeypot_like_behavior IS NULL),
    sell_restriction_detected INTEGER CHECK (sell_restriction_detected IN (0, 1) OR sell_restriction_detected IS NULL),
    buy_restriction_detected INTEGER CHECK (buy_restriction_detected IN (0, 1) OR buy_restriction_detected IS NULL),
    mutable_metadata INTEGER CHECK (mutable_metadata IN (0, 1) OR mutable_metadata IS NULL),
    suspicious_metadata INTEGER CHECK (suspicious_metadata IN (0, 1) OR suspicious_metadata IS NULL),
    suspicious_creator_activity INTEGER CHECK (suspicious_creator_activity IN (0, 1) OR suspicious_creator_activity IS NULL),
    source_name TEXT,
    safety_status_label TEXT NOT NULL CHECK (safety_status_label IN ('SAFETY_CLEAN', 'SAFETY_CAUTION', 'SAFETY_SUSPICIOUS', 'SAFETY_UNSAFE', 'SAFETY_UNKNOWN', 'SAFETY_DO_NOT_USE_FOR_MEMORY')),
    rug_risk_label TEXT NOT NULL CHECK (rug_risk_label IN ('RUG_RISK_LOW', 'RUG_RISK_MEDIUM', 'RUG_RISK_HIGH', 'RUG_RISK_CRITICAL', 'RUG_RISK_UNKNOWN')),
    liquidity_safety_label TEXT NOT NULL CHECK (liquidity_safety_label IN ('LIQUIDITY_SAFE', 'LIQUIDITY_THIN', 'LIQUIDITY_UNSTABLE', 'LIQUIDITY_LOCK_UNKNOWN', 'LIQUIDITY_DANGEROUS', 'LIQUIDITY_SAFETY_UNKNOWN')),
    authority_label TEXT NOT NULL CHECK (authority_label IN ('AUTHORITY_RENOUNCED_OR_SAFE', 'AUTHORITY_PRESENT', 'AUTHORITY_SUSPICIOUS', 'AUTHORITY_DANGEROUS', 'AUTHORITY_UNKNOWN')),
    distribution_label TEXT NOT NULL CHECK (distribution_label IN ('DISTRIBUTION_HEALTHY', 'DISTRIBUTION_CONCENTRATED', 'DISTRIBUTION_EXTREME_CONCENTRATION', 'DISTRIBUTION_UNKNOWN')),
    safety_payload_quality_label TEXT NOT NULL CHECK (safety_payload_quality_label IN ('SAFETY_CONTEXT_CLEAN', 'SAFETY_CONTEXT_PARTIAL', 'SAFETY_CONTEXT_STALE', 'SAFETY_CONTEXT_CONFLICTING', 'SAFETY_CONTEXT_UNKNOWN', 'SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY')),
    safety_gate_label TEXT NOT NULL CHECK (safety_gate_label IN ('ALLOW_SAFETY_CONTEXT', 'CAUTION_SAFETY_CONTEXT', 'BLOCK_UNSAFE_CONTEXT', 'MANUAL_REVIEW_REQUIRED', 'DO_NOT_TRAIN_SAFETY_CONTEXT')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    raw_safety_payload_json TEXT,
    normalized_safety_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_token_id
ON printer_safety_rug_snapshots(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_pair_id
ON printer_safety_rug_snapshots(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_token_mint
ON printer_safety_rug_snapshots(token_mint);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_pair_address
ON printer_safety_rug_snapshots(pair_address);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_captured_at
ON printer_safety_rug_snapshots(captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_safety
ON printer_safety_rug_snapshots(safety_status_label);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_rug
ON printer_safety_rug_snapshots(rug_risk_label);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_liquidity
ON printer_safety_rug_snapshots(liquidity_safety_label);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_authority
ON printer_safety_rug_snapshots(authority_label);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_distribution
ON printer_safety_rug_snapshots(distribution_label);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_gate
ON printer_safety_rug_snapshots(safety_gate_label);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_source_status
ON printer_safety_rug_snapshots(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_safety_rug_snapshots_data_quality
ON printer_safety_rug_snapshots(data_quality_label);
