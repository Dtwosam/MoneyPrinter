# V2-9.8B.21 — Eligible Token Supply Architecture Design

**Lane:** V2-9.8B.21  
**Authority inputs:**  
- `docs/printer-v1-v2-9-8b-eligible-token-supply-architecture-audit.md`  
- `docs/printer-v1-memory-growth-build-order-v2.md`  
- `AGENTS.md` / Clean Master Spec / Python Builder Guide  

**Verdict:** `V2_9_8B_21_ELIGIBLE_TOKEN_SUPPLY_ARCHITECTURE_DESIGN_PASS`

---

## 1. Goal

Make discovery and selection **complete within the governed reachable universe**:

* if ≥1 eligible token exists, Printer finds ≥1;
* if ≥2 eligible distinct tokens exist, Printer finds and selects 2;
* discovery continues inside one authorized campaign until capacity or proven
  exhaustion;
* shortage terminals carry an honest exhaustion certificate and classification.

Do **not** lower eligibility, admit one token into a two-token campaign, raise
the operation ceiling without separate proof, create automatic retries, or unlock
financial capabilities.

---

## 2. Completeness invariants (normative)

```text
ELIGIBLE_ONE_COMPLETENESS
ELIGIBLE_CAPACITY_COMPLETENESS
PERSISTENT_DISCOVERY_UNTIL_CAPACITY
HONEST_EXHAUSTION
```

Completeness is claimed **only** for the governed reachable universe of approved
free sources under active operation/duration ceilings. Completeness is **not**
claimed during genuine provider unavailability or outside approved channels.

---

## 3. Six-candidate boundary (clarified ownership)

| Bound | Owner parameter | Architectural role |
|---|---|---|
| Migration verify batch | `max_candidates = 5` | Cap newly on-chain-verified graduations per migration composition |
| Market evaluation batch | `front_door_max_candidates = 6` | Cap **one** exact-pool market-enrichment evaluation batch |
| Final selection set | required capacity 2 | Exactly two distinct eligible tokens after capacity is met |

**Rule:** Printer may run **multiple** deduplicated evaluation batches inside one
campaign while preserving a campaign eligible reserve. The six-candidate bound
never means “inspect only six tokens then declare market insufficient.”

---

## 4. Canonical Eligible Token Supply service

### 4.1 Module

```text
src/printer_v1/discovery/eligible_token_supply.py
```

Single owner for:

* inventory load / field-level freshness views;
* durable eligible reserve;
* persistent multi-round discovery loop;
* exhaustion certificate construction and persistence;
* shortage classification.

Existing owners remain authoritative for their stages:

| Stage | Existing owner |
|---|---|
| Migration + verify | `run_direct_migration_discovery` |
| Registry | `pumpswap_graduated_registry` |
| Exact-pool market | `run_graduated_liquidity_front_door` |
| Carrier composition | `build_graduated_supply` (becomes thin orchestrator over the service) |
| Deterministic two-token selection | front-door combined reserve + holder funnel |

### 4.2 Durable tables (migration 046)

#### `printer_eligible_token_reserve`

Campaign-surviving eligible reserve (policy-gated). One row per mint.

Key columns:

* `mint_identity` PK (FK → graduated registry)
* `pumpswap_pool`, `market_identity`, `provenance`
* `liquidity_usd`, `liquidity_status`
* `eligibility_status` ∈ {`ELIGIBLE_FRESH`, `ELIGIBLE_STALE`, `REMOVED`, `EXCLUDED`}
* `last_validated_at`
* `source_provenance`
* `last_campaign_id`
* `created_at`, `updated_at`

A token is never treated as fully stale merely because one evidence field needs
revalidation. Selection requires a **fresh** full eligibility pass in the current
campaign loop (exact pool + floor + cooldown gates).

#### `printer_discovery_exhaustion_certificates`

Durable certificate rows when discovery ends with fewer than two eligible tokens.

---

## 5. Inventory evidence model

Inventory is the durable graduated registry plus market-floor state plus reserve.

Field domains tracked (status + last validation time where available):

| Domain | Source of truth |
|---|---|
| mint identity | graduated registry |
| graduation confirmation | graduated registry lifecycle + evidence hash |
| migration provenance | registry migration fields |
| exact PumpSwap pool | registry pool + market_identity |
| pool lifecycle | registry lifecycle_state |
| liquidity | market floor state / last front-door check |
| market activity | pair payload presence on last market check |
| cooldown | market floor `cooldown_until` + STNP rotation tables |
| exclusion | reserve exclusion / rejection reasons |
| source provenance | discovery_channel / path labels |

