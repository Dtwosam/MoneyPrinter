# Printer V1 — V2-9.7E.45 Canonical Graduated Supply, Selection, Activation and Full-Pilot Design

Frozen micro-design for lane **V2-9.7E.45 — Canonical Graduated Supply, Selection,
Activation, and Full-Pilot Closure**.

Starting commit: `81c69d0` (`Close continuous two-token full pilot proof`).

This lane eliminates the architectural reasons Printer repeatedly reports
insufficient graduated candidates even though lawful `$3K+` PumpSwap markets
exist, and converts the E.44 pre-lifecycle boundary (`stop_before_lifecycle`)
into a lawful **graduation-native atomic activation** that a sustained two-token
`FULL_PILOT` can consume.

It reuses the existing owners verbatim. It creates **no** parallel runner,
registry, selector, holder path, source loop, scheduler or lifecycle owner. It
adds no paid RPC dependency, no arbitrary free RPC endpoints, no endpoint
rotation, provider racing or hidden retries.

---

## 0. Owner map (confirmed by inspection, no duplication)

| Concern | Canonical owner (reused) |
|---|---|
| Durable graduated evidence | `sources/pumpswap_graduated_registry.py` (table `printer_pumpswap_graduated_candidate_registry`, migration 040) |
| Current migration discovery | `discovery/direct_migration_discovery.py` (E.42) |
| Exact `$3K` front door + partitions + mixed two-slot | `discovery/graduated_liquidity_front_door.py` (E.43) |
| FULL_PILOT supply composition | `operator_cli/graduated_supply_front_door.py` (E.44) |
| Admission / holder funnel / activation entry | `operator_cli/authoritative_live_operational_campaign.py::run_operational` |
| Atomic two-or-none activation + handoff | `discovery/combined_executor.py` (`_run_direct_lane`, `_origin_and_pumpswap`, `_apply_gates`, `_select`, `_handoff_one_slot`) |
| Create-origin durable registry | `sources/pumpfun_origin.py` (`record_confirmed_origin`, table `printer_pumpfun_finalized_origin_registry`, migration 036) |
| Holder evidence | `operator_cli/holder_reliability_budget_control.py` + GoPlus / fixed public Solana RPC / fixed Helius Free backup |
| Pilot runner / supervision / replay | `operator_cli/two_token_operational_pilot_runner.py` + proof supervision |

Permanent source decision preserved: GoPlus defensive context → fixed public
Solana RPC primary → fixed authenticated Helius Free backup, exact-target,
fixed-host, eligible-primary-failure, zero-retry. Helius secret is preflighted in
the executor process without printing or persisting it.

---

## 1. Repair 1 — Canonical durable graduated-candidate supply

The graduated-candidate registry (migration 040) is the **sole** canonical owner.
It already persists exactly discovery evidence (mint, migration signature,
migration slot/block time, exact pool + market identity, graduation evidence hash,
provenance, contract/parser version, first/last observation) and carries **no**
campaign / lifecycle / snapshot / memory / retrieval / decision / position / trade
/ PnL state. No schema change is required for the registry itself.

### 1a. Bootstrap of proven prior evidence
`sources/graduated_registry_bootstrap.py` (new, thin) performs **one bounded
governed import** from a retained prior graduated-registry DB into the canonical
registry. Each imported row must pass, or the row is skipped with an explicit
reason (never a partial/forced import):

* exact mint identity present and well-formed;
* exact stored migration signature present;
* exact PumpSwap pool present;
* `confirmation_evidence_hash` recomputes to the stored value
  (`graduation_evidence_hash(...)`), i.e. exact provenance/evidence-hash validation;
* `contract_version` source-policy compatible;
* integrity + foreign-key check on the source DB;
* no campaign/lifecycle/memory column present in the source row.

Import reuses `import_graduated_candidate_row` (idempotent; fail-closed
`GRADUATED_REGISTRY_CONFLICT` on conflicting evidence). Scratchpad-only claims,
raw unverified JSON and incomplete rows are rejected.

