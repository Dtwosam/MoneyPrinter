# V2-2AB: Minimal PumpPortal Live Transport — Implementation Proof

**Lane:** V2-2AB  
**Date:** 2026-07-10  
**Verdict:** `IMPLEMENTATION_PARTIAL_WITH_BLOCKER`

---

## 1. Design Anchor

This lane implements the design specified in:

```
docs/printer-v1-v2-2aa-minimal-pumpportal-launch-transport-design.md
```

Committed at `447e3fc` (V2-2AA design). All seven design questions answered in V2-2AA are addressed here.

---

## 2. Dependency Preflight Result

**Blocker: `websockets` package absent.**

`pyproject.toml` has `dependencies = []`. Neither `websockets` nor `websocket-client` is installed in the project environment. This is the primary reason the verdict is `IMPLEMENTATION_PARTIAL_WITH_BLOCKER` rather than `IMPLEMENTATION_PROOF_PASS`.

The implementation is structurally complete and correct for when `websockets` is installed. The `build_pumpportal_live_transport()` function uses a lazy import guard:

```python
def build_pumpportal_live_transport(...):
    try:
        import websockets as _ws
    except ImportError as exc:
        raise RuntimeError(
            "build_pumpportal_live_transport requires the 'websockets' package; "
            "add websockets to project dependencies before using live transport"
        ) from exc
    ...
```

When `websockets` is absent, calling `build_pumpportal_live_transport()` raises `RuntimeError`. The CLI wraps this as `ValueError` so operator-facing errors are consistent. No live WebSocket calls are made in this lane.

---

## 3. Files Changed

| File | Change |
|------|--------|
| `src/printer_v1/sources/pumpportal.py` | Metadata flags updated; constants added; `build_pumpportal_live_transport()` added |
| `src/printer_v1/sources/governed_execution.py` | TYPE_CHECKING guard added; `adapter` annotation widened to `FixtureSourceAdapter \| PumpPortalAdapter` |
| `src/printer_v1/operator_cli/commands.py` | `pumpfun_launch_stream` status READY; live transport build call + RuntimeError→ValueError wrap |
| `tests/test_v2_2ab_pumpportal_live_transport.py` | New: 35 focused tests (mock WebSocket, all pass) |
| `tests/test_post_rc_pumpportal_discovery_adapter.py` | 3 tests updated for new metadata and NOT_READY migration |
| `tests/test_v2_2x2_t2_token_age_evidence.py` | 1 test updated for new metadata flags |
| `docs/printer-v1-v2-2ab-minimal-pumpportal-live-transport-implementation-proof.md` | This file |

---

## 4. Transport Bounds Implemented

All bounds from V2-2AA design are enforced:

| Bound | Value | Location |
|-------|-------|----------|
| Max events | 5 (`_PUMPPORTAL_MAX_EVENTS_DEFAULT`) | `pumpportal.py` constant |
| Wall-clock duration | 30s (`_PUMPPORTAL_DURATION_SECONDS_DEFAULT`) | `pumpportal.py` constant |
| Connect timeout | 10s (`_PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT`) | `pumpportal.py` constant |
| Reconnects | 0 — connect failure returns empty list | `_collect()` except clause |
| Background threads | 0 — `asyncio.run()` blocks until complete | `transport()` callable |
| Events filter | Only `dict` payloads accepted | `isinstance(data, dict)` check |

---

## 5. Metadata and Status Changes

| Field | Before V2-2AB | After V2-2AB |
|-------|--------------|--------------|
| `supports_network_execution` | `False` | `True` |
| `fixture_transport_only` | `True` | `False` |
| `enabled_by_default` | `False` | `False` (unchanged) |
| `pumpfun_launch_stream` plan status | `NOT_READY` | `READY` |
| `pumpfun_migration_stream` plan status | `NOT_READY` | `NOT_READY` (unchanged) |

`enabled_by_default = False` is preserved. The adapter is never active unless explicitly constructed with `enabled=True`.

---

## 6. Source Governor Compatibility

- `build_pumpportal_live_transport()` returns a plain callable `(SourceAdapterContext) -> Mapping[str, Any]`
- The callable is passed as `fixture_transport` to `build_pumpportal_adapter()`
- `PumpPortalAdapter.execute()` calls the transport through the existing governed execution path
- `execute_source_request_with_governor()` signature widened to accept `PumpPortalAdapter` via `TYPE_CHECKING` guard — no runtime import change
- Governor approval, recording, and failure paths unchanged

