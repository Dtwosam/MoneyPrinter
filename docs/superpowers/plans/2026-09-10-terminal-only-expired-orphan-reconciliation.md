# Terminal-Only Expired-Orphan Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, operator-authorized, terminal-only recovery path for a proven-dead, expired operational four-token Standard-4H campaign without resuming work, reusing authorization, or creating new clean memory.

**Architecture:** A new `expired_orphan_reconciliation` module owns a read-only exact orphan inspection and a compare-and-swap terminalizer. Inspection binds exact campaign/run/configuration/supervision identity, immutable consumed authorization facts, process absence, expired lease ownership, lawful 4/2/2 admitted shape, database health, active ownership, and memory preservation into a stable SHA. Terminalization requires that approved SHA, creates a verified pre-recovery backup, re-inspects, delegates only to existing terminal reconciliation and supervision cleanup owners, and proves zero active residue with no new source/Scheduler/memory/financial work.

**Tech Stack:** Python 3.11, SQLite, argparse, pytest/unittest-compatible tests, existing Printer V1 campaign/supervision/backup/terminal owners.

**Spec:** `docs/superpowers/specs/2026-09-10-terminal-only-expired-orphan-reconciliation-design.md`

## Global Constraints

- Scope is only `four-token-standard-four-hour-run`.
- Consumed authorization remains permanently non-reusable: no retry, rerun, resume, restart, or successor.
- Recovery performs zero provider/RPC/WebSocket/source calls and executes no Scheduler work.
- Source Governor and Central Scheduler ownership contracts remain unchanged.
- Recovery creates no campaign, cycle, factory run, source request, Scheduler job, episode, fingerprint, retrieval, decision, position, PnL, wallet, signing, funds, or trading action.
- Existing clean 15m/1h/4h memories are preserved; incomplete windows are never promoted.
- `WINDOW_5M` remains support-only; `WINDOW_12H` and `WINDOW_24H` remain locked.
- Zero-state remains read-only and is not turned into an auto-repair owner.
- Historical `recover-orphan` behavior remains separate and unchanged.
- Tests use disposable databases/artifacts only and no live network/provider/Scheduler execution.
- No schema migration is authorized by this plan. If one becomes necessary, stop implementation and revise the design.

---

### Task 1: Stable read-only expired-orphan inspection

**Files:**
- Create: `src/printer_v1/operator_cli/expired_orphan_reconciliation.py`
- Create: `tests/test_v2_9_8b_expired_orphan_reconciliation.py`

**Interfaces:**
- Consumes: `four_token_operational_composition.exact_operational_policy()`, `campaign_evidence_sha256()`, `host_process_inventory()`, `is_printer_operational_runtime_command()`, `canonical_migration_names()`, `campaign_active_work_report()`.
- Produces: `inspect_expired_orphan(db_path, *, campaign_id, run_id, artifact_root, process_inventory=None, now=None) -> dict[str, Any]` and `ExpiredOrphanReconciliationError`.

- [ ] **Step 1: Write the failing inspection tests**

Add a disposable fixture that applies canonical migrations to a temp SQLite database, inserts one exact operational 4/2/2 campaign/config/run/origin-cycle/supervision graph, and writes an exact expired lease file. The configuration must include `command_mode="four-token-standard-four-hour-run"`, exact operational policy facts, an internal authorization marker with canonical SHA, and the durable operational database-target expectation with `authorization_consumed_once=True`, invocation counts `1/1`, and all five reuse flags false.

Add tests asserting:

```python
result = orphan.inspect_expired_orphan(
    db_path,
    campaign_id=campaign_id,
    run_id=run_id,
    artifact_root=artifact_root,
    process_inventory=lambda: (),
    now=expired_now,
)
assert result["eligible"] is True
assert result["blockers"] == []
assert result["admitted_shape"] == "PRE_ADMISSION"
assert len(result["inspection_sha256"]) == 64
assert result["source_calls"] == 0
assert result["scheduler_runtime_calls"] == 0
assert result["database_writes"] == 0
```

Also assert the same unchanged orphan inspected at two later wall-clock instants returns the same `inspection_sha256`; a visible `four-token-standard-four-hour-run` host process blocks; a non-expired lease blocks; wrong mode/policy/reuse flags block; missing/malformed/mismatched lease blocks; ambiguous second active supervision blocks; and partial/duplicate cycle-slot shapes block.

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```bash
python -m pytest -q tests/test_v2_9_8b_expired_orphan_reconciliation.py -k inspection
```

Expected: import/attribute failure because the new module/inspector does not exist.

- [ ] **Step 3: Implement the smallest read-only inspector**

Implement constants:

```python
INSPECTION_SCHEMA_VERSION = "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_EXPIRED_ORPHAN_INSPECTION_V1"
RECOVERY_CAUSE = "OPERATIONAL_CAMPAIGN_ORPHANED_AFTER_LEASE_EXPIRY"
AUTHORIZED_MODE = "four-token-standard-four-hour-run"
```