**Partial staleness rule:** revalidate only the domains that are due; do not
discard graduation facts when only liquidity is due for recheck.

---

## 6. Eligible reserve rules

The reserve must:

1. preserve eligible candidates found in earlier discovery rounds;
2. survive campaign boundaries where policy permits (durable table);
3. revalidate stale entries before selection;
4. remove entries that no longer pass eligibility;
5. retain valid unselected candidates for later bounded use;
6. never allow rejected or stale tokens to consume eligible capacity;
7. never allow support-only 5m evidence to establish eligibility by itself.

Eligible capacity count = number of **distinct** mints currently
`ELIGIBLE_FRESH` after revalidation in the active campaign loop.

---

## 7. Persistent discovery loop (same campaign)

```text
1. Load current eligible reserve.
2. Revalidate stale reserve entries (governed exact-pool checks as needed).
3. If eligible_reserve_count >= 2: stop discovery; enter deterministic selection.
4. Else request a new bounded candidate batch:
   a. Prefer unexplored graduated inventory not yet evaluated this campaign.
   b. Skip active below-floor cooldown mints without Dex spend.
   c. Deduplicate against current round, earlier rounds, inventory, reserve,
      selected tokens, cooldown/exclusion sets.
   d. If inventory unexplored is empty and migration budget remains, allow one
      additional bounded migration intake (does not create a new campaign).
5. Validate each candidate (mint, graduation, exact pool, freshness, liquidity,
   activity evidence presence, cooldown, all existing eligibility gates).
6. Add eligible candidates to the campaign-level reserve.
7. Preserve eligible candidates across further rounds.
8. Continue while all of:
   - eligible_reserve_count < 2
   - lawful discovery source operations remain (with holder headroom)
   - campaign duration remains (when deadline provided)
   - approved channels remain usable
   - new unique supply remains reachable
9. Stop immediately once two distinct freshly eligible candidates are available.
10. Pass exactly two through existing deterministic non-ranked selection and
    tracking-handoff path.
```

Rejected candidates never end discovery while lawful unexplored work remains.

**No** retry, restart, successor campaign, second operator approval, or automatic
second production run is created.

### 7.1 Integration point

`build_graduated_supply` becomes the composition entry that calls:

```text
run_persistent_eligible_token_supply(...)
```

and returns the existing `GraduatedSupply` shape so operational admission,
holder funnel, and terminal reporting stay compatible.

---

## 8. Source-budget allocation

* Lifecycle-wide governed ceiling remains **45**.
* Default discovery-phase budget: **30** ops (reserve ~15 for holder/handoff).
* Stop source use immediately once two eligible tokens are confirmed.
* Prefer unexplored candidates over re-checking known below-floor/cooldown mints.
* Complete already-started candidate evidence before opening excessive new
  candidates.
* Never bypass Source Governor.
* No scoring, ranking, confidence, weighted selection, predicted profitability,
  or hidden prioritization.
* Ordering remains deterministic seeded-uniform / identity-stable non-ranked.

If a future audit separately proves the ceiling makes completeness impossible,
that is a **different** approved lane. This design does not raise 45.

---

## 9. Exhaustion certificate schema

Emitted whenever discovery ends with `eligible_reserve_count < 2`.

```text
campaign_id / execution_id / run_id / cycle_id
required_eligible_capacity
eligible_reserve_count
approved_discovery_channels_attempted[]
channels_unavailable[]
unique_tokens_observed
duplicate_observations_removed
tokens_already_known_from_inventory
pools_confirmed
fresh_market_checks
eligible_count
rejected_count
rejection_reasons{}          # exact categorical reasons
cooldown_skips
stale_evidence_exclusions
provider_failures
source_operations_used
source_operations_remaining
duration_used_seconds
duration_remaining_seconds
unexplored_work_prevented_by_hard_ceiling
last_reason_discovery_could_not_continue
shortage_classification
certificate_version
created_at
```

**Invalid certificate:** result based only on one five- or six-token batch while
ops remain and unexplored inventory remains.

### 9.1 Shortage classification

Exactly one of:

```text
TRUE_MARKET_SUPPLY_SHORTAGE
SOURCE_VISIBILITY_SHORTAGE
SOURCE_AVAILABILITY_FAILURE
BUDGET_EXHAUSTION
DURATION_EXHAUSTION
STALE_EVIDENCE_SHORTAGE
DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE   # must not be emitted post-repair under normal path
```

Classification rules (priority order for emission):

