# Printer V1 V2-9.7E.44 — Continuous Two-Token Full-Pilot Repair and Clean-Pass Session Closeout

## Verdict

`V2_9_7E_44_OPERATOR_DECISION_REQUIRED`

The canonical FULL_PILOT candidate-supply integration is committed and live-proven
end-to-end through the `$3,000` exact-pool front door. The real-wall-clock
`15m → 1h → 4h` lifecycle — and the create-origin backfill needed to activate
migration-discovered graduated candidates through the executor — require a separate,
continuously supervised, operator-authorized session. No sustained FULL_PILOT
attempt was consumed and no full-pilot PASS is claimed.

## Scope actually executed (operator-directed narrow slice)

The session began as a continuous full-pilot session. Preflight and code analysis
established that the adopted E.42 direct-migration discovery and E.43 `$3,000`
front door were **not wired into** the canonical FULL_PILOT (`run_operational`)
candidate supply (BL-44-01), so a live full pilot cold-started to
`BLOCKED_INSUFFICIENT_GRADUATED_POOL` and could never reach holder, activation or
lifecycle. Per operator direction the session was rescoped to a narrow
supply-integration slice + one bounded live pre-lifecycle proof, closing with
`V2_9_7E_44_OPERATOR_DECISION_REQUIRED`. The three sustained FULL_PILOT
authorizations were **not** consumed.

## Starting and ending commits

- **Starting commit:** `d0bd8cafb752acb722d030e78664b9b07cffa564`
  (`Close $3K graduated discovery front-door repair`).
- **Integration commit:** `b273179`
  (`Wire graduated discovery and $3K front door into full-pilot supply`).
- **Ending commit:** this closeout + blocker-register update + the two E.43 wording
  corrections (`Close continuous two-token full pilot proof`). No tag.

## The defect and the repair (BL-44-01)

`MISSING_INTEGRATION` (operational continuation of BL-41-04). Neither
`run_direct_migration_discovery` (E.42) nor `run_graduated_liquidity_front_door`
(E.43) had any caller in `src/`; `run_two_token_operational_pilot` invoked
`run_operational` with no `graduation_proofs`, and `run_operational` never ran
discovery or the front door.

Repair (design:
`docs/printer-v1-v2-9-7e-44-full-pilot-supply-integration-design.md`):

- **New** `operator_cli/graduated_supply_front_door.build_graduated_supply` — pure
  composition of the two adopted owners (no new gate, score, ranking, selector or
  provider). For each front-door-*selected* mint it builds the confirmed-origin
  carrier (the **real** Pump bonding-curve PDA derived from the mint via the existing
  `pumpfun_direct.derive_program_address`, plus the on-chain migration signature) and
  the exact PumpSwap graduation proof.
- **`run_operational`** gains `graduated_supply` / `migration_transport` /
  `graduated_supply_kwargs` / `stop_before_lifecycle` (all default-off → byte-for-byte
  the prior behaviour). The graduated candidates join the admission universe, holder
  eligibility runs on them, and the pre-lifecycle path returns **atomic two-slot
  readiness** without invoking the scheduler/lifecycle/memory driver.

Reused verbatim: Source Governor, Central Scheduler, durable graduated registry,
exact-pool front door, seeded-uniform mixed two-slot selection, holder-eligibility
path, atomic-handoff readiness. No parallel runner, discovery loop, selector, holder
path, lifecycle owner or proof harness was created.

### Honest boundary (why activation is deferred)

E.42 discovery captures only the **migration** evidence per graduated token
(`mint`, `migration_signature`, `pumpswap_pool`, `graduation_block_time/slot`,
`market_identity`). It does **not** capture the token's original Pump **create**
transaction (create signature/slot, associated bonding curve, creator address),
which the executor activation path (`record_confirmed_origin`) requires. The narrow
slice therefore wires the supply → `$3K` front door → holder → **atomic two-slot
readiness** boundary and stops before create-centric activation. A create-origin
backfill (or a graduation-native activation path) is the deferred operator decision.

## Attempts, identities, HEADs, first terminal cause

| Attempt | Kind | HEAD | Execution identity | First terminal cause |
|---|---|---|---|---|
| Bounded live supply proof (does **not** consume a FULL_PILOT attempt) | pre-lifecycle | `b273179` | `e44-live` (isolated `e44-live-*` DB) | `BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL` (sparse live migration supply; below-`$3K` fresh pool) |

Sustained FULL_PILOT attempts consumed: **0 of 3**.

## Repair commits

- `b273179` — `Wire graduated discovery and $3K front door into full-pilot supply`
  (BL-44-01). No further production repair was required; the bounded live proof
  exposed no code defect (sparse supply and a below-floor fresh pool are not defects).

## Selected tokens, pools, provenance, liquidity