---

## 7. T2 Safety Rules

T2 token-age evidence rules are **unchanged**. Verified by `test_v2_2x2_t2_token_age_evidence.py` (all 79 tests pass after metadata assertion update):

- Only `pumpfun_launch_stream` events set `token_created_at`
- Migration events never receive T2 tier
- `captured_at` never becomes `token_created_at`
- Priority order: `tokenCreatedAt → createdTimestamp → timestamp`
- Staleness ≤ 3600s enforced in `_extract_launch_timestamp()`
- Future timestamps rejected

---

## 8. Tests Run

### New focused test file (V2-2AB)
```
tests/test_v2_2ab_pumpportal_live_transport.py
```
**35 tests — 35 PASSED**

Coverage:
- `TestLiveTransportDependencyGuard` (2): RuntimeError raised without websockets, both function and call path
- `TestLiveTransportMockedWebSocket` (11): max events bound, connect failure empty list, no reconnect, subscribeNewToken sent, duration timeout, non-dict skipped, asyncio.run used, ws.close called
- `TestFixtureTransportsUnchanged` (3): existing fixture_success and fixture_failure transports still work
- `TestPlanCatalogStatus` (5): launch_stream READY, migration NOT_READY, no trading kinds
- `TestGovernorExecutesPumpPortalAdapter` (2): request+response row on success, failure row on transport error
- `TestNoDownstreamRowsCreated` (1): no memory/retrieval/paper/trading rows
- `TestMetadataFlags` (5): supports_network_execution=True, fixture_transport_only=False, enabled_by_default=False
- `TestT2SafetyRules` (6): migration no T2, launch valid T2, stale rejected, captured_at isolation, priority, future rejected

### Updated existing test files
```
tests/test_post_rc_pumpportal_discovery_adapter.py   (3 tests updated)
tests/test_v2_2x2_t2_token_age_evidence.py           (1 test updated)
```

### Combined result
```
158 passed in 120.03s
```

---

## 9. Safety Confirmations

- **No live network calls made** — all transport tests use fake websockets injected via `patch.dict(sys.modules, {"websockets": fake_ws})`
- **No new dependencies added** — `pyproject.toml` `dependencies = []` unchanged
- **T2 rules preserved** — existing T2 test suite passes unchanged (except metadata assertion update)
- **`enabled_by_default = False`** — verified by test
- **No BUY/SELL/HOLD, positions, trades, paper decisions** — verified by `TestNoDownstreamRowsCreated`
- **`pumpfun_migration_stream` stays NOT_READY** — verified by plan catalog test
- **V2-3 remains paused** — no retrieval, no memory generation, no scoring
- **`asyncio.run()` used** — no lingering threads, synchronous caller contract preserved

---

## 10. Remaining Blockers

### Blocker 1 (Critical — live use blocked)
`websockets` package not in `pyproject.toml` dependencies. Until added, `build_pumpportal_live_transport()` raises `RuntimeError` at build time. The operator CLI wraps this as `ValueError`.

**Resolution path:** Add `websockets>=12.0` to `pyproject.toml` `[project]` dependencies in a dedicated dependency lane; then re-verify import guard is no longer triggered.

### Blocker 2 (Design scope — deferred)
No live WebSocket proof in this lane. Transport correctness is verified via mock fixture only. A live smoke test against `wss://pumpportal.fun/api/data` is deferred to a future lane after `websockets` is installed.

---

## 11. V2-3 Status

**V2-3 remains PAUSED.**

No retrieval, no memory generation, no scheduling, no scoring, no paper decisions, no BUY/SELL/HOLD were introduced or enabled in this lane.

---

## 12. Recommended Next Lane

**V2-2AC: Add `websockets` dependency**

Scope:
1. Add `websockets>=12.0` to `pyproject.toml` `[project] dependencies`
2. Verify `build_pumpportal_live_transport()` no longer raises `RuntimeError` on import
3. Verify existing 35-test suite still passes
4. Verdict: `DEPENDENCY_ADDED` or `DEPENDENCY_PROOF_PASS`

After V2-2AC, a live smoke lane (V2-2AD or similar) can attempt a bounded 5-event/30s collection against the real PumpPortal endpoint.

---

## 13. Commit

All changes committed under:

```
Implement V2-2AB minimal PumpPortal live transport
```
