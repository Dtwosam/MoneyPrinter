-- V2-9.7E.26: reserve the complete DexScreener + exact 15m completion path.

ALTER TABLE printer_holder_campaign_operation_ledgers
ADD COLUMN reserved_snapshot_completion_operations INTEGER NOT NULL DEFAULT 4
    CHECK (reserved_snapshot_completion_operations = 4);
