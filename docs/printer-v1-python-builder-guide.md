# Printer V1 Python Builder Guide

**Document status:** `ACTIVE_PRINTER_V1_PYTHON_BUILDER_GUIDE`
**Repository status:** Adopted by V2-9.7E.33A after repository runtime, SQLite, pytest, journal-mode, and evidence-reference inspection.
**Purpose:** Printer-specific Python implementation, verification, and blocker-investigation law
**Applies to:** Claude, Codex, Grok, and any future coding agent working on Printer V1
**Official-source review date:** 2026-07-23
**Scope:** Python code, SQLite persistence, tests, runners, source adapters, schedulers, reports, migrations, proof tooling, and Python-related blocker analysis

---

## 0. Authority, scope, and non-unlock statement

This guide is **not the sole source of truth**. It is active only inside the Printer V1 source stack and is subordinate to:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`
7. the approved lane design and closeout documents
8. committed Solana Builder, provider, protocol, and Source Governor contracts
9. this Python Builder Guide

A higher-authority Printer document always wins. A conflict blocks implementation until the conflict is resolved; an agent must not silently choose the easier rule.

This guide defines **how already-approved Python work must be built and investigated**. It does not choose the active lane, authorize source fetching, create a new capability, change a provider contract, permit a live proof, or loosen any V1 restriction.

It does not unlock:

- live trading, wallets, private keys, signing, or real funds;
- paid APIs;
- scoring, ranking, confidence percentages, or weighted logic;
- embeddings or vectors;
- Source Governor or Central Scheduler bypass;
- dirty-memory retrieval or decision support;
- `WINDOW_5M_MICRO_EVENT` as a main outcome memory;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, or PnL;
- 12h/24h operation before its explicit approved lane;
- unbounded runtime or automatic restart after terminal failure.

Every major capability still follows:

```text
audit/readiness
â†’ design/specification
â†’ implementation, if approved
â†’ bounded proof/test
â†’ closeout
```

Code existence is not proof of readiness.

---

## 1. Evidence and classification system

Every rule in this guide must be classified by its real authority.

| Classification | Meaning |
|---|---|
| `OFFICIAL_PYTHON` | Directly supported by the official Python documentation or Python language reference |
| `OFFICIAL_PYTEST` | Directly supported by official pytest documentation |
| `OFFICIAL_SQLITE` | Directly supported by official SQLite documentation |
| `OFFICIAL_WINDOWS` | Directly supported by official Microsoft Windows or PowerShell documentation |
| `PRINTER_BINDING` | Required by the active Printer source stack, design, provider contract, or capability locks |
| `PRINTER_PROVEN` | Established by a committed Printer test/proof or a documented Printer incident |
| `RECOMMENDED` | A conservative default that is useful but is not universal law |
| `UNKNOWN_REQUIRES_RESEARCH` | Evidence is insufficient; implementation must not invent behavior |
| `PROHIBITED` | Conflicts with Printer architecture, safety, reproducibility, or an explicit lane boundary |

Official Python documentation cannot establish Printer product policy. For example, Source Governor ownership is `PRINTER_BINDING`, not `OFFICIAL_PYTHON`. Conversely, Printer documents do not redefine Python transaction or subprocess behavior.

A rule may be promoted only when its authority, Printer relevance, and minimum verification are explicit.

---

## 2. Mandatory work gate before Python changes

Before changing Python code, an agent must record:

1. exact baseline commit and tracked-tree state;
2. active lane and source stack;
3. allowed work;
4. forbidden work;
5. canonical owners affected;
6. exact defect, requirement, or design section being implemented;
7. expected files and database boundary;
8. minimum sufficient tests;
9. stop-on-first-relevant-failure condition;
10. what remains locked after PASS.

The agent must inspect existing code and tests before proposing a new owner, runner, adapter, table, retry path, or abstraction.

### 2.1 No speculative repair

A Python repair is prohibited when:

- the blocker is only provider unavailability, rate limiting, missing indexing, or insufficient eligible candidates and the committed code behaved correctly;
- the active lane is audit-only or design-only;
- an official/provider contract is missing;
- the proposed fix requires weakening evidence, safety, budgets, identity, or capability locks;
- the change merely makes a test pass without correcting the proven cause;
- a narrower existing owner can be corrected instead.

### 2.2 Narrow scope

`PRINTER_BINDING`

- Implement only the approved lane.
- Do not combine unrelated cleanup with a repair.
- Do not rename established concepts without an approved contract change.
- Do not add future capability â€œwhile already in the file.â€
- Preserve unrelated pre-existing failures as baseline facts unless they affect the lane.
- Do not broaden tests merely to appear thorough; use risk-based verification from `AGENTS.md`.

---

## 3. Canonical ownership and orchestration

### 3.1 Source Governor ownership

`PRINTER_BINDING`

Source Governor owns every external source request and its:

- approval;
- request identity;
- budget charge;
- transport operation count;
- response;
- failure;
- provenance;
- freshness;
- conflict status;
- redaction.

An engine, selector, memory owner, report owner, or test helper must not call a provider directly.

### 3.2 Central Scheduler ownership

`PRINTER_BINDING`

Central Scheduler owns scheduled work, deadlines, pacing decisions, cancellation, fairness, and approved retry decisions. Engines must not create private loops or competing schedules.

### 3.3 One canonical runner

`PRINTER_BINDING`, `PRINTER_PROVEN`

A bounded capability must have one committed repository-owned orchestration path before it can be proven live.

The canonical path must reuse the approved:

- preflight;
- authorization owner;
- Source Governor;
- Central Scheduler;
- budget ledger;
- source owners;
- lifecycle owners;
- persistence;
- reporting/replay;
- cleanup.

A temporary, reconstructed, notebook-only, or ad-hoc harness cannot establish product readiness.

When different stopping boundaries are needed, add explicit modes to the canonical runner rather than duplicating orchestration. Each mode must specify allowed stages, forbidden owners, budgets, terminal report, and stop boundary.

### 3.4 No automatic successor

`PRINTER_BINDING`

Terminal completion, blocker, cancellation, or failure must not create an automatic successor or silently restart. A new run requires its own approved durable authorization.

---

## 4. Python interfaces, validation, and state

### 4.1 Type annotations are not validation

**Authority:** `OFFICIAL_PYTHON` â€” `PY-TYPE-01`

Python does not enforce function or variable annotations at runtime. Therefore:

- use type hints to clarify contracts and support static tools;
- still validate external payloads, database rows, enum values, identities, and configuration at runtime;
- do not treat `TypedDict`, `Protocol`, dataclass annotations, or return annotations as evidence that live values are valid.

### 4.2 Use narrow interfaces where control is required

`RECOMMENDED`, `PRINTER_PROVEN`

Time, sleep, transport, filesystem roots, database factories, environment lookup, and process launch should be injectable at the boundary where deterministic testing requires control.

Prefer a small callable, protocol, or existing owner interface. Do not add a dependency-injection framework merely to satisfy this rule.

### 4.3 Explicit state vocabulary

`PRINTER_BINDING`

Use approved categorical enums/constants for lifecycle, evidence, terminal, and failure states. Do not replace them with:

- magic booleans;
- unversioned free text;
- numeric scores;
- ranks;
- confidence values;
- weighted combinations.

The first valid terminal cause is immutable. Cleanup or reporting failures are recorded separately and must not overwrite it.

---

## 5. Resource ownership and cleanup

### 5.1 Every resource has one visible owner

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-CTX-01`, `PY-EXC-01` documents context-managed cleanup, `finally`, `closing()`, and `ExitStack`.
**Printer rule:** `PRINTER_BINDING`, `PRINTER_PROVEN`

Every opened connection, cursor, file, socket, response stream, subprocess pipe, lock, and temporary resource must have one clear owner and guaranteed cleanup on:

- success;
- expected blocker;
- early return;
- exception;
- cancellation.

Use:

- `with` for actual closing context managers;
- `contextlib.closing()` for objects exposing `close()` whose context manager does not close them;
- `try/finally` where a context manager is unsuitable;
- `contextlib.ExitStack` for a dynamic collection of resources.

Do not rely on garbage collection.

