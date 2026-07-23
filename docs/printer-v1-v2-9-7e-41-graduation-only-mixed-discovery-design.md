# Printer V1 V2-9.7E.41 — Graduation-Only Selection and Mixed-Channel Discovery Micro-Design

## Status

Frozen micro-design for the operator-approved E.41 combined repair. It adopts no
new provider, adds no paid dependency, adds no source-budget increase, and adds
no schema table. It reuses the existing durable
`printer_pumpfun_finalized_origin_registry`, the combined discovery executor
(`CombinedPumpfunCampaignExecutor`), the PumpSwap on-chain confirmation owner,
the Source Governor and the Central Scheduler. It supersedes the E.40
maturity-age route to full-pilot eligibility.

## Frozen product law

**PRINTER V1 GRADUATION-ONLY TRACKING LAW**

Printer may discover and retain source evidence about a Pump.fun token before
graduation, but it must never select, activate, track, create a lifecycle for,
or generate memory about that token while it remains on the Pump.fun bonding
curve.

A Pump.fun token becomes selection-eligible only after exact governed evidence
confirms graduation and binds its exact mint to one valid post-graduation
PumpSwap market identity.

There is no minimum token-age or post-graduation waiting period. A token may be
selected immediately after confirmed graduation when all other categorical
source, market, liquidity, activity, cooldown and identity gates pass.

Age is context, not eligibility. Graduation is mandatory eligibility.

## Root problem restated

E.36–E.40 admitted full-pilot candidates by a categorical 900-second Pump-origin
maturity boundary (`evaluate_snapshot_maturity`). The direct `LATEST_PUMPFUN`
acquisition channel yields **only pre-graduation bonding-curve creates**
(`PUMP_CREATED_UNPAIRED`, `market_identity = pumpfun:<bonding_curve>`). The 900s
gate therefore admitted *aged bonding-curve tokens* — exactly the tokens the
graduation-only law forbids from selection. The E.40 persistent pool exported
those same aged, ungraduated origins as "candidates". Age was used as if it were
eligibility; graduation was never required.

The combined executor's `LIFECYCLE_MARKET` gate also failed to fail-closed an
ungraduated candidate: it rejected only a candidate that *claimed* `GRADUATED`
without confirmation, so a `PUMP_CREATED_UNPAIRED` candidate (no `GRADUATED`
substring) passed the gate and `_select` ranked it selectable. This is the exact
violation the E.40 closeout predicted as the "next-stage" `PUMP_CREATED_UNPAIRED`
market-eligibility block.

## Repair architecture

```text
direct LATEST_PUMPFUN creates        -> PENDING DISCOVERY ONLY (never selectable)
   (PUMP_CREATED_UNPAIRED)              retained as origin evidence + provenance

mixed graduated-discovery channels   -> per-candidate graduation verification
   (latest-graduated, active,           exact Pump origin
    trending, top, persisted,        -> exact successful migration/graduation
    revival, dump, consolidation,    -> exactly one PumpSwap pool, owner==program,
    decay)                              base_mint==mint
                                     -> PUMPSWAP_GRADUATED_CONFIRMED + PumpSwap
                                        market identity
                                     -> categorical source/liquidity/activity/
                                        cooldown/conflict gates
                                     -> categorical two-slot distribution
                                     -> deterministic seeded uniform selection
                                     -> atomic two-slot handoff -> WINDOW_15M
```

Graduation is the sole eligibility route. The 900-second boundary is removed from
every full-pilot path and remains unchanged in `SNAPSHOT_READINESS`.

## Repair 1 — Remove the 900-second rule from FULL_PILOT

`run(mode=FULL_PILOT)` / `run_operational`:

- no longer calls `evaluate_snapshot_maturity` as a selection gate;
- no longer computes `mature_candidates` / requires `DUE`;
- no longer waits for candidates to reach 900 seconds;
- no longer returns `BLOCKED_INSUFFICIENT_MATURE_POOL`.

The old `_mature_admission` (900s) is replaced by `_graduated_admission`, which
admits only graduation-confirmed candidates. When fewer than two graduated
candidates exist the honest terminal is `BLOCKED_INSUFFICIENT_GRADUATED_POOL`
(`run_status=NOT_STARTED`, `lifecycle_started=False`, zero forbidden deltas),
returned before any holder / snapshot / lifecycle / memory work.

`run(mode=SNAPSHOT_READINESS)` is untouched: it still requests an already-completed
historical 15-minute interval and keeps its 900-second maturity policy and its
focused tests unchanged. `SNAPSHOT_MATURITY_SECONDS` and `evaluate_snapshot_maturity`
remain the readiness-mode owners.

## Repair 2 — Enforce graduation-only selection

These lifecycle states are **discovery-only, permanently ineligible for active
selection**:

- `PUMP_CREATED_UNPAIRED`
- `PUMP_BONDING_CURVE_ACTIVE`
- `PUMP_MIGRATION_OBSERVED` without exact successful pool confirmation
- `PUMP_LIFECYCLE_UNKNOWN`
- `DISCOVERED_UNPAIRED`
- any missing / ambiguous / conflicting market identity

They may be persisted as pending discovery evidence, but they make zero
active-slot handoffs, lifecycle starts, `WINDOW_15M` creations, memory
generation, retrieval or decision activity.

A candidate becomes selectable only when all required facts pass, enforced by the
executor's `LIFECYCLE_MARKET` (now graduation) gate over the merged candidate:

1. exact Solana mint;
2. confirmed Pump.fun origin (`origin_state == CONFIRMED`);
3. exact successful migration/graduation evidence (a confirmed, unambiguous
   PumpSwap proof);
4. exactly one confirmed PumpSwap pool (`pumpswap_state == CONFIRMED`, the
   confirmation owner enforces unique-or-fail);
5. pool account owned by the adopted PumpSwap program
   (`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`);
6. exact `base_mint == candidate mint` (the confirmation owner's `base_mint@43`
   equality);
7. exact post-graduation market identity: on confirmation the candidate's
   tracking `market_identity` is rebound to `solana-mainnet:pumpswap:<pool>` and
   its lifecycle becomes `PUMPSWAP_GRADUATED_CONFIRMED`;
8. categorical source-quality, liquidity, activity, cooldown and conflict gates
   (unchanged fixed-gate order).

`_select`'s lifecycle rank is reduced to the single eligible state
`PUMPSWAP_GRADUATED_CONFIRMED`; any non-graduated candidate that somehow reaches
selection is defensively dropped.

Migration block time and pool creation time remain graduation evidence only
(`pumpswap_migration_block_time`). They never overwrite `token_created_at`. A
token confirmed graduated one second ago is eligible; a bonding-curve token any
age (1s, 900s, one hour, later) is ineligible.

## Repair 3 — Repurpose the persistent pool

The E.40 pool no longer uses age maturity as the route to pilot eligibility. Its
two roles are separated:

**Pending discovery population** (`printer_pumpfun_finalized_origin_registry`):
retains exact Pump origin, mint identity, creation signature/block time,
provenance and later migration observations. It is **never** directly exported as
a selectable pilot candidate. The age helpers are renamed to reflect discovery
scope:

- `pool_maturity_state` → `pool_pending_discovery_state` (age is discovery
  context, not eligibility; the old name is kept as a thin deprecated alias for
  historical callers).
- `seed_attempt_from_pool` → `seed_pending_discovery_from_pool` (seeds pending
  discovery evidence only; it is explicitly **not** a selectable-candidate
  export). The old name is kept as a deprecated alias.

**Graduated candidate population**: a candidate is exported to a fresh pilot only
when exact PumpSwap graduation and market identity are confirmed
(`export_graduated_pilot_candidates`, gated on confirmed graduation evidence).
Because the origin registry stores only pre-graduation origins, this export is
empty until a graduation-evidence owner supplies confirmed graduations — the
honest current state.

The persistent owner retains graduated candidates across cycles, preserves source
and migration provenance, excludes unpaired/bonding-curve candidates from pilot
export, deduplicates by exact token and market identity, never carries campaign /
authorization / lifecycle / memory / decision / terminal state into a fresh
pilot, and no longer requires `block_time + 900s` for export.

## Repair 4 — Mixed-channel discovery

The pilot universe is one merged set of confirmed **graduated** Pump.fun tokens
from all currently adopted and operationally permitted channels. Every
secondary-source candidate still passes exact Pump origin verification → exact
graduation verification → exact PumpSwap market confirmation. A provider label,
URL, rank, venue string or symbol cannot prove Pump origin or graduation.

Channel readiness at the starting commit (`00355fe`), verified against the
adopted contracts:

| Channel | Role | Operational state after E.41 |
|---|---|---|
| Direct Pump.fun on-chain (`solana_rpc`) | `LATEST_*` origin | OPERATIONAL for **pending discovery only** (pre-graduation bonding-curve creates; never selectable) |
| PumpSwap on-chain confirmation (`pumpswap`) | graduation confirmation authority | OPERATIONAL (confirmation-only; needs a migration signature/locator) |
| DexScreener (`dexscreener`) | active-market enrichment | OPERATIONAL for exact-market enrichment; cannot assert origin/graduation alone |
| GeckoTerminal (`geckoterminal`) | trending/active graduated discovery | `SKIPPED_BLOCKED_CONTRACT` (fixture-only contract not repaired) |
| Solana Tracker (`solana_tracker`) | trending/top graduated discovery | `SKIPPED_BLOCKED_CONTRACT` (free-REST contract not adopted) |
| PumpPortal (`pumpportal`) | migration event feed | `SKIPPED_BLOCKED_CONTRACT` (requires incompatible wallet/funds state) |
| Persisted graduated candidates | revival/older graduated supply | OPERATIONAL owner, currently empty (no graduated evidence persisted yet) |

