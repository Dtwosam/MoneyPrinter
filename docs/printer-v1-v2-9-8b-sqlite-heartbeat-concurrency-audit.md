# Printer V1 V2-9.8B.20 — Production SQLite Concurrency and Heartbeat Reliability Audit

**Document status:** `V2_9_8B_20_SQLITE_HEARTBEAT_CONCURRENCY_AUDIT_PASS_ROOT_CAUSE_PROVEN`

**Baseline HEAD:** `cfd4beb7d3b097d31f25cf6ce81e6736cf9a4860`  
**Subject:** `Close V2-9.8B production readiness consolidation`  
**Authoritative DB:** `data/printer_v1.sqlite3`  
**Audit date:** 2026-07-27

## 1. Verdict

```text
V2_9_8B_20_SQLITE_HEARTBEAT_CONCURRENCY_AUDIT_PASS_ROOT_CAUSE_PROVEN
SHARED_ROOT_CAUSE: OPEN_WRITE_TRANSACTION_ACROSS_SOURCE_IO
```

Both production campaigns terminated with durable:

```text
LEASE_RENEWAL_SQLITE_LOCKED
```

They share one architectural root cause: an operational writer opened a deferred
SQLite write transaction on the first source-ledger DML, then performed live
source I/O (and later sleeps/pacing) while the write lock remained held. The
heartbeat renewer could not obtain `BEGIN IMMEDIATE` inside its bounded busy
budget and failed closed with sanitized evidence.

This audit did not run production, live sources, or authoritative mutation.

## 2. Baseline gate

| Gate | Result |
|---|---|
| Exact HEAD `cfd4beb` | PASS |
| Clean tracked worktree at audit start | PASS |
| SQLite `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | zero rows |
| Active Printer process | none |
| Active supervision | zero (`TERMINAL` only) |
| Active factory `RUNNING` | zero |
| Active lease files | absent for both executions |
| SQLite journal mode (authoritative) | `delete` |
| Heartbeat busy contract | 2.0s timeout × 5 attempts + 0.05s retry sleep |

## 3. Failed executions

| Field | Execution A | Execution B |
|---|---|---|
| Execution ID | `20260727T202052Z-d42812d31bd8` | `20260727T203044Z-7f8e098bf267` |
| Campaign | `…-d42812d31bd8-campaign` | `…-7f8e098bf267-campaign` |
| Supervision | `…-d42812d31bd8-supervision` | `…-7f8e098bf267-supervision` |
| Launch HEAD | `cfd4beb…` clean | `cfd4beb…` clean |
| First terminal cause | `LEASE_RENEWAL_SQLITE_LOCKED` | `LEASE_RENEWAL_SQLITE_LOCKED` |
| Heartbeat attempt | `2026-07-27T20:21:22.430431+00:00` | `2026-07-27T20:31:14.410065+00:00` |
| Prior heartbeat (never advanced) | `20:20:52.422494Z` | `20:30:44.402165Z` |
| Prior lease expiry | `20:22:22.422494Z` | `20:32:14.402165Z` |
| `sqlite_locked` | 1 | 1 |
| Safe category | `SQLITE_LOCK_CONTENTION` | `SQLITE_LOCK_CONTENTION` |
| Campaign source calls | 21 | 16 |
| Factory run | `97c08ca3-…` `SAFE_STOPPED` | `a0ba28cc-…` `SAFE_STOPPED` |
| Terminal cleanup | `20:30:17.759910Z` | `20:42:48.929360Z` |
| Restart / successor | false / false | false / false |

Heartbeat interval is 30s (`HEARTBEAT_SECONDS`). Lease duration is 90s. Both
failures are the **first** renewal attempt (~30s after lease creation).

## 4. Exact shared lock owner and transaction boundary

### 4.1 Connection and code path holding the write lock

**Owner (shared for both failures):** the main operational campaign thread’s
discovery connection inside:

```text
direct_migration_discovery.run_direct_migration_discovery
  -> execute_source_request_with_governor
       -> record_source_request (INSERT starts deferred write)
       -> adapter.execute (live PumpPortal migration stream I/O)
       -> record_source_response
  ... multi-round + settle + verify, commit only at end of owner
