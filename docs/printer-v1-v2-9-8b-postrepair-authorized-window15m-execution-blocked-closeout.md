# Printer V1 V2-9.8B Post-Repair Authorized WINDOW_15M Execution — Blocked Closeout

Date: 2026-08-08
Linear: `DTW-78`

## Verdict
`V2_9_8B_POST_REPAIR_AUTHORIZED_WINDOW_15M_ONE_SHOT_BLOCKED_CONSUMED_PRE_LIFECYCLE_TRANSPORT_IDENTITY_RECONCILIATION`

Exactly one operator-authorized ordinary `WINDOW_15M` wrapper invocation ran under authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z` at exact authorized HEAD `1667d3a1391ef4e93766fcdc0d5824d3da2f2127`.

The authorization is consumed and permanently non-reusable. No retry, rerun, resume, restart, successor, or second invocation is permitted.

## Terminal truth
- wrapper classification `CHILD_EXITED_NONZERO`;
- child exit `1`;
- `CAMPAIGN_PRE_LIFECYCLE` / `OPERATIONAL_COMMAND_BLOCKED`;
- lifecycle started `null`;
- marker consumed `true`;
- source calls `10`;
- scheduler runtime calls `0`;
- DB writes `6`;
- cleanup complete and lease released;
- scheduler locked/pending/running `0`;
- retry/rerun/resume/restart/successor counters all `0`.

Execution: `20260808T140729Z-5fa4771d212a`.
Campaign: `20260808T140729Z-5fa4771d212a-campaign`.
Run: `20260808T140729Z-5fa4771d212a-campaign-run`.
Cycle: `20260808T140729Z-5fa4771d212a-cycle`.

First cause: `HolderBudgetError:MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS`.

The supplied set differences show campaign-owner (`C`) and action-local (`A`) transport identity sets agree, while the request manifest (`M`) has four additional identities. The visible sample is GeckoTerminal `candidate_market_batch`, endpoint `GET /api/v2/networks/solana/tokens/{mint}/pools`, target category `mint_pool_reconciliation`.

## Static defect candidate
At the authorized code lineage, the pre-holder owner correctly requires exact `M = C = A` transport identity truth. Static inspection shows `run_bounded_unknown_liquidity_backup()` performs governed backup calls, measures identities, and emits them into source-request coverage, but creates its `MeasuredTransportLedger` without `on_transport_recorded` and exposes neither a transport-identity observer nor stage-evidence sink. That path can therefore create manifest-only identities.

This is the leading defect candidate only. DTW-79 must prove the failed-run four identities came from this path using read-only DB/application evidence before any repair.

## Money usefulness
Fail-closed accounting prevented lifecycle/memory work from continuing while real source-call accounting was internally inconsistent.

## Still locked
No new real proof, longer windows, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live money/wallet paths, paid API dependency, scoring/ranking/confidence/weighting, embeddings/vectors. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Risks / blockers
- authorization consumed;
- terminal detail is truncated, so exact four-identity provenance needs read-only reconstruction;
- post-attempt DB contains six authorized pre-lifecycle writes that must be classified;
- no repair or new proof before audit -> design -> implementation -> bounded proof -> closeout.

## Next lane
`DTW-79 — Post-attempt pre-holder transport-identity reconciliation audit`

Audit-only: static inspection, read-only authoritative DB/application artifacts, exact M/C/A reconstruction, protected-surface checks, audit closeout. No source fetching, runtime, DB mutation, memory generation, new authorization, retry/rerun/resume/restart/successor, longer windows, retrieval, decisions, positions, trades, audits, or PnL.