### 5.2 SQLite connection context managers do not close the connection

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-SQLITE-01`
**Printer rule:** `PRINTER_BINDING`, `PRINTER_PROVEN`

A `sqlite3.Connection` used in a `with` block commits or rolls back according to the connection's configured transaction-control mode; leaving the block does not close the connection. Closure must still be explicit.

Do not copy a universal connection snippet into Printer. The correct connection sequence depends on the repository's supported Python version and adopted `autocommit`/`isolation_level` model. The repository connection owner must:

1. open the connection using the explicitly adopted transaction settings;
2. configure required connection pragmas before any transaction makes that configuration ineffective;
3. verify required pragmas;
4. define whether the caller owns or borrows the connection;
5. close owned connections on every path.

Changing transaction-control behavior is a design-sensitive change, not a cleanup shortcut.

---

## 6. SQLite and persistence law

### 6.1 Connection ownership

`PRINTER_BINDING`, `PRINTER_PROVEN`

A function must clearly own or borrow a connection.

- An owned connection is closed on every path.
- A borrowed connection is not closed by the callee.
- Cursor lifetime must not outlive its connection.
- Tests must not leave references that retain locks on Windows.
- Connection creation belongs to the approved repository factory/owner so transaction, pragma, row-factory, timeout, and journal-mode behavior do not drift across modules.

### 6.2 Threading and connection sharing

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-SQLITE-06`
**Printer rule:** `PRINTER_BINDING`, `PRINTER_PROVEN`

`check_same_thread=True` is Python's default. Setting it to `False` allows cross-thread access but does not make unsynchronized use safe; Python documents that write operations may need to be serialized by the application. The runtime `sqlite3.threadsafety` value depends on the SQLite library used by that interpreter.

Therefore:

- do not set `check_same_thread=False` as a workaround for an ownership or locking defect;
- prefer one clear connection owner and thread-local/operation-local connections;
- if cross-thread sharing is explicitly approved, record `sqlite3.threadsafety`, serialize writes through the approved owner, and prove cancellation, cleanup, and contention behavior;
- never share one connection concurrently across threads merely because a test passes once.

### 6.3 Parameterized SQL and identifiers

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-SQLITE-02` supports placeholders for SQL values and warns against string formatting for values.
**Printer rule:** `PRINTER_BINDING`

Use placeholders for values. Never interpolate provider payloads, identities, paths, or user-controlled data into SQL text.

Placeholders bind values, not SQL structure. Dynamic table names, column names, sort directions, or pragma names are allowed only when selected from a fixed, reviewed allowlist. Do not accept arbitrary identifiers from a provider, operator string, or model-generated value.

### 6.4 Timestamp adapters and converters

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-SQLITE-05`
**Printer rule:** `PRINTER_BINDING`

Python's default SQLite date/timestamp adapters and converters are deprecated, and the default timestamp converter ignores UTC offsets and returns a naive `datetime`.

Therefore:

- do not rely on the deprecated defaults for Printer evidence;
- serialize and parse timestamps explicitly under the adopted schema;
- preserve UTC offsets or normalize explicitly to Printer's UTC-aware convention;
- test round-trip behavior, fractional precision, invalid values, and historical migration compatibility;
- do not enable `detect_types` without verifying the exact registered converters and their effect on existing rows.

### 6.5 Foreign keys and integrity

**Official behavior:** `OFFICIAL_SQLITE` â€” `SQL-PRAGMA-01`
**Printer rule:** `PRINTER_BINDING`

- Enable `PRAGMA foreign_keys = ON` before opening a transaction on connections that rely on foreign-key enforcement, then query the pragma to verify it.
- Do not attempt to change `foreign_keys` while a transaction is pending; SQLite documents that doing so has no effect.
- Do not depend on SQLite's default setting.
- Use `PRAGMA foreign_key_check` at migration/proof/closeout boundaries required by the lane.
- Use `PRAGMA integrity_check` or an approved narrower check at those boundaries.
- `integrity_check` does not report foreign-key violations, and neither check replaces semantic row-count, identity, provenance, or hash reconciliation.

### 6.6 Read-only inspection

**Official behavior:** `OFFICIAL_PYTHON`, `OFFICIAL_SQLITE` â€” `PY-SQLITE-03`, `SQL-PRAGMA-02`, `SQL-WAL-01`
**Printer rule:** `PRINTER_BINDING`

Read-only audits and zero-source replay should use the repository's read-only owner.

- Where supported, open the database with a SQLite URI using `mode=ro`.
- `PRAGMA query_only=ON` may add defense against ordinary SQL data changes, but SQLite explicitly states that it does not make the database truly read-only and still permits operations such as checkpointing and `COMMIT`.
- A WAL-mode database has additional read-only requirements: the `-wal` and `-shm` files must already be available/readable, be creatable, or the database must be genuinely immutable.
- Do not use `immutable=1` merely to bypass permissions. It is allowed only for an artifact that the approved owner has established cannot change for the connection's lifetime.
- Do not claim that a normal connectionâ€”or `query_only` by itselfâ€”is a complete read-only boundary.

### 6.7 Transaction scope and lock safety

**Official behavior:** `OFFICIAL_SQLITE` â€” `SQL-TXN-01`, `SQL-LOCK-01`, `SQL-WAL-01`
**Printer rule:** `PRINTER_BINDING`, `PRINTER_PROVEN`

SQLite permits multiple readers but only one writer. The detailed lock model differs between rollback-journal and WAL modes; `SQL-LOCK-01` describes rollback-journal mode only.

Therefore:

- record and verify the actual `PRAGMA journal_mode` used by authoritative and proof databases;
- keep write transactions as short as the approved contract permits;
- never hold a write transaction while sleeping, pacing, calling a provider, waiting for a subprocess, or doing long report formatting;
- close/finalize cursors and blob handles so statements and transactions can finish;
- commit durable authorization before the first external request when the approved contract requires it;
- treat `SQLITE_BUSY` as a resource, active-statement, transaction-duration, or concurrency signalâ€”not permission to hide the cause with an arbitrarily large timeout;
- investigate ownership, unfinished statements, and transaction duration before changing a timeout;
- preserve the adopted Python `sqlite3` transaction model; do not change `autocommit` or `isolation_level` without a version-aware design and behavior proof.

### 6.8 WAL-specific safety

**Official behavior:** `OFFICIAL_SQLITE` â€” `SQL-WAL-01`
**Printer rule:** `PRINTER_BINDING`

When `PRAGMA journal_mode` is `wal`:

- all processes using the database must be on the same host; SQLite states that WAL does not work over a network filesystem;
- the `-wal` file is part of the database's persistent state and must remain with the database when it is copied or moved;
- do not copy only the main database file while WAL state may contain committed transactions;
- preserve and inspect `-wal`/`-shm` artifacts during cleanup and incident analysis;
- remember that readers and a writer can overlap, but there is still only one writer;
- define checkpoint ownership and prove that long-lived readers cannot create unbounded checkpoint starvation.

At this guide's review date, SQLite's official WAL documentation reports a rare WAL-reset corruption bug in SQLite 3.7.0 through 3.51.2, fixed in 3.51.3 and in the official 3.44.6 and 3.50.7 backports. Before persistent or live Printer work using WAL with multiple connections, record `sqlite3.sqlite_version` and block operation on an affected runtime unless an official fixed backport or an explicitly approved, source-backed mitigation is proven.

This version-specific guard must be rechecked against the current official SQLite WAL page at adoption and before any later runtime upgrade.

### 6.9 Ordering is never implicit

**Official behavior:** `OFFICIAL_SQLITE` â€” `SQL-ORDER-01`
**Printer rule:** `PRINTER_BINDING`, `PRINTER_PROVEN`

A query without `ORDER BY` has no guaranteed row order. Any order affecting:

- selection;
- fairness;
- continuation;
- replay;
- reports;
- evidence chronology;
- migration checks;
- proof comparisons

must use an explicit deterministic order and a complete tie-breaker.

### 6.10 Migrations

`PRINTER_BINDING`

- Applied migrations are append-only.
- Do not edit a migration already used by an authoritative or proof database.
- A new migration must work on a fresh database and on an upgrade from the previous head.
- Keep migrations deterministic.
- Do not mix unrelated cleanup with a narrow migration.
- Migration proof uses isolated copies, not the authoritative corpus, unless an explicit later lane authorizes otherwise.
- Required checks include schema version, counts, foreign keys, integrity, directly affected persistence tests, and journal-mode compatibility where relevant.

### 6.11 Backup and restore

**Official behavior:** `OFFICIAL_PYTHON`, `OFFICIAL_SQLITE` â€” `PY-SQLITE-04`, `SQL-BACKUP-01`, `SQL-WAL-01`
**Printer rule:** `PRINTER_BINDING`

For a live or persistent SQLite database, use the approved SQLite backup owner/API rather than an uncoordinated file copy while writers may be active. SQLite's online backup API produces a consistent destination snapshot, but concurrent writes can restart incremental backup work and, under sustained writes, can theoretically prevent completion.

Therefore:

- give backup work a bounded owner, progress reporting, and an approved stop/failure policy;
- do not assume the backup file's hash should equal a later, still-changing source file;
- do not copy only the main database file in WAL mode;
- consider a backup ready only after opening a disposable restore and reconciling the required integrity check, foreign-key check, schema/migration version, row counts, semantic identities, configuration/provenance, and hash procedure;
- keep backup and restore paths explicit;
- never overwrite the authoritative database during rehearsal.

### 6.12 Windows cleanup

`PRINTER_PROVEN`

Before deleting, replacing, copying, or reopening proof artifacts on Windows:

- close every connection and cursor;
- release blob handles, file handles, and subprocess pipes;
- release fixture references;
- ensure no worker still owns the file;
- account for `-wal` and `-shm` companions when WAL is active;
- verify the database can be reopened or removed when the proof requires it.

A longer sleep is not a fix for an unclosed resource.

---

## 7. Time, scheduling, pacing, and budgets

### 7.1 Persisted time

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-DATETIME-01` distinguishes aware and naive datetime objects; it does not itself mandate Printerâ€™s storage convention.
**Printer rule:** `PRINTER_BINDING`

Persist UTC-aware event timestamps under Printerâ€™s adopted contracts. Naive datetimes are prohibited for durable evidence unless a higher-authority contract explicitly defines their timezone and conversion.

Keep distinct fields for event, capture, request, receipt, and close times when the source contract distinguishes them. Do not replace exact evidence time with report-generation time.

### 7.2 Elapsed time and deadlines

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-TIME-01` defines a monotonic clock that cannot go backward and has an unspecified reference point.
**Printer rule:** `PRINTER_BINDING`

Use a monotonic clock for elapsed durations, pacing, deadline checks, and runtime timeouts. Never persist its raw value as an event timestamp or compare monotonic values from unrelated processes unless the adopted platform contract proves that comparison valid.

Wall-clock UTC remains appropriate for persisted historical timestamps. Do not use wall-clock subtraction as the only runtime safety clock.

### 7.3 No real sleeping in focused tests

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-TIME-02` states that `sleep()` can last longer than requested because of system scheduling.
**Printer rule:** `PRINTER_PROVEN`, `PROHIBITED`

Unit and focused contract tests must not use the production sleeper or wait through real provider pacing.

Use a fake clock/no-sleep pacer that:

- records requested delay and source;
- advances deterministic test time when needed;
- proves order and minimum spacing;
- never contacts a provider.

A test hanging because it invoked production pacing is a test defect. Increasing the test timeout is not the correction.

### 7.4 Scheduler fairness and close priority

`PRINTER_BINDING`

- Exact close/deadline work takes priority as defined by the active design.
- Less-served token fairness must be deterministic.
- One tokenâ€™s source or lifecycle failure must not corrupt the other tokenâ€™s identity or terminal state.
- Tie-breaking must be explicit and tested.
- Do not implement fairness through scores, ranks, or hidden weights.

### 7.5 Budget accounting

`PRINTER_BINDING`, `PRINTER_PROVEN`

- Distinguish a governed request from its underlying transport operations.
- Charge the unit defined by the committed source/campaign contract.
- Reserve mandatory close/snapshot work before optional work.
- Derive candidate/token caps from complete worst-case arithmetic.
- Print or persist the plan before authorization consumption where the design requires it.
- Zero retry means exactly one attempt.
- Never raise the ceiling, weaken eligibility, or hide operations to obtain PASS.

---

## 8. External transports and subprocesses

### 8.1 Fixed governed source contracts

`PRINTER_BINDING`

Every external integration must use its committed contract for:

- host and endpoint;
- request kind;
- authentication class;
- headers;
- timeout;
- pacing/ceiling;
- transport operation cost;
- response shape;
- nullable/missing behavior;
- target validation;
- freshness;
- provenance;
- redaction;
- conflict and failure semantics.

No endpoint rotation, hidden retry, reconnect loop, paid fallback, or additional backup is permitted unless explicitly approved.

### 8.2 Fail closed and preserve UNKNOWN

`PRINTER_BINDING`

Missing, stale, malformed, conflicting, mismatched, failed, unproven, or unsupported evidence remains exactly that.

Do not:

- normalize a missing number to zero without an approved semantic contract;
- infer a field from another source without an approved exact-identity join;
- treat source success as evidence completeness;
- let failure/absence override a clean conflicting fact;
- call a transport/auth/rate-limit failure a target mismatch;
- claim wallet authenticity, manipulation intent, liquidity state, or execution realism when the adopted source contract cannot prove it.

Use `UNKNOWN_REQUIRES_RESEARCH` rather than inventing provider or protocol semantics.

### 8.3 Subprocess argument construction

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-SUBPROCESS-01` documents argument sequences, Windows conversion of sequences to a command line, `shell=False` as the default, and the limited cases that need a shell.
**Printer rule:** `PRINTER_BINDING`

- Pass an argument sequence rather than a single shell command string when `shell=False`.
- Prefer `shell=False`.
- Use `sys.executable` when launching the same Python interpreter; otherwise resolve the approved executable explicitly rather than relying on an ambiguous PATH lookup.
- Use a shell only when a verified platform-specific contract truly requires a shell built-in or approved shell script behavior.
- If `cmd.exe /c` or PowerShell quoting is required, centralize and test the exact contract.
- Never concatenate untrusted or provider-derived values into a shell command.

### 8.4 Subprocess environment

**Official behavior:** `OFFICIAL_PYTHON`, `OFFICIAL_WINDOWS` â€” `PY-SUBPROCESS-02`, `PY-ENV-01`, `WIN-ENV-01`
**Printer rule:** `PRINTER_BINDING`, `PRINTER_PROVEN`

A child normally inherits the parent process environment unless `env=` supplies a replacement mapping. PowerShell's Process scope is created for the process; later User/Machine changes do not retroactively rewrite an already-running executor's environment. Python's `os.environ` mapping is captured when `os` is imported.

Therefore:

- preflight the exact executor process that will run the task;
- do not infer executor access from another PowerShell window;
- after changing User/Machine variables, start a fresh shell/executor when inheritance is required;
- prefer a fresh executor over trying to refresh a long-running process in place;
- `os.reload_environ()` is Python 3.14+ and is documented as not thread-safe; it is prohibited as the normal Printer secret/configuration fix unless the supported runtime and single-threaded call boundary are explicitly proven;
- never paste or print a secret merely to prove presence;
- when supplying `env=`, start from an approved sanitized copy of the required environment rather than accidentally dropping required platform variables; on Windows preserve variables required by the subprocess contract, including `SystemRoot` when applicable.

### 8.5 Subprocess completion and timeout

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-SUBPROCESS-03`
**Printer rule:** `PRINTER_BINDING`

Python documents several different timeout behaviors:

- `subprocess.run(timeout=...)` kills and waits for the child after expiry, then re-raises `TimeoutExpired`;
- `Popen.communicate(timeout=...)` does not kill the child; the documented cleanup pattern is to kill it and call `communicate()` again;
- process creation itself may be non-interruptible on some platform APIs, so a subprocess timeout is not guaranteed to be an absolute wall-clock ceiling from before launch;
- `communicate()` buffers captured output in memory and is unsuitable for large or unbounded output.

Therefore:

- every external process must have an approved finite timeout plus an outer bounded-proof expectation;
- use `communicate()` or an approved streaming equivalent when pipes are captured so buffers do not deadlock the process;
- implement cleanup according to the exact API used;
- after termination, drain and close pipes, reap the child, and preserve the factual timeout result;
- stream, cap, or redirect output when its size is not tightly bounded;
- do not log command lines or environment mappings containing secrets.

---

## 9. Secrets and configuration

### 9.1 Secret boundary

`PRINTER_BINDING`

Secrets:

- enter only through the approved environment/config owner;
- are checked by presence, never by printing value;
- never enter SQLite rows, reports, source evidence, authenticated URLs, exceptions, command history, fixtures, snapshots, or committed files;
- are redacted before logging or persistence;
- cause preflight failure before authorization consumption or provider contact when missing.

Tests use fake values.

### 9.2 Configuration identity

`PRINTER_BINDING`

A live/proof campaign must link to immutable, versioned configuration and exact Git provenance where required. Do not reconstruct historical configuration from current defaults during replay.

Dirty-tree handling follows the approved lane contract. A report must not claim a committed clean baseline if the actual launch state was different.

---

## 10. Exceptions, failures, terminal state, and reporting

### 10.1 Catch only what the boundary can handle

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-EXC-01`, `PY-EXC-02` documents handler matching, exception chaining, and `finally`.
**Printer rule:** `PRINTER_BINDING`

- Catch the narrowest useful exception category.
- Use exception chaining (`raise ... from exc`) when translating an error and preserving cause.
- Use `finally` or a context manager for cleanup.
- Printer prohibits bare `except:` because an expression-less handler matches exceptions derived from `BaseException`, including control-flow exceptions that ordinary `Exception` handlers do not catch.
- Do not swallow exceptions, return false success, or convert implementation defects into provider blockers.

