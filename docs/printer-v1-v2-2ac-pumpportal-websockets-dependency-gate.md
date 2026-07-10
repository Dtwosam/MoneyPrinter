# V2-2AC: PumpPortal websockets Dependency and Deterministic Availability Gate

**Lane:** V2-2AC  
**Date:** 2026-07-10  
**Executor:** Claude Sonnet 4.6  
**Verdict:** `DEPENDENCY_GATE_PROOF_PASS_WITH_BLOCKERS`

---

## 1. Design Anchors

| Anchor | Commit | Content |
|---|---|---|
| V2-2AA design | `447e3fc` | Minimal PumpPortal launch-stream transport design |
| V2-2AB implementation | `45dfb2c` | Live transport implementation with ImportError guard |
| V2-2AB.1 verification | `fbf59de` | Found: websockets absent from pyproject.toml; ambient importable in Python 3.14 env |

V2-2AB.1 identified three blockers addressed in this lane:
1. `websockets` absent from `pyproject.toml` `dependencies`
2. `pumpfun_launch_stream = READY` with no deterministic dependency gate
3. Transport builder accepted unsafe bound overrides without rejection

---

## 2. Files Changed

| File | Change |
|---|---|
| `pyproject.toml` | Added `"websockets>=12.0"` to `dependencies` |
| `src/printer_v1/sources/pumpportal.py` | Added bound rejection in `build_pumpportal_live_transport()` |
| `tests/test_v2_2ab_pumpportal_live_transport.py` | Added `TestWebsocketsDependencyDeclaration` + `TestBoundHardening` (8 new tests); fixed `max_events=10` → `max_events=5` in one existing test |
| `tests/test_post_rc_pumpportal_discovery_adapter.py` | Added `from unittest.mock import patch`; updated `test_no_transport_raises_for_pumpportal` with `patch.dict(sys.modules, {"websockets": None})` |
| `docs/printer-v1-v2-2ac-pumpportal-websockets-dependency-gate.md` | This file |

`commands.py` was not changed — the RuntimeError→ValueError wrap added in V2-2AB is already correct.

---

## 3. Dependency Declaration Result

**`pyproject.toml`** now declares:
```toml
dependencies = ["websockets>=12.0"]
```

Before V2-2AC: `dependencies = []`

The websockets package is available in the Python 3.14 global environment on this machine, but is NOT installed in the Python 3.12 environment used by the pytest test runner. The pyproject.toml declaration makes the dependency explicit and reproducible for `pip install -e .` users. A `test_websockets_declared_in_pyproject_dependencies` test verifies the declaration at the source level.

Note: The Python 3.12 pytest environment does not have websockets installed. All transport tests use `patch.dict(sys.modules, ...)` with fake websockets modules and do not require the real package to be present.

---

## 4. READY / Gating Decision

**Decision: Keep `pumpfun_launch_stream = READY` with clear failure if import fails.**

Rationale:
- The dependency is now declared in pyproject.toml
- The CLI wraps `RuntimeError` → `ValueError` with a clear operator message
- `enabled_by_default = False` — adapter never activates without explicit operator action
- All tests use `patch.dict(sys.modules, {"websockets": None})` to simulate import failure deterministically

The `test_no_transport_raises_for_pumpportal` test was previously environment-dependent: in Python 3.14, websockets was importable so no ValueError was raised; in Python 3.12 (pytest), it wasn't. The fix forces `sys.modules["websockets"] = None` via `patch.dict`, making the test deterministic regardless of global site-packages state.

Status table (unchanged from V2-2AB):

| Item | Value |
|---|---|
| `pumpfun_launch_stream` plan status | `READY` |
| `pumpfun_migration_stream` plan status | `NOT_READY` |
| `enabled_by_default` | `False` |
| `supports_network_execution` | `True` |
| `fixture_transport_only` | `False` |
| Source Governor path | required |

---

## 5. Bound Hardening Result

`build_pumpportal_live_transport()` now rejects unsafe override values before attempting the websockets import:

```python
if max_events > _PUMPPORTAL_MAX_EVENTS_DEFAULT:        # > 5
    raise ValueError(...)
if duration_seconds > _PUMPPORTAL_DURATION_SECONDS_DEFAULT:   # > 30.0
    raise ValueError(...)
if connect_timeout_seconds > _PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT:  # > 10.0
    raise ValueError(...)
```

The bounds check fires BEFORE the websockets import. This means:
- Unsafe bounds raise `ValueError` even if websockets is absent (`RuntimeError` would normally come first)
- Callers get a clear, actionable error message
- No clamping — operators must provide valid bounds

Approved limits (unchanged from V2-2AA design):