**State of retained artifacts at lane start:** an exhaustive scan of `data/`,
`artifacts/`, `operator-runs/` and the scratchpad found **no** surviving DB
containing `printer_pumpswap_graduated_candidate_registry` (E.42/E.43/E.44 live
proofs used scratchpad isolated DBs that did not survive). Therefore the canonical
registry is populated through **bounded live migration cycles** (Repair 2B). No
persisted history is fabricated. The bootstrap importer is implemented and proved
offline against a synthetic prior-registry DB so it is ready for any future
retained artifact.

### 1b. Isolated-attempt immutable export
`export_isolated_attempt_registry(source_db, attempt_db, *, export_identity)`
(new, thin) copies the canonical registry into a **fresh isolated attempt DB**
as a candidate-only, deterministic, replayable export. It carries provenance
hashes and an export identity, and crosses **no** campaign/lifecycle/memory row.
Reuses `export_graduated_candidates` + `import_graduated_candidate_row`. A fresh
attempt therefore never starts with an artificially empty persisted-candidate
universe when valid rows exist.

---

## 2. Repair 2 — Canonical mixed discovery planner

Extends the E.44 `graduated_supply_front_door.build_graduated_supply` composition
owner (no second planner).

* **A. Persisted registry** — the E.43 front door already loads
  `export_graduated_candidates` and refreshes each through the exact-pool
  DexScreener path; below-`$3K`/unproven/inactive candidates stay in the registry
  and simply cannot consume a slot. E.45 adds a **durable categorical cursor**
  (`persisted_refresh_cursor`) so a bounded batch is refreshed in a
  deterministic seeded-rotation order, preventing permanent first-row
  concentration. Ordering is never by liquidity/rank/boost/provider order.
* **B. Current migration discovery** — reuse E.42 `run_direct_migration_discovery`
  with **multiple finite collection rounds**. A single quiet window is not
  sufficient evidence. Frozen ceilings (below).
* **C. DexScreener fresh profiles (locator only)** — wire the already-READY,
  keyless `dexscreener_fresh_profiles` request kind as a **locator**. It surfaces
  currently-visible Solana mints/pairs. Response ordering, rank, boosts,
  popularity and promotional fields are discarded. A fresh-profile mint may
  proceed **only** when it already matches an exact confirmed graduated-registry
  row (the on-chain graduation verifier is not re-run in this lane for a bare
  profile — it is retained locator-only with an explicit rejection reason). It can
  never be smuggled into selection. GeckoTerminal trending and Solana Tracker
  remain `SKIPPED_BLOCKED_CONTRACT`.

### Frozen discovery ceilings (before any live proof)
```
max migration rounds            : 3
max duration per round          : 120 s   (proven productivity reference)
max total discovery duration    : 420 s
max migration events            : 12
max verification operations     : 12
max empty rounds                : 3
max transient reverifications   : 1 per candidate
max failures                    : 5
settle seconds                  : 6 s
fresh-profile requests          : 1 (locator)
```

---

## 3. Repair 3 — Exact front door and truthful partitions

Preserved verbatim from E.43: retain all confirmed graduates; only fresh
exact-pool `liquidity_usd >= 3000` enters active selection; `$3,000` is the only
numeric market-performance threshold; missing/stale/conflicting/estimated/
token-level/wrong-pool liquidity fails closed; missing liquidity is never zero.
Categorical gates (identity, graduation, exact pool, source quality, activity,
dedup, STNP, cooldown, rotation) preserved. Partitions `LATEST_GRADUATED`
(confirmed this cycle) and `PERSISTED_GRADUATED` (confirmed before this cycle,
present in the immutable export). No `DUMP/DECAY/REVIVAL/CONSOLIDATION` derived
pre-snapshot.

---

## 4. Repair 4 — Holder-aware reserve selection

