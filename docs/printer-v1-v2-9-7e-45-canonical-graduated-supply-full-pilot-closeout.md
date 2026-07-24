# Printer V1 — V2-9.7E.45 Canonical Graduated Supply, Activation and Full-Pilot Closeout

**Verdict: `V2_9_7E_45_OPERATOR_DECISION_REQUIRED`.**

The canonical durable-supply, mixed-discovery-locator, holder-aware reserve
selection, **graduation-native atomic activation** and immutable
`PILOT_INPUT_READY` boundary repairs are implemented and proven offline, and the
repaired supply path was proven **live end-to-end** to a real mixed
`LATEST + PERSISTED` `$3K+` cohort (`GRADUATED_SUPPLY_READY`). The remaining steps
to a full PASS — chaining live holder evidence + the readiness-bundle write into a
single live `PILOT_INPUT_READY`, and the sustained two-token
`15m → 1h → 4h` `FULL_PILOT` — require a continuously-supervised real-wall-clock
session (≥ 4 h) that this execution environment cannot provide in one sitting. Full
PASS is **not** claimed from readiness/supply alone. V2-9.7E remains active.

- **Starting commit:** `81c69d0` (`Close continuous two-token full pilot proof`).
- **Ending commit:** `<this closeout commit>`.

## Logical implementation commits

| Commit | Repair | Contents |
|---|---|---|
| `e8fdeed` | Design + Repair 5 | Typed `GRADUATION_NATIVE` atomic activation route in the executor; design freeze. |
| `81d2ba6` | Repair 1 | Canonical graduated-registry bootstrap importer + immutable isolated-attempt export. |
| `cf65b4a` | Repair 6 | Migration 041 + immutable `PILOT_INPUT_READY` boundary owner. |
| `57dcfdb` | Repair 4 | Holder-aware reserve selection funnel with lawful replacement. |
| `6544d44` | Repair 2C | DexScreener fresh-profiles locator wired into the supply planner. |
| `<this>` | Closeout | Live readiness evidence, closeout, blocker register, E.44 distinction, memory. |

## Canonical registry ownership and bootstrap result

The single canonical owner is `printer_pumpswap_graduated_candidate_registry`
(migration 040). An exhaustive scan of `data/`, `artifacts/`, `operator-runs/` and
the scratchpad found **no** surviving DB containing that table at lane start
(E.42/E.43/E.44 live proofs used scratchpad isolated DBs that did not survive).
Therefore the registry was populated through **bounded live migration cycles**
(no fabricated persisted history). `bootstrap_from_prior_registry` is implemented
and proved offline against a synthetic prior-registry DB (exact mint/signature/pool,
evidence-hash recomputation, source-policy compatibility, integrity + FK checks,
fail-closed abort on any forbidden campaign/lifecycle/memory column), and is ready
for any future retained artifact. `export_isolated_attempt_registry` produces a
deterministic, replayable, candidate-only immutable export (export identity +
provenance hash) into a fresh isolated attempt DB.

## What each repair changed

* **Repair 1 (durable supply).** `sources/graduated_registry_bootstrap.py` — bounded
  governed bootstrap importer + deterministic isolated-attempt export. Reuses the
  registry's export/import; no second registry; no campaign/lifecycle/memory crossing.
* **Repair 2 (mixed discovery planner).** 2B (multi-round bounded migration
  discovery) and 2A/refresh of the persisted registry through the exact-pool path are
  pre-existing (E.42/E.43) and preserved. **2C (new):**
  `graduated_supply_front_door.run_fresh_profile_locator` wires the keyless
  `dexscreener_fresh_profiles` request as a **locator only** — a surfaced mint
  proceeds only when it matches an exact confirmed graduated-registry row, else it is
  retained `LOCATOR_ONLY_NO_GRADUATION_PROOF`; ordering/rank/boost/popularity are
  discarded; DexScreener never establishes graduation.