Use immutable/read-only SQLite access. Resolve exactly one requested campaign/run, exactly one configuration and supervision, parse configuration JSON, compare `command_mode` and the embedded four-token policy to `exact_operational_policy()`, recompute the internal authorization marker SHA, validate the durable database-target expectation identities and one-shot non-reuse facts, prove migration/integrity/FK/sidecar health, classify host processes through the existing runtime-command classifier, validate the exact regular non-symlink lease file against supervision identity, prove lease expiry, classify admitted shape as only `PRE_ADMISSION`, `CYCLE_1_ADMITTED`, or `TWO_CYCLES_ADMITTED`, collect exact active ownership, and snapshot campaign-linked memory/episode/fingerprint identities.

Build a stable canonical payload that excludes observation timestamps and includes only meaningful durable/process state. Compute:

```python
inspection_sha256 = hashlib.sha256(
    (json.dumps(stable_payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    .encode("utf-8")
).hexdigest()
```

Return categorical blockers instead of mutating on any failed proof.

- [ ] **Step 4: Run inspection tests GREEN**

Run the same focused command and require all inspection tests pass.

- [ ] **Step 5: Commit Task 1**

Commit test + inspector together after RED→GREEN evidence.

---

### Task 2: Backup-bound terminal-only recovery and memory preservation

**Files:**
- Modify: `src/printer_v1/operator_cli/expired_orphan_reconciliation.py`
- Modify: `tests/test_v2_9_8b_expired_orphan_reconciliation.py`

**Interfaces:**
- Consumes: Task 1 inspection result, `operational_backup_restore_preflight()`, `reconcile_campaign_terminal()`, `reconcile_admitted_campaign_terminal()`, `cleanup_campaign_supervision()`.
- Produces: `terminalize_expired_orphan(db_path, *, campaign_id, run_id, artifact_root, inspection_sha256, operator_approved, process_inventory=None, now=None, backup_preflight=operational_backup_restore_preflight) -> dict[str, Any]`.

- [ ] **Step 1: Write failing terminalization tests**

Cover `PRE_ADMISSION`, one-cycle/two-slot, and two-cycle/four-slot orphans. Assert that terminalization without `operator_approved=True` blocks; stale inspection SHA blocks before mutation; backup failure causes zero DB mutation; and successful recovery results in `TERMINAL_FAILED` campaign/run/cycles, terminal failed supervision, released/removed lease, zero exact active work, and non-active linked factory run/steps.

Snapshot before/after IDs and payloads for `printer_memory_windows`, `printer_episodes`, and `printer_memory_fingerprints`; assert no episode/fingerprint additions, no clean-memory promotion, no quality upgrade, and byte-for-byte preservation of pre-existing clean episode/fingerprint payloads.

- [ ] **Step 2: Run terminalization tests and observe RED**

```bash
python -m pytest -q tests/test_v2_9_8b_expired_orphan_reconciliation.py -k 'terminalize or recovery or memory'
```

Expected: missing `terminalize_expired_orphan` or unimplemented terminal behavior.

- [ ] **Step 3: Implement backup/CAS/terminal flow**

Require a lowercase 64-hex approved inspection SHA and explicit operator approval. Inspect first; require `eligible=True` and exact SHA. Create deterministic recovery directory:

```text
<artifact_root>/<execution_id>/orphan-recovery/<inspection_sha256>/
```

Run existing backup preflight using:

```text
printer_v1.pre-recovery.backup.sqlite3
printer_v1.restore-rehearsal.sqlite3
```

Then re-run inspection and require the stable SHA still equals the approved SHA before any authoritative mutation.

Resolve the linked factory run only from `printer_memory_factory_campaign_runs.authoritative_run_id`. Use `reconcile_campaign_terminal(..., run_status="FAILED")` for `PRE_ADMISSION`; otherwise use `reconcile_admitted_campaign_terminal(..., run_status="FAILED")`. Then call `cleanup_campaign_supervision(..., terminal_status="FAILED", first_terminal_cause=RECOVERY_CAUSE)` with exact identities. Never call source, discovery, lifecycle progression, memory-quality, or Scheduler execution APIs.

Perform read-only postconditions and fail success reporting unless exact active work is zero and the memory/source/Scheduler/locked-capability snapshots prove no forbidden creation/promotion. Write exactly one immutable `terminal-only-recovery.json` only after DB terminalization is proven.

- [ ] **Step 4: Run Task 2 tests GREEN**

Run the focused terminalization selection and then the whole recovery test file.

- [ ] **Step 5: Commit Task 2**

Commit only the terminalizer and its tests.

---

### Task 3: Explicit auxiliary CLI modes

