# Printer V1 V2-9.8B Strengthened Discovery Operation-Budget Exhaustion Audit

Date: 2026-08-04

Lane:

```text
V2-9.8B — Strengthened Discovery/Selection Live Attempt Root-Cause Audit
```

Mode: **audit-only** (read-only DB + existing artifacts; no providers, no repair, no production/test mutation).

## Starting point (verified before work)

| Item | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Full HEAD SHA | `d1fded597e2741559bc1c84bbba2854fe8ce0c23` |
| Short SHA | `d1fded5` |
| Subject | `Close strengthened 15m attempt` |
| Tracked tree | Clean |
| Intentionally untracked | `operator-runs/v2-9-8b-authoritative-mig050/` (Migration-050 package) |
| `/private/tmp/mp-preclaim` | Untouched |

## Audit verdict

```text
V2_9_8B_DISCOVERY_OPERATION_BUDGET_AUDIT_PASS_ROOT_CAUSE_PROVEN
```

## Market-shortage determination (exactly one)

```text
MIXED_OPERATIONAL_CAUSES
```

Dominant mixture (ordered):

1. **Stale persisted inventory + repeated recent exact-pair no-match rechecks** burned most of the 30-operation ceiling.
2. **Operation budget exhausted before governed universe exhaustion** (`unexplored_work_prevented_by_hard_ceiling=true`; 11 registry mints never evaluated).
3. **Fresh nomination productivity was weak this cycle** (migration page empty; locator did not add newly confirmed PumpSwap inventory into the evaluated set).
4. **Not** validation-ordering failure; **not** tracking-block waste; **not** proven genuine absence of two eligible tokens across the full inventory.

---

## Evidence sources

### Artifacts (existing only)

