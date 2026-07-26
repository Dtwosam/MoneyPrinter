# Printer V1 V2-9.8B.5 — Operational Discovery Productivity Audit

## Verdict

`V2_9_8B_5_DISCOVERY_PRODUCTIVITY_AUDIT_PASS`

This audit is read-only. It does **not** authorize implementation by itself, does
**not** mark V2-9.8B complete, and does **not** authorize a production retry.

## Baseline

| Item | Value |
|---|---|
| Local HEAD (authoritative) | `6f9a738fbdc95ee06250a9efa7de7801fb5f7f44` |
| Working tree | clean |
| Remote `origin/master` cross-check | `93a3ca214277c5840fc35d88f44ca15c1ec10863` (local ahead; no pull/merge) |
| Audited production execution | `20260726T172119Z-941d6d86aa56` |
| Prior reporting closeout | `docs/printer-v1-v2-9-8b-blocked-supply-source-reporting-closeout.md` |

## Objective metric

Maximize, under locked ceilings and exact gates:

```text
selection-ready eligible candidates per governed source operation
```

Expected bounded capacity (already designed on the pilot path, not fully used in
production):

```text
up to 5 newly graduation-confirmed candidates
up to 6 fresh market-eligible reserve candidates
up to 5 fully vetted candidates
exactly 2 selected tokens
```

## Exact production wiring (confirmed)

### Public production command

`operational_memory_factory_command.run_operational_campaign`:

| Parameter | Production value | Notes |
|---|---|---|
| Migration transport | `max_events=4`, `duration_seconds=120` | One transport instance reused per round call |
| `graduated_supply_kwargs` | **not passed** | Falls through to `build_graduated_supply` defaults |
| Admission / source ceiling | `45` | Unchanged |
| Outer config `discovery_requests` | `2` | Configuration metadata only; **not** enforced on migration rounds |
| Token capacity | `2` | Locked |
| Main window | `WINDOW_15M` / 900s | Locked |

### `build_graduated_supply` defaults (what production currently uses)

| Parameter | Default | E.46B pilot productive values |
|---|---:|---:|
| `collection_rounds` | **1** | **3** |
| `max_candidates` | 5 | 5 |
| `settle_seconds` | **0.0** | **6.0** |
| `reverify_on_transient` | **False** | **True** |
| `reverify_settle_seconds` | **0.0** | **6.0** |
| `front_door_max_candidates` | **64** | **6** |
| `run_locator` | **False** | **True** |

### Pilot runner (not the public production command)

`two_token_operational_pilot_runner` already wires the productive E.46B kwargs:

```text
collection_rounds=3
max_candidates=5
settle_seconds=6.0
reverify_on_transient=True
reverify_settle_seconds=6.0
front_door_max_candidates=6
run_locator=True
```

### Front door / reserve / holder

| Stage | Owner | Bound | Behavior |
|---|---|---|---|
| Migration intake | `run_direct_migration_discovery` | `collection_rounds` × bounded stream | Dedup by mint/signature across rounds; conflicts fail closed |
| On-chain verify | same | `max_candidates` (5) | Exact PumpSwap confirmation required before registry write |
| Registry | `printer_pumpswap_graduated_candidate_registry` | durable confirmed only | Graduation evidence immutable |
| Market floor | `run_graduated_liquidity_front_door` | `max_candidates` refresh batch | Exact-pool DexScreener; `$3,000` categorical floor |
| Combined reserve | front door `combined_reserve_order` | eligible after floor | Deterministic seeded-uniform; not ranked |
| Holder funnel | authoritative campaign | budget `candidate_cap` + max 8 | Stops after two holder-eligible distinct tokens |
| Selection | two-token | exactly 2 | Unselected reserves do not auto-activate |

### Budget / reservations (unchanged)

