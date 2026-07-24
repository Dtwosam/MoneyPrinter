# Printer V1 V2-9.7E.44 — FULL_PILOT Candidate-Supply Integration (Narrow Micro-Design)

## Status

Narrow production repair design, frozen before implementation. Scope authorized by
the operator: wire the already-adopted **E.42 direct-migration discovery** and
**E.43 `$3,000` exact-pool front door** into the canonical `FULL_PILOT`
(`run_operational`) **candidate-supply path**, reusing all existing owners, then
prove it offline plus one bounded live pre-lifecycle proof. No sustained
`15m → 1h → 4h` lifecycle is run in this slice.

## Root defect (extends BL-41-04)

The graduation-only tracking law (E.41), the direct-migration discovery channel
(E.42) and the `$3,000` exact-pool front door (E.43) are all committed, but **none
of them is wired into the canonical `FULL_PILOT` runner**:

- `run_two_token_operational_pilot` (`two_token_operational_pilot_runner.py`) calls
  `AuthoritativeLiveOperationalCampaignOwner.run_operational(...)` with **no
  `graduation_proofs`**.
- `run_operational` never invokes `run_direct_migration_discovery` (E.42) or
  `run_graduated_liquidity_front_door` (E.43). Its candidate universe is the fresh
  live Pump-*create* acquisition (bonding-curve creates), which never graduates in
  the same cycle.
- Neither discovery owner has any caller in `src/`; both were proven only by
  scratchpad drivers.

Consequence: a live `FULL_PILOT` cold-starts straight to
`BLOCKED_INSUFFICIENT_GRADUATED_POOL` and can never reach holder eligibility,
atomic activation or lifecycle. This is a `MISSING_INTEGRATION` production defect
(the operational continuation of BL-41-04). New id: **BL-44-01**.

## What is faithfully in scope (and what is not)

E.42 discovery captures, per graduated token, only the **migration** evidence:
`mint`, `migration_signature`, `pumpswap_pool`, `graduation_block_time`,
`graduation_slot`, `market_identity`. It does **not** capture the token's original
Pump **create** transaction (create signature/slot, associated bonding curve,
creator address). The executor's activation path
(`combined_executor` → `record_confirmed_origin`) requires a full
`PumpCreateObservation`, including those create-time fields.

Therefore the faithful narrow slice wires discovery + front door up to the
**candidate-supply → `$3K` front door → holder eligibility → atomic two-slot
readiness** boundary — exactly the operator's bounded live chain — and **stops
before** the create-centric executor activation. Fabricating create-time fields
for a migration-discovered token, or re-fetching each token's historical create
transaction, is out of scope and is the explicit downstream operator decision
(recorded as the deferred item, verdict `V2_9_7E_44_OPERATOR_DECISION_REQUIRED`).

Only these origin-proof fields are structurally required upstream of activation
(`_finalized_holder_candidates` / `_graduated_admission`): `mint`, `bonding_curve`
(non-empty), `signature` (non-empty), `slot` (`>= 0`), `confirmed`. All are
faithfully available:

- `mint`, `signature = migration_signature`, `slot = graduation_slot or 0`,
  `block_time = graduation_block_time` — from the durable graduated registry.
- `bonding_curve` — the **real** Pump bonding-curve PDA, derived deterministically
  from the mint via the existing
  `pumpfun_direct.derive_program_address((b"bonding-curve", b58(mint)), PUMP_PROGRAM_ID)`.
  (No fabricated address; verified against the E.43 live mint.)
- `graduation_proofs[mint] = FixturePumpSwapProof(mint, pool_address=pool,
  program_id=PUMPSWAP_PROGRAM_ID, confirmed=True, ambiguous=False)` — from the
  registry pool. This is exactly the confirmation object `_classify_graduation`
  expects; the tracking identity is the exact PumpSwap pool.

The migration signature is a real on-chain signature and the on-chain proof of the
graduation lineage; it is used as the confirmed-origin transaction reference for a
migration-discovered graduated token. Under the E.41 graduation-only law,
graduation — not the historical create — is the eligibility event.

## New composition owner (glue only, no parallel selector)

`src/printer_v1/operator_cli/graduated_supply_front_door.py`

```
build_graduated_supply(
    db_path, *, cycle_seed,
    migration_transport=None,            # live PumpPortal subscribeMigration (default live)
    verifier_transport_factory=None,     # live PumpSwap on-chain verify (default live)
    dexscreener_transport_factory=None,  # live exact-pool DexScreener (default live)
    discovery_rounds, settle_seconds, reverify_on_transient, ...,  # bounded ceilings
    max_candidates,
) -> GraduatedSupply
```

Behaviour (pure composition of existing owners; adds no source-call, gate, score or
provider of its own):

1. `run_direct_migration_discovery(db_path, migration_transport=..., collection_rounds=..., ...)`
   → governed migration intake → governed on-chain graduation verification →
   `record_graduated_candidate` into the durable registry. Returns the
   confirmed-this-cycle mints (the `LATEST` partition).
