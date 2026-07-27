# V2-9.8B.21 — Eligible Token Supply and Discovery/Selection Architecture Audit

**Lane:** V2-9.8B.21  
**Document kind:** Architecture audit (read-only evidence; no production run)  
**Baseline HEAD:** `a089fff` (`Close V2-9.8B SQLite concurrency consolidation`)  
**Production execution audited:** `20260727T211548Z-5d626101ec34`  
**Audit date:** 2026-07-27  
**Verdict:** `V2_9_8B_21_ELIGIBLE_TOKEN_SUPPLY_ARCHITECTURE_AUDIT_PASS`

---

## 1. Baseline gates (pre-implementation)

| Gate | Result |
|---|---|
| Exact HEAD `a089fff` | PASS (`a089fffa8c3697e28855f4518120cb8674a573c3`) |
| Clean tracked worktree | PASS (empty `git status --porcelain`) |
| SQLite integrity | PASS (`ok`) |
| Foreign-key violations | PASS (`[]`) |
| Active campaign / supervision | PASS (all 11 campaigns terminal; all supervision `TERMINAL` with lease released) |
| Active factory / discovery work | PASS (discovery work `SUCCEEDED` only; proof supervision empty) |
| Scheduler active jobs | PASS (no `PENDING`/`RUNNING` jobs; only `SUCCEEDED`/`FAILED`/`CANCELLED`) |
| SQLite sidecars (`-wal`/`-shm`/`-journal`) | PASS (none under `data/`) |
| Locked capabilities | PASS (no lane change; retrieval/financial tables not activated by this audit) |

**Note on historical queue rows:** `printer_tracking_queue` retains 17 historical `QUEUED` rows from earlier discovery/handoff activity (oldest from 2026-06). These are not bound to any active campaign, supervision lease, or running factory cycle. Campaign-scoped active work for the audited production execution is clean-terminal. This audit does not rewrite historical queue rows.

---

## 2. Governing completeness invariants (audit framing)

```text
ELIGIBLE_ONE_COMPLETENESS
If at least one eligible token exists in the governed reachable universe,
Printer discovers at least one.

ELIGIBLE_CAPACITY_COMPLETENESS
If at least two eligible distinct tokens exist in the governed reachable
universe, Printer discovers and selects two.

PERSISTENT_DISCOVERY_UNTIL_CAPACITY
Discovery continues across bounded rounds inside the same authorized
campaign until eligible_reserve_count >= required_token_capacity
or a governed exhaustion condition is proven.

HONEST_EXHAUSTION
BLOCKED_INSUFFICIENT_GRADUATED_POOL is valid only when bounded evidence
proves fewer than two eligible tokens were reachable through all remaining
approved discovery work under source, operation, and duration ceilings.
```

This audit proves the current architecture **violates** `PERSISTENT_DISCOVERY_UNTIL_CAPACITY` and therefore can emit `BLOCKED_INSUFFICIENT_GRADUATED_POOL` without satisfying `HONEST_EXHAUSTION`.

---

## 3. Architecture path audited

```text
approved source channels
  → raw discovery observations (PumpPortal migration stream + optional DexScreener locator)
  → mint identity validation
  → graduation evidence (migration tx + on-chain PumpSwap pool)
  → exact PumpSwap pool confirmation
  → persistent graduated inventory (printer_pumpswap_graduated_candidate_registry)
  → locator and rediscovery (registry match only; never creates graduation)
  → market freshness (DexScreener exact-pool pair_market_snapshot)
  → exact-pool liquidity ($3,000 categorical floor)
  → activity evidence (pair payload present; no activity score)
  → cooldown and exclusions (STNP + below-floor 3600s market cooldown)
  → eligible reserve (front-door combined_reserve_order only; campaign-ephemeral)
  → deterministic selection (seeded-uniform combined two-token order)
  → tracking handoff (existing operational path after two ready)
```

### 3.1 Canonical owners (current)

| Stage | Owner |
|---|---|
| Migration intake / verify | `run_direct_migration_discovery` |
| Durable graduated inventory | `printer_pumpswap_graduated_candidate_registry` |
| Exact-pool market floor | `run_graduated_liquidity_front_door` + `printer_graduated_market_floor_state` |
| Supply composition | `build_graduated_supply` |
| Production kwargs | `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` |
| Operational admission terminal | `AuthoritativeLiveOperationalCampaignOwner.run_operational` |
| Terminal reporting | unified terminal closure / blocked-supply package |

