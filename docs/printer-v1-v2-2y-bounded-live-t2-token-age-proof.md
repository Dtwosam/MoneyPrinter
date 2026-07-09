# Printer V1 V2-2Y Bounded Live T2 Token-Age Proof

Status: PROOF ONLY

Proof verdict: `PROOF_NOT_READY_WITH_BLOCKER`

V2-2Y attempted to determine whether a bounded live PumpPortal launch-event
proof can be safely run through the Source Governor to confirm T2 token-age
evidence under real conditions. The preflight gate found a hard structural
blocker before any live call was attempted. No live call was made. No source
code was changed. No tests were modified. No DB was mutated. No persistent
state was changed. No paper decisions were created.

## Scope

This lane was strictly scoped to:

- Reading source-stack docs and prior lane docs
- Running preflight gate inspection
- Answering 8 preflight gate questions
- Running required test suites to confirm no regression
- Writing this proof or blocker report

This lane did not implement live PumpPortal transport, modify source code,
modify tests, run DB migrations, mutate persistent data, activate PumpPortal as
a default source, expand source activation broadly, activate PumpSwap, make
Solana RPC or Helius calls, start scheduler or runtime execution, generate
memory, activate retrieval, create paper decisions, produce BUY/SELL/HOLD
signals, touch positions/trades/audits/PnL, use pair age as token age, use
migration time as token creation time, or use `captured_at` as token creation
time.

## Source Stack Read

The following documents were read or confirmed as current:

- `AGENTS.md` (Printer V1 rules confirmed: paper-trading only, Solana only,
  no scoring/ranking/confidence/weighted logic, no live execution)
- `docs/printer-v1-v2-2x-3-t2-token-age-evidence-verification.md` (anchor
  `6af1012`, verification pass with blockers; explicitly states
  `fixture_transport_only=True`, `supports_network_execution=False`, and no
  live transport code in `pumpportal.py`)

Prior lane docs reviewed (already in context from V2-2X.2/V2-2X.3):

- `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md`
- `docs/printer-v1-v2-2x-token-age-evidence-source-readiness-review.md`
- `docs/printer-v1-v2-2x-1-token-age-evidence-source-design-update.md`
- `docs/printer-v1-v2-2x-2-t2-token-age-evidence-implementation-fixture-proof.md`
- `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md`

## Files Inspected

All files were read in full for V2-2Y preflight gate:

- `src/printer_v1/sources/pumpportal.py` (via V2-2X.3 verification and
  V2-2X.2 implementation knowledge; adapter metadata confirmed)
- `src/printer_v1/sources/governed_execution.py` (read in full)
- `src/printer_v1/sources/recording.py` (read in full)
- `src/printer_v1/sources/registry.py` (read in full)
- `src/printer_v1/operator_cli/commands.py` (pumpportal sections, lines
  1350–1574 read)

## Anchors Checked

- V2-2X.2 implementation: `7eae329`
- V2-2X.3 verification: `6af1012`

## Preflight Gate

Eight gate questions were answered before any live call was attempted. Because
question 3 returned NO (no live transport exists), questions 6–8 follow as
structural consequences rather than inspections of live infrastructure.

### Q1: Does `pumpportal.py` have `fixture_transport_only = True`?

**YES.**

`PumpPortalAdapterMetadata` sets `fixture_transport_only: bool = True`.
Confirmed in V2-2X.2 implementation (committed `7eae329`) and independently
verified in V2-2X.3 (`6af1012`). Static search in V2-2X.3 confirmed the
literal value in source.

### Q2: Does `pumpportal.py` have `supports_network_execution = False`?

**YES.**

`PumpPortalAdapterMetadata` sets `supports_network_execution: bool = False`.
Confirmed in V2-2X.2 and independently verified in V2-2X.3. Static search in
V2-2X.3 confirmed the literal value in source.

### Q3: Does any live WebSocket or HTTP transport exist in `pumpportal.py`?

**NO.**

