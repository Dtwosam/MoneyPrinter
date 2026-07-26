# Printer V1 V2-9.8B.6 — Expanded Eligible-Pool Design

## Verdict

`V2_9_8B_6_EXPANDED_ELIGIBLE_POOL_DESIGN_PASS`

This design authorizes the **minimum** productivity repair implied by the
V2-9.8B.5 audit. It does **not** raise admission ceilings, lower market/holder
requirements, invent a second registry/selector/source counter, or unlock any
financial capability.

## Authority inputs

- `docs/printer-v1-v2-9-8b-operational-discovery-productivity-audit.md`
  (`V2_9_8B_5_DISCOVERY_PRODUCTIVITY_AUDIT_PASS`)
- E.46B pilot supply bounds already committed in
  `two_token_operational_pilot_runner.py`
- Locked V1 / V2 rules in `AGENTS.md` and the memory-growth build order

## Design goal

Maximize:

```text
selection-ready eligible candidates per governed source operation
```

within:

```text
up to 5 newly graduation-confirmed candidates
up to 6 fresh market-eligible reserve candidates
up to 5 fully vetted candidates
exactly 2 selected tokens
source ceiling 45
```

When supply is short, report the truthful shortfall and exact reason. Never force
a second token.

## Smallest repair

Two changes only:

1. **Wire production to the existing E.46B multi-round bounded supply contract**
   already used by the pilot path.
2. **Add categorical below-floor market revalidation cooldown** so recently failed
   graduated mints do not re-consume DexScreener every campaign.

Everything else (exact PumpSwap confirmation, `$3,000` floor, two-token stop,
deterministic non-ranked order, holder funnel, Source Governor, Scheduler) stays.

## Contract 1 — Production graduated-supply bounds

Public `run_operational_campaign` must pass a single frozen kwargs map into
`AuthoritativeLiveOperationalCampaignOwner.run_operational` as
`graduated_supply_kwargs`:

| Key | Value | Role |
|---|---:|---|
| `collection_rounds` | 3 | Accumulate distinct migrations across bounded stream windows |
| `max_candidates` | 5 | Cap on-chain verifies / newly confirmed this cycle |
| `settle_seconds` | 6.0 | One bounded settle before verify |
| `reverify_on_transient` | True | Exactly one re-verify on transient RPC/not-found only |
| `reverify_settle_seconds` | 6.0 | Bounded settle before that single re-verify |
| `front_door_max_candidates` | 6 | Market-enrichment / reserve depth |
| `run_locator` | True | Optional registry rediscovery only; never creates graduated rows |

Migration transport remains:

```text
max_events=4
duration_seconds=120
connect_timeout_seconds=10
```

per governed migration request. Three rounds ⇒ up to three governed migration
requests; each round re-enters the transport bound independently.

### Cross-round accumulation rules (already implemented; must remain)

- Distinct mint/signature pairs accumulate across rounds.
- Same mint+signature is a duplicate (does not consume verify capacity twice).
- Same mint different signature, or same signature different mint → conflict,
  recorded, never verified/persisted.
- Verify/persist only after exact PumpSwap confirmation.
- Confirmed candidates remain in the durable registry for later cycles.

### Locator rules (already implemented; must remain)

- Locator matches fresh profiles to registry only.
- `LOCATOR_ONLY_NO_GRADUATION_PROOF` never becomes a graduated candidate.
- No second discovery owner.

### Outer `discovery_requests: 2`

This configuration field remains the outer 15m discovery-job policy metadata and
is **not** the migration multi-round bound. This design does **not** raise the
admission operation ceiling (45). Migration multi-round depth is the E.46B stage
bound `collection_rounds=3` already present on the pilot path.

## Contract 2 — Below-floor market revalidation cooldown

### Problem

Front door always enriches each bounded registry candidate with a fresh
DexScreener exact-pool call. Recently below-floor mints burn source budget without
increasing eligible supply.

### State

Durable categorical state (new narrow table; graduation evidence stays immutable):

```text
printer_graduated_market_floor_state
  mint_identity PRIMARY KEY  (exact graduated mint)
  pumpswap_pool TEXT NOT NULL
  liquidity_status TEXT NOT NULL
    in {LIQUIDITY_PROVEN, LIQUIDITY_BELOW_SELECTION_FLOOR, LIQUIDITY_UNPROVEN}
  liquidity_usd REAL NULL
  last_checked_at TEXT NOT NULL
  cooldown_until TEXT NULL
  updated_at TEXT NOT NULL
```

Only the front-door market owner reads/writes this table. No second source
counter.

### Policy

