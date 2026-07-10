# Printer V1 V2-2AB.1 PumpPortal Transport Verification

Status: VERIFICATION ONLY

Verification verdict: `VERIFICATION_PARTIAL_WITH_BLOCKER`

Target commit verified:

`45dfb2c Implement V2-2AB minimal PumpPortal live transport`

This lane independently verified the partial PumpPortal launch-stream transport
implementation. It did not implement code, edit tests, add dependencies, add
migrations, mutate the persistent DB, run source fetching, call PumpPortal live,
start scheduler/runtime, generate memory, activate retrieval, create paper
decisions, unlock BUY/SELL/HOLD, create positions, create trades, create paper
audits, or create PnL.

V2-3, V2-4, PumpSwap, broad source expansion, runtime/scheduler, memory
generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, and PnL remain paused.

## Source Stack Read

Required source documents checked:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2aa-minimal-pumpportal-launch-transport-design.md`
- `docs/printer-v1-v2-2ab-minimal-pumpportal-live-transport-implementation-proof.md`

Current anchors:

- V2-2AA design: `447e3fc`
- V2-2AB implementation: `45dfb2c`

## Target Commit Scope

`git show --name-only --oneline --no-renames 45dfb2c` confirmed the target
commit changed only the expected V2-2AB files:

- `docs/printer-v1-v2-2ab-minimal-pumpportal-live-transport-implementation-proof.md`
- `src/printer_v1/operator_cli/commands.py`
- `src/printer_v1/sources/governed_execution.py`
- `src/printer_v1/sources/pumpportal.py`
- `tests/test_post_rc_pumpportal_discovery_adapter.py`
- `tests/test_v2_2ab_pumpportal_live_transport.py`
- `tests/test_v2_2x2_t2_token_age_evidence.py`

No memory, retrieval, paper-decision, paper-position, trade, audit, PnL, wallet,
private-key, migration, or scheduler/runtime files were changed by the target
commit.

## Files Inspected

Inspection was limited to the requested files:

- `src/printer_v1/sources/pumpportal.py`
- `src/printer_v1/sources/governed_execution.py`
- `src/printer_v1/operator_cli/commands.py`
- `tests/test_v2_2ab_pumpportal_live_transport.py`
- `tests/test_post_rc_pumpportal_discovery_adapter.py`
- `tests/test_v2_2x2_t2_token_age_evidence.py`
- `pyproject.toml`

## Dependency State

Declared project dependency state:

- `pyproject.toml` has `dependencies = []`.
- `rg -n "websockets|websocket-client" pyproject.toml` found no declared
  `websockets` or `websocket-client` dependency.

Runtime environment dependency state:

- `python -c "import importlib.util; ... find_spec('websockets')"` reported
  `websockets_importable=True`.
- Import origin:
  `C:\Users\dtwof\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\websockets\__init__.py`

Verification finding:

`websockets` is absent from project dependencies but present in the current
global Python environment. This makes the missing-dependency safety behavior
environment-dependent.

## READY / Status Safety Assessment

Status findings:

| Item | Verification result |
| --- | --- |
| `pumpfun_launch_stream` in plan catalog | `READY` |
| `pumpfun_migration_stream` in plan catalog | `NOT_READY` |
| `enabled_by_default` | `False` |
| `supports_network_execution` | `True` |
| `fixture_transport_only` | `False` |
| Source Governor path | still required |

Assessment:

`pumpfun_launch_stream = READY` is not fully safe to leave unqualified before a
dependency lane, because the current environment can import `websockets` even
though the project does not declare it. The implementation proof expected the
missing dependency to force a clear failure. That failure still occurs in an
environment where `websockets` is truly absent, but it does not occur in this
current environment.

Mitigating factors:

- The adapter remains disabled by default.
- The CLI still requires the existing governed/operator-approved discovery
  command path.
- No live source call was run in this verification lane.
- `pumpfun_migration_stream` remains `NOT_READY`.

Blocking concern:

The dependency lane should either declare `websockets` explicitly or the
PumpPortal READY path should include a deterministic project-dependency gate.
Relying on ambient site-packages makes the partial state less predictable.

## Transport Bounds Verification

`src/printer_v1/sources/pumpportal.py` defines:

| Bound | Value |
| --- | ---: |
| `_PUMPPORTAL_MAX_EVENTS_DEFAULT` | 5 |
| `_PUMPPORTAL_DURATION_SECONDS_DEFAULT` | 30.0 |
| `_PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT` | 10.0 |

`build_pumpportal_live_transport()`:

- Lazily imports `websockets`.
- Raises `RuntimeError` when `websockets` cannot be imported.
- Uses `asyncio.timeout(connect_timeout_seconds)` for the initial WebSocket
  connection.
- Sends only `{"method": "subscribeNewToken"}`.
- Reads events until `len(events) < max_events` fails or duration expires.
- Returns only dict events.
- Closes the websocket in `finally`.
- Uses `asyncio.run()` for synchronous bounded execution.
- Does not create a reconnect loop.
- Does not start a background thread.
- Does not create scheduler jobs.
- Does not write to the DB directly.

Bound nuance:

The default bounds are correct: 5 events, 30 seconds, 10-second connect timeout.
The builder accepts override arguments (`max_events`, `duration_seconds`,
`connect_timeout_seconds`) and does not clamp them internally. The current CLI
uses defaults, so no CLI-exposed unbounded option was found in this inspection,
but the transport function itself can be called by tests or future code with a
higher `max_events` value. This should be documented or clamped in the
dependency/proof lane if the operator wants a hard invariant independent of
caller discipline.

## CLI Missing-Dependency Behavior

Expected behavior from V2-2AB proof:

- Missing `websockets` -> `build_pumpportal_live_transport()` raises
  `RuntimeError`.
- CLI catches that and raises operator-facing `ValueError`.

Code inspection:

- `commands.py` wraps `RuntimeError` from `build_pumpportal_live_transport()`
  as `ValueError("PumpPortal live transport unavailable: ...")`.

Test result:

- `tests/test_post_rc_pumpportal_discovery_adapter.py` failed
  `PumpPortalCLIDiscoveryTests.test_no_transport_raises_for_pumpportal`.
- Expected: `ValueError`.
- Actual: no `ValueError` raised.

Likely cause:

The current Python environment has an importable `websockets` package even
though `pyproject.toml` does not declare it. The builder therefore succeeds
instead of raising `RuntimeError`, so the CLI no longer reaches the missing
dependency wrapper in this environment.

This is the primary blocker found by V2-2AB.1.

## Source Governor Compatibility

Confirmed:

- `governed_execution.py` widens the adapter annotation to
  `FixtureSourceAdapter | PumpPortalAdapter` under a `TYPE_CHECKING` import.
- Runtime behavior of `execute_source_request_with_governor()` remains the
  existing governed path.
- Request, response, and failure recording are still handled by the Source
  Governor execution function.
- PumpPortal adapter still validates Source Governor context before execution.
- No direct source fetching was run in this verification lane.

## T2 Safety Confirmation

T2 token-age tests passed:

- Only `pumpfun_launch_stream` events can produce `token_created_at`.
- Migration events remain blocked from T2.
- `captured_at` is not used as `token_created_at`.
- Timestamp priority remains `tokenCreatedAt` -> `createdTimestamp` ->
  `timestamp`.
- Stale and future timestamps remain rejected.
- A3 behavior with and without T2 evidence remains covered by the focused suite.

## Tests and Checks Run

Focused tests:

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_v2_2ab_pumpportal_live_transport.py -q` | PASS: 35 passed, 1 warning |
| `python -m pytest tests/test_post_rc_pumpportal_discovery_adapter.py -q` | FAIL: 1 failed, 40 passed, 2 warnings |
| `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q` | PASS: 82 passed, 1 warning |

