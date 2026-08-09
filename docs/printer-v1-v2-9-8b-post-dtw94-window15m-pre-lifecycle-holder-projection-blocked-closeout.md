# Printer V1 V2-9.8B — Post-DTW94 WINDOW_15M Pre-Lifecycle Blocked Closeout

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW94_WINDOW_15M_ONE_SHOT_BLOCKED_PRE_LIFECYCLE_HOLDER_PROJECTION_CONTRACT`

The fresh one-use authorization was consumed exactly once. The ordinary `WINDOW_15M` child exited normally, but the campaign did not pass and the lifecycle never started.

No retry, rerun, resume, restart, or successor is authorized.

## Exact attempt

- authorization: `V2_9_8B_WINDOW_15M_AUTH_20260809T011312Z`
- authorization SHA-256: `db453fa7c14bd892bf13fb7fe9a96a43f6beb29b7d33ad5858fafcd3b1ac3eb4`
- authorized branch: `agent/v2-9-8b-post-dtw93-window15m-authorization-preparation`
- authorized HEAD: `6c30377c28d62c578020ad3f7d32e020c393fc0e`
- execution: `20260809T011506Z-4042a9a92b7a`
- campaign: `20260809T011506Z-4042a9a92b7a-campaign`
- run: `20260809T011506Z-4042a9a92b7a-campaign-run`
- host-awake safeguard: used (`caffeinate -dimsu`)
- application marker consumed: yes
- child exit: `0`
- lifecycle started: false
- first terminal cause: `FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS`
- campaign acceptance verdict: `HONEST_BLOCKED`
- campaign pass: false

## Safe terminal evidence

The pre-lifecycle accountable stage completed six-unit accounting:

- accounting status: `SIX_UNIT_ACCOUNTING_COMPLETE`
- source transport operations: 13
- normalized source rows: 81
- source response bytes: 107735
- local validation steps: 8
- Scheduler work items: 0
- lifecycle reservations: 0

Cleanup/reconciliation were clean:

- cleanup complete: true
- lease released: true
- active owned work after cleanup: 0
- no restart/resume/successor/automatic retry
- reconciled state: `TERMINAL_BLOCKED`
- no lifecycle windows were started

The DTW93 host-suspension failure did not recur.

## Controlling blocker

Static inspection of the exact authorized HEAD confirms the memory-observation path intentionally treats holder condition as context rather than a memory-admission gate. `pilot_input_readiness.py` also explicitly states that `MEMORY_OBSERVATION` does not require holder eligibility.

The retained activation contract nevertheless correctly rejects an internally contradictory projection: `fully_eligible=True` with a holder condition other than `HOLDER_CONCENTRATION_PASS`/`HOLDER_CONCENTRATION_HEALTHY` raises `FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS`.

The contradiction is upstream and requires a dedicated static/offline audit before code changes.

## Money-usefulness contribution

The attempt proves host-awake supervision is now working and exposes a semantic projection defect before any memory window can be incorrectly admitted. Fixing the projection should allow Printer to observe risky holder conditions as memory context without pretending they passed a future-action holder condition.

## What this improves

- confirms the one-shot/host-awake path no longer fails on lease expiry;
- confirms pre-lifecycle accounting and cleanup are fail-closed and complete;
- isolates a holder semantic/projection blocker before lifecycle activation;
- preserves the activation consistency guard instead of weakening it.

## Still locked

No capability is unlocked. `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys, real funds, live execution, paid APIs, scoring/ranking/confidence/weighted systems, embeddings and vectors remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- Holder evidence usability and holder-condition pass currently share ambiguous `eligible` naming in older holder plumbing.
- Removing the activation consistency guard would hide contradictory state and is prohibited.
- Flipping source-resolution `eligible` semantics globally could make valid concentrated/extreme evidence appear unavailable and is also unsafe.
- The consumed authorization cannot be reused.

## Next permitted lane

Static/offline audit of holder evidence usability vs holder-condition pass projection. No source fetching, authoritative DB mutation, runtime, new authorization, or real `WINDOW_15M` attempt is permitted until that audit closes.