Expected operational outcomes should use explicit result/terminal categories rather than exceptions as ordinary control flow.

### 10.2 Failure precedence

`PRINTER_BINDING`, `PRINTER_PROVEN`

Preserve distinct categories for:

- configuration/secret;
- authorization;
- contract drift;
- timeout;
- rate limit;
- authentication;
- transport;
- provider;
- parser/schema;
- target mismatch;
- stale evidence;
- conflict;
- budget;
- cancellation;
- implementation defect;
- unknown.

A target mismatch requires an actual returned target that differs. An empty payload following a transport failure is not a mismatch.

### 10.3 First terminal cause

`PRINTER_BINDING`

The first valid terminal cause is immutable. Later cleanup, replay, or reporting errors are attached separately.

Verdicts and commit messages must describe the actual outcome. Examples:

- preflight stopped before provider contact;
- authorization remained unconsumed;
- source reliability blocked;
- valid fail-closed data outcome;
- committed-code defect;
- offline proof passed.

### 10.4 Logging

**Official behavior:** `OFFICIAL_PYTHON`, `OFFICIAL_PYTEST` â€” `PY-LOG-01`, `PYTEST-LOG-01` documents logging calls, `logger.exception()` inside exception handling, and pytest log capture.
**Printer rule:** `PRINTER_BINDING`

- Use module loggers and the repository's structured categorical fields.
- Call `logger.exception()` only while handling an exception whose traceback should be recorded.
- Record exact identity, source, stage, request/failure linkage, and terminal cause.
- Redact secrets and authenticated URLs before logging.
- Do not log unbounded raw provider payloads.
- Tests that assert logging should use `caplog` or the repository wrapper and must not replace the root handler in a way that removes pytest's capture handler.

### 10.5 Durable reports and zero-source replay

`PRINTER_BINDING`, `PRINTER_PROVEN`

Authoritative reports must read durable committed rows. Process memory may enrich an in-flight view but cannot be the only location of a fact required after cleanup.

Report-only replay must:

- use exact report/replay identity;
- perform no discovery, provider, scheduler, lifecycle, or memory work;
- write nothing;
- not recapture current Git/configuration as historical truth;
- return equivalent diagnostics or an explicit `REPLAY_BLOCKED`;
- never repair a lifecycle, create a promotion, or fill missing historical facts.

Do not reconstruct unpersisted timestamps or outcomes as though observed.

---

## 11. Determinism, identity, serialization, and artifacts

### 11.1 Exact identity

`PRINTER_BINDING`

Use the exact durable identity required by the active contract, including where applicable:

- mint;
- pair;
- source/request/response/failure;
- campaign/configuration/cycle/run;
- token-local lifecycle;
- window kind and parent window;
- checkpoint;
- scheduler work;
- predecessor;
- authorization;
- report/replay;
- Git commit/configuration.

Never substitute symbol for mint, nominal price for setup identity, or a nearby timestamp for exact evidence identity.

### 11.2 Deterministic collections

`PRINTER_BINDING`, `PRINTER_PROVEN`

Any ordering that affects behavior or proof must have an explicit key and complete tie-breaker. Do not depend on set/dict insertion accidents, provider order, filesystem order, or unordered SQL output.

If controlled randomness is explicitly approved, persist the seed and candidate universe. Randomness must never become hidden ranking.

### 11.3 JSON artifacts

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-JSON-01`
**Printer rule:** `PRINTER_BINDING`

Python's standard `json` module is not, by itself, a cross-language canonical-JSON specification. Defaults permit non-finite numbers and accept duplicate object names by keeping the last value.

Where byte-stable JSON is part of a committed proof/report contract:

- use an explicitly versioned serializer profile;
- require string keys;
- sort keys;
- define separators, Unicode normalization/escaping, number policy, unknown-value policy, and final-newline behavior;
- use `allow_nan=False`;
- reject duplicate object keys when reading authoritative proof artifacts;
- reject or normalize values whose representation is not covered by the adopted profile;
- test exact bytes under the pinned runtime.

For hashes or comparisons across Python versions or other languages, adopt a named canonicalization contract rather than assuming that `sort_keys=True` alone is canonical.

Where byte identity is not required, compare validated parsed semantic structures and document that choice.

### 11.4 Hashes

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-HASH-01` provides guaranteed algorithms including SHA-256 and warns that MD5 and SHA-1 have known collision weaknesses.
**Printer rule:** `PRINTER_BINDING`

Use SHA-256, or another explicitly adopted collision-resistant algorithm available in the supported runtime, for new Printer integrity/reconciliation artifacts. Do not create a new Printer integrity contract using MD5 or SHA-1.

Record the algorithm, exact byte source, encoding/canonicalization profile, included file boundaries, and newline rules. Different digests prove that the hashed byte sequences differ. Matching SHA-256 digests provide strong cryptographic evidence that the byte sequences match, but are not mathematical proof and do not establish semantic correctness, provenance, freshness, completeness, database consistency, or safety.

Pair hashes with the required database, identity, provenance, and restore checks.

### 11.5 File replacement

**Official behavior:** `OFFICIAL_PYTHON` â€” `PY-FILE-01` states that `os.replace()` overwrites an existing destination file when permitted; it states atomic success as a POSIX requirement, not as a universal cross-platform durability guarantee.
**Printer rule:** `PRINTER_PROVEN`

Use the repositoryâ€™s tested replacement/lease owner. On Windows, prove the complete write, optional durability step, close, replace, contention, and cleanup behavior with focused tests.

Do not call a workflow â€œatomic,â€ crash-durable, or contention-safe solely because it invokes `os.replace()`.

---

## 12. pytest and verification law

### 12.1 Test isolation

**Official tools:** `OFFICIAL_PYTEST` â€” `PYTEST-TMP-01`, `PYTEST-MONKEY-01` provide per-test paths and reversible patching of attributes/environment.
**Printer rule:** `PRINTER_BINDING`

Focused tests use:

- a per-test temporary directory such as `tmp_path`;
- an isolated fresh or migrated database;
- fixture transports, never live network;
- fake clocks and no-sleep pacers;
- fake environment values patched for the test;
- deterministic inputs and ordering;
- bounded process doubles;
- explicit assertions for zero forbidden calls and deltas.

Tests must not depend on:

- the operatorâ€™s authoritative corpus;
- real User/Machine secrets;
- current provider availability;
- execution order;
- files from a previous test;
- mutable process-global campaign truth.

### 12.2 Negative-path proof

`PRINTER_BINDING`

For every changed safety boundary, test the success path and the nearest dangerous failures, such as:

- exact-target mismatch;
- missing/malformed/stale fields;
- auth/transport/rate failure;
- conflicting clean facts;
- budget exhaustion;
- duplicate/second execution;
- early-stop cleanup;
- replay mutation;
- forbidden owner invocation;
- dirty evidence promoted clean;
- token/pair/campaign mixing;
- future-data leakage.

Do not generate broad low-value permutations without a risk reason.

### 12.3 Risk-based verification

`PRINTER_BINDING`

- Documentation/audit/design: static checks, source/authority checks, diff and unlock scans.
- Narrow Python change: changed tests, nearest affected contract tests, compilation/import checks, and diff checks.
- Cross-cutting migration/Governor/Scheduler/cadence/lease/DB/budget/memory-quality change: focused tests plus directly affected regressions.
- Broad/full suite: major lane closeout, pre-live proof, checkpoint/release, or broad architectural change.

Never loosen a test, safety gate, evidence rule, or proof requirement to save time.

### 12.4 Hang diagnosis

`PRINTER_PROVEN`

When a focused command exceeds its expected bounded duration without useful progress:

1. interrupt once;
2. run the exact test/node verbosely with stop-first behavior;
3. inspect real sleep, real network, lock ownership, subprocess wait, and fake-clock injection;
4. correct the proven cause;
5. rerun the minimum focused command.

Do not repeatedly rerun an unchanged hanging command. Do not begin a full suite while the nearest focused test is unresolved.

### 12.5 Logging tests

**Authority:** `OFFICIAL_PYTEST` â€” `PYTEST-LOG-01`

Use `caplog` or the repositoryâ€™s approved wrapper. Avoid replacing the root logging configuration in a way that removes pytestâ€™s capture handler.

---

## 13. Mandatory Source-Grounded Blocker Investigation

This section must be used **before ChatGPT, Claude, Codex, Grok, or another agent recommends Python coding for any Printer blocker, bug, failing test, or live-proof failure**.

No repair prompt may be issued before classification.

### 13.1 Required inputs

