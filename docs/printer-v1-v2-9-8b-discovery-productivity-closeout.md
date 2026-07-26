# Printer V1 V2-9.8B.7 — Discovery Productivity Repair Closeout

## Verdict

`V2_9_8B_7_DISCOVERY_PRODUCTIVITY_REPAIR_PASS`

V2-9.8B.5 audit, V2-9.8B.6 design, and V2-9.8B.7 implementation/proof are closed
PASS. This does **not** mark V2-9.8B complete and does **not** authorize a
production campaign, restart, successor, retry, tag, or push.

## Root cause

### Primary — production under-used designed capacity

The public operational command called graduated supply **without** the E.46B
multi-round kwargs already wired on the pilot path:

| Bound | Production before | After repair |
|---|---:|---:|
| `collection_rounds` | 1 | 3 |
| `max_candidates` | 5 (unused depth) | 5 |
| `settle_seconds` | 0 | 6.0 |
| `reverify_on_transient` | false | true |
| `front_door_max_candidates` | 64 default | 6 |
| `run_locator` | false | true |

The audited execution therefore spent one thin migration window, confirmed one
mint, re-enriched a stale low-liquidity registry row, and closed with 4/45
source budget used.

### Secondary — below-floor re-enrichment tax

No durable market-floor revalidation state existed. A graduated mint below
`$3,000` exact-pool liquidity consumed a DexScreener call on every campaign.

## Final contract

### Graduated-supply productivity bounds (shared constant)

```text
OPERATIONAL_GRADUATED_SUPPLY_KWARGS
  collection_rounds=3
  max_candidates=5
  settle_seconds=6.0
  reverify_on_transient=True
  reverify_settle_seconds=6.0
  front_door_max_candidates=6
  run_locator=True
```

Used by:

- public `run_operational_campaign`
- pilot runner (shared source of truth)

### Below-floor market revalidation

```text
table: printer_graduated_market_floor_state (migration 043)
cooldown: BELOW_FLOOR_MARKET_COOLDOWN_SECONDS = 3600
skip reason: LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN
```

Rules:

1. Below-floor result records last liquidity + `cooldown_until`.
2. While cooldown active: **no DexScreener call**; retain last measurement; reject
   with cooldown reason.
3. After expiry: fresh exact-pool DexScreener required before eligibility.
4. Proven liquidity clears cooldown.
5. Unproven does not get a multi-hour floor cooldown.

### Unchanged locks

- two-token requirement
- `$3,000` exact-pool floor
- exact PumpSwap confirmation before registry entry
- admission source ceiling 45
- deterministic non-ranked selection
- no auto-activation of unselected reserves
- no scoring/ranking/confidence/weights
- no retrieval / decisions / positions / trades / audits / PnL
- no production retry authorization from this closeout

## Files changed

| File | Role |
|---|---|
| `docs/printer-v1-v2-9-8b-operational-discovery-productivity-audit.md` | V2-9.8B.5 audit |
| `docs/printer-v1-v2-9-8b-expanded-eligible-pool-design.md` | V2-9.8B.6 design |
| `docs/printer-v1-v2-9-8b-discovery-productivity-closeout.md` | This closeout |
| `migrations/043_graduated_market_floor_state.sql` | Durable floor revalidation state |
| `src/printer_v1/discovery/graduated_liquidity_front_door.py` | Cooldown skip + record |
| `src/printer_v1/operator_cli/graduated_supply_front_door.py` | Shared supply kwargs constant |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Wire kwargs; migration count 43 |
| `src/printer_v1/operator_cli/two_token_operational_pilot_runner.py` | Use shared kwargs |
| `tests/test_v2_9_8b_5_7_discovery_productivity.py` | Focused productivity proofs |
| `tests/test_v2_9_7e_43_graduated_liquidity_front_door.py` | FD-07 advances past cooldown |

## Focused proof

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_5_7_discovery_productivity.py \
  tests/test_v2_9_7e_43_graduated_liquidity_front_door.py \
  tests/test_v2_9_7e_42_direct_migration_discovery.py \
  tests/test_v2_9_8b_4_blocked_supply_source_reporting.py \
  tests/test_v2_9_7e_44_full_pilot_supply_integration.py \
  tests/test_v2_9_8b_2_holder_budget_supervision_repair.py \
  -q
```

Result:

```text
77 passed (discovery/front-door/productivity/reporting/supply suite)
+ 9 passed (holder budget suite)
```

Proof coverage:

1. Five distinct migrations → up to five confirmed candidates  
2. Fewer available → honest lower count  
3. Cross-round duplicates do not double-consume verify capacity  
4. Conflicting mint/signature evidence fails closed  
5. Exact PumpSwap confirmation remains mandatory  
6. Fresh eligible reserve can reach six  
7. Recently below-floor candidate skipped without DexScreener  
8. Revalidation after cooldown expiry with fresh call  
9. Fresh market evidence required before selection after expiry  
10. Selection stops after two eligible distinct tokens  
11. Unselected eligible reserves do not auto-activate  
12. Deterministic non-ranked ordering unchanged  
13. Stage-local source accounting under ceiling 45  
14. Retrieval/financial locked tables unchanged  
15. No retry/restart/successor/production run in this lane  

Migration `043` applied to the local authoritative DB so the ledger expects 43
migrations. No `-Mode run` / production campaign was executed.

## Money-usefulness contribution

1. **Spend idle budget on new confirmations**, not re-polling dead low-liquidity
   graduated pools.
2. **Raise candidates-per-source-op** without lowering market or holder gates.
3. **Preserve capital protection**: still need two exact `$3K+` eligible tokens
   before any lifecycle path.
4. **Honest shortfall remains valid** when live migration yield is thin.

## What remains locked

- V2-9.8B complete claim
- automatic production retry authorization
- retrieval, paper decisions, BUY/SELL/HOLD
- positions, trades, audits, PnL
- live wallets / private keys / signing / real funds
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- raising admission ceiling 45
- lowering `$3,000` or two-token requirements

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Residual risk / status |
|---|---|
| Live migration yield still stochastic | Three rounds help but cannot invent markets; honest block remains valid |
| 1h below-floor cooldown | May delay recheck of a recovered pool until expiry; fresh revalidation then required |
| Outer config `discovery_requests: 2` vs 3 migration rounds | Outer field remains 15m job metadata; migration multi-round is E.46B stage bound; admission 45 not raised |
| Locator still cannot graduate | Correct; only rediscovers registry |
| Production not run after repair | Required; next operator-authorized attempt only after readiness review |

## Proof required before production

Before any operator-authorized production retry:

1. Clean tree on the closeout HEAD.
2. `preflight-only` READY (migration 43, integrity ok, zero active work).
3. Operator explicitly approves a single bounded run (not this closeout).
4. Expect multi-round collection, floor cooldown skips for known below-floor
   mints, and blocked-supply reporting with campaign source totals if shortfall.

## Stop conditions honored

- No production `-Mode run`
- No live source calls during proof
- No tag or push
- No V2-9.8B complete claim
- No financial unlock