```

Supporting long writers with the same anti-pattern (same architectural defect
class, later in the same campaigns):

| Writer | Path | Holds write across |
|---|---|---|
| Migration discovery | `direct_migration_discovery.py` | multi-round PumpPortal I/O, `settle_seconds` sleep, verify I/O |
| Liquidity front door | `graduated_liquidity_front_door.py` | DexScreener pair I/O per candidate until final commit |
| Locator | `graduated_supply_front_door.py` | DexScreener fresh-profiles I/O |
| Holder funnel | `_evaluate_holder_eligibility` + `_collect_preclose_context` | GoPlus/RPC/Helius I/O and request pacer sleeps |
| Combined fixture executor | `combined_executor.py` | whole discovery cycle (fixture-speed; same shape) |

### 4.2 When the transaction began and ended (Execution A)

Proven by source ledger wall-clock times on the authoritative DB:

| Step | Time (UTC) | Event |
|---|---|---|
| Lease / heartbeat create | `20:20:52.422` | supervision ACTIVE |
| Source request 1205 | `20:20:52`–`20:20:53` | DexScreener fresh profiles (locator) |
| Source request 1206 **INSERT** | `20:20:53.988` | PumpPortal migration stream request row |
| **First DML on discovery connection** | ~`20:20:53.988` | deferred write transaction opens (RESERVED) |
| Heartbeat renewal attempt | `20:21:22.430` | `BEGIN IMMEDIATE` fails → `LEASE_RENEWAL_SQLITE_LOCKED` |
| Source response 1206 | `20:22:17.938` | stream still open ~84s after request |
| Later multi-round / verify / holder | `20:22`–`20:30` | same campaign continues |
| Outer commit / factory / cleanup | `20:30:17` | terminal cleanup; factory zero-step `SAFE_STOPPED` |

Execution B is isomorphic:

| Step | Time (UTC) |
|---|---|
| Lease create | `20:30:44.402` |
| PumpPortal request 1229 | `20:30:46.077` |
| Heartbeat fail | `20:31:14.410` (mid-stream) |
| PumpPortal response 1229 | `20:32:47.248` (~121s stream) |
| Cleanup | `20:42:48.929` |

### 4.3 Operations performed while the transaction remained open

While the deferred write stayed open, the owner performed:

1. Governed source request INSERT (starts deferred transaction).
2. Live adapter transport (`adapter.execute`) for PumpPortal `subscribeMigration`
   lasting **~84s** (A) and **~121s** (B).
3. Source response INSERT after the stream returned.
4. Additional migration rounds, optional settle sleep (`settle_seconds=6.0`),
   PumpSwap verification I/O, graduated candidate writes.
5. Later stages (front door DexScreener, holder GoPlus/RPC/Helius) reused the
   same architectural anti-pattern on shared connections.

### 4.4 Crossed source I/O / sleeps / other SQLite owners

| Crossed boundary | Proven |
|---|---|
| Source I/O while write open | YES — PumpPortal stream mid-flight at heartbeat |
| Intentional settle sleep while write open (code path) | YES — `time.sleep(settle_seconds)` after first DML, before final commit |
| Request pacing sleep while write open (holder path) | YES — `SequentialRequestPacer.pace` before governed execute |
| Lengthy computation while write open | not required for root cause; I/O alone exceeds budget |
| Concurrent operational writers | single main campaign writer + heartbeat renewer |

No second campaign process was active. The contention is **intra-process**:
main writer connection vs heartbeat thread’s separate connection.

### 4.5 Why heartbeat renewal could not obtain a bounded write opportunity

`renew_campaign_lease`:

1. Loads supervision (read-only connection).
2. Replaces lease lock file.
3. Opens a writer and runs `_begin_immediate` with:
   - `PRAGMA busy_timeout=2000`
   - up to 5 attempts
   - 0.05s sleep between attempts  
   → maximum wait ≈ **10.2s**.

The migration stream held the RESERVED write lock for **~84s / ~121s**. The
first heartbeat at 30s therefore always lost.

### 4.6 Same root cause for both executions

| Check | Result |
|---|---|
| Same terminal cause | `LEASE_RENEWAL_SQLITE_LOCKED` |
| Same failure category | `SQLITE_LOCK_CONTENTION` |
| Same phase | first heartbeat (~30s) |
| Same concurrent owner class | discovery migration stream write txn |
| Same code path | `execute_source_request_with_governor` + shared connection |
| Same launch HEAD | `cfd4beb` |

**Yes — identical architectural root cause.**

### 4.7 Concurrent operational writers around each failed renewal

At first heartbeat only:

* main thread: discovery migration connection (write lock holder)
* heartbeat thread: renewer (blocked on `BEGIN IMMEDIATE`)
* no Scheduler runtime jobs
* no second campaign
* no SQLite sidecar process

Later (after heartbeat already failed) additional writers (front door, holder,
activation/terminal) ran until the cancellation probe terminalized the campaign.

### 4.8 Transaction / journal / busy / ownership contracts (pre-repair)

| Contract | Pre-repair state |
|---|---|
| Journal mode | `delete` (default) |
| Busy timeout (heartbeat) | 2.0s × 5 attempts |
| Busy timeout (many operational writers) | often unset / 0 |
| Connection ownership | ad hoc `sqlite3.connect` per owner |
| Transaction ownership | deferred autobegin on first DML; commit at end of multi-stage owner |
| Retry behaviour | heartbeat bounded; main writers generally no busy retry |
| WAL | not required for this root cause (write-write, not read-write) |

## 5. Residue from both executions (read-only)

| Object | Execution A | Execution B |
|---|---|---|
| Campaign state | `TERMINAL_FAILED` | `TERMINAL_FAILED` |
| Supervision | `TERMINAL/FAILED` lease released | `TERMINAL/FAILED` lease released |
| Factory | `SAFE_STOPPED`, 0 steps | `SAFE_STOPPED`, 0 steps |
| Token slots | `MANUAL_REVIEW` ×2 | `MANUAL_REVIEW` ×2 |
| Tracking queues 20–23 | `SKIPPED` / `MANUAL_REVIEW` | same |
| Lease files | absent | absent |
| Active Scheduler work | none | none |
| Heartbeat failure rows | durable, immutable | durable, immutable |

**No active operational residue requiring authoritative mutation.** Terminal
disposition from V2-9.8B.18 remains intact.

## 6. Disposable reproduction (pre-repair pattern)

Disposable proof (fixture DB only) reproduces the exact pattern:

1. Open operational connection.
2. INSERT source request (deferred write opens).
3. Hold without commit longer than the heartbeat busy budget.
4. Concurrent `renew_campaign_lease` → `renewal_confirmed=false`,
   `sqlite_locked=true`, `LEASE_RENEWAL_SQLITE_LOCKED`.

Repaired path proof:

1. `execute_source_request_with_governor` records request and **commits/releases**
   before adapter I/O.
2. Long adapter delay while heartbeat renews successfully.
3. `connection.in_transaction is False` during adapter execute.

## 7. Required architectural repair (not timeout patches)

Primary repair (proven, not speculative):

1. **Central write contract** (`printer_v1.db.sqlite_write_contracts`):
   - `release_write_transaction`
   - `connect_operational` / busy-timeout + foreign_keys
   - `short_write_transaction`
2. **`execute_source_request_with_governor`**: commit/release after request
   ledger write **before** `adapter.execute`; release after response/failure.
3. **Migration discovery**: release before settle/reverify sleeps; operational
   connect contract.
4. **Holder/preclose pacing**: release before `pace()` sleeps.
5. **Live campaign holder funnel**: release before holder source collection.
6. **Front door / locator / combined executor**: operational connect contract.

Explicitly **not** accepted as the primary fix:

* increasing lease duration
* slowing heartbeat interval
* increasing SQLite busy timeout alone
* automatic renewal retries that hide contention
* suppressing `LEASE_RENEWAL_SQLITE_LOCKED`
* continuing without confirmed renewal

## 8. Capability locks preserved

No change to: source ceiling 45, six-candidate policy, $3,000 liquidity floor,
two-token capacity, cooldown/rotation, `WINDOW_15M`, support-only 5m,
longer-window locks, retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, wallets, paid APIs, scoring/ranking/confidence.

## 9. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Classification | Note |
|---|---|---|
| Intermediate commit of source ledger before adapter I/O | intentional architecture | request rows can exist without response if process dies mid-I/O; more honest than locking the DB |
| Parent multi-object atomicity spanning source I/O | removed | pure SQLite batches remain short; I/O is outside write txns |
| Residual pure-write batches that are large but I/O-free | residual risk | should stay short; monitor if any pure write exceeds ~10s |
| WAL migration | not required | not minimum safe architecture for this defect |
| Combined executor whole-cycle transaction | residual fixture shape | fixture-speed; production migration uses repaired owners |

## 10. Next step after audit

Implement the proven concurrency repair, disposable concurrency stress +
operational regressions, exact residue recovery only if needed (currently
already clean), then closeout and commits.