### 3.2 Production bounds (current)

| Key | Value | Intended role |
|---|---:|---|
| `collection_rounds` | 3 | Migration stream accumulation rounds |
| `max_candidates` | 5 | On-chain verify / newly confirmed this cycle |
| `front_door_max_candidates` | 6 | **One** market-enrichment evaluation batch |
| Admission operation ceiling | 45 | Lifecycle-wide governed ops |
| Required token capacity | 2 | Exactly two selected tokens |
| Liquidity floor | `$3,000` | Exact-pool categorical floor |

---

## 4. Six-candidate boundary ownership (proven)

### 4.1 What the six-candidate rule is

`front_door_max_candidates = 6` is consumed only as
`run_graduated_liquidity_front_door(..., max_candidates=...)`.

Inside the front door, `_bounded_refresh_rows(..., max_candidates=6)` chooses **one
bounded evaluation batch** from the durable graduated registry:

- up to half LATEST / half PERSISTED when both partitions exist;
- deterministic Fisher–Yates by `cycle_seed` (non-ranked);
- then each selected row is market-enriched (or cooldown-skipped).

### 4.2 What the six-candidate rule is **not**

It must not mean:

```text
Printer may inspect only six tokens before declaring the governed market
insufficient.
```

### 4.3 Actual misuse (defect)

`build_graduated_supply` performs **exactly one** front-door invocation, then:

```text
ready = len(reserve_supply) >= 2
terminal = READY | BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL
```

There is:

* no multi-round evaluation loop over remaining registry inventory;
* no campaign-level eligible reserve that preserves a lone eligible token while
  discovery continues;
* no exhaustion certificate proving remaining unexplored work was empty or
  blocked by a hard ceiling;
* no classification distinguishing architecture stop from true market shortage.

**Ownership conclusion:** the six-candidate rule is a **per-evaluation-batch
bound**. The architecture incorrectly treats one batch as the entire discovery
universe for terminal shortage decisions.

The companion bound `max_candidates = 5` is a **per-cycle migration verify batch**
for newly confirmed graduations. It is not the final selection-facing set.

---

## 5. Historical supply-block attempts

All terminal causes of `BLOCKED_INSUFFICIENT_GRADUATED_POOL` in the operational DB
through baseline:

| Campaign | Terminal at | Observed | Validated | Eligible | Required | Source calls | Ops remaining (of 45) | Dominant classification |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `20260726T172119Z-941d6d86aa56` | 2026-07-26T17:23:24Z | (pre-reporting package) | — | — | 2 | (ledger-era incomplete package) | unknown | **DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE** (pre–V2-9.8B.4 package; short campaign, no multi-round) |
| `20260727T010656Z-0a54a31b6f2d` | 2026-07-27T01:13:21Z | 6 | 6 | **0** | 2 | **8** | **37** | **DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE** (batch of 6 only; mostly cooldown/unproven) |
| `20260727T122827Z-095d68927784` | 2026-07-27T12:33:42Z | 6 | 6 | **1** | 2 | **12** | **33** | **DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE** (1 eligible discarded; stop) |
| `20260727T211548Z-5d626101ec34` | 2026-07-27T21:21:15Z | 6 | 6 | **1** | 2 | **14** | **31** | **DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE** (latest production) |

### 5.1 Latest production execution detail (`20260727T211548Z-5d626101ec34`)

**Identity**

* execution_id: `20260727T211548Z-5d626101ec34`
* campaign_id: `20260727T211548Z-5d626101ec34-campaign`
* launch git HEAD: `a089fff` (clean)
* first_terminal_cause: `BLOCKED_INSUFFICIENT_GRADUATED_POOL`
* lifecycle_started: false
* restart_created / successor_created: false
* campaign_source_calls: **14**
* campaign_scheduler_calls: 0

**Batch evaluated (exactly 6)**

| Mint (prefix) | Path | Liquidity USD | Result |
|---|---|---:|---|
| `3dTTtUbXcc5h...` | LATEST | 8026.91 | **eligible** |
| `Ef21b6z1SzwN...` | LATEST | 0.95 | below floor |
| `6PfEWghusq49...` | LATEST | 19.49 | below floor |
| `7tKKxaDcb7w1...` | PERSISTED | 1756.95 | below floor |
| `ASmoyDqsuLed...` | PERSISTED | 1468.90 | below floor cooldown skip |
| `dwfwK985EsFU...` | PERSISTED | 1375.03 | below floor |

