# Printer V1 — Four-Concurrent 4/2/2 Terminal Transaction Safety + Production-Owner Proof Hardening Closeout

Status: **CLOSED PASS**

Verdict:

`V2_9_8B_FOUR_CONCURRENT_4_2_2_TERMINAL_TRANSACTION_AND_PRODUCTION_OWNER_PROOF_HARDENING_PASS`

This lane repaired unified-terminal speculative state-transition rollback and
hardened frozen production-owner proofs. It did not redesign the approved 4/2/2
architecture, parent-interrupt ownership, or campaign+run wait scope. It did
not run Printer, drain the surviving Sep-2 wait, prepare an authorization, or
call live providers.

## Identity

- start HEAD: `091a08be6ac5c914aae2f8e7ad032724907c8e8a`
- surviving wait (not drained):
  `prelifecycle-refresh-wait:20260902T123958Z-5a3e78f1a7b8-campaign:20260902T123958Z-5a3e78f1a7b8-campaign-run:20260902T123958Z-5a3e78f1a7b8-cycle-2:1`
  state still `WAITING`
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` remains
  `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

## Authoritative DB

Path: `data/printer_v1.sqlite3`

- SHA-256 before: `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`
- SHA-256 after: `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`
- unchanged

## Production files / functions changed

`src/printer_v1/operator_cli/unified_terminal_closure.py`

- `_transition` — no longer loops guessed candidate states. Callers pass the
  already-read current state and `transition_state` is invoked exactly once.
- `reconcile_campaign_terminal` — window, token-slot, cycle, run, and campaign
  transitions now use the exact current state. Speculative `SELECTED`-first
  token-slot attempts are gone.

Accepted `091a08be` behavior preserved:

- parent-interrupt owned `BEGIN IMMEDIATE` -> attempt/job terminalize -> wait
  abandon -> one commit
- campaign-terminal wait cleanup scoped by `campaign_id + run_id`

## Tests added/changed

Added:

`tests/test_v2_9_8b_four_concurrent_terminal_transaction_and_production_owner_proof.py`

Coverage:

- no speculative `_transition` guesses
- Cycle-1 `WINDOW_1H_CONTINUING` / `WINDOW_4H_CONTINUING` campaign-terminal
  retains Cycle-2 wait cleanup after reopen
- CLAIMED wait + work retained; unrelated campaign/run untouched
- injected later transition failure cannot return clean-terminal while
  surviving WAITING ownership is the report result
- production-owner four-token overlapping 15m / 1h / 4h
- Cycle-2 2400s expiry then Cycle-1 continuation snapshot actually executes
- serial close through `_execute_close_evidence_phase`; missed evidence is
  FAILED, not silent CLEAN
- cooperative resume through real `run_fresh_profile_locator` / Source
  Governor: one durable request, checkpoint replay, no duplicate response
- 476/118/444, retries 0, endpoint rotation false, no fifth token / third cycle

## Tests/checks run

```text
.venv/bin/pytest tests/test_v2_9_8b_four_concurrent_terminal_transaction_and_production_owner_proof.py tests/test_v2_9_8b_four_concurrent_post_implementation_correction.py tests/test_v2_9_8b_interrupted_cycle2_parent_interrupt_cleanup.py tests/test_v2_9_8b_pre_admission_terminal_cleanup_repair.py -q
.venv/bin/pytest tests/test_v2_9_8b_interrupted_four_token_followup_repair.py tests/test_v2_9_8b_cooperative_later_cycle_repair.py tests/test_v2_9_8b_four_concurrent_overlapped_two_cycle_fast_admission.py -q
```

Results: GREEN (33 + 28).

## Confirmations

- no Printer execution
- no providers/RPC/WebSockets
- no authorization prepared/applied
- no schema change
- no budget change
- no Scheduler-core change
- no refresh timing change (`+600/+1200/+1800/+2400`)
- all V1 locks preserved

## Exact next permitted action

```text
INDEPENDENT CODE REVIEW / OPERATOR REVIEW
```

Do not automatically reconcile the historical wait. Do not prepare an
authorization. Do not run Printer.
