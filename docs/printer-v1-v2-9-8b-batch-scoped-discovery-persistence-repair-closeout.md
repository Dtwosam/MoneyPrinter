# Printer V1 V2-9.8B.16 Batch-Scoped Discovery Persistence Repair Closeout

## 1. Verdict

```text
V2_9_8B_16_BATCH_SCOPED_PERSISTENCE_REPAIR_PASS
READY_FOR_OPERATOR_REVIEW_BEFORE_SEPARATE_PRODUCTION_RETRY
```

This verdict closes only the design, implementation, disposable proof, and
audit closeout authorized by V2-9.8B.16. It does not authorize a production
campaign, live source use, an automatic retry, or any capability unlock.

Implementation/proof commit:

```text
02445ac Repair V2-9.8B batch-scoped discovery persistence
```

## 2. Starting gate

The lane started at exact clean HEAD:

```text
e89efa47d63032e78458ea57c96f259e0daed393
```

The following gates passed before any edit:

- tracked and untracked worktree clean;
- no active Printer process;
- no active Printer Scheduler work;
- no active campaign lease or supervision;
- authoritative SQLite integrity `ok`;
- zero authoritative foreign-key violations.

The authoritative database was inspected read-only and was not used by any
proof. No production process or source was started.

## 3. Source-grounded blocker classification

```text
CLASSIFICATION: COMMITTED_CODE_DEFECT
REPAIR TYPE: identity ownership plus terminal observability
SCHEMA MIGRATION: NOT REQUIRED
HISTORICAL REWRITE: NOT REQUIRED
```

The V2-9.8B.15 audit proved that four batch-owned objects were assigned global
identities. Their immutable canonical content included the discovery batch, so
a later lawful campaign could reuse an ID while necessarily producing a
different hash or immutable value set.

The repair is code-justified and narrower than a schema or policy change.
Existing `TEXT` primary keys and FKs accept the new IDs, and historical rows
remain valid and untouched.

## 4. Repair implemented

### 4.1 Batch-scoped identities

One deterministic private constructor now produces:

```text
<object-kind>:<24-character batch SHA-256 prefix>:<24-character semantic SHA-256 prefix>
```

The semantic hash uses a fixed domain and length-delimited parts. The affected
objects are:

| Object | Batch-scoped semantic owner |
|---|---|
| provider observation | route/provider plus exact source-fact identity |
| merged candidate | exact candidate identity key |
| origin verification | batch-owned merged candidate |
| PumpSwap confirmation | batch-owned merged candidate |

Direct-create, graduation-native, and secondary-provider observations all use
the same constructor. The persistence functions, canonical payloads, immutable
hash checks, FK constraints, and transactions were not weakened.

Consequently:

- same batch plus identical object content resolves to the same ID and remains
  idempotent;
- same batch plus conflicting object content resolves to the same ID and is
  rejected;
- a later batch observing the same lawful mint/signature receives a distinct
  ID and independent provenance.

### 4.2 Safe structured fault evidence

`DiscoveryPersistenceError` terminalization now retains exactly:

```text
exception_type
safe_message
persistence_stage
object_kind
first_terminal_cause
lifecycle_started
```

Known repository-owned conflict messages may pass through a fixed allowlist.
Any other exception text is replaced with:

```text
discovery persistence contract rejected
```

The envelope propagates from executor result through activation/lifecycle and
into `terminal.fault_details` in the canonical terminal report and
`fault_details` in terminal summary evidence. `PERSISTENCE_FAULT` remains the
immutable first terminal cause, and the pre-lifecycle boundary remains false.

No payload, URL, source secret, filesystem path, or arbitrary exception text is
copied into terminal evidence.

### 4.3 Truthful stdout/stderr artifacts

The operational command no longer declares or touches `stdout.log` and
`stderr.log`. The PowerShell wrapper continues to run Python in the foreground,
so process output belongs truthfully to the invoking console. No historical
artifact was deleted.

## 5. Disposable proof results

All new proof work used fixture sources and newly migrated temporary SQLite
databases.

Command:

```text
.venv/bin/pytest -q tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py -x
```

Result:

```text
4 passed in 0.85s
```

| Required proof | Result | Evidence |
|---|---|---|
| sequential campaigns reuse the same mint/signature | PASS | two distinct batch IDs and two distinct IDs in each of the four affected tables |
| same-batch identical replay | PASS | all four canonical persistence owners accepted exact repeats idempotently |
| same-batch conflicting replay | PASS | all four owners raised their existing conflict errors |
| true conflict rollback | PASS | an actual first-write/second-conflicting-write sequence returned `PERSISTENCE_FAULT`; every measured discovery, selection, tracking, Scheduler, factory, window, episode, and fingerprint table returned to its before count |
| safe terminal details | PASS | six exact fields reached lifecycle and terminal report; injected `api_key=DO_NOT_EXPOSE` text was absent |
| truthful logging | PASS | artifact contract contains no stdout/stderr paths or touch calls; wrapper claims neither file |
| database and lock safety | PASS | disposable integrity `ok`, zero FK violations, zero active Scheduler/discovery work, and zero locked financial/retrieval rows |