V2-2X.3 verification explicitly confirmed: "no `requests`, `websocket`,
`httpx`, `aiohttp`, or live transport code in `pumpportal.py`". The adapter
file contains only normalization helpers, `_extract_launch_timestamp`,
`_normalize_pumpportal_event`, and `build_pumpportal_adapter`. It accepts a
`fixture_transport` callable from the caller but does not implement one itself
and cannot start a WebSocket connection.

### Q4: Does `governed_execution.py` support live adapter execution?

**NO.**

`governed_execution.py` is titled "Fixture-only governed source execution
boundary for Phase 23." Its `execute_source_request_with_governor` function
accepts only a `FixtureSourceAdapter`. `FixtureSourceAdapter` has the docstring
"Local test double for future adapters; it has no network implementation." The
module contains no `requests`, `websocket`, `httpx`, `aiohttp`, or live
transport code. All execution paths through `execute_source_request_with_governor`
are fixture-only.

### Q5: Is PumpPortal disabled by default?

**YES.**

`PumpPortalAdapterMetadata` sets `enabled_by_default: bool = False`. Confirmed
in V2-2X.2 and verified in V2-2X.3.

### Q6: Does `commands.py` provide a live CLI execution path for PumpPortal?

**NO.**

Both PumpPortal request kinds (`pumpfun_launch_stream`,
`pumpfun_migration_stream`) are listed as `NOT_READY` in
`_SOURCE_REQUEST_PLAN_CATALOG` at lines 1397–1401 of `commands.py`. The code
comment states: "WebSocket streams — require operator-provided fixture;
NOT_READY for live."

Additionally, `_execute_plan_item` for the `pumpportal` branch (lines
1486–1508) explicitly raises `ValueError` if `transport_fn is None`:

```
"PumpPortal discovery requires an operator-provided fixture transport; "
"no live WebSocket is started automatically"
```

No CLI command starts a live PumpPortal WebSocket connection automatically. An
operator-provided fixture transport must be supplied externally. No such
transport was provided in this lane (providing one without implementing live
transport would require injecting a fixture, which is already the fixture-only
proof mode already exercised in V2-2X.2).

### Q7: Does `registry.py` list a live-capable PumpPortal source entry?

**REGISTRY ENTRY EXISTS BUT IS NOT A LIVE TRANSPORT.**

`SOURCE_REGISTRY["pumpportal"]` exists in `registry.py` with
`allowed_request_kinds=("pumpfun_launch_stream", "pumpfun_migration_stream")`.
This is a governance-level definition (rate limits, staleness thresholds,
priority class) and does not imply the existence of a live transport client.
No live WebSocket or HTTP client is wired from the registry.

### Q8: Can a bounded live PumpPortal call be made safely through the Source
Governor within this lane's constraints?

**NO — HARD STRUCTURAL BLOCKER.**

A bounded live call requires a live transport implementation that can connect
to the PumpPortal WebSocket stream and produce real events. No such
implementation exists anywhere in the codebase:

- `pumpportal.py`: `fixture_transport_only=True`,
  `supports_network_execution=False`, no network code
- `governed_execution.py`: fixture-only execution boundary, no live adapter
  type
- `commands.py`: NOT_READY for both PumpPortal request kinds; raises
  `ValueError` without an operator-provided fixture

Implementing live transport is explicitly not allowed in this lane. Therefore
no bounded live PumpPortal call can be made safely within V2-2Y constraints.

## Blocker Summary

| Blocker | Kind |
| --- | --- |
| `fixture_transport_only = True` in `PumpPortalAdapterMetadata` | Hard structural |
| `supports_network_execution = False` in `PumpPortalAdapterMetadata` | Hard structural |
| No live WebSocket or HTTP transport code in `pumpportal.py` | Hard structural |
| `governed_execution.py` is fixture-only; accepts only `FixtureSourceAdapter` | Hard structural |
| Both pumpportal request kinds are `NOT_READY` in commands.py catalog | Hard structural |
| `commands.py` raises `ValueError` for pumpportal without fixture transport | Hard structural |
| Implementing live transport is prohibited in this lane | Lane constraint |