Today the E.43 front door picks one LATEST + one PERSISTED **before** holder
evidence; if a pick fails holder, `run_operational` blocks with other lawful
candidates unspent. E.45 introduces a **holder-aware reserve funnel** owned by
`graduated_liquidity_front_door` (new `select_holder_eligible_pair`) that:

1. produces a deterministic seeded-uniform **ordered queue** per partition (reuse
   `_seeded_uniform` over the full eligible partition, not a single pick);
2. evaluates one candidate from each partition through the existing holder gate
   (`run_operational._evaluate_holder_eligibility`, unchanged) in that order,
   within a frozen candidate + source-operation ceiling;
3. on failure/unknown, records the exact reason and advances to the next
   deterministic candidate **within the same partition only**;
4. stops as soon as one holder-eligible candidate exists per partition, or the
   bounded partition is exhausted;
5. never re-spends holder ops on a partition once accepted;
6. gives a rejected evidence identity no hidden second chance;
7. never turns a holder result into a score/rank/confidence/weight.

Final pair = one holder-eligible `LATEST_GRADUATED` + one holder-eligible
`PERSISTED_GRADUATED`. The candidate cap is derived from actual worst-case
operations (GoPlus + public RPC + fixed Helius Free backup + migration
verification + liquidity enrichment + lifecycle reservation) and the exact
arithmetic is printed and persisted before authorization consumption. Ceilings
are never raised nor evidence weakened to obtain two candidates.

---

## 5. Repair 5 — Graduation-native activation (lane centrepiece)

**Problem (BL-44-01):** migration-discovered candidates carry no Pump *create*
transaction; the executor activation path (`_run_direct_lane` →
`record_confirmed_origin`) requires create-centric evidence, so E.44 stuffed the
migration signature into a `FixtureOriginProof`/`PumpCreateObservation` and
stopped before activation. Persisting a migration signature into a create
signature field, or routing graduation-native evidence through
`record_confirmed_origin` as a fake `PumpCreateObservation`, is forbidden.

**Fix — a typed graduation-native activation route** that keeps downstream token,
pair, queue, scheduler and lifecycle identities identical.

Confirmed by inspection: `_handoff_one_slot` reads only the merged candidate's
`mint` and its (rebound) `market_identity = solana-mainnet:pumpswap:<pool>`; it
never reads `printer_pumpfun_finalized_origin_registry`. `_origin_and_pumpswap`
graduates a candidate and rebinds its market identity to the confirmed PumpSwap
pool whenever the mint has an exact confirmed proof in `fixtures.pumpswap_proofs`.
Therefore a graduation-native candidate needs **no** create-origin row to activate
lawfully — only an origin-confirmed observation plus its PumpSwap graduation proof.

Changes (all in `combined_executor.py`, additive and default-preserving):

* `FixtureOriginProof` gains `origin_route: str = "PUMP_CREATE"`. Value
  `"GRADUATION_NATIVE"` marks a migration-discovered candidate whose `signature`
  is the **migration** signature (graduation-lineage proof), `slot`/`block_time`
  the graduation slot/block time, `bonding_curve` the real derived Pump PDA. The
  historical create transaction is never fetched or fabricated.
* `_Observation` and `_Merged` carry `origin_route`.
* `_run_direct_lane` partitions `direct_observations` by route:
  * `PUMP_CREATE` → unchanged: `record_confirmed_origin` (create), channel
    `LATEST_PUMPFUN`, lifecycle `PUMP_CREATED_UNPAIRED`.
  * `GRADUATION_NATIVE` → **new block**: no `record_confirmed_origin`; no write to
    the create registry; a governed source-lineage reference records the migration
    signature/slot/block time as **migration** evidence; the observation is
    `pumpfun_origin_status="PUMPFUN_ORIGIN_CONFIRMED"` (origin confirmed by
    migration lineage), channel `LATEST_GRADUATED`, lifecycle
    `PUMP_MIGRATION_CONFIRMED`, pool = the graduation proof's PumpSwap pool.