| Bound | Approved limit |
|---|---|
| `max_events` | ≤ 5 |
| `duration_seconds` | ≤ 30.0 |
| `connect_timeout_seconds` | ≤ 10.0 |
| Reconnects | 0 (not a parameter) |

---

## 6. Tests / Checks Run

### Focused test suites

| Command | Result |
|---|---|
| `python -m pytest tests/test_v2_2ab_pumpportal_live_transport.py tests/test_post_rc_pumpportal_discovery_adapter.py tests/test_v2_2x2_t2_token_age_evidence.py -v` | **166 passed** in 119.00s |

### New V2-2AC tests added

**`TestWebsocketsDependencyDeclaration`** (2 tests):
- `test_websockets_declared_in_pyproject_dependencies` — parses pyproject.toml, asserts "websockets" in dependencies list
- `test_websockets_minimum_version_specified` — asserts `websockets>=<digit>` pattern present

**`TestBoundHardening`** (6 tests):
- `test_max_events_above_limit_raises_value_error` — `max_events=6` raises ValueError
- `test_duration_above_limit_raises_value_error` — `duration_seconds=31.0` raises ValueError
- `test_connect_timeout_above_limit_raises_value_error` — `connect_timeout_seconds=11.0` raises ValueError
- `test_bound_error_raised_before_websockets_import` — ValueError fires even with websockets=None in sys.modules
- `test_exact_defaults_are_accepted` — all three defaults pass without error
- `test_below_default_max_events_accepted` — `max_events=4` passes

### Git checks
- `git diff --check`: passed (LF→CRLF warnings only, no whitespace errors)
- `git status --short`: 4 modified files (M), no unintended files staged
- `git diff --stat`: 4 files, 98 insertions, 7 deletions
- `git diff --name-only`: `pyproject.toml`, `src/printer_v1/sources/pumpportal.py`, `tests/test_post_rc_pumpportal_discovery_adapter.py`, `tests/test_v2_2ab_pumpportal_live_transport.py`

---

## 7. Safety Confirmations

- **No live network calls** — all transport tests use `patch.dict(sys.modules, ...)` with fake websockets
- **No new dependencies beyond `websockets>=12.0`** — pyproject.toml adds only the one required package
- **T2 safety rules preserved** — 82 T2 tests pass unchanged
- **`enabled_by_default = False`** — verified by test
- **No BUY/SELL/HOLD, positions, trades, paper decisions** — not touched
- **`pumpfun_migration_stream` stays NOT_READY** — verified by plan catalog test
- **V2-3 remains paused** — no retrieval, no memory generation, no scoring
- **Source Governor path required** — unchanged
- **No memory, retrieval, paper, trading, scheduler/runtime, PumpSwap, migrations, parser, or selection code touched**
- **`asyncio.run()` used** — no lingering threads
- **Bound validation is pure rejection** — no clamping, no silent truncation

---

## 8. Remaining Blockers

### Blocker 1 (Expected — installation not run)
`websockets` is declared in `pyproject.toml` but not installed in the Python 3.12 pytest environment. Users doing `pip install -e .` will get websockets installed. The test environment does not reflect the installed state. A future lane can verify importability after installation, or this can be treated as an operator setup step.

### Blocker 2 (Deferred — live proof scope)
No live WebSocket proof was run in this lane (per lane instructions). Transport correctness is verified via mock fixture only. A bounded live proof against `wss://pumpportal.fun/api/data` is deferred to a future lane.

### Blocker 3 (Intentional — migration)
`pumpfun_migration_stream` remains `NOT_READY`. No live migration transport exists.

---

## 9. V2-3 Status

**V2-3 remains PAUSED.**

No retrieval, no memory generation, no scheduling, no scoring, no paper decisions, no BUY/SELL/HOLD were introduced or enabled in this lane.

---

## 10. Exact Next Recommended Lane

**V2-2AD: Bounded Live PumpPortal Smoke Proof**

Scope:
1. Install websockets in the operator's active Python environment (or confirm it is installed)
2. Run a single bounded live proof: `build_pumpportal_live_transport()` with defaults → connect → collect ≤ 5 events → disconnect
3. Verify no DB rows written downstream (no memory, no paper)
4. Verdict: `LIVE_TRANSPORT_SMOKE_PASS` or `LIVE_TRANSPORT_SMOKE_PARTIAL` (if events = 0 due to empty stream)

Pre-conditions for V2-2AD:
- `websockets` must be installed in the active Python environment
- Operator approval required (live source call)
- No paper decisions, memory, or retrieval may occur

---

## 11. Commit

All changes committed under:

```
Add V2-2AC PumpPortal websockets dependency gate
```
