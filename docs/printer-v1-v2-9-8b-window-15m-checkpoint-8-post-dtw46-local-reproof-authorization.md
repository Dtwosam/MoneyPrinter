# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW-46 Local Re-proof Authorization

Date: 2026-08-07

Reviewed readiness HEAD: `f3a58d3a5b4b13e1c724eda957874fd16506eefb`

Proposed proof ID: `C8_REPROOF_AFTER_DTW46_20260807`

## Explicit operator authorization

The operator explicitly authorized exactly one fresh local Checkpoint 8 controlling re-proof after DTW-46.

Authorization scope received:

- permission to consume one disposable C8 proof attempt only;
- use the approved no-auth, deterministic fixture-backed, zero-provider/network proof capability;
- use the reviewed C8 lineage;
- create only this documentation-only authorization record before execution;
- execute exactly one fresh disposable attempt;
- no retry, rerun, resume, restart, or successor;
- on BLOCK/FAIL, preserve/freeze evidence and stop;
- on PASS candidate, stop runtime and perform the required independent inspection before any Checkpoint 8 closeout.

## Exact execution scope

This authorization permits exactly one fresh local proof attempt using:

- the exact authorization Git HEAD produced by this documentation-only commit;
- one disposable isolated local worktree;
- the existing project Python environment with Python >=3.11;
- a fresh disposable SQLite database;
- a fresh disposable artifact root;
- a fresh proof identity and one-shot sentinel namespace;
- the deterministic full Checkpoint 8 fixture composition;
- process-local zero-network tripwire protection;
- the ordinary public `run_operational_campaign()` proof path with the approved disposable proof capability;
- exact `WINDOW_15M` Checkpoint 8 acceptance law and frozen evidence.

No GitHub Actions workflow is authorized or required.

## One-shot law

The authorization is consumed when the controlling harness claims the fresh one-shot sentinel and begins the single public proof sequence.

This authorization does not permit a second attempt for any reason. There is no retry, rerun, resume, restart, or successor permission.

Historical Checkpoint 8 attempts remain immutable consumed/no-rerun evidence and are not reused.

## PASS / BLOCK / FAIL handling

A PASS candidate requires frozen evidence with `campaign_pass == true` and `campaign_acceptance_verdict == CAMPAIGN_PASS`, plus the complete approved Checkpoint 8 acceptance law.

If the attempt blocks or fails, freeze/preserve all available disposable evidence and stop without a second attempt.

If it produces a PASS candidate, stop runtime and perform the required independent read-only inspection of the retained disposable DB/artifacts before any Checkpoint 8 closeout or DTW-34 completion.

## Locks preserved

This authorization does not authorize operational `WINDOW_15M` memory growth, live/provider execution, authoritative DB use, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper-trade audits, PnL, wallets, private keys, real funds, paid API dependency, scoring/ranking/confidence/weighted logic, or embeddings/vectors.

Source Governor, Central Scheduler, six-unit accounting, clean-memory quality gates, cleanup, replay, and all downstream locks remain mandatory.
