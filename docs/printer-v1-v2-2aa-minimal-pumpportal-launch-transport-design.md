# Printer V1 V2-2AA Minimal PumpPortal Launch Transport Design

**Lane:** V2-2AA — Minimal PumpPortal Launch-Stream Transport Design
**Type:** Design-only — no implementation, no tests, no code changes
**Verdict:** `DESIGN_COMPLETE_WITH_BLOCKERS`
**Date:** 2026-07-09
**Executor:** Claude Sonnet 4.6

V2-3, V2-4, PumpPortal live transport activation, PumpSwap, source expansion,
runtime/scheduler, memory generation, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, and PnL remain paused. This document is design-only.

---

## 1. Source Stack Read

| Document | Purpose |
|---|---|
| `docs/printer-v1-v2-2y-bounded-live-t2-token-age-proof.md` | V2-2Y blocker summary — preflight gate failure, no live call made |
| `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md` | V2-2X.1 source design; T2 path chosen; readiness table |
| `src/printer_v1/sources/pumpportal.py` | Adapter, metadata flags, transport injection, normalization |
| `src/printer_v1/sources/governed_execution.py` | Source Governor; type annotation blocker identified |
| `src/printer_v1/sources/registry.py` | PumpPortal registry entry; already registered |
| `src/printer_v1/sources/recording.py` | Request/response/failure recording; already wired |
| `src/printer_v1/operator_cli/commands.py` | Plan catalog, PLAN_STATUS, execute-item path |

Anchors verified:

| Anchor | Commit | Content |
|---|---|---|
| V2-2Y proof | latest | `PROOF_NOT_READY_WITH_BLOCKER`; no live call made; blockers catalogued |
| V2-2X.1 design | `5b9f93b` | T2 = governed PumpPortal launch-event timing as chosen path |

---

## 2. V2-2Y Blocker Summary

V2-2Y attempted a bounded live PumpPortal launch-stream proof through the Source
Governor. The preflight gate stopped execution before any live call. Three
structural blockers were identified:

| # | Blocker | Location |
|---|---|---|
| 1 | `fixture_transport_only = True` | `PumpPortalAdapterMetadata` in `pumpportal.py` |
| 2 | `supports_network_execution = False` | `PumpPortalAdapterMetadata` in `pumpportal.py` |
| 3 | `execute_source_request_with_governor` type annotation accepts only `FixtureSourceAdapter` | `governed_execution.py` |

No live code existed at the time of V2-2Y. No transport callable connected to a
WebSocket. The commands.py pumpportal branch raises `ValueError` if no
`transport_fn` is provided — correct behaviour that must stay until a live
transport is built and explicitly passed.

---

## 3. Design Question Answers

### Q1 — What is the minimal transport scope?

A single async-to-sync callable that:

1. Opens a WebSocket connection to `wss://pumpportal.fun/api/data`
2. Sends one subscription message: `{"method": "subscribeNewToken"}`
3. Reads events until the first of: 5 events received, 30 seconds elapsed
4. Closes the connection cleanly regardless of outcome
5. Returns `{"events": [...], "subscription_method": "subscribeNewToken"}`

No reconnect logic. No background thread. No scheduler integration. No event
persistence outside the return value. No token discovery or intake path. No
pool confirmation. No migration-stream subscription. No PumpSwap involvement.

The callable signature matches the existing injection point:

```python
def build_pumpportal_live_transport(
    *,
    max_events: int = 5,
    duration_seconds: float = 30.0,
    connect_timeout_seconds: float = 10.0,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    ...
```

This function lives in `src/printer_v1/sources/pumpportal.py` alongside the
existing `fixture_success_transport` and `fixture_failure_transport` helpers.
It returns a callable that is passed to `build_pumpportal_adapter(fixture_transport=...)`.
The name `fixture_transport` is already used; the live transport uses the same
injection slot because the adapter calls `self.transport(context)` uniformly.

### Q2 — What are the bounds?