2. `run_graduated_liquidity_front_door(db_path, cycle_seed=..., latest_mints=<confirmed this cycle>, ...)`
   → exact-pool DexScreener enrichment → `$3,000` floor → identity / source-quality
   / STNP / cooldown gates → truthful `LATEST`/`PERSISTED` provenance → frozen mixed
   two-slot selection (`<= 1 LATEST` + `<= 1 PERSISTED`) → atomic-handoff readiness.
3. For each **front-door-selected** mint, read its registry row
   (`lookup_graduated_candidate`) and build:
   - a `FixtureOriginProof` carrier (real derived bonding curve, migration
     signature, graduation slot/block time, `confirmed=True`), and
   - a `FixturePumpSwapProof` graduation confirmation.
4. Return `GraduatedSupply(graduated_supply=(...proofs...),
   graduation_proofs={mint: proof}, discovery_report, front_door_report,
   selected_latest, selected_persisted, handoff_readiness)`.

`GraduatedSupply` carries no behaviour derivation, ranking or score. Selection stays
owned by the front door's frozen seeded-uniform mixed two-slot rule.

## Minimal `run_operational` extension

Add two optional parameters (default off → byte-for-byte the current behaviour):

- `graduated_supply: GraduatedSupply | None = None` — externally-built supply. When
  a live `migration_transport` is supplied instead, `run_operational` calls
  `build_graduated_supply` itself against `command.db_path`.
- `stop_before_lifecycle: bool = False` — return the pre-lifecycle readiness bundle
  (admission decisions + holder facts + handoff readiness) without invoking
  `self._driver.run` (no scheduler, snapshot, lifecycle, memory).

Wiring inside `run_operational` (all existing owners unchanged):

- Admission universe `= tuple(acquisition.origin_proofs) + tuple(supply.graduated_supply)`.
- `graduation_proofs` merged with `supply.graduation_proofs`.
- Existing `_graduated_admission` admits only graduation-confirmed candidates (the
  fresh creates have no graduation proof and remain staged pending-discovery, as
  today). Deterministic seeded-uniform selection, `$3K` floor already applied by the
  front door, mixed one-LATEST/one-PERSISTED preserved.
- Existing `_evaluate_holder_eligibility` runs only on the graduated candidates.
- If `stop_before_lifecycle`: return a readiness result
  (`lifecycle_started=False`, `stop_reason="PRE_LIFECYCLE_SUPPLY_READY"` or an honest
  block) carrying the admission diagnostics, holder facts and handoff readiness.
- Else (full path, not exercised in this slice): fall through to the existing
  `self._driver.run(...)`. For migration-discovered candidates this reaches the
  create-origin requirement and blocks honestly (`ORIGIN_NOT_IN_REGISTRY`) —
  documented as the deferred operator decision, not a regression.

No change to the executor, holder path, atomic-handoff owner, lifecycle owner,
Source Governor, Central Scheduler, memory, reporting or replay owners.

## Ceilings (bounded; no unbounded "until success")

Discovery: explicit `collection_rounds`, per-round governed migration ceiling,
`settle_seconds`, single bounded transient reverify, `max_candidates`. Front door:
one governed exact-pool DexScreener request per candidate, `max_candidates`. The
bounded live proof terminates at the first of: one lawful `LATEST` + one lawful
`PERSISTED` `$3K+` candidate ready; or any configured round / duration /
source-operation / empty-round / failure ceiling. If the lawful pair is unavailable
at the ceiling, terminate honestly with
`BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL` before holder work. Market supply is
not automatically a code defect.

## Tests (offline, injected transports)

`tests/test_v2_9_7e_44_full_pilot_supply_integration.py`:

- `build_graduated_supply` composes discovery + front door and yields exactly one
  `LATEST` + one `PERSISTED` `$3K+` proof with the real derived bonding curve and
  faithful graduation proof.
- Below-floor / unproven candidates are excluded from supply.
- Sparse supply (fewer than 2 eligible) → honest
  `BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL`, no holder work.
- `run_operational(..., graduated_supply=..., stop_before_lifecycle=True)` admits
  exactly the two graduated candidates, runs holder eligibility, returns atomic
  two-slot readiness with `lifecycle_started=False` and zero forbidden deltas.
- Default `run_operational` (no supply, no live transport) is unchanged: cold-start
  → `BLOCKED_INSUFFICIENT_GRADUATED_POOL`.
- Integrity `ok`, zero FK violations, zero forbidden deltas throughout.

Directly affected regressions: E.11 operational, E.14 pilot runner, E.41 / E.42 /
E.43 discovery + front door, combined executor, atomic handoff.

## Permanent locks preserved

Solana-only; memecoin-only; paper-only; no wallet/keys/signing/funds/execution; no
paid APIs; no scores/ranks/confidence/weighted logic (the `$3K` floor is a
categorical pass/fail); no embeddings/vectors; no Source Governor / Central
Scheduler bypass; 5m support-only; no retrieval; no paper decisions; no
BUY/SELL/HOLD; no positions/trade events/paper audits/PnL in this slice; no
FULL_PILOT lifecycle execution in this slice; no V2-9.7F / V2-9.8 or later work.