* `_merge` propagates `origin_route`; `_origin_and_pumpswap` labels the confirmed
  origin evidence source `migration_graduation_lineage` (vs
  `direct_finalized_create`) for a graduation-native candidate.

Both lawful routes are preserved:
```
Route A (create-native): confirmed Pump create + confirmed PumpSwap graduation -> activation
Route B (graduation-native): confirmed Pump migration lineage + confirmed exact PumpSwap graduation -> activation
```
The graduation-native proof preserves exact mint, migration signature, migration
slot/block time (as migration evidence), exact Pump program evidence (E.42), exact
PumpSwap program + pool + owner + `base_mint == mint` + market identity, source
lineage, registry evidence identity, latest/persisted provenance, the E.43
front-door result and the holder result. It never fabricates create signature,
create slot/block time, creator, create layout, token creation time or historical
bonding-curve state. Activation remains exactly two-or-none: if either candidate
fails validation, neither activates. Existing create-origin activation and its
regressions are unchanged.

`run_operational` sets `origin_route="GRADUATION_NATIVE"` on the supply carriers
(via `graduated_supply_front_door._origin_proof_for`) and, when
`stop_before_lifecycle` is False, feeds `graduated_candidates` as
`direct_observations` to the driver for real atomic activation.

---

## 6. Repair 6 — Explicit pilot-input readiness boundary

A `PILOT_INPUT_READY` bundle is persisted (migration `041`,
`printer_pilot_input_readiness_bundle`) once, immutably, only when all of:

```
DISCOVERY_READY   - durable candidate universe evaluated
SELECTION_READY   - one lawful LATEST + one lawful PERSISTED identified
MARKET_READY      - both pass fresh exact-pool $3K front door + categorical gates
HOLDER_READY      - both pass the existing holder-evidence contract
ACTIVATION_READY  - both pass graduation-native/create-native atomic activation validation
```

Bundle fields: candidate mints; exact pools + market identities; latest/persisted
provenance; liquidity evidence + freshness; holder evidence + freshness;
activation evidence route; source ledger; configuration + Git identity;
deterministic selection seed; expiration/freshness boundary. It cannot be edited,
partially replaced or silently reselected. If mandatory evidence expires before
launch, the canonical owner refreshes it and builds a **new** readiness identity
(the old bundle is never mutated). No sustained attempt is consumed before the
bundle exists. Owner: `operator_cli/pilot_input_readiness.py` (new, thin) writing
through the readiness table; it enqueues no snapshot/lifecycle/memory work.

---

## 7. Offline proof plan

Durable supply, discovery composition, selection + holder funnel, activation, and
locks/integrity — as enumerated in the lane brief. Focused suites +
directly-affected regressions; broader V2-9.7E suite at the final checkpoint
before live authorization.

## 8. Live plan

Bounded live `PILOT_INPUT_READY` proof through the canonical path (multiple
bounded migration rounds, one governed fresh-profile locator, exact-pool refresh,
holder-aware replacement, graduation-native atomic activation, stop at
`PILOT_INPUT_READY`). If readiness passes, the sustained supervised two-token
`FULL_PILOT` (15m→1h→4h) runs in-session. If the execution environment imposes a
hard duration limit on the sustained lifecycle, the exact ready state is preserved
and the lane closes honestly with
`V2_9_7E_45_INPUT_READINESS_PASS_ENVIRONMENT_BLOCKED` — full PASS is never claimed
from readiness alone.

## 9. Locks preserved

Paper-only; Solana memecoin only; no live trading/wallet/keys/funds; no paid API;
no scoring/ranking/confidence/weighting; no engine bypassing Source Governor or
Central Scheduler; no memory/retrieval/decision/position/trade/audit/PnL before
lifecycle authorization; `$3,000` proves tracking admission only, not route/entry/
exit/slippage realism.