| Bound | Value | Rationale |
|---|---|---|
| Max events per call | 5 | Enough to verify T2 evidence path; prevents unlimited accumulation |
| Max call duration | 30s | Hard wall clock limit |
| Connect timeout | 10s | Fail fast if PumpPortal unreachable |
| Reconnect attempts | 0 | Single attempt only; proof must be bounded and reproducible |
| Concurrent calls | 1 | No parallelism; operator-triggered single proof run |
| Background workers | 0 | No threads, no asyncio event loops left running after return |
| Scheduler involvement | None | No job queuing, no job completion records |

The 5-event / 30s bounds are enforced inside the transport callable before
returning. The adapter and governor do not need to enforce these independently.

### Q3 — Source Governor path

The existing `execute_source_request_with_governor()` in `governed_execution.py`
is the correct execution path. It records `record_source_request` before calling
`adapter.execute()`, then records `record_source_response` on success or
`record_source_failure` on exception.

**Single change required:** The function's type annotation currently accepts only
`FixtureSourceAdapter`. It must be widened to accept `PumpPortalAdapter` (or a
structural protocol). The simplest safe change is:

```python
# Before
def execute_source_request_with_governor(
    db_path_or_conn: str | Path | sqlite3.Connection,
    source_request: SourceRequest,
    adapter: FixtureSourceAdapter,
    ...
) -> GovernedSourceExecutionResult:

# After
def execute_source_request_with_governor(
    db_path_or_conn: str | Path | sqlite3.Connection,
    source_request: SourceRequest,
    adapter: FixtureSourceAdapter | PumpPortalAdapter,
    ...
) -> GovernedSourceExecutionResult:
```

No behavioural change. The governor calls `adapter.execute(source_request)` in
both cases. The import of `PumpPortalAdapter` (or its class name from
`pumpportal.py`) must be added to `governed_execution.py`.

Alternatively: introduce a `SourceAdapter` protocol with a single
`execute(request)` method and annotate against that. Either approach satisfies
the type safety requirement. The union approach is simpler and requires fewer
new abstractions.

### Q4 — Metadata and status changes

Two flags in `PumpPortalAdapterMetadata` must change:

| Field | Current | After change |
|---|---|---|
| `fixture_transport_only` | `True` | `False` |
| `supports_network_execution` | `False` | `True` |

One entry in `_SOURCE_REQUEST_PLAN_CATALOG` in `commands.py` must change:

| Source | Request kind | Current | After change |
|---|---|---|---|
| `pumpportal` | `pumpfun_launch_stream` | `NOT_READY` | `READY` |
| `pumpportal` | `pumpfun_migration_stream` | `NOT_READY` | remains `NOT_READY` |

The `commands.py` pumpportal execution branch currently raises `ValueError` when
no `transport_fn` is provided. After the live transport is built, the CLI command
will pass the live transport directly:

```python
adapter = build_pumpportal_adapter(
    enabled=True,
    fixture_transport=build_pumpportal_live_transport(),
)
```

The `ValueError` guard can then be relaxed for `pumpfun_launch_stream` only, or
left as-is with the caller always passing a transport callable.

No registry change is needed. PumpPortal is already registered in `registry.py`
with `stale_after_seconds=60`, `default_rate_limit_per_minute=30`,
`dependency_type="free_public"`, `requires_paid_plan=False`.

### Q5 — T2 token-age safety rules

These rules are already implemented in `_normalize_pumpportal_event()` and
`_extract_launch_timestamp()` in `pumpportal.py`. They must not be violated by
any future implementation:

| Rule | Requirement |
|---|---|
| Only `pumpfun_launch_stream` events produce T2 evidence | Migration events (`pumpfun_migration_stream`) never set `token_created_at` |
| Timestamp priority | `tokenCreatedAt` → `createdTimestamp` → `timestamp`; use first non-None value |
| Staleness threshold | 3600s; events older than 3600s at call time are rejected |
| `captured_at` is never used as `token_created_at` | These are distinct fields; conflating them is forbidden |
| `token_age_evidence_tier` must be set to T2 | Only when a valid `token_created_at` is extracted from a launch event |
| Migration events produce T1 evidence at best | They do not carry original launch timestamp |
| `subscribeNewToken` subscription required | Migration subscription alone produces no T2 evidence |

