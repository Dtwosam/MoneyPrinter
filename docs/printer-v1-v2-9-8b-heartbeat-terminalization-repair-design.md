# V2-9.8B.18 — Heartbeat Evidence and Pre-Lifecycle Terminalization Repair Design

**Status:** `APPROVED_IMPLEMENTATION_DESIGN`

**Baseline:** `4d52a4e7d5f22b59715239722fbbb3793f013a1e`

**Failed execution:** `20260727T161750Z-95e40c3efae3`

**Exact factory run:** `42afd94c-2e5a-40c3-939d-e1941a4033e4`

## Classification and boundary

The committed V2-9.8B.17 audit already classified the incident as a
`COMMITTED_CODE_DEFECT`; this lane does not repeat that audit. The repair is
limited to the canonical heartbeat, factory lifecycle, unified terminal
closure, terminal report, and exact one-incident recovery owners.

No source contract, Scheduler policy, campaign limits, memory window, candidate
rule, retrieval path, paper decision, position, trade, audit, or PnL path may
change.

## Repair contract

### 1. First heartbeat-renewal failure evidence

Append-only migration `045` adds one exact, immutable failure row per campaign
supervision identity. The row stores only:

- an allowlisted safe error type;
- an allowlisted category and stable safe message;
- `sqlite_locked`;
- the renewal attempt time;
- the prior durable heartbeat and lease-expiry values;
- the confirmed/unconfirmed result;
- the stable terminal cause.

Raw exception messages are not persisted. The first row wins and a trigger
prevents update or deletion. If SQLite itself is locked, the same sanitized
record is first written to the exact owned lease file. The main coordinator
must copy that record into SQLite before canonical terminal cleanup releases the
lease. Terminal success is not reportable if the durable first-failure row
cannot be confirmed.

Stable future causes are categorical:

- `LEASE_RENEWAL_SQLITE_LOCKED`;
- `LEASE_RENEWAL_LEASE_EXPIRED`;
- `LEASE_RENEWAL_OWNERSHIP_MISMATCH`;
- `LEASE_RENEWAL_UNCONFIRMED`.

The historical execution receives no invented subtype. Its recovery cause is
`LEASE_RENEWAL_UNCONFIRMED_HISTORICAL_SUBTYPE_UNKNOWN`.

### 2. Lifecycle and exact factory identity

The factory publishes its newly committed factory-run ID through a narrow
callback immediately after creation. The operational coordinator retains that
ID even if the factory does not return normally.

Every cancellation probe after factory creation executes inside the factory's
canonical lifecycle `try/finally`. A cancellation therefore produces its
stable supplied cause and reaches factory closeout; `_ExternalStop` can no
longer escape from the post-creation/pre-lifecycle gap.

The retained factory ID is supplied to outer reconciliation and terminal
reporting on every path. A `RUNNING` zero-step factory run becomes
`SAFE_STOPPED`, with its first stop reason preserved.

### 3. Pre-lifecycle tracking and slot disposition

The unified terminal owner reconciles only rows provably owned through the
exact campaign/run/cycle slot graph:

- a campaign slot still `SELECTED` becomes `MANUAL_REVIEW`, with terminal cause
  and time preserved;
- its linked queue row still `QUEUED` becomes `SKIPPED`, with action
  `MANUAL_REVIEW` and a stable campaign-terminal reason;
- no token, pair, discovery, selection, source, holder, readiness, or historical
  row is deleted;
- already-terminal or unrelated rows are unchanged.

The transition is transactional with the remaining unified reconciliation and
is idempotent.

### 4. Exact historical recovery

The recovery owner is pinned to the exact execution, factory run, campaign,
run, cycle, supervision, report, two queue IDs, and two slot IDs. Before any
data mutation it must prove:

- exact expected ownership links and pre-recovery states;
- no Printer process, live lease, active Scheduler job, or campaign work;
- SQLite integrity and foreign keys;
- unchanged retrieval and financial tables;
- a fresh verified SQLite backup and disposable restore.

It then applies only the canonical terminal reconciliation and replaces the
incident's incorrect terminal report with an exact recovered report. Because
the historical heartbeat subtype was never recorded, recovery records the
unknown-subtype cause and must not add a heartbeat-failure evidence row. A
second invocation must report zero database changes and create no retry,
restart, or successor.

## Atomicity and ownership

- SQLite writes use short transactions with foreign keys enabled.
- Heartbeat threads signal only; they never run terminal cleanup.
- The main coordinator owns first-cause persistence, cleanup, lease release,
  reconciliation, and report persistence.
- Source Governor and Central Scheduler ownership are unchanged.
- No automatic retry, campaign restart, or successor is added.

## Disposable proof gate

Focused fixture-only tests must prove successful renewal, SQLite-lock failure,
expired-lease failure, redaction, first-failure immutability, immediate
post-create cancellation, factory-ID propagation, zero-step terminalization,
queue/slot reconciliation, report truth, clean active-work/integrity/FK state,
zero retrieval/financial deltas, and zero retry/restart/successor.

Minimum neighbouring regressions are the existing heartbeat reliability,
unified terminal closure, and cross-batch persistence tests. No broad suite is
authorized.

## Money-usefulness contribution

This repair does not create money, decisions, or trades. It protects the value
of future paper-only memory growth by making interrupted campaigns auditable,
preventing stale active ownership from contaminating rotation, and ensuring the
operator can distinguish lease contention, expiry, ownership faults, and other
renewal failures without exposing unsafe exception text.

## What remains locked

Retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper
trade audits, PnL, live execution, wallets, private keys, signing, paid APIs,
scoring, ranking, confidence percentages, weighted logic, embeddings, vectors,
12h/24h operation, unbounded runtime, automatic retry, restart, and successor
creation remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Required control | Stop condition |
|---|---|---|
| SQLite is unavailable long enough to block both ledger and lease-file evidence | Fail closed; never claim terminal success without durable sanitized evidence | First failure cannot be durably confirmed |
| A recovery target is only inferred rather than exact-linked | Require pinned IDs and exact relational ownership | Any ownership mismatch |
| Historical subtype is accidentally invented | Use explicit unknown-subtype cause and leave the new evidence table empty for the incident | Any subtype claim beyond retained evidence |
| Reconciliation touches unrelated queue/slot rows | Join only through exact campaign/run/cycle slot ownership | Any unrelated delta |
| Report replacement conflicts with immutable report owner | Recovery may replace only the exact proven incident payload and artifact as one explicit repair operation | Any different report identity or unexpected payload |
| A repair introduces retry/restart behavior | Assert zero retry, restart, and successor in fixture and authoritative closeout | Any retry/restart/successor |