```text
operation_ceiling                              = 45
zero_transport_operations                      = 9
reserved_snapshot_operations                   = 2
reserved_snapshot_completion_operations        = 4
fixed charge before base work                  = 15
available for base work                        = 30
holder worst-case transport ops / candidate    = 5
```

E.46B budget narrative: after fixed reservations, the safe fully-vetted depth is
about five candidates, with a six-candidate market reserve so one liquidity/holder
failure can be replaced without raising ceilings.

## Latest campaign productivity facts

Execution `20260726T172119Z-941d6d86aa56`:

| Evidence | Value |
|---|---|
| Governed source ops | 4 |
| Migration stream requests | 1 (`collection_rounds` default 1) |
| PumpSwap verifies | 1 |
| DexScreener pair snapshots | 2 |
| Newly confirmed graduated | 1 (`CrR3…`) |
| Registry size after | 2 |
| Market-eligible | 1 (`$10,248.29`) |
| Below-floor | 1 (`4hi84…` at `$9.06`) |
| Required tokens | 2 |
| Terminal | `BLOCKED_INSUFFICIENT_GRADUATED_POOL` |
| Lifecycle started | false |
| Budget used vs ceiling | 4 / 45 — large idle budget |

## Audit answers

### 1. Does production use multi-round and five-candidate capacity?

**No.** Production uses default `collection_rounds=1`. `max_candidates=5` is the
default but was never filled because only one migration pair was collected and
verified. The five-candidate / three-round / six-reserve E.46B capacity exists on
the pilot path and is **not wired** into the public operational command.

### 2. Why only one new confirmed candidate?

Primary mechanism:

1. Single migration collection round (not three).
2. That one round’s PumpPortal stream returned one valid mint/signature pair.
3. One PumpSwap confirmation succeeded and wrote one registry row.
4. No additional rounds accumulated further distinct migrations.
5. Transient re-verify settle was off (`reverify_on_transient=False`), so any
   near-miss finalize race would have been dropped without the designed single
   re-verify (not observed as the failure mode here, but capacity is disabled).

Market layer then evaluated two registry rows; only one cleared `$3,000`.

### 3. Does the locator add new candidates or only rediscover registry rows?

**Only rediscover / label.** `run_fresh_profile_locator` matches DexScreener fresh
profiles against the graduated registry. Dispositions:

- `LOCATOR_MATCHED_REGISTRY`
- `LOCATOR_ONLY_NO_GRADUATION_PROOF`

Locator-only mints are **not** inserted as graduated candidates. Exact on-chain
PumpSwap confirmation remains mandatory for registry entry. Production currently
sets `run_locator=False`, so even rediscovery matching is unused.

### 4. Does selection begin before bounded collection is exhausted?

Discovery collection completes (all configured rounds, then verify up to
`max_candidates`) before front-door market enrichment. Front door enriches its
bounded refresh batch fully, then builds the combined reserve. The holder funnel
stops after two eligible tokens — that stop is **after** market eligibility, not
during migration collection. With production `collection_rounds=1`, collection is
“exhausted” after one thin stream window.

### 5. Is the registry too small or stale?

**Both small and partially stale for market purposes.**

- Size: 2 confirmed rows after the latest campaign.
- One row is a previously confirmed low-liquidity graduated mint (`4hi84…`) that
  still consumes a DexScreener call every front-door pass.
- No durable market-floor freshness / below-floor cooldown state exists on the
  registry; only graduation observation fields are mutable.

### 6. Do below-floor candidates repeatedly consume DexScreener calls?

**Yes.** Front door walks bounded registry rows and always calls
`enrich_pool_liquidity` unless identity fails first. There is selection/STNP
cooldown for *selected* tokens, but **no below-floor market cooldown**. `4hi84…`
at `$9.06` consumed one of four campaign source ops without improving the eligible
pool.

### 7. Does freshness / cooldown / revalidation state exist?