The existing `_extract_launch_timestamp()` function already enforces the
staleness check. No new staleness logic is needed in the transport.

### Q6 — Future proof acceptance criteria

A live T2 proof (the next lane after implementation) is accepted when all of the
following hold:

| Criterion | Requirement |
|---|---|
| Proof uses isolated proof DB | Not the persistent DB; path passed explicitly |
| Persistent DB hash unchanged | SHA-256 or row count of `printer_token_snapshots` matches before/after |
| At least one launch event received | `events` list contains ≥ 1 entry from `subscribeNewToken` |
| `token_created_at` is non-null | Extracted from the event's `tokenCreatedAt` / `createdTimestamp` / `timestamp` field |
| `token_age_seconds` is non-null | Derived from `token_created_at` and `captured_at` |
| `token_age_evidence_tier` is `T2` | Set by normalization path |
| Source Governor records exist | `printer_source_requests` row and `printer_source_responses` row both present in proof DB |
| No migration events produced T2 | Migration event rows, if present, have `token_age_evidence_tier = None` or `T1` |
| No snapshot was written to persistent DB | Proof is read-only on the persistent side |
| No paper decision, memory, or trading row created | Proof is strictly observational |
| All required regression suites pass | As specified in the proof lane instruction |

### Q7 — Implementation handoff

To implement the minimal live transport, a future implementation lane must make
exactly these changes:

**File: `src/printer_v1/sources/pumpportal.py`**

1. Add `build_pumpportal_live_transport()` function returning a transport
   callable. The callable must use `websockets` or `websocket-client` (whichever
   is already a project dependency) to connect, subscribe, collect events up to
   bounds, and disconnect. It must not block indefinitely — implement the 30s
   wall-clock and 10s connect timeout using the chosen library's timeout support.
2. Change `PumpPortalAdapterMetadata.fixture_transport_only` from `True` to
   `False`.
3. Change `PumpPortalAdapterMetadata.supports_network_execution` from `False` to
   `True`.

**File: `src/printer_v1/sources/governed_execution.py`**

4. Widen the `adapter` type annotation from `FixtureSourceAdapter` to
   `FixtureSourceAdapter | PumpPortalAdapter` (or an equivalent structural
   protocol). Add the necessary import.

**File: `src/printer_v1/operator_cli/commands.py`**

5. Change `pumpfun_launch_stream` status from `_PLAN_STATUS_NOT_READY` to
   `_PLAN_STATUS_READY` in `_SOURCE_REQUEST_PLAN_CATALOG`.
6. Update the `pumpportal` execution branch to call
   `build_pumpportal_live_transport()` when no operator `transport_fn` is
   provided and the request kind is `pumpfun_launch_stream`.

**No other files require changes.** Recording (`recording.py`), registry
(`registry.py`), and the adapter's `execute()` method all work without
modification.

---

## 4. Bounded Execution Contract

```
BOUNDED EXECUTION CONTRACT — pumpfun_launch_stream live transport

Entry:     execute_source_request_with_governor() called with live PumpPortalAdapter
Isolation: proof DB only; persistent DB path never passed to proof run
Duration:  hard wall ≤ 30s; connect timeout ≤ 10s
Events:    collect at most 5; stop immediately when limit or duration reached
Reconnect: 0 — single attempt; if connect fails, raise and let governor record failure
Threads:   0 — no background worker; call is synchronous from caller's perspective
Output:    dict with "events" list; empty list allowed (0 events received is valid)
Side effects inside transport: none — no DB writes, no file writes, no memory paths
Governor side effects: request row + (response row or failure row) in proof DB only
```

---

## 5. Source Governor Design

