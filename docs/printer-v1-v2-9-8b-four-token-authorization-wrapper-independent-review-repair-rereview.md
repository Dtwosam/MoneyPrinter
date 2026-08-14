# Printer V1 V2-9.8B Four-Token Authorization Wrapper Independent-Review Repair Rereview

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_AUTHORIZATION_WRAPPER_REPAIR_REREVIEW_BLOCKED_PROCESS_PROBE_COVERAGE`

This is an independent rereview only. It creates no authorization, starts no Printer process, performs no source/RPC call, mutates no authoritative database, applies no migration, and does not run the four-token proof.

## Baseline and ancestry

- prior independent review: `66c9c559992dac689a71dce11ea9951bd9c1f055`
- submitted repair closeout HEAD: `92dc9ca0953d5effbd1091f80c97924e617509c3`
- GitHub compare: repair HEAD is 5 commits ahead, 0 behind, with merge base exactly `66c9c559992dac689a71dce11ea9951bd9c1f055`
- no GitHub commit statuses and no pull-request workflow runs are attached to `92dc9ca`; reported pytest/py_compile/diff-check results are local supporting evidence only

Accepted seams from the previous review remain accepted and are not reopened: dedicated four-token authorization/profile/schema, exact 4/2/2 policy, separate 900/18,000 clocks, migration-055 evidence binding, one-marker/one-child law, proof-only CLI composition, canonical factory integration, historical authorization non-reuse, and existing WINDOW_15M / standard-four-hour wrapper locks.

## Blocker 1 rereview — PASS

RED `1c47315` correctly reproduces the historical-supervision defect. GREEN `21c69cb` changes only the two supervision projections:

- campaign supervision counts `ACTIVE` / `STOPPING` only;
- proof supervision counts `STARTING` / `RUNNING` only.

This matches migrations 033 and 030, which deliberately retain `TERMINAL` supervision as durable history. The focused tests also keep the active-state cases blocking and verify terminal rows survive unchanged. This blocker is closed.

## Blocker 2 rereview — BLOCKED

The hard-coded empty process probe was removed, but the replacement does not yet satisfy the design requirement to detect another active Printer runtime before marker creation.

`active_printer_runtime_processes(...)` derives every candidate PID exclusively from:

```sql
SELECT process_id
FROM printer_proof_run_supervision
WHERE execution_status IN ('STARTING','RUNNING')
  AND process_id IS NOT NULL
```

This is insufficient for the current wrapper-bound operational architecture for two independent reasons.

### 1. The probe adds no process coverage beyond an existing zero-state blocker

The same zero-state gate already counts `printer_proof_run_supervision` rows in `STARTING` / `RUNNING` and fails whenever that count is non-zero. Therefore every process the new helper can discover is already rejected by the durable `proof_supervision` domain before process liveness adds any new safety information.

The helper does not cover a live Printer process that is absent from that historical proof-supervision ledger.

### 2. Current wrapper-bound operational children are not guaranteed to own proof-supervision rows

Repository search shows production `create_execution(...)` usage belongs to the older proof-supervision / two-token pilot path, not the current public operational wrapper path. `one_command_15m_factory` can attach a PID only when a `supervision_execution_id` is supplied, while the current `operational_memory_factory_command.py` wrapper-bound ordinary / standard-four-hour / four-token composition does not establish that proof-supervision execution identity.

Accordingly, a current ordinary, standard-four-hour, or four-token wrapper-bound Printer child is not guaranteed to appear in `printer_proof_run_supervision` merely because its host process exists.

The new focused test does not prove this missing case. Its `existing Printer runtime` fixture first inserts a synthetic `RUNNING` proof-supervision row and then makes the injected liveness predicate return true for that row's PID. That proves liveness filtering of proof-supervised PIDs; it does not prove detection of the current operational child class that motivated the independent-review blocker.

This matters most at the startup concurrency boundary: a live wrapper-bound child can exist before durable campaign ownership has become visible to the zero-state DB projections. The process check was required as an independent host-state guard for that gap, not as a second reading of the same proof-supervision ownership row.

## Required repair boundary

Repair only host-process coverage. Do not reopen blocker 1 or any accepted authorization-wrapper seam.

The production pre-consumption gate must perform one bounded, read-only host-state check that can identify another active Printer runtime of the current wrapper-bound operational command independently of `printer_proof_run_supervision` rows.

Requirements:

- detect current operational Printer child processes, including ordinary `run`, `standard-four-hour-run`, and `four-token-bounded-capacity-proof-run` command shapes where applicable;
- exclude the harmless current wrapper process / its legitimate launcher context;
- do not signal, kill, mutate, or poll processes;
- fail closed when host process state cannot be inspected reliably;
- stay before marker creation;
- retain the durable zero-state DB checks as a separate defence;
- do not broaden public authority or add a second factory/runner;
- use focused RED -> GREEN tests where RED demonstrates a live current wrapper-bound operational child that has no proof-supervision row is missed by the present implementation.

If reliable host-process enumeration cannot be composed from existing project/platform owners without a broader cross-platform design decision, stop and report that exact blocker rather than silently treating proof-supervision as complete process authority.

## What remains locked

No real authorization preparation or creation, Printer runtime, live sources, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live wallet/private keys/real funds, paid APIs, retries, reruns, resumes, restarts, or successors are unlocked by this rereview.

## Next permitted lane

`FOUR_TOKEN_AUTHORIZATION_WRAPPER_HOST_PROCESS_PROBE_REPAIR`

After a focused repair closeout, perform one more independent rereview of that single seam. Only a PASS may move to fresh four-token authorization preparation.