| Surface | Path |
| --- | --- |
| Campaign report | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260804T014608Z-ee2e19ddcf60/reports/20260804T014608Z-ee2e19ddcf60-report.campaign-report.json` |
| Terminal summary | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260804T014608Z-ee2e19ddcf60/terminal-summary.json` |
| Wrapper application | `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z/` |
| Prior attempt report | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260804T005054Z-b7e4d39744aa/reports/…-report.campaign-report.json` |
| Strengthening closeout | `docs/printer-v1-v2-9-8b-discovery-selection-strengthening-closeout.md` |
| Live attempt closeout | `docs/printer-v1-v2-9-8b-strengthened-discovery-window-15m-attempt-closeout.md` |
| Authoritative DB (RO) | `data/printer_v1.sqlite3` |

### Identity under audit

| Field | Value |
| --- | --- |
| Authorization | `V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z` |
| Execution | `20260804T014608Z-ee2e19ddcf60` |
| Campaign | `20260804T014608Z-ee2e19ddcf60-campaign` |
| Run | `20260804T014608Z-ee2e19ddcf60-campaign-run` |
| Implementation SHA at run | `0ab3fa33e580cbe1c55e3a6bfd2b318edd93aa6c` |
| Terminal | `PRE_LIFECYCLE_OPERATION_BUDGET_EXHAUSTED` / `BUDGET_EXHAUSTION` |
| First stop reason | `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` |
| Lifecycle / factory / `WINDOW_15M` | none / not_found / 0 |

### Preceding attempt (comparison)

| Field | Prior `20260804T005054Z-b7e4d39744aa` | This attempt |
| --- | --- | --- |
| Terminal shortage | `SOURCE_VISIBILITY_SHORTAGE` | `BUDGET_EXHAUSTION` |
| Malformed liquidity | 21 | **0** |
| Exact-pair no-match | 0 (misclassified) | **22** |
| Provider failures | 22 | **0** |
| Below floor | 6 | 6 (+2 cooldown skips) |
| Tracking blocks | 7 | 7 |
| Source ops used | 30 | 30 |
| Eligible | 0 | 0 |

Strengthening repair is live-confirmed: null-pair exact snapshots are lawful `PARTIAL` / `LIQUIDITY_NO_EXACT_PAIR`, not provider malformation.

---

## 1. Exact source-operation ledger

### Reconciliation (no material discrepancy)

| Counter | Value | Notes |
| --- | --- | --- |
| Campaign source-operation count | **30** | Report `campaign_source_calls` / cert `source_operations_used` |
| `SOURCE_TRANSPORT_OPERATION` | **31** | Six-unit evidence; **expected** +1 vs campaign ops |
| `printer_source_requests` this run | **30** | IDs `1847`–`1876` |
| `printer_source_responses` this run | **30** | One response per request |
| `printer_source_failures` this run | **0** | Matches provider_failures=0 |
| Fresh market checks | **28** | Exact-pair snapshots only |
| Exhaustion certificate ops | 30 used / 0 remaining | Matches campaign report |
| Candidate evaluation rows | **37** | Report `candidates_validated` |

**Why 30 campaign ops vs 31 transports:**  
`ops_used = locator.source_requests(1) + migration.source_requests(1) + market_calls(28)`.  
The DexScreener fresh-profiles locator is **one** governed source request that expands to **two** atomic transports (`GET /token-profiles/latest/v1` + `GET /tokens/v1/solana/{mints}`). Six-unit accounting correctly counts both transports.

### Chronological ledger (31 transports / 30 campaign ops)

| Ord | Campaign op? | Source | Request kind | Target | Stage | Result | Led to more work? | Avoidable? |
| ---: | :---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Yes (req 1847, part 1/2) | dexscreener | `dexscreener_fresh_profiles` | fresh profiles | DEXSCREENER_DISCOVERY | OK, 26 rows, 23728 B | Yes → token batch | No (channel attempt) |
| 2 | (same req 1847) | dexscreener | `dexscreener_fresh_profiles` | token pairs | DEXSCREENER_DISCOVERY | OK, 26 rows, 33599 B | Feeds locator payload | No |
| 3 | Yes (req 1848) | solana_rpc | `restored_pump_migration_signature_page` | pump program | DIRECT_PUMP_NOMINATION | OK, **0 signatures** | No new mints | No (channel attempt) |
| 4–31 | Yes (req 1849–1876) | dexscreener | `dexscreener_pair_snapshot` / `pair_market_snapshot` | exact PumpSwap pool | DEXSCREENER_DISCOVERY | 22× null pairs PARTIAL; 6× COMPLETE with liq | Rejection only | **16 of 22 no-match rechecks** (see §3) |

Round structure of exact-pair calls (from `request_key` `…-rN-liq-…`):

| Round | Pair snapshots | Notes |
| ---: | ---: | --- |
| 1 | 6 | first evaluation batch |
| 2 | 6 | |
| 3 | 6 | |
| 4 | 5 | |
| 5 | 4 | |
| 6 | 1 | final op before budget hit 0 |

Discovery rounds reported: **6**. Budget after locator+migration leaves 28 exact-pair slots; all 28 consumed.

### Ops → candidate disposition map (compact)

| Campaign ops | Disposition class | Count | Source requests |
| --- | --- | ---: | --- |
| 1 | Fresh-profile locator | 1 logical | 1847 |
| 1 | Pump migration tail | 1 | 1848 |
| 22 | Exact-pair no-match → `LIQUIDITY_NO_EXACT_PAIR` | 22 | 1849–1852,1854–1855,1857–1858,1860–1863,1865–1872,1875–1876 |
| 6 | Exact pair visible → below $3k floor | 6 | 1853,1856,1859,1864,1873,1874 |
| 0 | Tracking-blocked (7) | 7 cands | none |
| 0 | Below-floor cooldown skip (2) | 2 cands | none |

No holder/safety/RPC protocol calls after liquidity rejection. Deepest validation stage reached: **`LIQUIDITY_FLOOR_FAILED`** (6 candidates). Eligible: **0**.

---

## 2. Tracking-blocked candidates (7)

All seven consumed **zero** source/transport operations. Blocking state was local and known before any liquidity call.

| Mint | Pool | Reason | Local state facts | Known before live call? | Ops | Class |
| --- | --- | --- | --- | --- | ---: | --- |
| `UUdf…pump` | `7PZL…` | `DUPLICATE_ACTIVE_TRACKING` | Token TRACK_NORMAL; queue QUEUED; campaign slot SELECTED (2026-07-27) still non-terminal | Yes | 0 | `CORRECTLY_FILTERED_BEFORE_SOURCE_WORK` |
| `7tKK…pump` | `Gocs…` | `DUPLICATE_ACTIVE_TRACKING` | Same pattern; slot 2 of same campaign | Yes | 0 | `CORRECTLY_FILTERED_BEFORE_SOURCE_WORK` |
| `3BTS…pump` | `5E8R…` | `TERMINAL_TRACKING_STATE` | Slot MANUAL_REVIEW / `LEASE_RENEWAL_UNCONFIRMED…`; queue SKIPPED | Yes | 0 | `CORRECTLY_FILTERED_BEFORE_SOURCE_WORK` |
| `DqLo…pump` | `7vQ1…` | `TERMINAL_TRACKING_STATE` | Same campaign terminal pair | Yes | 0 | `CORRECTLY_FILTERED_BEFORE_SOURCE_WORK` |
| `Av2c…` | `REUd…` | `TERMINAL_TRACKING_STATE` | Latest slot MANUAL_REVIEW `OPERATIONAL_CAMPAIGN_FAILED:KeyError`; queue SKIPPED | Yes | 0 | `CORRECTLY_FILTERED_BEFORE_SOURCE_WORK` |
| `5iRB…pump` | `DLV5…` | `TERMINAL_TRACKING_STATE` | MANUAL_REVIEW `LEASE_RENEWAL_SQLITE_LOCKED` | Yes | 0 | `CORRECTLY_FILTERED_BEFORE_SOURCE_WORK` |
| `2C3C…` | `AR4e…` | `TERMINAL_TRACKING_STATE` | Same KeyError terminal pattern as Av2c | Yes | 0 | `CORRECTLY_FILTERED_BEFORE_SOURCE_WORK` |

Block nature:

| Kind | Count | Permanent market ban? |
| --- | ---: | --- |
| Active-duplicate (state / already-selected tracking) | 2 | No — identity currently owns a non-terminal tracking posture |
| Terminal tracking / MANUAL_REVIEW residue | 5 | State-based terminal for re-entry; not a permanent venue ban |

**Conclusion:** tracking pre-filter worked. **No** source budget was wasted on blocked candidates. These are **not** the dominant cause of budget exhaustion.

---

## 3. Exact-pair no-match population (22)

All 22:

* Venue: **PumpSwap** (`solana-mainnet:pumpswap:…`, program `pAMMBay…`).
* Nomination/source_path: **`graduated_registry_or_migration:PERSISTED_GRADUATED`** (durable registry, not fresh live nomination).
* Observation: DexScreener exact-pair HTTP envelope with **`pairs: null`** → lawful PARTIAL `source_returned_null_pairs`.
* Floor state after: `LIQUIDITY_UNPROVEN`, **`cooldown_until = NULL`** (no no-match suppression).

### Grouping

| Group | Count | Basis |
| --- | ---: | --- |
| `REPEATED_RECENT_NO_MATCH` (+ `STALE_PERSISTED_POOL`) | **16** | Same mint/pool rejected ~55 minutes earlier in prior attempt as `LIQUIDITY_SOURCE_dexscreener_malformed_fixture` (same null-pairs underlying fact; pre-repair label) |
| `STALE_PERSISTED_POOL` (not in prior attempt candidate set) | **6** | Still registry-persisted PumpSwap pools; first_observed mostly 2026-07-26…07-28; not fresh nominations |

No evidence classification used for silent pool substitution. No migration/revival event rows tied to these 22 during this campaign. Some historically had COMPLETE exact-pair rows (e.g. 2026-07-31) then later null — consistent with indexer loss / pair disappearance, not proven on-chain migration in this evidence set.

### Representative table (all 22)

| Mint (prefix) | Pool (prefix) | This req | Prior attempt | Class |
| --- | --- | ---: | --- | --- |
| Fesow6… | 4zZ5… | 1849 | not in prior set | STALE_PERSISTED_POOL |
| CKVkBH… | 4U7X… | 1850 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| EgjSyM… | Cj82… | 1851 | not in prior set | STALE_PERSISTED_POOL |
| 12u9FU… | ECob… | 1852 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 7S4XmH… | BDBB… | 1854 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 6PfEWg… | 59HQ… | 1855 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| dwfwK9… | DJCY… | 1857 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 23Z8qs… | 6Nge… | 1858 | not in prior set | STALE_PERSISTED_POOL |
| 3dQoup… | 9Xtx… | 1860 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| FQmF2C… | DbDd… | 1861 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 4G5y3x… | 6x9z… | 1862 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| aQVkmu… | 2nTe… | 1863 | not in prior set | STALE_PERSISTED_POOL |
| F9fAYJ… | BY3Y… | 1865 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 23d5qF… | 9TYz… | 1866 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 2vLNEm… | 7dWP… | 1867 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 4hi84N… | 9G3n… | 1868 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| AQi9C9… | DoLY… | 1869 | not in prior set | STALE_PERSISTED_POOL |
| BHeDDS… | 4ZWf… | 1870 | not in prior set | STALE_PERSISTED_POOL |
| 8QmAVA… | EJFC… | 1871 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| oFSAgc… | 5t4L… | 1872 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| 3sfFdf… | 8a3y… | 1875 | malformed_fixture | REPEATED_RECENT_NO_MATCH |
| kMnJ98… | Hvve… | 1876 | malformed_fixture | REPEATED_RECENT_NO_MATCH |

**Negative-result suppression:**  
Below-floor uses `BELOW_FLOOR_MARKET_COOLDOWN_SECONDS = 3600` via `printer_graduated_market_floor_state.cooldown_until`. Exact-pair no-match records `LIQUIDITY_UNPROVEN` with **no cooldown**. Therefore the same null-pair identity can (and did) re-consume ops within the hour. That is a **real efficiency defect**, not a provider transport failure.

---

## 4. Below-floor candidates (6 + 2 cooldown)

### Floor behavior

All six observed liquidities are **strictly below $3,000**. Floor enforcement is correct.

| Mint (prefix) | Pool (prefix) | Liq USD | Req | Source path | Fresh vs recycle | Prior (~55m) | Ops before floor | Post-floor expensive calls |
| --- | --- | ---: | ---: | --- | --- | --- | ---: | --- |
| 3dTTtU… | CmoZ… | **2374.92** | 1853 | PERSISTED | recycled inventory | not in prior set | 1 exact-pair | none |
| ASmoyD… | Gukz… | **1435.30** | 1856 | PERSISTED | recycled | not in prior | 1 | none |
| 5o2WFR… | 9hT4… | **1705.67** | 1859 | PERSISTED | recycled | not in prior | 1 | none |
| 2RL5JT… | E4fj… | **1875.79** | 1864 | PERSISTED | recycled | not in prior | 1 | none |
| HsoCTf… | 5LBS… | **1556.18** | 1873 | PERSISTED | recycled | not in prior | 1 | none |
| GLcxHM… | Uk5Z… | **2057.30** | 1874 | PERSISTED | recycled | not in prior | 1 | none |

### Cooldown skips (correct)

| Mint (prefix) | Historical liq | Status | Ops | Notes |
| --- | ---: | --- | ---: | --- |
| FWAXQX… | 1697.16 | `LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN` | 0 | Same liq as prior attempt; 1h cooldown not expired |
| CrR3AB… | 1756.87 | `LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN` | 0 | Same |

Cooldown: `record_market_floor_state` only sets `cooldown_until` when status is `LIQUIDITY_BELOW_SELECTION_FLOOR` — working as designed.

---

## 5. Nomination-source productivity

Approved channels **attempted** (hard-coded in `eligible_token_supply`):

| Channel | Ran? | Source ops | Raw productivity | Unique mint/pool into evaluated set | Eligible |
| --- | :---: | ---: | --- | ---: | ---: |
| `dexscreener_fresh_profiles_locator` | Yes | 1 req / 2 transports | 52 normalized rows in response payload | **0** of 37 evaluated cands attributed to fresh locator | 0 |
| `direct_pump_finalized_live_tail` | Yes | 1 | **0 signatures** returned | 0 new confirmed migrations | 0 |
| `exact_pump_pumpswap_graduation_verify` | Attempted path (paired with migration) | (same ledger) | no new confirmations this cycle | 0 | 0 |
| `dexscreener_exact_pool_market` | Yes | 28 | 6 visible + 22 null | 28 market-checked | 0 |

Evaluated candidate source_path mix:

| source_path | Count | Role |
| --- | ---: | --- |
| `…:LATEST_GRADUATED` | 7 | All tracking-blocked; no market ops |
| `…:PERSISTED_GRADUATED` | 30 | Entire market-check population |

Registry inventory size: **48** (`printer_pumpswap_graduated_candidate_registry`).  
`tokens_already_known_from_inventory`: **48**.

### Channels in code but not feeding this owner

* **GeckoTerminal** (and any non-listed locator): **not** in `channels_attempted` for this operational acquisition owner. Not a silent runtime failure — it is outside the wired WINDOW_15M supply path.
* Fresh DexScreener profiles **do run** but do **not** substitute for PumpSwap graduation confirmation; they did not expand the confirmed graduated inventory used for exact-pool evaluation in this execution.

**Productivity verdict:** fresh live nomination was **low-yield this cycle** (empty migration page). The campaign walked **stale confirmed inventory**, not a stream of newly graduated markets.

---

## 6. Durable reserve and multi-round behavior

| Metric | Value |
| --- | --- |
| Graduated registry at start | 48 |
| Eligible-token reserve rows | 10 (all REMOVED/EXCLUDED; none campaign-eligible) |
| Candidate-acquisition reserve | 0 |
| Discovery rounds | 6 |
| Unique evaluated | 37 |
| Eligible retained | 0 |
| Unexplored registry mints at stop | **11** |
| Source ops remaining | **0** |
| Source continuations still available? | Channels not marked unavailable; **budget** is the hard stop |
| Another lawful evaluation round possible? | **Yes**, inventory remained — blocked solely by operation ceiling |

Unexplored mints (registry present, never in the 37):  
`Be9m…`, `DoCu…`, `kvNh…`, `3zh9…`, `Ef21…`, `4TtB…`, `AkYn…`, `ApPL…`, `Ak6X…`, `2XzK…`, `G3xU…`.

Four of these were **below floor on the prior attempt** (e.g. kvNh 2604.84, ApPL 2202.55, 3zh9 1524.93, 2XzK 1867.42) — still under $3k then; unknown now, but **not** evidence of two ≥$3k eligible tokens.

### Exhaustion classification correctness

| Question | Answer |
| --- | --- |
| Correctly `BUDGET_EXHAUSTION` / `DISCOVERY_OPERATION_BUDGET_EXHAUSTED`? | **Yes** |
| Would `GOVERNED_UNIVERSE_EXHAUSTED` / `TRUE_MARKET_SUPPLY_SHORTAGE` have been correct? | **No** — `unexplored_work_prevented_by_hard_ceiling=true` and ops remaining 0 |
| Code path | `eligible_token_supply.classify_shortage`: `source_operations_remaining <= 0` → `BUDGET_EXHAUSTION` |

---

## 7. Validation ordering

Intended order:

```text
local identity/state
→ nomination quality
→ exact pool visibility
→ liquidity/activity
→ protocol/mint validation
→ holder/safety
→ final eligibility
```

### Observed (by class)

| Class | Actual order | Source after definitive reject? |
| --- | --- | --- |
| Tracking-blocked | local tracking disposition → exclude | **No** source calls |
| Exact-pair no-match | local admit → exact pair → PARTIAL null → reject | **No** further calls |
| Below floor | local admit → exact pair COMPLETE → liq USD → reject | **No** holder/safety |
| Cooldown below-floor | local floor-state cooldown → reject | **No** network |
| Deepest survivors | stop at liquidity floor | Never reached holder/safety |

**No validation-ordering defect.** No holder/RPC/safety spend after an earlier definitive rejection. The expensive waste is **repeat exact-pair probes on known-null identities**, not post-reject over-validation.

---

## 8. Pool rediscovery and identity safety

| Capability | Status |
| --- | --- |
| Rediscover current pool by mint after persisted pool disappears | **`MISSING`** as a governed acquisition path after `LIQUIDITY_NO_EXACT_PAIR` |
| Distinguish canonical migration vs unrelated second pool | STNP classifications exist in selection-batch code (`MIGRATION` / `PAIR_DRIFT` / …) but **are not invoked** as a post-no-match rediscovery owner |
| Preserve mint while changing market identity | Identity model supports mint≠pool; no automatic rewrite observed |
| STNP / cooldown / pair-drift protection on silent substitute | Exact-pool path **does not** substitute pools (correct safety) |
| Exact base/quote orientation | Enforced when pairs exist (`candidate_pair_orientation_status` on COMPLETE rows) |
| Prevent silent replacement | **Preserved** — null pair rejects; no alternate pool injected |

**Classification:**

```text
MISSING
```

More precisely: identity-safe exact-pool evaluation is operational; **governed mint→current-pool rediscovery after no-match is missing**. Adding it without STNP/migration proof would be `UNSAFE_TO_ADD_WITHOUT_DESIGN`.

---

## 9. Counterfactual operation accounting

Using only proven facts:

| Bucket | Ops | Notes |
| --- | ---: | --- |
| Already definitively tracking-blocked | **0** | Correct |
| Below-floor cooldown skips | **0** | Correct |
| Fresh nomination overhead | **2** | locator + migration (required channel attempts) |
| Fresh/meaningful later validation (below floor) | **6** | Required to learn current liq |
| Exact-pair no-match total | **22** | Dominant spend |
| Of which repeated recent no-match (≤~1h prior same identity) | **16** | **Proven avoidable under a no-match cooldown policy analogous to below-floor** |
| First-time-this-window no-match (not in prior candidate set) | **6** | Not proven avoidable without prior no-match memory |

| Counterfactual | Value |
| --- | --- |
| Ops safely avoidable (evidence-backed) | **16** |
| Ops remaining if those skipped | 16 (would cover all **11** unexplored + headroom) |
| Additional candidates evaluable within same ceiling | up to **11** unexplored inventory identities |
| Would that produce two eligible tokens? | **Not supported by evidence.** Prior readings for several unexplored mints were still &lt;$3k; no candidate in either attempt cleared floor + holder/safety. |

Do **not** raise the 30-op ceiling first: the ceiling was **inefficiently consumed**, not proven “efficient but short.”

---

## 10. Market-shortage answers

| Question | Answer |
| --- | --- |
| Reachable governed candidate universe exhausted? | **No** (11 unexplored registry mints) |
| Approved source continuations exhausted? | Channels available; **operation budget** exhausted |
| All fresh nominations exhausted? | Migration page empty this cycle; locator returned rows but did not admit new confirmed graduated inventory |
| Unexplored candidates left? | **Yes** |
| Could two eligible tokens have existed beyond the ceiling? | **Possible but unproven** |
| Does evidence prove genuine absence of two eligible tokens? | **No** |

Shortage verdict: **`MIXED_OPERATIONAL_CAUSES`** (see top).

---

## Root-cause hierarchy

### 1. Primary root cause

**Stale persisted PumpSwap inventory repeatedly exact-pair-checked under a 30-op ceiling, with no temporary suppression for recent exact-pair no-match outcomes**, so the campaign terminalized on `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` while unexplored inventory remained.

### 2. Secondary contributing causes

* Weak fresh graduation inflow this cycle (0 migration signatures).
* Fresh-profile locator not converting into confirmed graduated evaluation inventory.
* Missing governed pool-rediscovery after exact pool vanishes (cannot lawfully replace pool without design).
* Interaction of multi-round walk with FIFO/batch selection that re-touches known-bad pairs before finishing the 48-mint registry.

### 3. Symptoms (not causes)

* Terminal label `PRE_LIFECYCLE_OPERATION_BUDGET_EXHAUSTED` / `BUDGET_EXHAUSTION`.
* Zero eligible / zero lifecycle / zero factory / zero `WINDOW_15M` memory.
* 22 no-match + 6 below-floor funnel shape.
* Prior attempt’s “malformed” count (mislabel fixed; underlying null pairs remain).

### 4. Behavior that worked correctly

* Strengthening null-pair → lawful no-match (0 provider failures).
* Tracking pre-filter (7 blocks, 0 ops).
* Below-floor $3,000 gate and 1h cooldown skips.
* Validation order (no post-reject holder/safety spend).
* Exhaustion class `BUDGET_EXHAUSTION` rather than false market insufficiency.
* Exact pool identity safety (no silent substitution).
* Source Governor ownership of all provider calls; six-unit accounting complete and matched.

### 5. Exact defects (Printer)

1. **No temporary recheck suppression for exact-pair no-match / `LIQUIDITY_UNPROVEN`**, unlike below-floor (`printer_graduated_market_floor_state.cooldown_until` left null).  
   Owners: `graduated_liquidity_front_door.record_market_floor_state` / front-door admit path; consumption in multi-round `eligible_token_supply` walk.
2. **No governed mint-level pool rediscovery** after persisted pool exact-pair disappearance (design gap, not a runtime crash).

### 6. Source/provider limitations (not Printer defects)

* DexScreener exact-pair often returns `pairs: null` for aged PumpSwap pools that remain in local graduated registry.
* Pump finalized migration signature page returned **empty** this cycle (no new graduations in the polled window).
* Indexer visibility ≠ on-chain pool existence; Printer correctly refuses to fabricate pairs.

---

## Exact next action (narrowest evidence-supported)

**Design + implement a temporary exact-pair no-match / `LIQUIDITY_UNPROVEN` recheck cooldown** (mirror the existing below-floor 1h market-floor state mechanism), applied only to the **exact mint+pool** identity that produced lawful no-match, without pool substitution and without permanent exclusion.

| Field | Content |
| --- | --- |
| Owner / function | `src/printer_v1/discovery/graduated_liquidity_front_door.py` — `record_market_floor_state` + admit/cooldown check used by `run_graduated_liquidity_front_door`; multi-round consumer `eligible_token_supply.run_persistent_eligible_token_supply` |
| Current behavior | Below-floor sets `cooldown_until`; exact-pair no-match sets `LIQUIDITY_UNPROVEN` with **`cooldown_until=NULL`**, so the next campaign re-spends an op within minutes/hours |
| Required behavior | On lawful `LIQUIDITY_NO_EXACT_PAIR` / exact-pair unavailable, set a bounded cooldown (same order as below-floor, e.g. 3600s) for that mint+pool; skip network recheck until expiry; still count as evaluated/excluded with explicit reason; never substitute another pool |
| Money-usefulness | Frees ops currently wasted on known-null pairs (16/30 in this run) for unexplored inventory and any true new graduations |
| Safety invariants preserved | Exact pool identity; no silent pool replace; no floor/holder/safety weakening; no permanent ban of temporary indexer gaps; Source Governor still owns any eventual recheck |
| Minimum focused proof | Unit/integration: null-pair → cooldown written; second evaluation within window → 0 market call + cooldown reason; after expiry → one recheck allowed; below-floor path unchanged; no-match ≠ malformed |
| Still does not unlock | Memory PASS by itself; new graduation inflow; pool rediscovery; holder/safety; guaranteed two eligible tokens |

**Do not** (this audit):

* raise the 30-op ceiling first;
* lower the $3k floor;
* weaken holder/safety;
* add retries/providers/ranking;
* permanently exclude temporary no-matches;
* substitute pools without exact identity/STNP proof.

Optional **later** design (out of scope until no-match cooldown lands): governed mint→pool rediscovery under STNP/migration contracts (`UNSAFE_TO_ADD_WITHOUT_DESIGN` today).

---

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Severity | Note |
| --- | --- | --- |
| Exact-pair no-match recheck thrash | **High (efficiency)** | Dominant budget sink; 16/22 no-matches were ≤1h rechecks |
| Stale graduated registry vs DexScreener visibility | High (supply quality) | Inventory age weeks; many pools no longer indexed |
| Empty migration page this cycle | Medium | No new confirmed graduations to refresh inventory |
| Missing pool rediscovery | Medium (capability gap) | Cannot lawfully follow mint to a new pool after exact pair vanishes |
| Fresh profiles not graduating into evaluation inventory | Medium | Locator ops spent without evaluated-set expansion |
| Tracking MANUAL_REVIEW residue | Low for this terminal | Correctly blocked; separate cleanup concern for long-term inventory hygiene |
| 30-op ceiling | Not primary defect | Inefficient consumption, not proven undersized efficient walk |
| Strengthening repair regression | None observed | 0 provider failures; honest no-match path live |

---

## Candidate funnel (summary)

```text
Registry inventory                 48
Pre-source tracking exclusions      7  (0 ops)
Cooldown-floor cooldown skips         2  (0 ops)
Exact-pair market checks           28  (28 ops)
  └─ no-match                      22
  └─ below floor                    6
Holder / safety                     0
Eligible                            0
Selected / lifecycle / factory      0
Unexplored at budget stop          11
```

---

## Final statements

* Root cause of `PRE_LIFECYCLE_OPERATION_BUDGET_EXHAUSTED` for `20260804T014608Z-ee2e19ddcf60` is **proven**.
* Strengthening’s malformation fix is **not** the remaining blocker; efficiency of **post-repair no-match handling** and **stale inventory walk** are.
* Audit document only; no production, test, budget, threshold, migration, or provider changes.

```text
V2_9_8B_DISCOVERY_OPERATION_BUDGET_AUDIT_PASS_ROOT_CAUSE_PROVEN
```
