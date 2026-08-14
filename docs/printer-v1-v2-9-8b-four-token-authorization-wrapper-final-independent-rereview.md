# Printer V1 V2-9.8B Four-Token Authorization Wrapper Final Independent Rereview

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_AUTHORIZATION_WRAPPER_FINAL_INDEPENDENT_REREVIEW_PASS_READY_FOR_AUTHORIZATION_PREPARATION`

This rereview is code/document review only. It creates no real authorization, consumes no authorization, starts no Printer runtime, performs no source/RPC call, mutates no authoritative database, and applies no migration.

## Authority and baseline

- Previous rereview: `dfcad739fe8fc4d5277a4a0619da3f01b1e142b8`
- Repair HEAD reviewed: `418f78aa614fb5fc38fe763a98b8109a1ea8cafe`
- GitHub comparison: repair HEAD is exactly 3 commits ahead, 0 behind, merge-base equal to the rereview baseline.
- Scope: the remaining host-process coverage blocker only. The already accepted supervision-state repair and authorization-wrapper seams were not reopened.

## Finding

PASS. The host-process coverage blocker is closed.

### RED validity

`1cf92dc5a5ea9b8c02cc21dbe0b69f3ccf949856` correctly exposed that the prior probe missed a live wrapper-bound operational child when `printer_proof_run_supervision` contained no active row. That is the exact gap identified in the prior rereview.

### GREEN validity

`4c756220b1d2f80abbc128aac680fa0000089ff7` adds a genuinely independent host-state authority while preserving the durable proof-supervision PID check as a second defence.

The implementation reuses the repository's existing platform process enumeration in `operational_campaign_recovery` by factoring it into `host_process_inventory(...)`:

- POSIX: one `ps -axo pid=,command=` pass;
- Windows: one `Get-CimInstance Win32_Process` pass;
- fixed default 5-second timeout;
- `check=False`, `shell=False`;
- no polling, signalling, killing, or process mutation;
- inspection errors fail closed.

The Windows extraction corrects the pre-existing JSON/parsing mismatch by parsing the requested CIM JSON and failing closed on malformed data. The existing recovery probe now consumes the shared inventory and retains its prior matching semantics.

### Four-token gate coverage

`active_printer_runtime_processes(...)` now combines:

1. host inventory matched against the current operational command shapes; and
2. live PIDs from active proof-supervision rows checked through the existing `process_is_alive` owner.

Host matching requires both a known operational launcher and one exact runtime mode token:

- `run`
- `standard-four-hour-run`
- `four-token-bounded-capacity-proof-run`

This closes the startup-gap class where a live wrapper-bound operational child exists before/without a proof-supervision row. Read-only auxiliary modes remain excluded.

The current wrapper PID and parent are excluded. Durable zero-state DB checks remain separate and unchanged.

### Testability seam

`printer_host_process_inventory` is a lowest-level injection seam only. Production defaults still call the shared platform `host_process_inventory(...)`; tests inject host inventory without starting Printer. The seam therefore improves deterministic testing without weakening production behaviour.

## Verification reviewed

Repair closeout reports:

- focused and directly affected set: `120 passed, 11 subtests passed`;
- `py_compile`: PASS for 3 touched production modules;
- `git diff --check`: clean;
- tracked worktree clean, with the protected operator artifacts left untracked/untouched.

The reported `test_v2_9_8b_1_first_operation_blocker_repair.py` failure is baseline-identical at the rereview baseline and repair HEAD and is unrelated to this extraction. No scope expansion is required.

No GitHub Actions workflow is attached to this branch HEAD; acceptance therefore relies on the reported local focused verification plus independent static review.

## Accepted wrapper state

The complete authorization-wrapper implementation is now accepted for authorization preparation:

- dedicated proof-only authorization profile/schema;
- exact 4/2/2 capacity and >=300-second spacing;
- separate 900-second acquisition and 18,000-second proof clocks;
- derived 472 / 117 / 420 capacity authority;
- migration-055 evidence narrowly bound;
- active-only supervision zero-state semantics preserving terminal history;
- independent host-process and durable-state guards before marker creation;
- one marker -> at most one child;
- proof-only CLI mode -> `FourTokenProofController.exact()` -> one canonical factory path;
- no second runner/event loop;
- historical authorizations non-reusable;
- no retry/rerun/resume/restart/successor;
- 12h/24h, retrieval, decisions, positions/trades/PnL remain locked.

## Next permitted lane

`FOUR_TOKEN_FINAL_AUTHORIZATION_PREPARATION`

Authorization preparation may create one fresh, unconsumed four-token authorization package only after a new exact-head/read-only authoritative-state snapshot passes. The authorization must then undergo a separate independent review before it may be consumed. No Printer runtime is authorized by this rereview.