**Files:**
- Modify: `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- Modify: `tests/test_v2_9_8b_expired_orphan_reconciliation.py`

**Interfaces:**
- Consumes: Task 1/2 public functions.
- Produces: CLI modes `inspect-expired-orphan` and `terminalize-expired-orphan`, with exact `--campaign-id`, `--run-id`, and terminalization-only `--inspection-sha256`.

- [ ] **Step 1: Write failing CLI tests**

Assert both new modes require campaign+run together and never fall back to latest. Assert inspection rejects `--operator-approved` as unnecessary authority if supplied only as a flag but performs no mutation; terminalization requires `--operator-approved` and `--inspection-sha256`. Assert wrapper provenance environment bindings are rejected/ignored as run authorization for these auxiliary modes and no child terminal binding is created.

- [ ] **Step 2: Run CLI tests RED**

```bash
python -m pytest -q tests/test_v2_9_8b_expired_orphan_reconciliation.py -k cli
```

Expected: argparse rejects the new modes or routes nowhere.

- [ ] **Step 3: Wire the CLI minimally**

Add constants for the two auxiliary mode strings, add `--inspection-sha256`, expand campaign/run argument validation to permit exactly `report-only`, `inspect-expired-orphan`, and `terminalize-expired-orphan`, reject missing paired IDs, and dispatch the new functions using `AUTHORITATIVE_DB` and `ARTIFACT_ROOT`. Keep both modes outside `wrapper_bound_modes` and `campaign_modes` so they never inherit child-run authorization semantics.

- [ ] **Step 4: Run CLI tests GREEN**

Run the CLI selection and the full recovery test file.

- [ ] **Step 5: Commit Task 3**

Commit CLI wiring + tests.

---

### Task 4: Replay, conflict, and preservation hardening

**Files:**
- Modify: `src/printer_v1/operator_cli/expired_orphan_reconciliation.py`
- Modify: `tests/test_v2_9_8b_expired_orphan_reconciliation.py`

**Interfaces:**
- Consumes/produces the same Task 1/2 APIs; no new public authority.

- [ ] **Step 1: Add failing replay/conflict tests**

Test: reconciliation committed with `RECOVERY_CAUSE` but cleanup not complete; cleanup complete but lease release incomplete; fully recovered state; conflicting first terminal cause; terminal supervision plus unrelated active residue; and state drift between approved inspection and terminalization. Require fresh inspection SHA for every mutating replay.

- [ ] **Step 2: Run replay tests RED**

```bash
python -m pytest -q tests/test_v2_9_8b_expired_orphan_reconciliation.py -k 'replay or conflict or drift'
```

- [ ] **Step 3: Implement only the explicit idempotent replay states**

Permit continuation only when existing first causes are null or exactly `RECOVERY_CAUSE`, ownership remains exact, and the replay matches one of the spec’s named partial-recovery states. A fully recovered target returns an `ALREADY_TERMINAL`/no-mutation result. Any different terminal cause or ambiguous residue remains blocked.

- [ ] **Step 4: Run full recovery test file GREEN**

```bash
python -m pytest -q tests/test_v2_9_8b_expired_orphan_reconciliation.py
```

- [ ] **Step 5: Commit Task 4**

Commit hardening + tests.

---

### Task 5: Shared-boundary verification, diff review, and durable handoff

**Files:**
- Modify: `.github/workflows/v2-9-8b-focused-repair-verify.yml` only as needed to execute the new recovery test on this lane and compile the new module.
- Modify: `CURRENT_HANDOFF.md` after verification.

**Interfaces:** none beyond existing CI and handoff state.

- [ ] **Step 1: Ensure branch CI executes the focused recovery test**

Add `assistant/terminal-only-expired-orphan-reconciliation` to the existing focused workflow branch filter and add an early step:

```bash
python -m pytest -q tests/test_v2_9_8b_expired_orphan_reconciliation.py
```

Add `src/printer_v1/operator_cli/expired_orphan_reconciliation.py` to the compile list. Do not change existing shared test semantics.

- [ ] **Step 2: Run/observe fresh verification on the final production tree**

Require:

```bash
python -m pytest -q tests/test_v2_9_8b_expired_orphan_reconciliation.py
python -m pytest -q tests/test_v2_9_8b_four_token_clean_4h_memory_proof.py::test_two_cycle_four_token_real_factory_forms_exactly_four_clean_4h_memories
```

Then require the existing shared-boundary regression step, affected-module compile, and `git diff --check` to pass.

- [ ] **Step 3: Review the actual diff against safety constraints**

Confirm the diff contains no provider/RPC calls, retry/resume/restart/successor logic, new Scheduler execution owner, memory promotion, relaxed quality/evidence thresholds, schema migration, 12h/24h unlock, retrieval/decision/financial activation, or change to historical `recover-orphan` semantics.

- [ ] **Step 4: Update `CURRENT_HANDOFF.md`**

Record the verified commit, exact test results, repaired catastrophic-orphan blocker, remaining operational caveat that this is terminal-only recovery rather than campaign survival/resume, and the next permitted action. State explicitly that no real recovery was executed against the authoritative DB.

- [ ] **Step 5: Final completion check**

Completion requires disposable proof that a consumed four-token Standard-4H campaign with a dead child and expired exact lease can be explicitly terminalized as failed, preserve already-valid clean memory, create no new source/Scheduler/lifecycle/memory/financial work, and leave zero exact owned active residue so a later separately authorized run can be evaluated by the unchanged zero-state gate.