Failed test:

`tests/test_post_rc_pumpportal_discovery_adapter.py::PumpPortalCLIDiscoveryTests::test_no_transport_raises_for_pumpportal`

Failure detail:

- Expected `ValueError`.
- Actual no `ValueError` raised.

Additional checks:

- `python -c "import importlib.util; ... find_spec('websockets')"`:
  `websockets_importable=True`
- `rg -n "websockets|websocket-client" pyproject.toml`: no matches
- `git diff --check`: passed

Warnings:

- Pytest cache warnings were observed for `.pytest_cache` path creation.
- Harness printed default local `gltest` configuration messages.

## Risks Found

| Risk | Severity | Notes |
| --- | --- | --- |
| Ambient `websockets` importable despite undeclared project dependency | High | Makes missing-dependency failure environment-dependent |
| `pumpfun_launch_stream = READY` before dependency is declared | Medium/High | Safe only if operator/governed path is respected; no deterministic dependency gate |
| CLI missing-dependency regression failed | High | Focused regression expected `ValueError`, actual no error |
| Transport bounds are defaults, not hard clamps | Medium | CLI uses defaults, but builder can be called with larger values |
| No live proof yet | Expected blocker | Live proof must wait for dependency/governed proof lane |

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| `websockets` absent from project dependencies | BLOCKER |
| `websockets` present in ambient environment, undermining missing-dependency proof | BLOCKER |
| PumpPortal CLI missing-dependency regression failed | BLOCKER |
| No live PumpPortal proof run | BLOCKED until dependency/gate lane |
| PumpSwap remains paused | Intentional |
| PumpPortal migration stream remains `NOT_READY` | Intentional |
| V2-3 remains paused | Intentional |

