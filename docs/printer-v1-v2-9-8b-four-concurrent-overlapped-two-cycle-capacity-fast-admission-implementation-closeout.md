# Printer V1 — Four-Concurrent Overlapped Two-Cycle Capacity + Cycle-2 Fast Admission Implementation Closeout

Status: **CLOSED PASS**

Implementation verdict:

`V2_9_8B_FOUR_CONCURRENT_OVERLAPPED_TWO_CYCLE_CAPACITY_FAST_ADMISSION_IMPLEMENTATION_PASS`

This lane implemented source-stack adoption, Cycle-2 pre-lifecycle liveness
repair, wait-row cleanup ownership, official zero-state wait inclusion, and
focused frozen proof. It did not run Printer, drain the surviving Sep-2 wait,
prepare an authorization, call live providers, or unlock 12h/24h/retrieval/
financial capability.

## Identity

- branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
- start HEAD: `a4920c3e4706771b6b71ac1a6de5804038b056e8`
- governing design:
  `docs/printer-v1-v2-9-8b-four-concurrent-overlapped-two-cycle-capacity-fast-admission-design.md`
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` remains
  `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`
- surviving wait (not drained):
  `prelifecycle-refresh-wait:20260902T123958Z-5a3e78f1a7b8-campaign:20260902T123958Z-5a3e78f1a7b8-campaign-run:20260902T123958Z-5a3e78f1a7b8-cycle-2:1`
  state still `WAITING`

## Authoritative DB

Path: `data/printer_v1.sqlite3`

- SHA-256 before: `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`
- SHA-256 after: `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`
- unchanged

## What was implemented

1. Source-stack wording now permits four concurrent through-4h tokens as two
   overlapping two-slot cycles. No third cycle. No fifth token. Compiled 6/3
   unused. Freeze `>=4` / 2+2 / disjointness / SG / Scheduler / no retry /
   12h/24h locks unchanged.

2. Factory gate uses the next cooperative governed-request bound, not the
   ~115s `PERSISTED_REFRESH` aggregate, when Cycle 2 is waiting for refresh.

3. Cooperative `_request` claims a past-due `WAITING` wait instead of
   returning because `_waiter is None`.

4. `CLAIMED` waits are immediately re-enterable.

5. Cycle-2 `acquisition_deadline_at` is a later-cycle re-entry wake, not
   factory `PROOF_DEADLINE`.

6. `abandon_scoped_refresh_waits` is the canonical wait cleanup owner, called
   from parent-interrupt reconcile and campaign terminal reconcile.

7. Official zero-state counts `WAITING`/`CLAIMED` refresh waits.

Refresh timing remains `+600/+1200/+1800/+2400`. No schema migration. No
budget increase.

## Focused tests

PASS (representative):

- `tests/test_v2_9_8b_four_concurrent_overlapped_two_cycle_fast_admission.py`
- `tests/test_v2_9_8b_cooperative_later_cycle_repair.py`
- `tests/test_v2_9_8b_interrupted_cycle2_parent_interrupt_cleanup.py`
- `tests/test_v2_9_8b_interrupted_four_token_followup_repair.py`
- `tests/test_v2_9_8b_4_2_2_orchestration_correctness.py`
- `tests/test_v2_9_8b_persistent_refresh_owner_proof.py`
- `tests/test_v2_9_8b_slice_g_cadence_isolation.py`
- `tests/test_v2_9_8b_four_token_gate_h_integrated_disposable.py`
- `tests/test_v2_9_8b_four_token_proof_integration.py`
- `tests/test_v2_9_8b_multi_cycle_session_coordinator.py`
- `tests/test_v2_9_8b_pre_lifecycle_zero_attempt_no_stranding.py::test_early_cycle1_terminal_leaves_no_stranded_ownership`

Together these cover: Cycle-1 gap protection; sub-115s later-cycle gate;
past-due WAITING claim; CLAIMED re-entry; 2400s exhaustion without
`PROOF_DEADLINE`; max four / no fifth / no third cycle; wait abandon;
zero-state WAITING/CLAIMED; 476/118/444 / retries 0; four-token step-key
isolation and `active_through_4h_peak = 4` accounting.

Not run as live proof. No providers/RPC/WebSockets. No Printer campaign.

## Confirmations

- authoritative DB unchanged
- surviving Sep-2 `WAITING` row not manually drained
- no live providers/RPC/WebSockets
- no Printer campaign
- no authorization created or applied
- `59fdefe7` remains permanently non-reusable
- no 12h/24h/retrieval/financial unlock

## Exact next permitted action

```text
OPERATOR REVIEW / BOUNDED-LIVE-AUTHORIZATION DECISION
```

Do not automatically prepare or apply an authorization. Do not run Printer.
Do not drain the surviving wait as a substitute for a later approved campaign
zero-state closeout.

`V2_9_8B_FOUR_CONCURRENT_OVERLAPPED_TWO_CYCLE_CAPACITY_FAST_ADMISSION_IMPLEMENTATION_PASS`
