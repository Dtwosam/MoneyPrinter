# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW48 Local Re-Proof Authorization

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW48_ONE_SHOT_LOCAL_REPROOF_AUTHORIZED`

Reviewed readiness parent: `0e3f14cc2f99073deb98131ebaf6fea11beb67fb`
Parent issue: `DTW-34`

## Authorization

The operator explicitly authorizes exactly one fresh local Checkpoint 8 controlling re-proof after DTW-48.

This authorization is single-use. The resulting authorization commit SHA is the immutable expected proof HEAD for the one allowed attempt.

## Allowed proof capability

The one attempt must:

- use the approved Checkpoint 8 public-composition proof capability;
- remain deterministic and fixture-backed;
- perform zero provider/network access;
- use `WINDOW_15M` only;
- use completely fresh disposable proof-root, migrated DB, artifact, worktree, and sentinel namespaces;
- execute exactly once;
- preserve Source Governor, Central Scheduler, six-unit accounting, clean-memory, cleanup, replay, and downstream-lock contracts;
- preserve all prior consumed attempts as historical and non-reusable.

## Single-use / stop law

No retry, rerun, resume, restart, or successor is authorized.

If the attempt blocks or fails:

1. preserve all evidence;
2. do not run again;
3. audit the first blocker separately.

If the attempt produces a PASS candidate:

1. stop runtime;
2. preserve/freeze all evidence;
3. perform independent read-only inspection against the complete Checkpoint 8 acceptance law;
4. do not close `DTW-34` unless that independent inspection passes.

A candidate result alone is not Checkpoint 8 PASS.

## Explicit non-authorization

This authorization does not authorize:

- operational `WINDOW_15M` memory growth;
- provider/network access or source fetching;
- authoritative DB use;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet, private keys, real funds, or live execution;
- paid APIs;
- scoring/ranking/confidence/weighted systems;
- any Source Governor or Central Scheduler bypass.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot become a main outcome authority.

## Acceptance boundary

The one attempt must still satisfy the complete frozen Checkpoint 8 acceptance law, including ordinary public composition, exactly two terminal current-run `WINDOW_15M` windows, clean E2Q candidates, canonical `CLEAN_MEMORY` episodes and fingerprints, exact `CAMPAIGN_PASS`, terminal/cleanup/lease/zero-active-work truth, canonical report/artifact parity, zero-work public replay, exact Source Governor/Scheduler/six-unit accounting, zero protected downstream deltas, and no longer-window activation.

This document authorizes one attempt only. It does not declare readiness beyond the already reviewed parent and does not declare Checkpoint 8 PASS.
