# Multi-Round Market-Batch Six-Unit Sequencing Repair Plan

> Inline execution this session.

**Goal:** Distinct logical mint-market batches seal as `MINT_MARKET_BATCH|1`, `|2`, `|3` without resetting after protocol work, while duplicate seal of the same logical batch remains blocked.

**Root cause:** `run_dexscreener_batch_market_resolution` hardcodes `stage_sequence=1` when sealing six-unit evidence.

**Architecture:** Allocate monotonic `stage_sequence` at durable request-key creation (`-mint-batch-rN` / `-protocol-resume-mbN`), pass into the market-resolution sealer, embed ordered mint digest in sealed report metadata. Duplicate stage_id protection stays unchanged.

**Owners:** permanent_discovery_availability (REPAIR), eligible_token_supply (REPAIR), campaign_six_unit_accounting (ALREADY_CORRECT).