1. provider failures blocked all remaining channels → `SOURCE_AVAILABILITY_FAILURE`
2. duration deadline reached → `DURATION_EXHAUSTION`
3. discovery op budget / lifecycle ceiling reached → `BUDGET_EXHAUSTION`
4. only stale evidence left and revalidation could not refresh → `STALE_EVIDENCE_SHORTAGE`
5. all reachable unique candidates evaluated; channels exhausted; <2 eligible →
   `TRUE_MARKET_SUPPLY_SHORTAGE` (or `SOURCE_VISIBILITY_SHORTAGE` when channels
   were available but returned no additional unique graduated supply)
6. otherwise internal fault → `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` (fail closed)

Provider unavailability must never be reported as true market insufficiency.

---

## 10. Legitimate stop conditions below capacity

Discovery may stop with fewer than two eligible tokens only when one or more of:

* all approved discovery channels exhausted;
* all reachable candidates deduplicated and evaluated;
* governed discovery/lifecycle operation ceiling reached;
* campaign duration ceiling reached;
* providers unavailable;
* no additional unique candidates reachable;
* fewer than two eligible tokens genuinely existed in the governed reachable
  universe.

---

## 11. Deterministic selection and handoff

Once `eligible_reserve_count >= 2`:

1. Build combined eligible set from freshly validated reserve members.
2. Use existing `combined_reserve_order` / holder funnel path.
3. Select exactly two distinct tokens (non-ranked, seeded-uniform).
4. Hand off through existing operational tracking path.
5. Do not auto-activate unselected reserve members.

---

## 12. Reporting compatibility

Blocked-supply terminal continues to use
`BLOCKED_INSUFFICIENT_GRADUATED_POOL` when capacity is unmet **and** an exhaustion
certificate proves legitimacy.

Extend terminal reporting package with:

```text
exhaustion_certificate: { ... }
shortage_classification: <enum>
discovery_rounds: N
eligible_reserve_count: N
```

Do not invent a second source-accounting owner. Stage-local ledgers remain.

---

## 13. Disposable proof matrix (required)

Fixture sources and disposable SQLite only. Minimum proofs:

1. One eligible after many below-floor still discovered  
2. Two eligible outside first six raw observations discovered and selected  
3. Eligible at positions 7 and 19 found in one campaign  
4. Round-1 eligible preserved until later round finds second  
5. First batch with one eligible does not terminalize while capacity remains  
6. Heavy cross-channel duplicates do not consume unique capacity  
7. Known below-floor pools do not repeatedly consume budget  
8. Cooldown-heavy inventory does not block fresh exploration  
9. Persisted reserves survive campaign boundaries and revalidate  
10. Stale reserve cannot enter selection without revalidation  
11. Failed/incomplete evidence cannot enter selection  
12. Two eligible anywhere in modeled universe ⇒ not `BLOCKED_INSUFFICIENT_GRADUATED_POOL`  
13. Only one eligible ⇒ complete honest exhaustion certificate  
14. Provider failure classified separately  
15. Budget exhaustion classified separately  
16. Duration exhaustion classified separately  
17. Selection deterministic and non-ranked  
18. Exactly two distinct eligible enter tracking handoff path  
19. Operation ceiling enforced  
20. Source Governor / Scheduler not bypassed  
21. Integrity `ok`  
22. FK violations zero  
23. No active campaign/discovery/factory/queue/slot/lease/Scheduler residue  
24. Retrieval/financial table deltas zero  
25. No automatic retry/restart/successor  

Adversarial scenarios included in the same suite.

---

## 14. Hard locks

All V1 / V2 policy locks from the operator prompt remain in force. Especially:

* no production run in this lane;
* no live sources in disposable proof;
* no BUY/SELL/HOLD, retrieval, positions, trades, audits, PnL;
* no automatic retry/restart/successor;
* no floor or capacity reduction.

---

## 15. Implementation plan

1. Migration `046_eligible_token_supply.sql`  
2. `eligible_token_supply.py` service (inventory, reserve, loop, certificate)  
3. Front door: `exclude_mints` / unexplored-batch selection  
4. `build_graduated_supply` multi-round orchestration  
5. Exhaustion certificate into blocked-supply reporting  
6. Disposable proof suite + discovery/selection regressions  
7. Commit implementation; closeout + readiness review; final commit  

---

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Mitigation |
|---|---|
| Multi-batch Dex spend | Stop at two eligible; skip cooldowns; discovery budget 30 |
| Stale cross-campaign reserve | Forced revalidation before selection |
| True thin market after honest work | Certificate + TRUE_MARKET / VISIBILITY classes |
| Regression of single-batch tests | Keep `front_door_max_candidates` as batch size; loop is outer |
| Ceiling 45 too tight after holder | Discovery budget reserves headroom; separate lane if proven insufficient |