The governor path is unchanged behaviorally. The only structural change is the
type annotation in `governed_execution.py`.

Recording flow:

```
1. record_source_request()   → printer_source_requests (proof DB)
2. adapter.execute()         → calls transport callable → WebSocket → events
3a. record_source_response() → printer_source_responses (proof DB)  [on success]
3b. record_source_failure()  → printer_source_failures (proof DB)   [on exception]
```

All three recording functions in `recording.py` use `writable_connection()` and
are already called unconditionally by `execute_source_request_with_governor()`.
No new recording logic is needed.

---

## 6. Request / Response / Failure Recording Design

**Already complete.** The recording layer in `recording.py` is generic. It
stores whatever is passed as the normalized payload. For a live launch-stream
call, the response row's `normalized_payload_json` will contain:

```json
{
  "events": [...],
  "subscription_method": "subscribeNewToken",
  "source_name": "pumpportal"
}
```

The `printer_source_responses` schema already accommodates arbitrary JSON payloads.
No migration is needed. No new columns are needed.

---

## 7. Safety Confirmations

- No live source call was made in this design lane. No WebSocket was opened.
- No source code was changed.
- No tests were written or modified.
- No DB was mutated.
- No persistent state was changed.
- No paper decisions, memory, retrieval, BUY/SELL/HOLD, positions, trades,
  audits, or PnL paths were touched.
- PumpSwap remains paused and untouched.
- V2-3 and V2-4 remain paused.
- This design does not activate PumpPortal as a default source.
- `enabled_by_default = False` is unchanged and must remain False.
- The live transport is operator-triggered, single-shot, proof-only.

---

## 8. Money-Usefulness Contribution

PumpPortal `pumpfun_launch_stream` is the only available source that carries a
cryptographically-timestamped token launch event (`tokenCreatedAt`) at the moment
of creation. This is T2 evidence — the highest-quality tier for token age that
does not require a Solana RPC call or Helius subscription.

Token age (`token_age_seconds`) is an A3 input to the paper decision function.
Without T2 evidence, `token_age_seconds` remains None for all tokens, A3 uses
the absent-age fallback, and the paper decision cannot distinguish a 30-second-old
token from a 30-minute-old one. Unblocking T2 evidence directly improves
paper-decision accuracy for the fast-exit timer logic.

---

## 9. Remaining Blockers

The following blockers must be resolved before a live T2 proof can run:

| # | Blocker | Lane action |
|---|---|---|
| 1 | No live transport callable exists | Implement `build_pumpportal_live_transport()` |
| 2 | `fixture_transport_only = True` | Change to `False` |
| 3 | `supports_network_execution = False` | Change to `True` |
| 4 | `governed_execution.py` type annotation rejects `PumpPortalAdapter` | Widen annotation |
| 5 | `pumpfun_launch_stream` is `NOT_READY` in plan catalog | Change to `READY` |

All 5 blockers are in the implementation scope. No DB migration is needed. No
new source registration is needed. No parser changes are needed.

---

## 10. Next Recommended Lane

**V2-2AB — Minimal PumpPortal Live Transport Implementation**

Scope: implement exactly the 6 changes in Section 3 Q7 (Implementation Handoff).
Add fixture proof tests verifying the live transport interface contract using
`fixture_success_transport` to avoid any live WebSocket call in CI. Run all
required regression suites. Commit only the implementation files.

After V2-2AB is implemented and passes, the following becomes possible:

**V2-2AC — Bounded Live T2 Token-Age Proof**

This is the re-attempt of V2-2Y with all blockers resolved. The proof verifies
that a single governed call to `pumpfun_launch_stream` yields a response row
containing at least one event with non-null `token_created_at`, `token_age_seconds`,
and `token_age_evidence_tier = T2` in an isolated proof DB, with no mutation of
the persistent DB.

---

## 11. V2-3 Status

V2-3 remains paused. Nothing in this design unblocks V2-3. V2-3 depends on the
full memory-quality audit pass and retrieval activation, neither of which is
addressed here.