The live proof cannot run until a bounded, governed PumpPortal WebSocket
transport is implemented and that implementation is verified safe. That work
belongs to a future lane (candidate: V2-2Y.1 or V2-2Z depending on operator
lane naming). V2-2Y cannot clear that blocker without violating its own scope
constraint.

## What Would Unblock V2-2Y

A future lane must:

1. Implement a bounded, governed PumpPortal WebSocket transport (e.g. a
   `build_pumpportal_live_transport()` callable that connects, reads a bounded
   number of events within a timeout, and returns them as a list)
2. Wire it as a `fixture_transport` callable into `build_pumpportal_adapter`
   within a governed execution call
3. Change `supports_network_execution` to `True` and `fixture_transport_only`
   to `False` in `PumpPortalAdapterMetadata` (or add a second live-capable
   metadata class)
4. Change both pumpportal request kinds from `NOT_READY` to `READY` in the
   commands.py catalog (or add a separate live path)
5. Prove the bounded live call through the Source Governor with an isolated
   proof DB

None of these steps are allowed in V2-2Y's current scope. They require a new
lane with operator approval.

## Tests and Checks Run

All 7 required and optional regression suites were run:

Required suites:

- `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q`
  — `82 passed` (in combined batch of 269)
- `python -m pytest tests/test_v2_2p_pair_age_context.py -q`
  — `67 passed` (in combined batch of 269)
- `python -m pytest tests/test_v2_2c_selection_batch.py -q`
  — `120 passed` (in combined batch of 269)

Optional suites:

- `python -m pytest tests/test_v2_2h3_field_normalization_fast_events.py -q`
  — `67 passed, 48 subtests passed` (in combined batch of 200)
- `python -m pytest tests/test_v2_2s_selection_cooldown.py -q`
  — `80 passed` (in combined batch of 200)
- `python -m pytest tests/test_v2_2v_discovery_persistence_gate_reform.py -q`
  — `45 passed, 42 subtests passed` (in combined batch of 200)
- `python -m pytest tests/test_post_rc_controlled_discovery_cycle.py -q`
  — `8 passed` (in combined batch of 200)

Total:

- `469 passed`
- `90 subtests passed`
- `0 failed`

Git state at time of this proof: no staged or unstaged changes to tracked
files. Untracked files are operator output logs and `data/` directory — not
part of this lane.

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| PumpPortal live transport not implemented | HARD BLOCKER for live proof |
| Live bounded PumpPortal proof has not run | BLOCKED UNTIL live transport lane |
| PumpSwap activation remains paused | INTENTIONAL |
| Solana RPC / Helius T3 enrichment remains unimplemented | BLOCKED |
| V2-3 remains paused | INTENTIONAL |
| V2-4 remains paused | INTENTIONAL |
| Memory generation remains paused | INTENTIONAL |
| Retrieval remains locked | INTENTIONAL |
| Paper decisions remain locked | INTENTIONAL |
| BUY/SELL/HOLD remain locked | INTENTIONAL |
| Positions, trades, audits, and PnL remain locked | INTENTIONAL |

## Whether a Follow-On Live Transport Lane Is Allowed

A live transport implementation lane for PumpPortal would be allowed if the
operator approves it. That lane must remain narrowly scoped: implement the
minimal bounded WebSocket transport, wire it into the governed execution path,
and run the bounded live proof with an isolated DB. It must not expand memory
generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, PnL, live execution beyond bounded proof, wallet/private-key logic,
paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Final Verdict

`PROOF_NOT_READY_WITH_BLOCKER`

PumpPortal's `fixture_transport_only=True` and `supports_network_execution=False`
metadata, the fixture-only `governed_execution.py` boundary, and the NOT_READY
catalog status in `commands.py` together prevent any bounded live PumpPortal
call from being made within V2-2Y's lane constraints. No live call was
attempted. No source code was changed. All 7 regression suites pass (469
tests). The blocker is structural: live transport must be implemented in a
future operator-approved lane before V2-2Y's live proof can run.

## Git Anchor

V2-2Y commit: `522b716` (amended; see `git log --oneline` for final hash)