Collect the minimum sufficient evidence:

1. exact baseline commit, branch, tracked/untracked state;
2. active lane and capability locks;
3. exact task prompt given to the implementation agent;
4. the agentâ€™s todo, assumptions, and final report;
5. changed-file diff;
6. relevant call path and canonical owner;
7. exact failing command/test;
8. complete error, traceback, source failure, or durable artifact;
9. related database rows/read-only report when applicable;
10. Python, SQLite, pytest, journal-mode, threading, and platform versions when behavior may be version-sensitive;
11. relevant Printer design, closeout, provider contract, and nearest tests;
12. relevant current official Python/SQLite/pytest/Microsoft documentation;
13. whether any live authorization or provider budget was consumed.

Never ask for or expose secrets.

### 13.2 Evidence comparison

The investigator must answer:

| Question | Required evidence |
|---|---|
| What was the agent asked to do? | Exact prompt and lane |
| What did it actually change? | Diff and call path |
| What failed? | Exact command, traceback, logs, DB/artifact |
| Did the existing code behave according to its committed contract? | Tests, owner, design |
| Does the implementation conflict with official technical behavior? | Current official source |
| Does it conflict with Printer architecture or lane boundaries? | Active source stack |
| Is the failure reproducible offline? | Minimal fixture/test |
| Is this a product-code defect or an external/operational outcome? | Classification below |
| What is the minimum safe response? | No change, configuration correction, narrow code repair, missing boundary completion, or design block |
| What must remain untouched? | Explicit file/capability boundary |

### 13.3 Mandatory classifications

Choose exactly one primary classification:

#### `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`

The committed code behaved correctly and failed closed because of provider availability, rate limiting, incomplete indexing, missing eligible candidates, missing mandatory evidence, or another expected real-world outcome.

Response: preserve artifacts, report honestly, and do not create a repair lane automatically.

#### `CONFIG_OR_ENVIRONMENT_BLOCKER__NO_PRODUCT_CODE`

Examples: missing process-scoped secret, wrong shell inheritance, unavailable executable, wrong operator path, or unauthorized target.

Response: correct operator/configuration setup and repeat only if authorization rules permit. Do not modify product code unless configuration handling itself is defective.

#### `TEST_HARNESS_DEFECT`

The product owner is correct, but the fixture, fake clock, temporary DB, assertion, or test-only helper is wrong.

Response: repair only the harness and prove that production behavior was unchanged.

#### `COMMITTED_CODE_DEFECT`

A reproducible mismatch exists between committed behavior and official/Printer contracts.

Response: propose the smallest correction in the canonical owner with focused regression proof.

#### `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`

The approved design requires a committed path or stopping boundary that was never implemented; temporary code previously filled the gap.

Response: complete the missing boundary inside the canonical architecture. Do not create a parallel runner.

#### `CONTRACT_DRIFT`

Current official/provider behavior differs from the committed contract or preflight assumptions.

Response: stop live work, perform a contract audit, update the committed contract only through an approved design/repair lane, then implement and prove.

#### `DESIGN_GAP`

The active design does not define enough behavior to implement safely.

Response: no coding. Return to design/specification.

#### `LANE_VIOLATION`

The requested fix or implementation is outside the active lane or unlocks a prohibited capability.

Response: reject or reshape it to the nearest roadmap-compliant task.

#### `UNKNOWN_REQUIRES_RESEARCH`

Evidence is insufficient or official sources conflict.

Response: static/read-only research only. No guessed code.

### 13.4 Coding recommendation gate

A coding prompt may be produced only for:

- `TEST_HARNESS_DEFECT`;
- `COMMITTED_CODE_DEFECT`;
- `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`;
- an approved implementation following a completed `CONTRACT_DRIFT` or `DESIGN_GAP` lane.

The recommendation must include:

1. exact baseline;
2. classification and evidence;
3. exact canonical owner;
4. minimal code scope;
5. files that must not change;
6. official-source rule applied;
7. Printer contract applied;
8. focused proof;
9. directly affected regressions;
10. stop condition;
11. what remains locked;
12. factual verdict names.

### 13.5 Required blocker-investigation output

```text
BLOCKER CLASSIFICATION:
EVIDENCE:
OFFICIAL-SOURCE COMPARISON:
PRINTER-CONTRACT COMPARISON:
ROOT CAUSE:
CODE CHANGE JUSTIFIED: YES / NO
MINIMUM SAFE RESPONSE:
FOCUSED PROOF:
UNTOUCHED SCOPE:
AUTHORIZATION STATUS:
NEXT ROADMAP-COMPLIANT STEP:
```

### 13.6 No patch-loop rule

After a correctly implemented bounded live proof:

- provider unavailability;
- temporary rate limiting;
- incomplete fresh-pair indexing;
- missing liquidity/holder fields;
- insufficient eligible candidates;
- valid clean/dirty/blocked evidence outcomes

do not automatically justify code changes.

A new repair requires evidence of a concrete committed-code defect, missing approved boundary, or verified contract drift.

---

## 14. Printer historical issue register

This register translates known Printer failures into standing Python controls. It is not permission to reopen completed lanes.

### 14.1 Roadmap and orchestration drift

**Observed:** one-command memory growth was fragmented across lane-specific commands, manual token lists, proof scripts, and artifacts; historical roadmap state also drifted.

**Standing controls:**

- active lane/source-stack preflight;
- one canonical committed runner;
- no ad-hoc live proof;
- explicit modes and stop boundaries;
- audit â†’ design â†’ implementation â†’ proof â†’ closeout.

### 14.2 Discovery, selection, age, and rotation

**Observed issues:**

- discovery/selection initially produced narrow or AGE_UNKNOWN-heavy pools;
- pair age could not substitute for token creation age;
- token/pair cooldown and fair rotation required durable categorical state;
- source productivity and category diversity could be hidden by raw counts.

**Standing controls:**

- exact mint/pair/source identity;
- source-tier rules and `UNKNOWN` preservation;
- categorical buckets rather than scores;
- deterministic selection ordering;
- durable cooldown/rotation;
- diversity/concentration reporting;
- no source field claiming a category it cannot prove.

Completed implementation patterns may be reused, but their lanes must not be restarted blindly.

### 14.3 Unsupported pool and provider semantics

**Observed:** exact-pool LP lock/burn semantics were not proven for all pool types; interpreting nearby token-level fields would have invented pool behavior.

**Standing controls:**

- missing source/protocol contract blocks implementation;
- unsupported exact-pool state remains `UNKNOWN_REQUIRES_RESEARCH`;
- no field-name similarity or model memory may establish a provider contract;
- implement only adopted exact identity and semantic joins.

### 14.4 Context, memory quality, and closeout

**Observed issues:**

- context reuse/ownership previously blocked one-command memory closeout;
- evidence quality, outcome direction, and safety could be conflated;
- clean promotion could be under-counted in reports;
- a clean negative outcome could be mistaken for dirty memory;
- close ordering and boundary timing required explicit proof.

**Standing controls:**

- exact context identity and idempotency;
- separate evidence quality from market outcome;
- complete-window and gap gates;
- authoritative episode/promotion reporting;
- immutable cutoff and checkpoint boundaries;
- no future-data leakage.

### 14.5 Windows SQLite locks and heartbeat contention

**Observed issues:**

- unclosed SQLite resources caused Windows test/file locks;
- heartbeat/lease replacement experienced Windows contention.

**Standing controls:**

- explicit connection/cursor/file ownership;
- no write transaction during sleep or external I/O;
- focused Windows cleanup/reopen/remove tests;
- tested lease replacement owner;
- first-cause preservation and fail-closed heartbeat behavior;
- no timeout increase as the first fix.

### 14.6 Reporting truth and process-memory loss

**Observed:** E.23 report-only projection queried `status` instead of `queue_status`; read-only recovery succeeded, but in-memory Pump timing detail was lost and could not be reconstructed honestly.

**Standing controls:**

- report queries use actual migrated schema;
- durable facts required after cleanup are persisted before terminalization;
- zero-source replay reads SQLite, not process memory;
- missing historical facts remain missing;
- report defects after a consumed live cycle do not authorize an automatic rerun.

### 14.7 Holder-source reliability and operation accounting

**Observed across E.20â€“E.24:**

- GoPlus exact-target success often lacked usable holder concentration;
- public RPC paths produced rate-limit/transport failures;
- governed adapter calls could consume multiple transport operations;
- failure precedence incorrectly labeled some failed responses as target mismatch;
- pacing, provenance, reserve arithmetic, and fixed-backup independence required explicit proof.

**Standing controls:**

