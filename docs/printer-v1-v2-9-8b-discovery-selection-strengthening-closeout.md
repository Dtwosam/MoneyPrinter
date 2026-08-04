# Printer V1 V2-9.8B Discovery and Selection Strengthening Closeout

Date: 2026-08-03

Lane:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

## Implementation verdict

```text
V2_9_8B_DISCOVERY_SELECTION_STRENGTHENING_IMPLEMENTATION_PASS
```

## Starting baseline

| Item | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Required HEAD | `b26e9aa96fb93f4a503a590ea8e8e1f51689451b` |
| Subject | `Remove separate 15m readiness prerequisite` |
| Tracked tree | Clean at start |
| Untracked left untouched | Migration-050 package; prior auth `V2_9_8B_WINDOW_15M_AUTH_20260804T005013Z` |
| `/private/tmp/mp-preclaim` | Untouched |

## Latest execution evidence inspected (offline)

```text
20260804T005054Z-b7e4d39744aa
```

| Fact | Value |
| --- | --- |
| Terminal | `SOURCE_VISIBILITY_SHORTAGE` |
| Eligible | 0 / required 2 |
| Unique tokens | 34 |
| Fresh market checks | 27 |
| Liquidity `LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL` | 21 |
| Liquidity `LIQUIDITY_EXACT_BELOW_FLOOR` | 6 |
| Rejection `LIQUIDITY_SOURCE_dexscreener_malformed_fixture` | 21 |
| Pre-source tracking exclusions | 7 (2 duplicate active, 5 terminal) |
| Source ops used / remaining | 30 / 0 |
| Last stop | `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` |
| Root cause of 21 “malformed” rows | HTTP 200 exact-pair responses with `pairs_field_type=NULL` misclassified as `dexscreener_malformed_fixture` |

No providers were contacted during inspection or implementation.

## Phase 1 — Current-wiring classification

Operational chain owners (unchanged; no parallel engine):

| Stage | Canonical owner | Classification |
| --- | --- | --- |
| Source nomination | Combined discovery / graduated registry + DexScreener fresh-profile + Pump/PumpSwap governed paths | `ALREADY_CORRECT` |
| Candidate normalization | Source adapters + candidate acquisition foundation | `ALREADY_CORRECT` |
| Durable reserve | `printer_candidate_reserve` / eligible-token supply reserve | `ALREADY_CORRECT` |
| Duplicate / re-entry | Tracking handoff + STNP/cooldown + market-floor cooldown | `ALREADY_CORRECT` |
| Validation planning | Persistent eligible supply multi-round walk + front-door batch | `ALREADY_CORRECT` |
| Liquidity evidence | `enrich_pool_liquidity` → DexScreener exact-pair via Source Governor | **`DEFECTIVE`** (null/empty no-match path) |
| Holder / safety | Post-liquidity holder reserve only | `ALREADY_CORRECT` |
| Final eligibility | Front-door + supply gates ($3k floor intact) | `ALREADY_CORRECT` |
| Neutral selection | `selection_authority.select_two_candidates` | `ALREADY_CORRECT` |
| Scheduler / tracking handoff | Central Scheduler ownership + handoff compatibility | `ALREADY_CORRECT` |
| Lifecycle entry | Authoritative campaign after two eligible | `ALREADY_CORRECT` |

Requirement matrix:

| ID | Topic | Classification | Notes |
| --- | --- | --- | --- |
| A | DexScreener exact-pair `pairs` contract | **`DEFECTIVE` → repaired** | Live: `pairs:null` + HTTP 200 treated as malformed |
| B | Canonical multi-source nomination | `ALREADY_CORRECT` | Single reserve; provenance merge; no new provider |
| C | Token vs market identity | `ALREADY_CORRECT` | Mint/pool identities; one mint per slot |
| D | State-aware local triage | `ALREADY_CORRECT` | Pre-source tracking exclusions; below-floor cooldown skips network |
| E | Migration / revival / resurface | `ALREADY_CORRECT` | Existing categorical paths; no new protocol variants |
| F | Cheap-to-expensive planner | `ALREADY_CORRECT` | Local/tracking before market; holder only on survivors |
| G | Durable reserve multi-round | `ALREADY_CORRECT` | Campaign continues until capacity/budget/duration |
| H | Terminal truth / funnel accounting | **Partial defect via A** | Malformed count inflated visibility shortage; fixed with A |
| I | Neutral selection + atomic handoff | `ALREADY_CORRECT` | Seeded deterministic; mint/pair distinctness |

No `BLOCKED_BY_CONTRACT` requiring separate approval. No new schema, provider, protocol layout, or budget increase.

## Phase 2 — Exact defects repaired

### A. DexScreener exact-pair response correction