**Reserve outcome**

* eligible_candidates = 1
* required_token_capacity = 2
* no second discovery round
* the single eligible token was **not** preserved into a multi-round reserve for
  continued discovery

**Inventory outside the batch (same DB at audit time)**

Durable graduated registry size: **29**.

Market-floor rows with `LIQUIDITY_PROVEN` present in inventory at audit time
include multiple mints **not** in the six-row terminal batch, for example:

* `12u9FULaUfHD...` — 3113.85 (proven)
* `3zh9CTwPf8vv...` — 8752.18 (proven)
* `5iRB5xMpnxvu...` — 18546.45 (proven)
* `Av2cD8GQT5dn...` — 13477.44 (proven)
* `DqLouq9H8qaf...` — 306545.62 (proven)
* `FWAXQXDB3jsK...` — 11001.82 (proven)

These proven rows demonstrate that **eligible / previously eligible graduated
inventory existed outside the single six-candidate evaluation batch**. Even
where some proven rows may later fail STNP/cooldown or revalidation, the
architecture never attempted a second bounded evaluation batch while 31
governed operations remained.

### 5.2 Reachable vs evaluated

| Metric | Latest production | Structural pattern |
|---|---:|---|
| Unique graduated inventory | 29 | Grows across campaigns |
| Evaluated per blocked campaign | 6 | Hard batch bound |
| Unique candidates admitted to terminal package | 6 | = evaluation batch |
| Eligible retained across rounds | 0 (no multi-round) | Architecture gap |
| Source ops used at block | 8–14 | Far below 45 |
| Exhaustion certificate | absent | Reporting gap |

---

## 6. Shortage classification of every historical shortfall

Classification rules used:

| Class | Meaning |
|---|---|
| `TRUE_MARKET_SUPPLY_SHORTAGE` | All approved work exhausted; fewer than two eligible tokens existed |
| `SOURCE_VISIBILITY_SHORTAGE` | Approved free sources cannot see enough graduated PumpSwap surface |
| `SOURCE_AVAILABILITY_FAILURE` | Provider/transport failure prevented lawful discovery |
| `BUDGET_EXHAUSTION` | Operation ceiling reached before capacity |
| `DURATION_EXHAUSTION` | Duration ceiling reached before capacity |
| `STALE_EVIDENCE_SHORTAGE` | Only stale evidence remained; revalidation blocked by policy |
| `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` | Stopped while lawful unexplored work and budget remained |

| Campaign | Classification | Proof |
|---|---|---|
| `941d6d86aa56` | `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` | Short terminal; no multi-round; architecture single-shot |
| `0a54a31b6f2d` | `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` | 6 evaluated, 0 eligible, **37 ops remaining** |
| `095d68927784` | `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` | 6 evaluated, **1 eligible retained nowhere**, **33 ops remaining** |
| `5d626101ec34` | `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` | 6 evaluated, **1 eligible**, **31 ops remaining**, 29-row registry |

**None** of the four blocked-supply campaigns prove `TRUE_MARKET_SUPPLY_SHORTAGE`.
**None** prove budget or duration exhaustion.
**None** prove provider unavailability as the terminal cause.

---

## 7. Defect inventory (structural)

### D1 — Single-shot discovery stop (dominant)

`build_graduated_supply` runs one discovery composition + one front-door batch,
then terminals on `< 2` eligible. Violates `PERSISTENT_DISCOVERY_UNTIL_CAPACITY`.

### D2 — Six-candidate batch treated as universe

`front_door_max_candidates=6` correctly bounds **one evaluation batch** but is
incorrectly used as the entire market sample for shortage terminalization.

### D3 — Eligible candidates discarded instead of reserved

When round 1 yields exactly one eligible token, that token is not preserved in a
campaign-level eligible reserve while discovery continues. The production report
shows 1 eligible and immediate block.

### D4 — No exhaustion certificate

`BLOCKED_INSUFFICIENT_GRADUATED_POOL` is emitted without durable proof of:

* unique tokens observed across rounds;
* channels attempted/unavailable;
* ops used/remaining;
* duration used/remaining;
* unexplored work prevented by a hard ceiling;
* shortage classification.

A result based only on one five- or six-token batch is **not** a valid exhaustion
certificate under the lane invariants.

### D5 — Unexplored graduated inventory ignored

With 29 durable graduated rows, later batches of unexplored mints were never
requested. Budget remained. False scarcity.

### D6 — Budget spent / not spent asymmetrically