The rollback proof covered these paths together:

```text
discovery batch/work/source/observation/candidate/origin/PumpSwap
selection links and selected items
tracking queue and token slots
Scheduler jobs
factory runs and steps
memory windows, episodes, and fingerprints
retrieval and financial tables
```

## 6. Focused neighboring regressions

Changed-path compilation and static checks passed:

```text
.venv/bin/python -m py_compile <five changed Python owners> <new proof>
git diff --check
```

Minimum neighboring regression command:

```text
.venv/bin/pytest -q \
  tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py \
  tests/test_v2_9_7d_7b_4c_discovery_persistence.py \
  tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py -x
```

Result:

```text
30 passed in 18.85s
```

Additional terminal/artifact neighbors:

```text
tests/test_v2_9_8a_public_operational_command.py
  5 passed, 1 deselected

tests/test_v2_9_8b_4_blocked_supply_source_reporting.py
  3 passed
```

No broad suite was run.

### 6.1 Confirmed pre-existing disposable-fixture setback

An initial neighboring run stopped at the first failure after 32 passes, as
required. The unchanged test
`test_preflight_is_zero_source_and_zero_write_after_scheduler_terminal` copies
the current authoritative corpus, deletes only the campaign ownership tables,
and then asks preflight to verify FKs. Retained historical discovery, report,
slot, and holder-operation rows still reference those deleted rows, so the
test's disposable copy contains FK orphans before the assertion.

This boundary was proven by replaying the unchanged baseline setup SQL against
a disposable copy. `PRAGMA foreign_key_check` identified only references made
orphan by that setup. The test and preflight integrity logic are byte-identical
at baseline `e89efa4`; this repair changes only the operational artifact keys
and fault-detail arguments in that module. The authoritative database itself
still reports integrity `ok` and zero FK violations.

The stale fixture was not changed because it is neither a repair dependency nor
a product defect in this lane. It does not invalidate any required changed-path
proof, but it remains an efficiency blocker for a future test-maintenance lane.

## 7. Invariants preserved

- no migration and no historical-row rewrite;
- canonical immutable hashes and conflict rejection preserved;
- FK ownership and atomic rollback preserved;
- Source Governor and Central Scheduler ownership preserved;
- candidate policy and fixed six-row limit unchanged;
- `$3,000` floor unchanged;
- source ceiling 45 unchanged;
- two-token capacity unchanged;
- cooldowns and windows unchanged;
- retrieval and financial deltas zero;
- no successor, restart, campaign retry, or production authorization created.

## 8. Money-usefulness contribution

The corpus can now retain lawful recurrence across bounded campaigns instead of
misclassifying a repeated mint/signature as a persistence fault. Each campaign
keeps exact independent provenance, while conflicting same-batch evidence still
fails closed. Structured redacted fault evidence also reduces wasted diagnosis
time and source budget without admitting dirty or partial memory.

This is operational reliability for future clean-memory growth; it is not a
profit claim and does not unlock a financial capability.

## 9. Minimum justified next lane

The minimum justified next action is:

```text
operator review of V2-9.8B.16 before any separately authorized production retry
```

If the operator later authorizes a production retry, that must be a separate
bounded lane with a fresh clean-HEAD gate, quiescence/lease/Scheduler checks,
backup verification, authoritative SQLite integrity/FK checks, exact source and
duration ceilings, and terminal evidence review. This closeout is not that
authorization.

## 10. What remains locked

The following remain locked:

- production retry and live source use without separate operator authority;
- automatic retry, unbounded runtime, restart, or successor creation;
- clean-memory promotion beyond an explicitly authorized lane;
- 1h/4h/12h/24h production expansion;
- retrieval activation;
- paper decisions and BUY/SELL/HOLD;
- paper positions, trades, audits, and PnL;
- wallets, private keys, signing, real funds, and live execution;
- paid APIs;
- scoring, ranking, confidence percentages, and weighted logic;
- embeddings and vectors.

## 11. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Current state | Control / next action |
|---|---|---|
| digest collision risk | bounded by two independent 96-bit SHA-256 prefixes; no observed collision | retain full canonical hash/constraint checks and fail closed |
| unknown persistence text | arbitrary text could contain secrets | fixed allowlist plus generic safe message |
| historical ID coexistence | old and new ID shapes coexist by design | no rewrite; batch/FK ownership remains authoritative |
| touch-only logs removed | console output is not retained in operation directory | truthful parent-console ownership; a future explicit tee design would require its own lane |
| stale operational preflight fixture | one unchanged neighboring test creates FK orphans in its disposable copy | future test-maintenance lane should construct a relationally complete quiescent fixture |
| production recurrence not re-proven | prohibited in this lane | separate operator-reviewed bounded campaign only |
| money outcome unchanged | reliability repair creates no trade or PnL evidence | keep financial capabilities locked |

## 12. Closeout

V2-9.8B.16 is complete. The proven cross-batch persistence defect is repaired
without schema change, historical rewrite, policy drift, live source use, or
authoritative database mutation. Required disposable proof passes. Another
production campaign is not automatically authorized.