| Kind | Exists? |
|---|---|
| Graduation evidence | Yes (immutable registry) |
| Observation touch fields | Yes (`latest_observed_at`, count) |
| Exact-pool liquidity freshness | Implicit: each front-door pass re-fetches when not skipped |
| Below-floor market cooldown | **No** |
| Selected-token STNP cooldown | Yes (selection rotation tables) |
| Market revalidation eligibility clock | **No** |

### 8. Did the latest operation leave usable budget idle?

**Yes.** Ledger charged 4 governed ops against ceiling 45 (plus fixed 9/6
reservations in the ledger model). Idle headroom could have funded additional
migration rounds, verifies, and market enrichments without raising ceilings.

### 9. Do reserve and holder-selection logic already work correctly?

**Yes for correctness; underfed for productivity.**

- Combined reserve order is deterministic and non-ranked.
- Holder funnel stops after two eligible distinct tokens.
- Unselected eligible reserves do not auto-activate.
- Two-token requirement and `$3,000` floor are enforced.
- Failure mode was honest insufficient eligible supply, not selector corruption.

## Root-cause summary

```text
PRIMARY: PRODUCTION_SUPPLY_KWARGS_NOT_WIRED
  Public operational campaign does not pass E.46B multi-round / bounded-depth
  graduated_supply_kwargs already proven on the pilot path.

SECONDARY: NO_BELOW_FLOOR_MARKET_COOLDOWN
  Recently below-floor graduated mints re-consume DexScreener budget every
  campaign without improving eligible supply.

CONTRIBUTING: THIN_LIVE_MIGRATION_YIELD_ON_SINGLE_ROUND
  One 120s migration window produced one confirmed mint; multi-round
  accumulation was available but unused.
```

Classification:

```text
MIXED_BLOCKER
primary: COMMITTED_CODE_WIRING_GAP (production path under-uses designed capacity)
secondary: MISSING_APPROVED_MARKET_REVALIDATION_STATE (below-floor cooldown)
market: HONEST_INSUFFICIENT_ELIGIBLE_SUPPLY under the observed thin yield
```

## What must not be “fixed”

- Do not lower `$3,000` floor
- Do not drop two-token requirement
- Do not raise admission ceiling 45
- Do not add scoring/ranking/confidence/weights
- Do not auto-activate unselected reserves
- Do not treat locator-only mints as graduated
- Do not bypass Source Governor or Central Scheduler
- Do not unlock retrieval / decisions / positions / trades / audits / PnL

## Money-usefulness

Improving candidates-per-source-op without loosening gates protects capital by:

1. Spending idle budget on additional **confirmed** migrations rather than
   re-polling dead low-liquidity pools.
2. Increasing the chance of a lawful two-token ready set under free public data.
3. Keeping every activation still bound to exact mint/pool/holder evidence.

## Proof required before production retry

After design + implementation + focused disposable proof:

1. Multi-round accumulation can confirm up to five distinct migrations.
2. Front-door market reserve can reach six when supply exists.
3. Below-floor cooldown skips DexScreener for recent failures and reopens after
   expiry with fresh evidence still required.
4. Selection still stops at two; budget stays ≤ 45; locks unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Impact | Audit implication |
|---|---|---|
| Production ignores pilot supply kwargs | Single-round thin yield | Wire existing kwargs; do not invent a second selector |
| Below-floor re-enrichment tax | Wastes DexScreener ops | Add categorical cooldown/revalidation state |
| Outer `discovery_requests: 2` vs 3 migration rounds | Config semantics confusion | Outer value is not a hard migration enforcer today; do not raise admission 45; document migration multi-round as E.46B stage bound |
| Live migration yield still stochastic | Even 3 rounds may underfill | Honest shortfall reporting remains required |
| `front_door_max_candidates=64` default | Could over-spend Dex on large registries | Production must use 6 |
| Schema for market floor state | Needed for durable cooldown | Prefer narrow migration only if unavoidable |

## Stop decision

Audit **PASS**. Proceed to expanded eligible-pool design. No production run.