No lawful mixed pair was selected in the one bounded live window. Cycle 2 confirmed
**one** live graduated LATEST candidate on-chain and enriched its exact PumpSwap pool
live; its fresh liquidity was **below `$3,000`**, so the front door excluded it
(`LIQUIDITY_BELOW_SELECTION_FLOOR`) — the floor firing live is positive evidence the
wiring works (mirrors E.43 Attempt 2's live `$8.70` exclusion). Cycle 1's window was
quiet (0 migrations), so no `PERSISTED` cohort existed. Selected LATEST / PERSISTED:
**none within ceilings**.

## Holder, lifecycle/window, memory, continuation results

Not exercised live (supply not ready → the run stopped before holder/atomic work).
Offline, the committed wiring was proven to run holder eligibility on exactly two
graduated candidates and return atomic two-slot readiness
(`PRE_LIFECYCLE_ATOMIC_TWO_SLOT_READY`, both holder-eligible) with
`lifecycle_started == False`. No lifecycle windows, 1h/4h completions, memory
windows, promotions, or continuation decisions occurred (by design — this slice
stops before lifecycle).

## Source and scheduler accounting

All migration intake and on-chain graduation verification ran through the Source
Governor; all front-door liquidity requests were governed exact-pool DexScreener
snapshots (one per candidate). No retry-until-success, endpoint rotation, source
substitution, budget increase, added provider, or paid source. Cycle 1: 1 governed
migration round (0 valid pairs). Cycle 2: 1 governed migration round → 1 valid pair →
1 governed on-chain verification → 1 persisted; 1 governed front-door liquidity
request. Blocked trending/top channels remained `SKIPPED_BLOCKED_CONTRACT`.

## Replay, cleanup, integrity, forbidden deltas

- Bounded live proof: `integrity_check == ok`; `foreign_key_violations == 0`;
  discovery and front-door forbidden-capability delta totals `0`; the isolated proof
  DB is disposable (no authoritative-corpus mutation).
- No stale queue, scheduler, lease, lifecycle or temporary artifact was created; no
  successor or automatic restart. Report-only replay is not applicable (no lifecycle
  run started).
- Offline: zero retrieval, decision, position, trade, paper-audit and PnL deltas;
  `integrity_check == ok`, zero FK violations (SI-03).

## Tests

- New `tests/test_v2_9_7e_44_full_pilot_supply_integration.py` (5 tests): composition
  yields the mixed `$3K+` pair with the real derived bonding curve and faithful
  graduation proof (SI-01, SI-05); a below-floor LATEST is excluded → honest
  `BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL` (SI-02); `run_operational(...,
  graduated_supply=..., stop_before_lifecycle=True)` admits exactly two graduated
  candidates, runs holder eligibility, returns atomic two-slot readiness with
  `lifecycle_started False` and zero forbidden-capability rows (SI-03); default
  `run_operational` is unchanged, cold-start blocked (SI-04).
- Directly affected regressions (all pass, **142 total** including the 5 new):
  E.11 operational, E.14 pilot runner, E.41 graduation-only, E.42 direct migration,
  E.43 front door, E.40 admission, E.40b persistent pool.

## Money-usefulness contribution

Before E.44 the adopted graduated-discovery channel and the `$3,000` front door were
committed but unreachable from the FULL_PILOT runner, so the money machine had no
operational way to supply a lawful, liquidity-vetted graduated pair into a pilot. E.44
connects them: a live FULL_PILOT can now discover a freshly-migrated Pump graduate,
verify its graduation on-chain, retain it durably, prove at least `$3,000` of real
exact-pool liquidity, and present a mixed one-LATEST/one-PERSISTED pair to holder
eligibility and atomic activation. The `$3,000` floor proves **active-tracking
admission only** — it does not by itself prove realistic entry, exit, route, slippage
or price impact. The bounded live proof demonstrated the whole chain executing on
real sources and the floor excluding a real below-`$3K` pool.

## What remains blocked

- **Create-origin backfill / graduation-native activation** — required to activate
  migration-discovered graduated candidates through the executor (deferred operator
  decision, BL-44-01 remaining limitation).
- **Sustained real-wall-clock `15m → 1h → 4h` lifecycle** — needs a continuously
  supervised, operator-authorized session (~4.25 h+ per attempt).
- **BL-43-01 live migration-supply timing** — sparse/bursty graduations mean a single
  bounded window may catch no lawful mixed `$3K+` pair; a productive session must
  persist discovery across enough bounded cycles (still within finite ceilings).
- **BL-41-04 trending/top channels** — remain `SKIPPED_BLOCKED_CONTRACT` (separate
  optional lane; the direct migration channel does not require them).

## Functionality Risks / Setbacks / Efficiency Blockers

- **Risk (activation boundary):** the committed slice stops at atomic readiness for
  migration-discovered candidates; driving them through executor activation without
  the create-origin backfill would block at `record_confirmed_origin` — a known
  design boundary, not a regression.
- **Setback (supply timing):** BL-43-01 — a bounded window may catch zero graduations
  or only below-floor fresh pools (as this proof saw). Fresh-graduate liquidity is
  market-dependent; a just-migrated pool is frequently below `$3,000` before it
  fills.
- **Efficiency blocker:** public PumpPortal/RPC/DexScreener latency and the sparse
  live migration cadence govern how quickly a lawful mixed pair appears; failures are
  honest, governed and never fabricated or retried beyond the adopted bounded
  reverify.

## Is V2-9.7F ready?

**No.** V2-9.7F must not start. The FULL_PILOT supply integration is committed and
live-proven to atomic readiness, but a full clean two-token lifecycle PASS has not
been achieved and requires (1) the create-origin activation decision and (2) a
continuously supervised real-wall-clock lifecycle session.

## Permanent locks preserved

Solana-only; Solana memecoin-only; paper-only; no wallet/keys/signing/funds/
execution; no paid APIs; no scoring/ranking/confidence/weighted decisions (the
`$3,000` floor is a categorical pass/fail); no embeddings/vectors; no Source Governor
or Central Scheduler bypass; 5m support-only; no retrieval; no paper decisions; no
BUY/SELL/HOLD; no positions/trade events/paper audits/PnL; no FULL_PILOT lifecycle
execution in this slice; no successor or automatic restart; no V2-9.7F / V2-9.8 or
later work. The free-tier Helius secret was confirmed present and never printed or
persisted.
