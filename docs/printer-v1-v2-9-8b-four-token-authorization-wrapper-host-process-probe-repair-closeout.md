# Printer V1 V2-9.8B Four-Token Authorization Wrapper Host-Process Probe Repair Closeout

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_AUTHORIZATION_WRAPPER_HOST_PROCESS_PROBE_REPAIR_PASS_READY_FOR_FINAL_REREVIEW`

This repair lane created no authorization, started no Printer runtime, performed
no live source or RPC call, mutated no authoritative database, applied no
migration, and did not run the four-token proof.

## Baseline

- Rereview HEAD: `dfcad739fe8fc4d5277a4a0619da3f01b1e142b8`
- Local branch synchronized to that HEAD by fast-forward only; no reset, clean,
  stash, or removal of untracked operator artifacts. Both protected
  `operator-runs/` directories remain untracked and untouched.

Scope was limited to the single host-process coverage blocker. The
supervision-state repair and every accepted authorization-wrapper seam were left
untouched.

## Defect

`active_printer_runtime_processes(...)` derived every candidate PID from
`printer_proof_run_supervision` rows in `STARTING`/`RUNNING`. Those same rows are
already rejected by the durable zero-state domain, so the probe added no host
coverage, and a current wrapper-bound operational child — which owns no
proof-supervision row — was missed entirely.

## Reused platform owner

No third-party process library is available (`pyproject.toml` declares only
`websockets`), so none was added. The repository already owns exactly one
platform process-enumeration implementation:
`operational_campaign_recovery._default_live_process_probe`, which runs
`ps -axo pid=,command=` on POSIX and `Get-CimInstance Win32_Process` on Windows
with a fixed 5-second timeout, `check=False`, `shell=False`.

That enumeration half was extracted into `host_process_inventory(...)` in the
same module and is now the single shared owner. No broader cross-platform design
decision was required, so this lane did not need to stop.

`_default_live_process_probe` keeps its exact matching semantics and now consumes
the shared inventory. A focused regression test locks its behaviour: own PID
skipped, unrelated processes unmatched, `operational_memory_factory_command ...
run` matched, and `execution_id` substring matched.

One deliberate behaviour difference exists on Windows only: the previous code
requested compressed CIM JSON but parsed it with POSIX line splitting, so it
would have silently yielded nothing. `_windows_process_inventory` now parses that
JSON and fails closed on malformed output. This is strictly more capable than the
prior silent empty result and cannot weaken the rule; the production operator
platform is macOS, whose behaviour is byte-identical.

## Host-state authority in the four-token gate

`active_printer_runtime_processes(...)` now combines two independent authorities
in one bounded read-only pass, with neither treated as complete:

- **host state** — one `host_process_inventory()` pass matched by
  `is_printer_operational_runtime_command(...)`. A match requires both a known
  operational launcher (the command module, `Start-PrinterV1-MemoryFactory`, or
  `printer-run-v2-9-8-memory-factory`) **and** one of `run`,
  `standard-four-hour-run`, or `four-token-bounded-capacity-proof-run` present as
  its own whitespace-delimited argument token;
- **durable supervision** — live PIDs from proof-supervision rows still claiming
  active ownership, unchanged from the accepted repair.

Requiring both a launcher and an exact mode token is what keeps unrelated Python
processes, a `grep` naming the module, and read-only auxiliary modes such as
`status` from false-positiving.

Properties preserved: one bounded inspection, read-only, no polling, no
signal/kill/mutation, the wrapper's own process tree (`os.getpid()`,
`os.getppid()`) excluded, fail-closed on any host or durable inspection error,
the check before application-marker creation, and the durable zero-state database
domains retained as a separate defence.

`apply_authorization_once(...)` gained a `printer_host_process_inventory` seam
alongside the existing database and liveness seams. All three default to
production behaviour; tests inject only the lowest-level host inventory.

## RED / GREEN

| Step | SHA |
|---|---|
| RED | `1cf92dc` |
| GREEN | `4c75622` |

### RED evidence

With no `printer_proof_run_supervision` row present and a permissive liveness
predicate, the pre-repair probe returned `()` — the documented miss. The host
seam did not exist at all:

```
TypeError: active_printer_runtime_processes() got an unexpected keyword argument
'host_process_inventory'
AttributeError: module 'operational_campaign_recovery' has no attribute
'host_process_inventory'
```

```
12 failed, 1 passed
```

### GREEN evidence

```
11 passed, 3 subtests passed
```

Proven by the focused tests:

1. a live ordinary operational child blocks;
2. a live standard-four-hour child blocks;
3. a live four-token proof child blocks;
4. no application marker or canonical directory is created and no child launches
   on block;
5. unrelated Python, shell, `grep`, and `status`-mode processes do not
   false-positive;
6. the current wrapper PID and its parent are excluded;
7. host-inspection failure fails closed with `printer_process_state_unavailable`;
8. clean host state proceeds and launches exactly one child with
   `printer_processes=0`;
9. the existing active/terminal supervision semantics are unchanged, verified by
   the full zero-state suite.

Items 1–4 and 8 are exercised through the real default zero-state gate; the gate
itself is never replaced by a fake.

## Files changed

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/operational_campaign_recovery.py` | extracted `host_process_inventory(...)`, added Windows JSON parsing, `_default_live_process_probe` consumes the shared owner |
| `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` | operational command-shape matcher and host-state authority in the probe |
| `src/printer_v1/operator_cli/four_token_proof_one_shot_wrapper.py` | `printer_host_process_inventory` seam threaded to the default gate |
| `tests/test_v2_9_8b_four_token_proof_host_process_probe.py` | new focused host-process contract |

## Verification

Focused probe, zero-state, one-shot wrapper, integrated disposable wrapper,
authorization profile, migration-055 evidence, CLI mode, existing-wrapper locks,
standard-four-hour activation authorization, and WINDOW_15M one-shot wrapper:

```
120 passed, 11 subtests passed
```

`py_compile` passed for all three touched production modules. `git diff --check`
is clean. The tracked worktree is clean; only the two protected operator-runs
directories remain untracked.

`tests/test_v2_9_8b_1_first_operation_blocker_repair.py` reports 7 failed /
1 passed identically at the baseline `dfcad73` and at this HEAD, verified in a
detached worktree. It is a pre-existing baseline failure, not caused by the
inventory extraction, and was not expanded into this lane. The extracted probe's
behaviour is locked directly by the new focused regression test instead.

## What remains locked

No real authorization preparation or creation, Printer runtime, live sources,
authoritative database mutation, migration, 12h/24h, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, live wallet/private keys/real
funds, or paid APIs. Retry, rerun, resume, restart, and successor remain false.

## Next permitted lane

One focused independent rereview of this single seam. Only a PASS may move to
fresh four-token authorization preparation.