- exact-target response is not evidence completeness;
- count underlying transport operations;
- preserve snapshot/close reserves;
- derive candidate caps from worst-case arithmetic;
- fake-clock pacing tests;
- transport/auth/rate failure precedes mismatch unless a different target was returned;
- no retry, rotation, or higher ceiling without approved design.

### 14.8 Snapshot composition and nullable fields

**Observed across E.25â€“E.30:**

- holder eligibility did not guarantee complete market snapshots;
- DexScreener liquidity could be absent;
- exact-pair liquidity and 15m microstructure required approved multi-source composition;
- GeckoTerminal version/header/pacing drift blocked preflight;
- Pump acquisition used more operations than an earlier assumption;
- missing liquidity could not be normalized to zero.

**Standing controls:**

- preflight current committed source contracts before authorization;
- exact pair/base-mint validation;
- nullable fields remain unknown unless an approved exact-pool source supplies them;
- compose sources only through explicit provenance and conflict rules;
- update worst-case budgets from actual operation counts;
- stop early when mandatory downstream evidence cannot complete.

### 14.9 Process environment and Helius authorization

**Observed in E.31:** the Helius secret existed at User/Process scope in one shell but was absent in the executor environment.

**Standing controls:**

- preflight the exact process;
- start a fresh executor after persistent environment changes;
- check presence without printing;
- classify as configuration/environment unless product secret handling is defective;
- do not spend authorization while preflight is incomplete.

### 14.10 Missing committed readiness boundary

**Observed in E.32:** prior readiness cycles depended on temporary harnesses; the committed readiness path stopped too early while the full operational path ran too far.

**Standing controls:**

- classify as `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`;
- extend the canonical runner with an explicit readiness stop;
- reuse owners, budgets, reporting, cleanup, and authorization;
- no parallel runner;
- offline fixture proof before one separately authorized live proof.

**Current operator-approved correction:** `V2-9.7E.33 â€” Canonical Operational Readiness Boundary Closure` is the planned documentation/design/implementation/proof closure for this missing boundary. This guide records the coding discipline for that work but does not execute the lane, authorize provider calls, or alter the active build order by itself.

### 14.11 V2-9 operational carry-forward defects

**Observed and carried into V2-9.7:**

- authoritative clean-promotion yield could be under-counted at the top report layer;
- safety labels could be read as timeframe-confusing even when gates remained strict;
- heartbeat replacement could contend on Windows;
- wallet-level flow authenticity remained partial/unknown;
- Git provenance was not fully embedded in run artifacts;
- a separate operational zero-source report-only replay was absent;
- stale queue/lifecycle rows could survive without explicit reconciliation.

**Standing controls:**

- reconcile reports against authoritative episode/promotion rows;
- keep safety acceptance unchanged while making labels exact;
- test lease renewal/replacement on Windows and preserve first terminal cause;
- retain partial/caution/unknown wallet language;
- capture exact Git/configuration identity at launch;
- implement zero-source replay as read-only;
- prove terminal queue, scheduler, lease, and temporary-artifact cleanup.

---

## 15. Remaining build-order Python risk map

These controls prepare future agents to code safely **only when the corresponding lane becomes active**. They do not unlock future work.

### 15.1 V2-9.7 â€” Operational Memory Factory implementation/pilot

Python must prevent:

- all-token/all-timeframe tracking;
- 5m becoming a main outcome or continuation authority;
- token/pair/campaign mixing;
- starvation and missed close boundaries;
- false reversal/phase labels;
- hidden snapshot gaps;
- wick-only peak treated as capturable exit;
- nominal-price matching;
- look-ahead;
- re-entry without a fresh approved setup;
- wallet-authenticity overclaim;
- raw row counts driving continuation;
- missing cooldown/archive/rotation;
- ambiguous persistent DB target;
- report under-count;
- stale queue/scheduler/lease/temp artifacts;
- automatic restart;
- replay mutation;
- journal-mode or runtime-SQLite drift, including unsafe WAL operation on an affected runtime.

### 15.2 V2-9.8 â€” Active bounded corpus growth

Python must prevent:

- proof command or proof DB being used as production;
- persistent corpus pollution;
- dirty memory called clean;
- raw row count treated as success;
- token concentration hidden;
- continuation overuse;
- free-source budget exhaustion;
- terminal failure followed by restart;
- any retrieval or financial delta.

### 15.3 V2-10, V2-11, V2-11.7, V2-11.8 â€” 12h/24h readiness and operation

Python must prevent:

- fake long-window aggregation from shorter windows;
- source budget collapse;
- stale evidence and hidden gaps;
- token/pair drift;
- dead/revived tokens represented ambiguously;
- long-window concentration;
- all-token long continuation;
- orphaned jobs/locks after safe stop;
- technically complete but money-useless reports;
- dirty long windows hidden as clean.

### 15.4 V2-12 â€” Corpus quality reporting

Python must prevent:

- clean counts that disagree with authoritative promotion rows;
- dirty/audit-only rows included as clean;
- 5m support counted as main memory;
- winner-only or survivor-biased corpus;
- missing dead/trap/revival/round-trip categories;
- source failures hidden;
- timeframe overclaim;
- report mutation of the corpus.

### 15.5 V2-13 â€” Clean retrieval review

Python must prevent:

- dirty, audit-only, or 5m-support memory entering main retrieval;
- cross-token/pair/window identity leakage;
- similarity that cannot be explained categorically;
- hidden confidence/ranking/weighting;
- concentrated corpus presented as broad evidence;
- retrieval preview writing persistent rows without approval.

### 15.6 V2-14 â€” WAIT/AVOID/NO_ACTION readiness

Python must prevent:

- conservative outputs being presented as a position or trading signal;
- decision rows before the explicit approved lane;
- insufficient or mixed memory sounding confident;
- vague rationale without exact clean-memory linkage;
- BUY language or position creation;
- financial/PnL side effects.

### 15.7 V2-15 â€” Paper BUY readiness review

Python must prevent:

- automatic BUY unlock;
- fake chart profit;
- entry without event-time route/quote/liquidity;
- exit without realistic opportunity duration and quote/liquidity;
- ignored slippage or price impact;
- BUY without clean-memory backing;
- overfitting to a small or concentrated corpus;
- paper results presented as real money;
- wallet, signing, or live execution.

---

## 16. Prohibited Python patterns

Unless a later approved design explicitly proves necessity, the following are prohibited:

- direct source calls outside Source Governor;
- independent scheduler, polling, reconnect, or retry loops;
- unbounded `while True` operational runtime;
- real `sleep` in unit/focused tests;
- live network in unit/focused tests;
- ad-hoc live proof harnesses;
- duplicate orchestration paths;
- hidden automatic restart;
- bare `except:` or silent exception swallowing;
- generic success after an unresolved failure;
- mutable process-global campaign truth;
- report truth stored only in memory;
- implicit SQL or collection ordering that affects proof;
- SQL interpolation of payload values;
- secrets in URLs, logs, DB, reports, fixtures, or committed files;
- editing an applied migration;
- holding a write transaction during provider or subprocess waits;
- replacing missing evidence with zero without contract authority;
- raising budgets or weakening gates to obtain PASS;
- broad unrelated refactoring in a narrow lane;
- dynamic scores, ranks, confidence values, weighted decisions, embeddings, or vectors.

---

## 17. Minimum builder checklist

### Before editing

- [ ] Confirm exact baseline and active lane.
- [ ] Read the routed source stack and provider/protocol contracts.
- [ ] Classify the work: audit, design, implementation, proof, closeout, or blocker investigation.
- [ ] Identify canonical owners.
- [ ] Confirm DB target and whether mutation is allowed.
- [ ] Confirm whether source/runtime/live authorization is allowed.
- [ ] Identify official technical sources relevant to the change.
- [ ] State stop-on-first-failure behavior.

### Before declaring PASS

- [ ] One canonical path; no bypass or duplicate loop.
- [ ] Exact identity and deterministic ordering.
- [ ] Resources close on every path.
- [ ] Time/network/environment are test-controllable.
- [ ] SQL is parameterized and transactions are bounded.
- [ ] Source facts fail closed with correct failure precedence.
- [ ] Budget arithmetic uses actual transport operations.
- [ ] Secrets are absent from durable and visible output.
- [ ] Reports are DB-backed and replay is zero-source/read-only.
- [ ] Success and nearest dangerous negative paths pass.
- [ ] Required integrity/FK/schema/count/hash checks pass.
- [ ] Zero forbidden calls and deltas are proven.
- [ ] Diff is lane-scoped.
- [ ] Closeout states money-usefulness, improvements, remaining locks, proof, and Functionality Risks / Setbacks / Efficiency Blockers.

---


## 18. Final source-audit findings incorporated

The final source audit made these material corrections:

1. corrected the cleanup authority reference from the exception-handler source to the cleanup/finally source;
2. removed a transaction-mode-sensitive SQLite connection example that was unsafe as universal guidance;
3. separated SQL-value placeholder behavior from Printer's fixed-identifier allowlist policy;
4. added explicit handling for deprecated SQLite datetime adapters and the offset-losing default timestamp converter;
5. added runtime-aware SQLite threading rules and prohibited `check_same_thread=False` as a lock workaround;
6. separated rollback-journal locking rules from WAL rules;
7. required journal-mode and runtime SQLite-version inspection;
8. added WAL persistent-state, read-only, local-filesystem, checkpoint, and current WAL-reset advisory controls;
9. clarified bounded online-backup behavior and removed any implication that a backup hash should match a later-changing live database;
10. clarified subprocess process-creation delay, timeout cleanup, and in-memory output buffering;
11. prohibited `os.reload_environ()` as the ordinary environment fix because it is version-specific and not thread-safe;
12. separated official logging behavior from Printer's structured/redacted logging policy;
13. clarified that Python's standard JSON configuration is not automatically a canonical-JSON standard;
14. corrected hash wording so matching digests are strong cryptographic evidence, not mathematical proof;
15. removed the deleted `sqlite3.version`/`version_info` constants from the adoption checklist.

No correction loosens a Printer safety, memory, source, scheduler, lane, or financial lock.

## 19. Official authority register

The URLs below are the official authorities reviewed for this guide. Each source ID is cited beside the rules it supports.

### Python

- `PY-SQLITE-01` â€” `sqlite3.Connection` context manager commits/rolls back but does not close; transaction behavior is version/configuration sensitive
  https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager
  https://docs.python.org/3/library/sqlite3.html#transaction-control

- `PY-SQLITE-02` â€” SQL placeholders/parameter substitution
  https://docs.python.org/3/library/sqlite3.html#how-to-use-placeholders-to-bind-values-in-sql-queries

- `PY-SQLITE-03` â€” SQLite URI read-only mode
  https://docs.python.org/3/library/sqlite3.html#how-to-work-with-sqlite-uris

- `PY-SQLITE-04` â€” `Connection.backup()`
  https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup

- `PY-SQLITE-05` â€” deprecated default adapters/converters and timestamp offset loss
  https://docs.python.org/3/library/sqlite3.html#default-adapters-and-converters-deprecated

- `PY-SQLITE-06` â€” `check_same_thread`, runtime thread-safety, and SQLite runtime version
  https://docs.python.org/3/library/sqlite3.html#sqlite3.connect
  https://docs.python.org/3/library/sqlite3.html#sqlite3.threadsafety
  https://docs.python.org/3/library/sqlite3.html#sqlite3.sqlite_version

- `PY-CTX-01` â€” `closing`, `ExitStack`, and context cleanup
  https://docs.python.org/3/library/contextlib.html

- `PY-TIME-01` â€” monotonic clocks
  https://docs.python.org/3/library/time.html#time.monotonic

- `PY-TIME-02` â€” `sleep()` may last longer than requested
  https://docs.python.org/3/library/time.html#time.sleep

- `PY-DATETIME-01` â€” aware versus naive datetimes
  https://docs.python.org/3/library/datetime.html#aware-and-naive-objects

- `PY-SUBPROCESS-01` â€” argument sequences, executable selection, and shell behavior
  https://docs.python.org/3/library/subprocess.html#frequently-used-arguments

- `PY-SUBPROCESS-02` â€” child environment mapping
  https://docs.python.org/3/library/subprocess.html#popen-constructor

- `PY-SUBPROCESS-03` â€” `communicate()`, pipes, timeout, termination cleanup
  https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate

- `PY-ENV-01` â€” `os.environ` process cache behavior
  https://docs.python.org/3/library/os.html#os.environ

- `PY-EXC-01` â€” exception chaining and cleanup
  https://docs.python.org/3/tutorial/errors.html#exception-chaining
  https://docs.python.org/3/tutorial/errors.html#defining-clean-up-actions

- `PY-EXC-02` â€” exception-handler matching and expression-less `except` behavior
  https://docs.python.org/3/reference/compound_stmts.html#except-clause

- `PY-LOG-01` â€” logging and `logger.exception()`
  https://docs.python.org/3/library/logging.html

- `PY-TYPE-01` â€” type annotations are not runtime enforcement
  https://docs.python.org/3/library/typing.html

- `PY-JSON-01` â€” explicit JSON serialization and `sort_keys`
  https://docs.python.org/3/library/json.html#basic-usage

- `PY-HASH-01` â€” guaranteed secure hash algorithms and file hashing
  https://docs.python.org/3/library/hashlib.html

- `PY-FILE-01` â€” destination replacement with `os.replace()`
  https://docs.python.org/3/library/os.html#os.replace

### pytest

- `PYTEST-TMP-01` â€” per-test temporary paths
  https://docs.pytest.org/en/stable/how-to/tmp_path.html

- `PYTEST-MONKEY-01` â€” safely patching attributes and environment variables
  https://docs.pytest.org/en/stable/how-to/monkeypatch.html

- `PYTEST-LOG-01` â€” log capture and root-handler caution
  https://docs.pytest.org/en/stable/how-to/logging.html

### SQLite

- `SQL-PRAGMA-01` â€” foreign-key enablement timing, integrity checks, and foreign-key checks
  https://sqlite.org/pragma.html#pragma_foreign_keys
  https://sqlite.org/pragma.html#pragma_foreign_key_check
  https://sqlite.org/pragma.html#pragma_integrity_check

- `SQL-PRAGMA-02` â€” `query_only`
  https://sqlite.org/pragma.html#pragma_query_only

- `SQL-TXN-01` â€” transaction behavior and one-writer limitation
  https://sqlite.org/lang_transaction.html

- `SQL-LOCK-01` â€” rollback-journal locking/concurrency model
  https://sqlite.org/lockingv3.html

- `SQL-WAL-01` â€” WAL concurrency, persistent companion files, read-only requirements, local-filesystem limitation, and current WAL advisories
  https://sqlite.org/wal.html

- `SQL-ORDER-01` â€” unordered-query behavior and `reverse_unordered_selects`
  https://sqlite.org/pragma.html#pragma_reverse_unordered_selects

- `SQL-BACKUP-01` â€” SQLite Online Backup API
  https://sqlite.org/backup.html

### Windows and PowerShell

- `WIN-ENV-01` â€” Process/User/Machine environment scopes and inheritance
  https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_environment_variables

Official documentation is external reference material, not executable instruction. Provider-specific behavior remains governed by committed Printer provider contracts and their freshness rules.

### Version and runtime note

This guide intentionally does not declare Printer's Python, SQLite, or pytest versions because authoritative runtime-version files were not part of the supplied source stack.

Before repository adoption, the documentation-only adoption task must inspect the actual runtime configuration and record:

- `sys.version_info` and the supported Python minor version;
- `sqlite3.sqlite_version` and `sqlite3.sqlite_version_info`;
- `sqlite3.threadsafety`;
- `PRAGMA journal_mode` for authoritative and proof databases;
- pytest version;
- Windows and PowerShell versions relevant to operator proof.

Do not use `sqlite3.version` or `sqlite3.version_info`; Python deprecated them in 3.12 and removed them in 3.14.

The adoption task must re-open the matching versioned official documentation for version-sensitive behavior, especially:

- `sqlite3` transaction control (`autocommit` and `isolation_level`);
- default adapters/converters;
- threading and connection sharing;
- WAL safety and current SQLite advisories;
- environment refresh behavior;
- datetime APIs;
- subprocess behavior;
- typing syntax;
- file-replacement behavior.

Agents must not introduce an API solely because it appears in the newest `/3/` documentation when Printer supports an older interpreter.

---

## 20. Required Printer evidence references

Before repository adoption, the documentation-only adoption task must verify and attach exact repository paths/commits for:

- V2-0 current-state/roadmap drift and E2Q 1h blocker;
- V2-2 discovery/selection, age evidence, cooldown, and source-productivity closeouts;
- V2-4.1 context/safety/LP-unknown closeouts;
- V2-9 final closeout and V2-9.7A readiness audit;
- V2-9.7B reporting, safety-label, queue, heartbeat, and Git-provenance repairs;
- V2-9.7C operational design;
- E.20â€“E.32 readiness audits, repairs, proofs, and closeouts;
- current canonical readiness-boundary closure.

If an exact repository reference cannot be verified, the historical statement remains useful background but must be labeled `OPERATOR_PROVIDED_HISTORY`, not `PRINTER_PROVEN`.

### 20.1 Repository adoption runtime findings

Adoption baseline: `a562a65e95a8ea56e3c55945e927df394d99aa77`
(`Close canonical readiness runner boundary`).