## Safety Confirmations

Confirmed:

- Verification-only lane.
- No implementation changes.
- No source code changed.
- No tests changed.
- No migrations added.
- No DB mutation by this lane.
- No live source fetching run by this lane.
- No direct API call outside Source Governor.
- No scheduler/runtime execution.
- No memory generation.
- No retrieval activation.
- No paper decisions.
- No BUY/SELL/HOLD unlock.
- No paper positions.
- No trades.
- No paper audits.
- No PnL.
- No wallet/private-key/signing/live execution logic.
- No paid API dependency added.
- No scoring/ranking/confidence/weighted logic added.
- No embeddings or vectors added.
- `pumpfun_migration_stream` remains `NOT_READY`.
- T2 safety focused suite passed.

## Final Verdict

`VERIFICATION_PARTIAL_WITH_BLOCKER`

V2-2AB changed only the intended files and preserved Source Governor, T2,
memory, retrieval, paper, trading, and financial locks. The transport is
bounded by default, uses lazy import, has no reconnect loop, and does not start
background scheduler/runtime work.

However, this verification found a real blocker: `websockets` is not declared
in `pyproject.toml`, but it is importable in the current Python environment.
That means the expected missing-dependency `RuntimeError` and CLI `ValueError`
are not guaranteed. The focused PumpPortal adapter regression failed because no
`ValueError` was raised when no explicit transport was supplied.

## Exact Next Recommended Lane

`V2-2AC - PumpPortal websockets Dependency and Deterministic Availability Gate`

Required purpose:

- Add or explicitly gate the `websockets` dependency in a dedicated lane.
- Make PumpPortal live transport availability deterministic from project
  dependencies, not ambient global site-packages.
- Decide whether `pumpfun_launch_stream` should remain `READY` before the
  dependency/proof lane or be downgraded/gated until dependency proof passes.
- Add/adjust focused tests so CLI missing-dependency behavior is deterministic.
- Preserve all locks: no memory generation, no retrieval, no paper decisions,
  no BUY/SELL/HOLD, no positions, no trades, no audits, no PnL.

V2-3 remains paused.