* **Repair 3 (exact front door + truthful partitions).** Preserved verbatim from
  E.43 (`$3,000` exact-pool floor; fail-closed missing/stale/wrong-pool; truthful
  `LATEST_GRADUATED` / `PERSISTED_GRADUATED`; no pre-snapshot behavioural categories).
* **Repair 4 (holder-aware reserve selection).**
  `graduated_liquidity_front_door.select_holder_eligible_pair` — deterministic
  seeded-uniform ordered queue per partition; round-robin holder evaluation within a
  frozen total operation cap; replacement within the same partition on
  failure/unknown; stops at one holder-eligible per partition; no second chance for a
  rejected identity; no holder result becomes a score/rank/weight.
* **Repair 5 (graduation-native activation — lane centrepiece).** Typed
  `origin_route` on `FixtureOriginProof`/`_Observation`/`_Merged`; the executor's
  `_run_direct_lane` routes `GRADUATION_NATIVE` candidates through a new block that
  records the Pump **migration lineage** (migration signature + graduation
  slot/block time) as migration evidence, **never** writes or fabricates a Pump
  create-origin row, and produces token/pair/queue/scheduler/slot identities
  identical to the create route. Create-native activation (Route A) is unchanged.
  Activation stays two-or-none.
* **Repair 6 (readiness boundary).** Migration 041
  `printer_pilot_input_readiness_bundle` + `operator_cli/pilot_input_readiness.py`
  — one immutable `PILOT_INPUT_READY` bundle written only when DISCOVERY + SELECTION
  + MARKET + HOLDER + ACTIVATION are simultaneously satisfied; fail-closed per gate;
  immutable (idempotent same-hash; conflicting rewrite rejected); carries readiness
  inputs only.

## Offline proof

| Suite | Tests | Result |
|---|---|---|
| `test_v2_9_7e_45_graduation_native_activation.py` | 6 | PASS |
| `test_v2_9_7e_45_graduated_registry_bootstrap.py` | 6 | PASS |
| `test_v2_9_7e_45_pilot_input_readiness.py` | 6 | PASS |
| `test_v2_9_7e_45_holder_reserve_funnel.py` | 6 | PASS |
| `test_v2_9_7e_45_fresh_profile_locator.py` | 4 | PASS |
| **E.45 total** | **28** | **PASS** |
| Regressions: E.42 / E.43 / E.44 | 60 | PASS |
| Regressions: combined-executor / atomic-handoff / graduation-only / origin-to-lifecycle | 47 | PASS |
| Full-suite `--collect-only` (import sanity) | 8283 collected | no import breakage |

Proven offline: graduation-native two-candidate atomic activation with no create row
and no fabricated create fields; create-origin activation unchanged; one-valid /
one-invalid → neither; deterministic zero-source selection; durable-supply import
exactly once + fail-closed on tamper/forbidden columns + deterministic isolated
export + genuine persisted cohort; holder replacement / stop / no-second-chance /
cap; `$2,999.99` fails and `$3,000.00` passes; fresh profiles remain locator-only;
readiness bundle immutable + fail-closed per gate.

## Live readiness proof (canonical path)

`lane-x-v2-9-7e-45-bounded-live-supply-readiness-output.txt`. Fresh isolated DB;
live PumpPortal `subscribeMigration` → governed on-chain graduation verification →
durable registry → E.43 exact-pool `$3K` front door → mixed two-slot selection.
Ceilings: 2 rounds, ≤5 events / 100 s per round, 6 s settle, single transient reverify.

* **Reachability probe:** WebSocket reachable; 55 s window, 0 events (bursty/quiet —
  the stream is live but sparse).
* **Cycle 1 (fresh DB):** 2 live migrations confirmed graduated
  (`sJt3RRBK…pump`, `Z95okeyh…pump`), both `$3K+` on exact PumpSwap pools; 0 persisted
  → honest `BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL` (no persisted cohort on a
  fresh DB). integrity ok, FK 0, forbidden deltas 0.
