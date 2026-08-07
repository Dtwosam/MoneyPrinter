# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW49 Controlling Re-proof Authorization

Date: 2026-08-07

Parent: `DTW-34`

Reviewed readiness baseline:

`c18b17f8b7e0e455206ad37100a79fa978d983a5`

Readiness verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW49_REPROOF_READINESS_PASS_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`

## Explicit operator authorization

The operator explicitly authorized exactly one fresh local Checkpoint 8 controlling re-proof after DTW-49.

This authorization may be consumed once only.

Proposed proof ID:

`C8_REPROOF_AFTER_DTW49_20260807`

## Exact allowed execution

- local Mac execution only;
- one disposable isolated worktree pinned to this authorization commit;
- project Python environment `$HOME/Developer/MoneyPrinter/.venv`, Python >=3.11;
- entirely fresh disposable proof root, migrated DB, artifact directory, and one-shot sentinel;
- deterministic fixture-backed ordinary public `WINDOW_15M` composition only;
- process-local network tripwire must remain zero;
- exactly one controlling attempt;
- exact `report_only()` replay after the attempt;
- retain frozen proof evidence for independent inspection.

## One-shot law

No retry, rerun, resume, restart, or successor is authorized.

If the attempt blocks or fails, preserve the evidence and stop. A later attempt would require a new audit/readiness decision and a new explicit operator authorization.

If the attempt produces a PASS candidate, stop runtime and perform independent frozen-evidence inspection against the complete Checkpoint 8 acceptance law before closing `DTW-34`.

## Acceptance law remains unchanged

A Checkpoint 8 PASS requires all approved conditions together, including:

- ordinary `WINDOW_15M` public composition;
- exactly two terminal campaign-owned 15m windows;
- both current-run windows E2Q-clean;
- one canonical `CLEAN_MEMORY` episode and fingerprint per window;
- `clean_memory_outcome_pass=True`;
- campaign acceptance exactly `CAMPAIGN_PASS`;
- terminal cleanup and lease release;
- zero active, locked, or orphan work;
- canonical report row/artifact parity;
- zero-source / zero-Scheduler / zero-write replay;
- exact Source Governor, Scheduler, six-unit request/transport ownership and accounting;
- zero provider/network attempts;
- zero protected downstream deltas;
- no `WINDOW_1H+`;
- no retry, rerun, resume, restart, or successor.

## Locks preserved

This does **not** authorize operational `WINDOW_15M` memory growth, provider/network access, authoritative DB use, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live wallet use, private keys, real funds, or live execution.

`WINDOW_5M_MICRO_EVENT` remains support-only.
