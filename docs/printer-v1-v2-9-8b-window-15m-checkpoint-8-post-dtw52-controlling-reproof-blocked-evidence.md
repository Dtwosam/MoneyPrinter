# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW52 Controlling Re-proof Blocked Evidence

Date: 2026-08-07

Linear: `DTW-34` (Checkpoint 8 remains In Progress)

Authorization HEAD: `0aa7fdcfacdd7f28ae0883b045ee66be17c76f09`

Proof ID: `C8_REPROOF_AFTER_DTW52_20260807`

Proof root:

`/Users/Dtwo1/PrinterProofs/C8_REPROOF_AFTER_DTW52_20260807_20260807T222049Z_0aa7fdcf`

Frozen evidence path in repo:

`operator-runs/checkpoint8/C8_REPROOF_AFTER_DTW52_20260807_20260807T222049Z_0aa7fdcf/`

Harness exit code: `0` (summary freeze completed)

## Campaign verdict

- `campaign_acceptance_verdict`: **`BLOCKED_UNSAFE`**
- `campaign_pass`: **false**
- `run_status`: `COMPLETED`
- `first_terminal_cause`: `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`
- `clean_memory_outcome_pass`: **true** (not sufficient alone for C8 PASS)

## What advanced since DTW-50/51/52

- Disposable binding factory preflight did not stop the run.
- Terminal packaging projected campaign `run_id` (DTW-52 held).
- Pre-lifecycle source recon status: **OK**.
- Exactly two selected tokens, two terminal `WINDOW_15M` windows, two episodes, two fingerprints.
- Cleanup complete; lease released; zero longer windows; zero network attempts; one-shot sentinel ordinal 1.
- `report_only` zero-work counts are zero, but replay status is `REPLAY_BLOCKED` (`FULL_RUN_REPAIRED_EVIDENCE_INVALID`).

## First exact acceptance-law blocker

**Check:** `owner_action_local_equal_non_vacuous` = false

**Mismatch:** `LOCAL_VALIDATION_STEP:UNIT_IDENTITY_SET_MISMATCH`

| Unit | action_local_count | owner_count | identity_sets_equal |
|------|--------------------:|------------:|:--------------------|
| SOURCE_TRANSPORT_OPERATION | 46 | 46 | true |
| SCHEDULER_WORK_ITEM | 28 | 28 | true |
| LIFECYCLE_RESERVED_TRANSPORT_OPERATION | 28 | 28 | true |
| **LOCAL_VALIDATION_STEP** | **89** | **93** | **false** |

Owner six-unit ledger reported 93 local validation identities; action-local reconciliation surface reported 89. Identity sets are unequal, so full-run acceptance remains fail-closed as `BLOCKED_UNSAFE`.

## Second failing check (same acceptance surface)

**Check:** `reservation_attempt_outcomes_complete` = false

## Selected tokens / windows / memories

| Slot | Mint | State |
|------|------|-------|
| 1 | `Hx7d5gD9Lt23A7BQkBxiE6rnfFuw9ARsHSLGN6Acvcbb` | COOLDOWN |
| 2 | `5dqWELD3TqMDw8BHmi7wcKXrEhuvwNqeCDLCYQGijHut` | COOLDOWN |

- Terminal windows: 2 × `WINDOW_15M` / `CLEAN_PROMOTED`
- Episodes: 2; fingerprints: 2
- Window memory labels observed as `PARTIAL_MEMORY` / `CLEAN_DATA` with `CLEAN_EPISODE_ALLOWED` outcomes

## Integrity / locks

- DB integrity: ok
- FK violations: 0
- Network attempts: 0
- Protected capability deltas: all 0
- WINDOW_1H/4H/12H/24H: 0
- No retry/rerun/resume/restart/successor
- No production code modified under this authorization

## Final Checkpoint 8 verdict

```text
V2_9_8B_WINDOW_15M_CHECKPOINT_8_FULL_DISPOSABLE_PUBLIC_COMPOSITION_PROOF_BLOCKED
```

## Next law

Do not rerun under this authorization. A new narrow audit/design/repair lane is required for the first blocker class:

`LOCAL_VALIDATION_STEP:UNIT_IDENTITY_SET_MISMATCH` / `owner_action_local_equal_non_vacuous`

(and the related `reservation_attempt_outcomes_complete` failure).

DTW-34 remains In Progress. Operational WINDOW_15M memory growth remains locked.