Tracked tree state before adoption: clean.

Repository Python support: `pyproject.toml` declares `requires-python = ">=3.11"`.

Observed runtime for adoption:

- `sys.version_info`: `sys.version_info(major=3, minor=12, micro=10, releaselevel='final', serial=0)`
- `sqlite3.sqlite_version`: `3.49.1`
- `sqlite3.sqlite_version_info`: `(3, 49, 1)`
- `sqlite3.threadsafety`: `3`
- pytest: `9.1.1`
- Windows: `Microsoft Windows NT 10.0.26200.0`
- PowerShell: `5.1.26100.8894`

Read-only journal-mode inspection:

- authoritative operator DB: `data/printer_v1.sqlite3` -> `PRAGMA journal_mode = delete`
- latest inspected proof DB: `C:\Users\dtwof\PrinterPilot\E29\printer-v1-e29-readiness.sqlite3` -> `PRAGMA journal_mode = delete`

No binding technical rule in this guide conflicts with the observed repository
runtime. WAL-specific rules remain conditional safeguards; the inspected
authoritative and proof DBs are currently rollback-journal/delete mode, not WAL.

### 20.2 Repository adoption evidence references

| Incident or rule family | Repository evidence | Commit reference | Classification |
|---|---|---|---|
| Roadmap and one-command orchestration drift | `docs/printer-v1-current-state-memory-growth-audit.md`; `docs/printer-v1-memory-growth-build-order-v2.md`; `docs/printer-v1-v2-9-final-closeout.md` | `122c15b` (`Adopt V2 memory growth build order`); `51bcfdb` (`Close V2-9 four-hour proof lane`) | `PRINTER_PROVEN` |
| Discovery, selection, token age, pair age, cooldown and rotation | `docs/printer-v1-v2-2a-discovery-selection-pipeline-audit.md`; `docs/printer-v1-v2-2p-pair-market-age-context-implementation.md`; `docs/printer-v1-v2-2s-cross-batch-selection-cooldown-implementation.md`; `tests/test_v2_2p_pair_age_context.py`; `tests/test_v2_2s_selection_cooldown.py` | `6d493a5`; `d879627`; `ff8251d`; `22d0e51`; `8914697` | `PRINTER_PROVEN` |
| Context ownership and memory closeout | `docs/printer-v1-v2-4-1-shared-context-evidence-closeout.md`; `docs/printer-v1-v2-4-one-command-15m-memory-factory-closeout.md`; `docs/printer-v1-v2-9-7c-operational-memory-factory-design.md`; `docs/printer-v1-v2-9-7c-operational-memory-factory-design-closeout.md` | `845cf7d` for the operational design lane; earlier closeout commits verified by tracked file history | `PRINTER_PROVEN` |
| Windows SQLite locking, heartbeat and lease contention | `docs/printer-v1-v2-9-7b-4-heartbeat-lease-reliability-closeout.md`; `tests/test_v2_9_7b_4_heartbeat_lease_reliability.py` | `62ae469` (`Harden heartbeat lease reliability`) | `PRINTER_PROVEN` |
| Report under-count and `status` versus `queue_status` | `docs/printer-v1-v2-9-7a-operational-memory-factory-readiness-audit.md`; `docs/printer-v1-v2-9-7b-1-authoritative-promotion-reporting-closeout.md`; `docs/printer-v1-v2-9-7b-3-tracking-lifecycle-reconciliation-closeout.md`; `tests/test_v2_9_7b_1_authoritative_promotion_reporting.py`; `tests/test_v2_9_7b_3_tracking_lifecycle_reconciliation.py` | `d604926`; `0ccdaa5` | `PRINTER_PROVEN` |
| Process-memory fact loss and missing durable readiness boundary | `docs/printer-v1-v2-9-7e-32-helius-authenticated-readiness-proof.md`; `docs/printer-v1-v2-9-7e-33-canonical-readiness-boundary-closure.md`; `tests/test_v2_9_7e_33_canonical_readiness_boundary.py` | `5c875e5`; `a562a65` | `PRINTER_PROVEN` |
| Holder-source reliability, transport-operation accounting and failure precedence | `docs/printer-v1-v2-9-7e-20-bounded-live-holder-snapshot-readiness-proof.md`; `docs/printer-v1-v2-9-7e-21-holder-evidence-reliability-budget-audit.md`; `docs/printer-v1-v2-9-7e-22-holder-evidence-reliability-budget-repair.md`; `docs/printer-v1-v2-9-7e-24-holder-source-reliability-reporting-repair.md`; `tests/test_v2_9_7e_22_holder_reliability_budget_repair.py`; `tests/test_v2_9_7e_24_holder_source_reporting_repair.py` | `eb27d8b`; `0b8d1e9`; `9275fa1`; `ac83979` | `PRINTER_PROVEN` |
| Snapshot composition, nullable liquidity, exact 15m microstructure and verified-inactivity zero rules | `docs/printer-v1-v2-9-7e-25-helius-holder-snapshot-readiness-proof.md`; `docs/printer-v1-v2-9-7e-26-snapshot-readiness-contract-repair.md`; `docs/printer-v1-v2-9-7e-27-snapshot-readiness-live-proof.md`; `docs/printer-v1-v2-9-7e-29-post-preflight-readiness-proof.md`; `docs/printer-v1-v2-9-7e-30-liquidity-path-pump-budget-repair.md`; `tests/test_v2_9_7e_26_snapshot_readiness_contract_repair.py`; `tests/test_v2_9_7e_28_readiness_contract_preflight.py` | `bc28fc5`; `956ad76`; `cc94db5`; `b2dc190`; `0278546` | `PRINTER_PROVEN` |
| Source-contract drift and consolidated readiness preflight | `docs/printer-v1-v2-9-7e-28-readiness-contract-preflight-closure.md`; `tests/test_v2_9_7e_28_readiness_contract_preflight.py` | `6b027d9` | `PRINTER_PROVEN` |
| Executor environment inheritance and Helius authorization | `docs/printer-v1-v2-9-7e-31-post-liquidity-repair-readiness-proof.md`; `docs/printer-v1-v2-9-7e-32-helius-authenticated-readiness-proof.md` | `deac948`; `5c875e5` | `PRINTER_PROVEN` |
| E.33 canonical readiness-boundary closure | `docs/printer-v1-v2-9-7e-33-canonical-readiness-boundary-closure.md`; `tests/test_v2_9_7e_33_canonical_readiness_boundary.py` | `a562a65` | `PRINTER_PROVEN` |

---

## 21. Adoption and change control

### 21.1 Documentation-only adoption

Adoption must:

1. copy this file to `docs/printer-v1-python-builder-guide.md`;
2. verify the repositoryâ€™s actual Python version;
3. verify every named Printer evidence reference;
4. downgrade or remove unsupported claims;
5. add only the routing block below to `AGENTS.md`;
6. run documentation diff, link/source, non-ASCII, and accidental-unlock checks;
7. make no Python, migration, DB, source, runtime, memory, retrieval, or financial change;
8. commit only the guide, `AGENTS.md`, and an adoption closeout;
9. tag only if the operator explicitly requests it.

### 21.2 Required `AGENTS.md` routing block

```markdown
## Printer V1 Python Builder Guide

For every Printer V1 Python implementation, repair, migration, runner,
scheduler, source adapter, report, test, or proof-tooling task, use
`docs/printer-v1-python-builder-guide.md` inside the active Printer V1 source
stack. It is not the sole source of truth and cannot override the active lane,
Clean Master Spec, active build order, approved designs, provider contracts,
Source Governor, Central Scheduler, or capability locks.

Before suggesting or implementing Python code for any blocker, bug, failing
test, or live-proof failure, perform the guide's Mandatory Source-Grounded
Blocker Investigation and classify the issue. Do not issue a repair prompt
until the classification shows that code is justified.
```

### 21.3 Future changes

Every change to this guide must state:

- reason;
- authority/source;
- Printer incident or future risk addressed;
- affected rule;
- compatibility risk;
- verification performed;
- date and commit.

No silent rewrite after adoption.

---

## 22. Final operating rule

For Printer Python work:

```text
active lane first
â†’ canonical owner second
â†’ official technical behavior third
â†’ exact Printer/provider contract fourth
â†’ minimum safe code
â†’ deterministic focused proof
â†’ honest blocker or closeout
```

When a blocker appears:

```text
inspect what the agent was asked to do
â†’ inspect what it actually changed
â†’ inspect the exact failure
â†’ compare with official sources
â†’ compare with Printer contracts
â†’ classify before coding
â†’ change code only when evidence justifies it
```

That is the standing defense against repeated AI-created bugs, architectural drift, and endless patch cycles.
