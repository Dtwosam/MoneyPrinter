# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-52 Terminal Campaign Run Identity Repair Closeout

Date: 2026-08-07

Linear: `DTW-52`

Design HEAD: `f09a51283e8798541466190e0398d8e23bbd419c`

Implementation commit: `a5145dc5b62230d2289335f8244c217937b77c04`

Verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW52_TERMINAL_CAMPAIGN_RUN_IDENTITY_REPAIR_OFFLINE_PASS`

## Proven defect

After a real `run_operational_campaign()` return, the C8 harness stopped with `CHECKPOINT8_TERMINAL_IDENTITY_MISSING` before `report_only()` and frozen-summary creation. The terminal packaging surface exposed `campaign_id` but no campaign `run_id`, even though the authoritative campaign run identity already existed as `command.run_id`.

## Deterministic RED

At the approved design baseline, focused regression proved:

1. baseline success packaging shape lacks campaign run ID → extractor raises `CHECKPOINT8_TERMINAL_IDENTITY_MISSING`;
2. factory UUID cannot substitute for campaign run ID;
3. public terminal assembly source lacked `run_id` projection.

Classification: `DTW52_TERMINAL_CAMPAIGN_RUN_IDENTITY_MISSING_RED_CONFIRMED`.

## Repair

Project `"run_id": command.run_id` onto every public terminal packaging dict that already emits `command.campaign_id` (success, terminal-failure, and pre-lifecycle packaging returns).

Extractor conflict/cardinality law is unchanged. Factory run identity remains distinct and is not used as a substitute.

## Offline GREEN

- changed-file `py_compile`: PASS
- dedicated DTW-52 regression: `7 passed`
- existing C8 real-consumer compatibility: `9 passed`
- complete focused C8 suite: `117 passed`
- exact two-file implementation manifest: PASS
- `git diff --check`: PASS
- provider/network execution: NONE
- controlling C8 proof: NONE

## Money-usefulness contribution

A true Checkpoint 8 runtime result can now survive terminal identity extraction, zero-work report-only handoff, and frozen-summary packaging without losing campaign run identity.

## What remains locked

Checkpoint 8 remains open pending independent DTW-52 review/readiness and a separately authorized future one-shot proof. Operational `WINDOW_15M` memory activation, `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A future C8 attempt may expose a new downstream blocker; do not rerun automatically.
2. Another controlling proof requires a new explicit authorization after independent readiness review.