**Honest consequence:** no channel currently supplies **already-graduated**
Pump.fun tokens for fresh live discovery without a migration-signature locator.
The direct channel is pre-graduation; the trending/top graduated-discovery
channels remain blocked by their own contracts. The executor's per-candidate
verification machinery (origin verification + PumpSwap confirmation + graduation
gate) is fully wired, so a graduated candidate supplied with a confirmed PumpSwap
proof is admitted and selected; a cold-start live full pilot honestly blocks with
`BLOCKED_INSUFFICIENT_GRADUATED_POOL`.

Blocked providers stay explicitly `SKIPPED_BLOCKED_CONTRACT`; none is silently
activated; no paid dependency is added; no trending/top coverage is claimed while
its contract is blocked.

## Repair 5 — Categorical channel distribution

A frozen smallest deterministic two-slot policy prevents latest-only
concentration, without scoring or ranking:

- classify every eligible **graduated** candidate into `LATEST_GRADUATED`
  (channels include `LATEST_PUMPFUN` / `LATEST_GRADUATED`) or a non-latest
  category (`ACTIVE`, `TRENDING`, `TOP`, `PERSISTED_ACTIVE`, `REVIVAL`, `DUMP`,
  `CONSOLIDATION`, `DECAY`);
- when at least one eligible latest candidate and at least one eligible non-latest
  candidate exist, the two selected slots must **not** both be latest-only: one
  slot is filled from `LATEST_GRADUATED`, the other from an available non-latest
  category;
- selection within each eligible category is deterministic, seeded and uniform
  (canonical sort + `cycle_seed` Fisher–Yates with a per-category domain
  separator);
- when several non-latest categories are available, a durable categorical
  round-robin (categories ordered by a seeded key, advanced by a persisted
  batch-sequence cursor) picks the non-latest category — never weights, scores,
  ranks or popularity;
- if only one category is genuinely available, selection degrades honestly to
  that category (no fabricated diversity) and the diagnostics report the
  single-category concentration;
- a token appearing in multiple channels remains one candidate (identity-deduped)
  and receives no probability boost;
- provider response order, trend rank, boost, score or popularity cannot affect
  selection.

Persisted/reported per cycle: total eligible graduated candidates; channel and
category counts; latest vs non-latest concentration; skipped blocked channels;
the exact two selected categories; exact token and market identities; graduation
evidence; token-age and post-graduation-age context (when supported); and
discarded non-authoritative provider fields.

## Owners changed

- `src/printer_v1/discovery/combined_executor.py`
  - `_apply_gates` `LIFECYCLE_MARKET` → strict graduation gate (facts 1–7);
  - PumpSwap confirmation rebinds `market_identity` to the confirmed pool and
    lifecycle to `PUMPSWAP_GRADUATED_CONFIRMED`;
  - `_select` graduated-only + categorical two-slot distribution (Repair 5) via a
    new `_categorical_two_slot` helper and a `_channel_category` classifier;
  - a `graduation_distribution` diagnostic on the execution result.
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
  - `run_operational` uses `_graduated_admission` (graduation eligibility) and the
    `BLOCKED_INSUFFICIENT_GRADUATED_POOL` terminal; the 900s gate is removed from
    this path; graduation channel/category diagnostics replace the maturity
    diagnostics.
- `src/printer_v1/operator_cli/persistent_candidate_pool.py`
  - renamed discovery-only helpers, deprecated aliases, and a graduation-gated
    `export_graduated_pilot_candidates`.

No new table, migration, provider, Source Governor, Central Scheduler, holder,
snapshot, memory, retrieval, decision or financial owner is changed. The
`SNAPSHOT_READINESS` maturity owner is untouched.

## Offline proof (fixtures + isolated temporary DBs only)

`tests/test_v2_9_7e_41_graduation_only_mixed_discovery.py` proves the 18 required
properties; the E.40 admission / persistent-pool tests are updated to the
superseded graduation semantics. No live pilot, no live source, no persistent DB
mutation.

## Permanent locks preserved

Solana-only; Solana memecoin-only; paper-only; no wallet/keys/signing/funds/
execution; no paid APIs; no scoring/ranking/confidence/weighted decisions; no
embeddings/vectors; no Source Governor or Central Scheduler bypass; 5m
support-only; no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/
trade events/paper audits/PnL; no live pilot in this lane; no V2-9.7F / V2-9.8 or
later work.