```text
BELOW_FLOOR_MARKET_COOLDOWN_SECONDS = 3600
```

| Liquidity result | Cooldown action | Next front-door behavior |
|---|---|---|
| `LIQUIDITY_BELOW_SELECTION_FLOOR` | set `cooldown_until = last_checked_at + 3600s` | Until expiry: skip DexScreener; retain last measured liquidity; mark rejected with `LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN` |
| `LIQUIDITY_PROVEN` | clear cooldown (`cooldown_until=NULL`) | Eligible for reserve if other gates pass |
| `LIQUIDITY_UNPROVEN` | no multi-hour floor cooldown (fail closed for eligibility; may recheck next campaign) | Not eligible; do not invent liquidity |

After cooldown expiry:

1. Candidate becomes revalidation-eligible.
2. A **fresh** governed exact-pool DexScreener call is required before selection.
3. Stale below-floor numbers never become eligible without that fresh call.

### Non-goals for cooldown

- Not a score, rank, or liquidity magnitude sort key.
- Not a selected-token STNP rotation replacement.
- Not a reason to lower the `$3,000` floor.
- Not applied to mints never market-checked.

## Contract 3 — Reserve, holder funnel, selection (unchanged)

```text
front_door_max_candidates = 6
  -> up to 6 market-enriched registry rows per campaign
  -> eligible ($3K+) form the combined reserve
holder funnel
  -> deterministic combined order
  -> stop after 2 holder-eligible distinct tokens
  -> unselected eligible reserves do not auto-activate
exactly 2 selected tokens when ready
else honest blocked-supply terminal
```

## Source accounting (unchanged owner)

- Stage-local request IDs only (migration/verify/locator/front-door).
- Holder ledger remains the campaign operation total owner.
- No whole-table `COUNT(*)` on historical `printer_source_requests`.
- Admission ceiling remains 45; do not raise.

Illustrative upper-bound sketch (not a guarantee of live yield):

```text
migrations 3 + verifies ≤5 + locator 1 + market enrich ≤6
  = ≤15 pre-holder governed ops
remaining headroom still covers holder vetting under ceiling 45
```

If live yield is thin, ops stay lower and the campaign reports shortfall honestly.

## Reporting

Reuse V2-9.8B.4 blocked-supply / campaign-activity reporting:

- `campaign_source_calls` from durable ledger
- candidate eligibility / rejection reasons including
  `LIQUIDITY_BELOW_SELECTION_FLOOR` and
  `LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN`
- `required_token_capacity=2` vs observed/eligible counts

Optional diagnostics fields (no second owner):

```text
collection_rounds_configured
confirmed_this_cycle
front_door_market_calls
front_door_cooldown_skips
combined_reserve_count
```

## Implementation plan

1. Migration `043_graduated_market_floor_state.sql` for the revalidation table.
2. Small registry/front-door helpers:
   - load/skip/record market floor state
   - cooldown classification
3. `run_graduated_liquidity_front_door`: honor cooldown skip; record outcomes.
4. `operational_memory_factory_command`: pass frozen E.46B supply kwargs.
5. Keep `build_graduated_supply` defaults fixture-friendly; production overrides
   via kwargs only (or share one constant used by production + pilot).
6. Focused disposable tests for the 15 proof points in the operator prompt.
7. No production run.

## Hard locks preserved

- Solana memecoin-only, paper-only
- two-token requirement
- fresh exact-PumpSwap-pool liquidity ≥ `$3,000`
- exact mint/pool and holder-evidence rules
- source ceiling 45
- Source Governor and Central Scheduler
- deterministic non-ranked selection
- no scoring, ranking, confidence, weights, provider racing, broad retries,
  endpoint rotation, automatic restart/successor, wallets, funds, retrieval,
  decisions, positions, trades, audits, or PnL

## Stop conditions before implementation

Stop and report a blocker if implementation appears to require:

- raising admission ceiling 45
- lowering `$3,000` or two-token rules
- a second graduated registry or ranked selector
- whole-table source re-accounting
- live production campaign execution during proof

None of those are required by this design.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Mitigation |
|---|---|
| Three migration rounds still thin in live market | Honest shortfall remains valid terminal |
| Cooldown hides a recovered pool for up to 1h | Fresh revalidation after expiry; 3600s is campaign-scale, not permanent exile |
| Production kwargs drift from pilot | Share one constant map |
| Migration 043 on operational DB | Apply only through normal migrate path; tests use disposable DB |
| Locator source cost | One call; rediscovery only; optional productivity, not graduation authority |

## Design decision

Proceed to implementation under this minimum design.