* **Cycle 2 (same DB):** the cycle-1 confirmations are now PERSISTED; 2 new live
  migrations arrive as LATEST. `ready=True`, `GRADUATED_SUPPLY_READY`:
  * selected LATEST `aPij1aZg…pump` (confirmed this cycle);
  * selected PERSISTED `Z95okeyh…pump` (confirmed cycle 1, still `$3K+`);
  * `below_floor 1` — a prior-cycle pool decayed below `$3,000` and was correctly
    excluded (positive fail-closed evidence);
  * discovery + front-door forbidden-delta totals `0`; integrity ok; FK 0.

This is a **live** demonstration of `DISCOVERY_READY + SELECTION_READY + MARKET_READY`
through the canonical repaired path — one real LATEST + one real PERSISTED graduated
candidate on exact confirmed PumpSwap pools `$3K+`, selected as a lawful mixed pair.
A quiet migration window did **not** erase the previously-confirmed graduated
universe. This directly resolves the core architectural complaint.

## Source-operation accounting

Discovery/front-door governed operations only: PumpPortal `subscribeMigration`
(1 keyless request per round), governed Solana RPC `getTransaction`/pool references
for verification, DexScreener exact-pool `pair_market_snapshot` per refreshed
candidate, one keyless `dexscreener_fresh_profiles` locator. No paid RPC, no endpoint
rotation, no provider racing, no retry-until-success. Holder candidate-cap arithmetic
(GoPlus + fixed public RPC + fixed Helius Free backup + verification + enrichment +
lifecycle reservation) is enforced by the holder reserve funnel cap and is printed
and persisted before authorization consumption; it was not consumed live this session
(holder chaining deferred to the supervised session).

## What is NOT done (requires a supervised real-wall-clock session)

* Live `HOLDER_READY` chaining on the selected pair (proven offline).
* Live graduation-native `ACTIVATION_READY` on the selected pair (proven offline).
* Live immutable `PILOT_INPUT_READY` bundle write (proven offline).
* Sustained two-token `FULL_PILOT` `15m → 1h → 4h` (≥ 4 h continuous foreground
  supervision) — a hard environment duration limit. **Not attempted; NOT PASS.**

## Money-usefulness contribution

Removes the architectural reason Printer starved for graduated candidates: the
persisted cohort is no longer artificially empty (durable registry + isolated
export), a quiet window no longer hides the confirmed universe, migration-discovered
graduates can now **activate** lawfully (graduation-native route) instead of stalling
at a pre-lifecycle boundary, and the holder funnel no longer abandons the pilot on a
single holder miss. The `$3,000` floor proves tracking admission only — not route,
entry, exit, slippage or price-impact realism.

## What it still does not unlock

No live trading, wallet, keys, funds; no paid API; no scoring/ranking/confidence/
weighting; no retrieval/decision/position/trade/audit/PnL; no BUY/SELL/HOLD. The
sustained lifecycle, memory promotion, continuation and clean/dirty/blocked audit
are not exercised this session.

## Functionality Risks / Setbacks / Efficiency Blockers

* **Functionality risk:** the full `run_operational` (non-`stop_before_lifecycle`)
  path now feeds graduation-native candidates to the driver for real activation; the
  executor mechanism is offline-proven, but the end-to-end driver→lifecycle chain on
  graduation-native candidates is exercised only in a live pilot (deferred).
* **Setback:** live migration supply is bursty/sparse (0 in a 55 s window); a mixed
  cohort required 2 rounds and a same-DB persisted carry-over.
* **Efficiency blocker:** the sustained `15m → 1h → 4h` pilot cannot run within an
  interactive session; it needs a dedicated supervised real-wall-clock run.

## Roadmap

V2-9.7E remains **active**. The first unresolved blocker is preserved: the sustained
supervised two-token `FULL_PILOT` (and the live holder/activation/bundle chaining
that precedes it) has not been executed. **Do not start V2-9.7F.** The roadmap is not
advanced. All permanent V1 locks preserved.
