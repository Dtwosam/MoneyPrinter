# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW-47 Re-proof Authorization

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW47_SINGLE_REPROOF_AUTHORIZED`

Readiness baseline: `2a36f8ffbd66ccd95c061a7719b47893de6eeaea`

Linear parent: `DTW-34`

## Operator authorization

The operator explicitly authorizes exactly one fresh local Checkpoint 8 controlling re-proof after DTW-47.

This authorization is limited to one disposable C8 proof attempt under the approved deterministic fixture-backed, zero-provider/network proof capability.

The authorization commit containing this record becomes the immutable expected proof HEAD. The attempt must run only from a clean disposable worktree pinned exactly to that commit.

## Exact attempt contract

Proof ID: `C8_REPROOF_AFTER_DTW47_20260807`

The attempt must use completely fresh disposable namespaces for:

- proof root;
- migrated disposable SQLite DB;
- proof artifacts;
- one-shot sentinel.

Exactly one ordinary public-composition `WINDOW_15M` campaign attempt is authorized.

No retry, rerun, resume, restart, or successor is authorized.

All prior Checkpoint 8 attempts remain historical and consumed. None may be reused, resumed, restarted, or rerun.

## Provider and runtime boundary

The proof must remain deterministic and fixture-backed with:

- provider execution forbidden;
- provider fallback forbidden;
- zero live provider/network access;
- process-local network tripwire active around the campaign and report-only replay;
- no authoritative production DB use.

This authorization does not authorize operational `WINDOW_15M` memory growth or ordinary Printer/provider runtime outside the disposable proof capability.

## Required successful acceptance boundary

A PASS candidate requires the previously approved complete Checkpoint 8 acceptance law, including:

- exactly one ordinary public campaign call using the disposable proof capability;
- real public composition and authoritative operational campaign owner;
- `WINDOW_15M` only;
- exactly two campaign-owned terminal current-run 15m windows;
- both E2Q clean candidates;
- one canonical `CLEAN_MEMORY` episode with fingerprint for each selected token;
- no unrelated clean-memory promotions;
- `clean_memory_outcome_pass=True`;
- campaign full-run acceptance verdict exactly `CAMPAIGN_PASS`;
- internally consistent first-terminal cause and terminal supervision;
- cleanup complete and lease released;
- zero active/orphan owned work and zero active/locked Scheduler work;
- campaign/run/cycle/factory terminal state;
- exactly one canonical terminal report row and canonical report artifact with row/hash/bytes parity;
- exact `report_only()` replay for the terminal identity with zero source calls, zero Scheduler runtime calls, and zero DB writes;
- exact Source Governor, Central Scheduler, and six-unit ownership/accounting;
- zero protected downstream deltas;
- zero `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` activation;
- no retry/rerun/resume/restart/successor;
- `WINDOW_5M_MICRO_EVENT` remains support-only.

A frozen summary by itself is not sufficient for Checkpoint 8 PASS. Any PASS candidate must stop runtime and undergo independent read-only frozen-evidence inspection before Checkpoint 8 closeout.

## Failure boundary

If the single attempt blocks or fails:

1. preserve all available DB, artifact, sentinel, log, and frozen evidence;
2. do not retry or run a successor;
3. stop Checkpoint 8 execution;
4. open only an evidence-driven narrow audit/design lane if required.

## Capabilities not authorized

This authorization does not unlock or authorize:

- provider/network access;
- authoritative DB use;
- operational memory-growth execution;
- `WINDOW_1H+`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet, private keys, real funds, or live execution.

## Authorization consumption

The authorization is single-use. It becomes consumed when the controlling harness successfully claims the fresh one-shot sentinel and begins the authorized public sequence. A blocked or failed consumed attempt remains consumed.

No other statement, generic request, or later command expands this authorization.