Owner: `src/printer_v1/sources/dexscreener.py`

For **exact-pair** request kinds only (`pair_market_snapshot` and pair-snapshot aliases; not search/fresh-profile):

| Input | After repair |
| --- | --- |
| `pairs: []` | Lawful no-match → `PARTIAL` / `ACCEPTABLE_PARTIAL_DATA` |
| `pairs: null` | Lawful no-match → same |
| Missing `pairs` **with** success envelope (`schemaVersion` or HTTP 200) | Lawful no-match → same |
| Missing `pairs` **without** envelope | Still malformed |
| string / object / number / boolean `pairs` | Still malformed |
| HTTP / rate-limit / timeout / decode / byte-ceiling / transport failures | Unchanged distinct classifications |

Lawful no-match payload includes:

* empty `pairs` list (no fabricated liquidity)
* `no_matching_pairs` + exact reason
* bounded `pairs_field_present` / `pairs_field_type` / transport diagnostics
* complete measured transport / Source Governor lineage
* **no** failure row

### Companion: liquidity classification

Owner: `src/printer_v1/discovery/graduated_liquidity_front_door.py`

`enrich_pool_liquidity` now maps lawful PARTIAL no-match to:

* reason `LIQUIDITY_NO_EXACT_PAIR`
* category `LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH`
* not `LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL`
* not a provider-failure lineage

## Behavior already correct and left unchanged

* $3,000 liquidity floor
* Holder / safety gates and ordering
* Neutral selection (no scores/ranks/magnitude/provider order)
* Multi-source canonical reserve and identity merge
* Pre-source local triage (duplicate active, terminal tracking, cooldowns)
* Below-floor one-hour revalidation cooldown
* Migration/revival contracts without new protocol guessing
* Source Governor + Central Scheduler ownership
* No retrieval / paper decision / BUY-SELL-HOLD / wallet unlock
* No source budget increase, retries, or new providers
* 1h / 4h / 12h / 24h paths unmodified

## Files changed

| Path | Role |
| --- | --- |
| `src/printer_v1/sources/dexscreener.py` | Exact-pair no-match contract |
| `src/printer_v1/discovery/graduated_liquidity_front_door.py` | Liquidity no-match classification |
| `tests/test_v2_9_8b_dexscreener_pairs_schema_diagnostics.py` | Updated matrix |
| `tests/test_v2_9_8b_selective_1h_liquidity_evidence_repair.py` | Empty/null → exact-pair unavailable |
| `tests/test_v2_9_8b_discovery_selection_strengthening.py` | New focused strengthening suite |
| `docs/printer-v1-v2-9-8b-discovery-selection-strengthening-closeout.md` | This closeout |

## Focused checks

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_discovery_selection_strengthening.py \
  tests/test_v2_9_8b_dexscreener_pairs_schema_diagnostics.py \
  tests/test_v2_9_8b_selective_1h_liquidity_evidence_repair.py \
  -q --tb=short
# 38 passed

.venv/bin/python -m compileall -q \
  src/printer_v1/sources/dexscreener.py \
  src/printer_v1/discovery/graduated_liquidity_front_door.py \
  tests/test_v2_9_8b_discovery_selection_strengthening.py \
  tests/test_v2_9_8b_dexscreener_pairs_schema_diagnostics.py \
  tests/test_v2_9_8b_selective_1h_liquidity_evidence_repair.py

git diff --check
```

Related regression sample (unchanged foundation; one pre-existing unrelated migration pin failure in candidate-acquisition foundation test against migration 050): liquidity front-door, blocked-supply reporting, eligible supply architecture, selection authority, DexScreener disabled adapter — no new failures from this change set.

Covered scenarios include: empty/null pairs lawful no-match; malformed pair shapes; non-exact-pair null still failed; enrich no-match ≠ malformed; floor unchanged; below-floor exclusion; neutral selection order-independence; two distinct mints; one mint cannot occupy two slots.

## Remaining blockers

None for implementation PASS.

Live success is still market/source dependent: two simultaneously eligible tokens at ≥ $3,000 with holder/safety pass under declared ceilings. Honest pre-lifecycle shortage remains allowed.

## What remains locked

* No liquidity floor change
* No holder/safety bypass
* No fabricated eligibility
* No budget inflation, retries, or new sources
* No Source Governor / Scheduler bypass
* No manual candidate injection / second discovery engine
* No 1h/4h/12h/24h modification
* No retrieval / paper decision / trade / wallet surfaces
* No push

## Next steps (authorized by this prompt after PASS)

1. Fresh one-use `WINDOW_15M` authorization bound to the new HEAD (no readiness artifact).
2. Exactly one real wrapper application.
3. Live-result closeout commit.
