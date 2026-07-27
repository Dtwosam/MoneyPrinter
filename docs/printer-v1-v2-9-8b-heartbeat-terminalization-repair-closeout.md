# V2-9.8B.18 — Heartbeat Evidence and Pre-Lifecycle Terminalization Repair Closeout

**Final verdict:** `V2_9_8B_18_HEARTBEAT_TERMINALIZATION_REPAIR_PASS`

**Next-lane status:** `READY_FOR_OPERATOR_REVIEW_BEFORE_SEPARATE_PRODUCTION_RETRY`

**Implementation baseline:** `4d52a4e7d5f22b59715239722fbbb3793f013a1e`

**Implementation commit:** `455594e7f373745490429a16f1fbf32a75a44f10`

**Recovered execution:** `20260727T161750Z-95e40c3efae3`

**Recovered factory run:** `42afd94c-2e5a-40c3-939d-e1941a4033e4`

## Outcome

The repair, disposable proof, exact authoritative recovery, second-invocation
idempotency proof, and post-recovery closeout checks all passed.

No production campaign, live source, Source Governor request, Scheduler runtime,
retry, restart, or successor was run. This closeout does not authorize a
production retry.

## Implemented repair

### Durable first heartbeat failure

Migration `045_heartbeat_failure_evidence.sql` adds an immutable, one-row-per-
supervision ledger for the first renewal failure. It preserves:

- an allowlisted safe error type;
- a stable safe message and category;
- `sqlite_locked`;
- attempt time;
- prior heartbeat;
- prior lease expiry;
- confirmed/unconfirmed result;
- stable terminal cause.

Raw exception text is not persisted. SQLite-lock failure uses the exact owned
lease file as a durable sanitized fallback until the main coordinator can copy
the record into SQLite. The heartbeat thread remains signal-only; it does not
terminalize work.

### Stable cause and lifecycle boundary

Future heartbeat failures now use stable categorical causes:

- `LEASE_RENEWAL_SQLITE_LOCKED`;
- `LEASE_RENEWAL_LEASE_EXPIRED`;
- `LEASE_RENEWAL_OWNERSHIP_MISMATCH`;
- `LEASE_RENEWAL_UNCONFIRMED`.

The cancellation check immediately after factory creation is inside the
factory's canonical lifecycle `try/finally`. The newly committed factory-run ID
is published through a narrow callback and retained by the outer coordinator,
including failure paths. Outer reconciliation and reporting therefore receive
the exact initialized factory identity.

### Zero-step and pre-lifecycle terminal disposition

The unified terminal owner now:

- terminalizes an exact `RUNNING` zero-step factory as `SAFE_STOPPED`;
- moves exact campaign-owned `SELECTED` slots to `MANUAL_REVIEW`;
- moves only their linked `QUEUED` rows to `SKIPPED`;
- sets queue action to `MANUAL_REVIEW`;
- records the stable campaign-terminal reason;
- preserves every token, pair, discovery, source, selection, holder,
  readiness, and original report row.

The resumed disposable proof found one transaction-order mismatch: the queue
update reported `SKIPPED` but was rolled back by a later already-terminal
ownership transition. The exact row remained `QUEUED / PROMOTE_TO_TRACK_NORMAL`.
The fix placed the exact queue update before its selected-slot transition, so
the canonical slot transition commits the owned queue/slot pair together. The
ownership query and verification assertion were correct.

## Disposable proof

Command:

```text
.venv/bin/pytest -q tests/test_v2_9_8b_18_heartbeat_terminalization_repair.py -x
```

Result: `6 passed in 1.42s`.

Proven:

- successful heartbeat renewal;
- SQLite-lock renewal failure and lease-file durability fallback;
- expired-lease renewal failure;
- sanitized/redacted evidence and first-failure immutability;
- cancellation immediately after factory creation;
- exact factory-run ID propagation;
- zero-step factory terminalization;
- exact queue/slot reconciliation;
- truthful recovery report;
- zero active work;
- integrity `ok` and zero foreign-key violations;
- zero retrieval/financial deltas;
- no retry, restart, or successor;
- exact recovery idempotency.

Minimum neighboring regressions:

```text
.venv/bin/pytest -q -x \
  tests/test_v2_9_7b_4_heartbeat_lease_reliability.py \
  tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py \
  tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py
```

Result: `48 passed, 2 skipped, 35 subtests passed`.

No broad suite was run.

## Exact authoritative recovery

### Pre-mutation ownership gate

Read-only checks proved:

- exact execution, campaign, configuration, campaign run, cycle, supervision,
  and owner identities;
