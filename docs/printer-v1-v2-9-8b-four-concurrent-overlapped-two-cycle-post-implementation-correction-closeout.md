# Printer V1 — Four-Concurrent Overlapped Two-Cycle Post-Implementation Correction Closeout

Status: **CLOSED PASS**

Correction verdict:

`V2_9_8B_FOUR_CONCURRENT_OVERLAPPED_TWO_CYCLE_POST_IMPLEMENTATION_CORRECTION_PASS`

This lane applied the three narrow corrections required after independent code
review of `b9cb4d00fdf91967184f18c58e49deea70457a67`. It did not redesign the
approved 4/2/2 architecture or the Cycle-2 liveness repair. It did not run
Printer, drain the surviving Sep-2 wait, prepare an authorization, call live
providers, or unlock 12h/24h/retrieval/financial capability.

## Identity

- branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
- start HEAD: `b9cb4d00fdf91967184f18c58e49deea70457a67`
- reviewed implementation: `IMPLEMENTATION_PASS_WITH_REQUIRED_NARROW_CORRECTIONS`
- governing prior closeout:
  `docs/printer-v1-v2-9-8b-four-concurrent-overlapped-two-cycle-capacity-fast-admission-implementation-closeout.md`
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

## What was corrected

1. Parent-interrupt transaction ownership. `reconcile_parent_interrupted_open_pre_admission_attempts` no longer calls `abandon_scoped_refresh_waits` before it decides `owns_txn`. Refresh-wait abandonment now participates in the same owned `BEGIN IMMEDIATE` unit that terminalizes the Cycle-2 pre-admission attempt and its Scheduler job. There is still one commit. There is no independent commit inside `abandon_scoped_refresh_waits`. States A/B/C/D remain. Idempotent replay remains valid; State D reports `idempotent_replay` true when no leftover active wait is abandoned.

2. Campaign-terminal refresh-wait scope. `reconcile_campaign_terminal` now abandons active refresh waits by `campaign_id + run_id` across the campaign. It no longer restricts that campaign-wide cleanup call to the passed Cycle-1 `cycle_id`. `cycle_id` support remains on `abandon_scoped_refresh_waits` for genuinely cycle-local callers.

3. Deterministic frozen overlap/deadline proof. Focused tests now exercise actual lifecycle ownership for overlapping Cycle-1 and Cycle-2 `WINDOW_15M` / `WINDOW_1H` / `WINDOW_4H` state, Cycle-2 2400s acquisition-deadline behavior while Cycle 1 continues, serial close contention, cooperative-resume request identity, and unchanged 476/118/444 ceilings.

Preserved, not redesigned:

- four concurrent through-4h tokens = two overlapping two-slot cycles
- no third cycle; no fifth token; 2 slots per cycle
- next cooperative governed-request bound (not the ~115s gate)
- past-due `WAITING` can claim; `CLAIMED` is re-enterable
- Cycle-2 2400s deadline is not factory `PROOF_DEADLINE`
- refresh timing remains `+600/+1200/+1800/+2400`
- official zero-state counts `WAITING`/`CLAIMED` refresh waits
- Source Governor ceilings unchanged
- Scheduler core unchanged
- no schema migration

## Production functions changed

- `reconcile_parent_interrupted_open_pre_admission_attempts` in
  `src/printer_v1/operator_cli/four_token_factory_adapter.py`
- `reconcile_campaign_terminal` in
  `src/printer_v1/operator_cli/unified_terminal_closure.py`

## Tests added/changed

Added:

`tests/test_v2_9_8b_four_concurrent_post_implementation_correction.py`

Required GREEN coverage in that file:

- parent-interrupt atomic cleanup with durable reopen (`WAITING`, `CLAIMED`, job-already-cancelled, replay)
- campaign-terminal invoked with Cycle-1 `cycle_id` catches Cycle-2 `WAITING` and `CLAIMED` waits
- unrelated campaign/run untouched
- genuine four-token overlapping 15m / 1h / 4h lifecycle state
- Cycle-2 2400s deadline while Cycle 1 continues (`WAITING` and `CLAIMED`)
- serial close contention; missed close evidence is `FAILED` / `DIRTY`, not silently passed
- no duplicate source request on cooperative resume
- 476 / 118 / 444 unchanged; retries 0; endpoint rotation false
- no fifth token / third cycle
- disposable-DB FK/integrity
- no locked capabilities activated

## Tests/checks run

```text
.venv/bin/pytest tests/test_v2_9_8b_four_concurrent_post_implementation_correction.py -q
.venv/bin/pytest tests/test_v2_9_8b_interrupted_cycle2_parent_interrupt_cleanup.py tests/test_v2_9_8b_four_concurrent_overlapped_two_cycle_fast_admission.py -q
.venv/bin/pytest tests/test_v2_9_8b_interrupted_four_token_followup_repair.py tests/test_v2_9_8b_pre_admission_terminal_cleanup_repair.py -q
.venv/bin/pytest tests/test_v2_9_8b_cooperative_later_cycle_repair.py tests/test_v2_9_8b_four_concurrent_post_implementation_correction.py -q
```

Results: all focused commands GREEN.

No broad unrelated regression suite was run.

## Confirmations

- authoritative DB unchanged
- surviving Sep-2 `WAITING` row not drained
- no live providers/RPC/WebSockets
- no Printer campaign
- no authorization created or applied
- `59fdefe7` remains permanently non-reusable
- no schema change
- no budget change
- no Scheduler-core change
- no refresh timing change
- no 12h/24h/retrieval/financial unlock
- all V1 locks preserved

## Exact next permitted action

```text
INDEPENDENT CODE REVIEW / OPERATOR REVIEW
```

Do not automatically proceed to wait reconciliation, authorization
preparation, or live execution. Do not drain the surviving wait. Do not run
Printer. Do not call `apply_authorization_once`.

`V2_9_8B_FOUR_CONCURRENT_OVERLAPPED_TWO_CYCLE_POST_IMPLEMENTATION_CORRECTION_PASS`