Below-floor cooldown (V2-9.8B.6) correctly avoids re-calling Dex for known dead
pools **inside** a batch. It does **not** free the architecture to explore the
**next** unexplored batch. Cooldown alone cannot fix single-shot stop.

### D7 — No durable eligible reserve across campaigns

Eligible-but-unselected tokens are not revalidated from a persistent reserve on
the next campaign. Inventory has market-floor state, but no first-class eligible
reserve owner.

### D8 — Source-visibility residual (secondary, not dominant)

Approved free channels remain PumpPortal migration + optional DexScreener
locator + registry revalidation. Locator never creates graduation. Live market
visibility of graduated PumpSwap may still be thin in some windows — but the
four historical blocks fail **before** that question is honestly answerable,
because architecture stopped early.

### D9 — No classification of provider failure vs market insufficiency

When a future provider failure occurs, the current blocked-supply reason still
collapses to the same market-insufficiency terminal without a separate
classification field.

---

## 8. What is **not** the dominant cause

| Hypothesis | Status |
|---|---|
| Need to lower `$3,000` floor | Rejected — floor is correct; architecture stopped early |
| Need to admit one token into a two-token campaign | Rejected — two-token rule remains |
| Need to raise operation ceiling 45 | Not proven necessary; 31 ops unused at latest block |
| Need automatic retry/successor campaign | Rejected — continuation must be **inside** one authorized campaign |
| True market empty of ≥2 eligible tokens | **Not proven** for any historical block |
| Scoring/ranking would fix supply | Prohibited and unnecessary |

---

## 9. Dominant structural causes (proven; gate for implementation)

Implementation is justified only after these are proven. They are:

1. **Single-shot front-door evaluation** after one bounded batch.
2. **Missing campaign-level eligible reserve** that preserves early eligible finds.
3. **Missing multi-batch unexplored-inventory walk** under remaining budget/duration.
4. **Missing honest exhaustion certificate** with shortage classification.

These are `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE` causes. They are not narrow
timeout/retry/candidate-count patches.

---

## 10. Source-budget picture (latest production)

```text
ceiling: 45
used at block: 14
remaining: 31
evaluated unique: 6
registry unique: 29
eligible found: 1
eligible required: 2
```

Even a conservative allocation that reserves ~15 ops for holder/handoff still
left ~16 discovery ops unused while unexplored graduated inventory existed.

---

## 11. Policy locks confirmed unchanged by this audit

* Solana-only / memecoin-only / paper-only
* exact PumpSwap graduation + pool confirmation
* `$3,000` exact-pool floor
* two-token production requirement
* Source Governor / Central Scheduler
* operation ceiling 45 (unless separately proven impossible)
* cooldown / rotation
* `WINDOW_15M` main; `WINDOW_5M_MICRO_EVENT` support-only
* no automatic retry/restart/successor
* no retrieval / paper decisions / BUY-SELL-HOLD / positions / trades / audits / PnL
* no wallet / keys / signing / live execution / paid APIs
* no scoring / ranking / confidence / weights / embeddings / vectors

---

## 12. Audit conclusion

```text
V2_9_8B_21_ELIGIBLE_TOKEN_SUPPLY_ARCHITECTURE_AUDIT_PASS
```

The live market may still be thin on some windows. Printer nevertheless **must
not** declare governed-market insufficiency after a single six-candidate
evaluation batch while:

* durable graduated inventory remains unexplored;
* lawful source operations remain;
* campaign duration remains;
* one eligible token has already been found and discarded.

**Next required work:** design and implement the canonical Eligible Token Supply
service, persistent discovery loop, exhaustion certificate, and disposable proof
matrix — without production campaigns and without lowering eligibility standards.

---

## Functionality Risks / Setbacks / Efficiency Blockers (audit)

| Item | Detail |
|---|---|
| Risk | Multi-batch market enrichment could spend more Dex ops | Mitigation: stop at two eligible; reserve holder headroom; skip cooldown mints |
| Risk | Persisting reserve across campaigns could reselect stale pools | Mitigation: mandatory revalidation before selection |
| Risk | True market shortage still possible after honest exhaustion | Mitigation: keep two-token rule; emit honest certificate |
| Setback | Prior V2-9.8B.5–7 productivity work improved depth but not multi-round completeness | This lane supersedes single-shot shortage terminalization |
| Efficiency blocker | Re-inspecting known below-floor pools | Already cooldown-gated; multi-round must prefer unexplored mints |