- factory `42afd94c-2e5a-40c3-939d-e1941a4033e4` was `RUNNING` with zero steps;
- slot 1 linked token/pair `20/24` to queue `18`;
- slot 2 linked token/pair `21/25` to queue `19`;
- both slots were `SELECTED` and both exact queues were `QUEUED`;
- supervision was terminal and its lease file was absent;
- no active Printer process, campaign work, or Scheduler work existed;
- SQLite integrity was `ok` with zero foreign-key violations;
- no prior V2-9.8B.18 recovery report existed.

### Fresh backup

The committed recovery owner created and restore-verified:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/20260727T161750Z-95e40c3efae3/
v2-9-8b-18-recovery-20260727T210000Z/
printer_v1.pre-v2-9-8b-18-recovery.sqlite3
```

SHA-256:

```text
49d9d1cadf910acb011e31240bc6f38ab49d4e7bf2f6b8eb270cb3d9a949f851
```

The backup independently reopened with integrity `ok`, zero foreign-key
violations, and no migration `045`, proving it predates recovery mutation.

### Recovery result

Only the pinned incident was recovered:

- factory run: `SAFE_STOPPED`;
- factory stop reason:
  `LEASE_RENEWAL_UNCONFIRMED_HISTORICAL_SUBTYPE_UNKNOWN`;
- slot 1 and slot 2: `MANUAL_REVIEW` with the same stable cause;
- queues 18 and 19: `SKIPPED`, action `MANUAL_REVIEW`, stable campaign-terminal
  reason;
- recovery report identity:
  `20260727T161750Z-95e40c3efae3-v2-9-8b-18-recovery-report`;
- recovery report factory identity: exact factory run above;
- recovery report factory status: `SAFE_STOPPED`.

The original immutable incident report was preserved as historical evidence.
The new recovery report supplies the truthful factory identity and recovered
status. The historical campaign first cause was not rewritten. Because the
original heartbeat subtype was not durably captured, the recovery created zero
historical heartbeat-failure rows and explicitly records that the subtype is
unknown rather than guessing SQLite contention, expiry, thread failure, or
ownership mismatch.

### Idempotency

The second invocation returned:

```text
status = ALREADY_RECOVERED_IDEMPOTENT
database_writes = 0
source_calls = 0
scheduler_runtime_calls = 0
```

It created no backup directory, report duplicate, retry, restart, or successor.

## Final authoritative checks

- exact factory `RUNNING` count: `0`;
- exact factory pending/running steps: `0`;
- active campaign discovery work: `0`;
- active campaign Scheduler work: `0`;
- active campaign windows: `0`;
- globally active or locked Scheduler rows: `0`;
- Printer process hits: `0`;
- campaign lease file: absent;
- SQLite integrity: `ok`;
- foreign-key violations: `0`;
- source request/response/failure deltas from the fresh backup: `0/0/0`;
- Scheduler row delta from the fresh backup: `0`;
- retrieval query/match deltas: `0/0`;
- paper decision/position/trade-event/trade-audit/audit-report deltas:
  `0/0/0/0/0`.

All discovery, source, selection, holder, readiness, token, pair, and original
incident-report evidence was retained.

## Money-usefulness contribution

This repair creates no trading outcome and makes no profit claim. It improves
future paper-only money usefulness by preventing interrupted campaigns from
leaving false active ownership, preserving actionable failure diagnostics for
operator review, and ensuring candidate rotation and corpus reporting do not
mistake abandoned queue/slot state for live tracking. Clean memory remains
valuable only when its operational lineage and stop state are truthful.

## What remains locked

Retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper
trade audits, PnL, live execution, wallets, private keys, signing, paid APIs,
scoring, ranking, confidence percentages, weighted logic, embeddings, vectors,
12h/24h operation, unbounded runtime, automatic retry, automatic restart, and
successor creation remain locked.

A separate production retry requires explicit operator review and authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Current disposition | Residual control |
|---|---|---|
| Historical heartbeat subtype was never persisted | Intentionally remains unknown | Do not reinterpret the recovery cause as proof of SQLite contention, expiry, thread failure, or ownership mismatch |
| Original immutable report lacks the factory identity | Preserved as incident evidence; corrected by a new exact recovery report | Operator reporting must use the recovery report for terminal factory identity/status |
| SQLite lock can prevent immediate ledger persistence | Sanitized exact-lease-file fallback is proven | Main coordinator must confirm the SQLite first-failure row before successful terminal closeout |
| Queue update transaction ordering caused one disposable failure | Proven and repaired narrowly | Keep exact queue/slot pair regression in the focused suite |
| A production retry could expose a different operational condition | Not authorized here | Require a separate operator review and explicit bounded-run authorization |
| No broad suite was run | Intentional risk-based scope | Named focused and neighboring regressions passed; broader testing remains for a later major closeout if authorized |

## Final verdict

```text
V2_9_8B_18_HEARTBEAT_TERMINALIZATION_REPAIR_PASS
READY_FOR_OPERATOR_REVIEW_BEFORE_SEPARATE_PRODUCTION_RETRY
```

