# V2-9.7E.3 Live Eligibility Funnel Audit

**Status:** PASS  
**Lane:** V2-9.7E.3 — Live Eligibility Funnel Audit  
**Boundary:** read-only audit only; no pilot, source calls, code change, or DB mutation  
**Date:** 2026-07-21  
**Baseline HEAD:** `938e12749e6b122e41dbdd537bde703dd1ca7e74`

## Final Verdict

`V2_9_7E_3_LIVE_ELIGIBILITY_FUNNEL_AUDIT_PASS`

PASS means the **exact candidate-loss funnel** and **next repair scope** are known.
It does **not** authorize implementation, another pilot, V2-9.7F, or V2-9.8.

## Todo / Checklist

- [x] Verify HEAD `938e127…`.
- [x] Read D/E/E.1/E.2 closeouts and discovery/gate owners.
- [x] Read-only inspect both pilot SQLite targets.
- [x] Reconstruct observation → merge → origin → gate → selection funnel.
- [x] Classify blockers; define minimum roadmap-compliant repair sequence.
- [x] Write this audit; commit only the audit document.

## Method

- Read-only SQLite inspection of:
  - `data/printer_v1_v2_9_7e_pilot.sqlite3` (first pilot)
  - `data/printer_v1_v2_9_7e_pilot_rerun.sqlite3` (reauthorized rerun)
- Cross-check with redacted pilot result JSON and committed executor contracts:
  - `CombinedPumpfunCampaignExecutor` merge / origin / `GATE_ORDER` / selection
  - `ORIGIN_VERIFY_ADMISSIONS = 8`
  - Tracker row-level 180s freshness (`normalize_tracker_list`)
- No network, no writes to pilot DBs, no production edits.

---

## 1. Exact Funnel Counts — Both Pilots

Primary discovery batch = latest batch per DB (the authorized attempt that ended
in two-or-none).

### 1.1 Pilot 1 (first authorized attempt)

| Funnel stage | Count / result |
|---|---:|
| Provider observations received | **25** |
| Unique mints after observation | **23** |
| By source×channel | Dex `ACTIVE_PUMPFUN` **5**; Gecko `TRENDING_PUMPFUN` **20** |
| Tracker observations | **0** |
| Direct Pump observations | **0** |
| Merged candidates | **24** (unique mints **23**) |
| Origin verification rows | **24** |
| Origin admitted | **8** (`ADMITTED`) |
| Origin not admitted (ceiling) | **16** (`NOT_ADMITTED_CEILING`) |
| Origin confirmed | **0** |
| Origin admitted but FAILED | **8** |
| Eligible after fixed gates (runtime) | **0** |
| Selected item links | **0** |
| Token slots activated | **0** |
| Terminal selection cause | `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` |

Channel label sets on merged candidates:

- `TRENDING_PUMPFUN` only: 19  
- `ACTIVE_PUMPFUN` only: 4  
- both: 1  

### 1.2 Pilot 2 (reauthorized rerun)

| Funnel stage | Count / result |
|---|---:|
| Provider observations received | **26** |
| Unique mints after observation | **24** |
| By source×channel | Gecko trending **20** + Gecko active **1**; Dex active **5** |
| Tracker observations | **0** |
| Direct Pump observations | **0** |
| Merged candidates | **25** (unique mints **24**) |
| Origin verification rows | **25** |
| Origin admitted | **8** |
| Origin not admitted (ceiling) | **17** |
| Origin confirmed | **0** |
| Origin admitted but FAILED | **8** |
| Eligible after fixed gates (runtime) | **0** |
| Selected item links | **0** |
| Token slots activated | **0** |
| Terminal selection cause | `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` |

Channel sets: trending-only 19; active-only 5; both 1.

### 1.3 Side-by-side

| Metric | Pilot 1 | Pilot 2 |
|---|---:|---:|
| Secondary observations | 25 | 26 |
| Unique secondary mints | 23 | 24 |
| Direct creates | 0 | 0 |
| Tracker rows kept | 0 | 0 |
| Origin CONFIRMED | 0 | 0 |
| Eligible pool size | 0 | 0 |
| Two-slot activation | no | no |

**Conclusion:** both pilots lost **all** candidates at **Pump.fun origin confirmation**,
not at cooldown, infrastructure exclusion, or selection randomness.

---

## 2. Gate-by-Gate Rejection Reasons

Committed gate order (`GATE_ORDER`):

`OWNERSHIP → SOURCE_PROVENANCE → SOLANA_IDENTITY → PUMPFUN_ORIGIN →
LIFECYCLE_MARKET → FRESHNESS_CUTOFF → EVIDENCE_QUALITY → CANDIDATE_ROLE →
INFRASTRUCTURE_EXCLUSION → DUPLICATE_CONFLICT → B3_RECONCILIATION →
COOLDOWN → VACANCY → BUDGET`

### Runtime behavior (authoritative)

For every merged secondary candidate:

1. Merge attaches gap `ORIGIN_UNVERIFIED` / provider label only.  
2. Origin stage: at most **8** secondary mints admitted per cycle
   (`ORIGIN_VERIFY_ADMISSIONS`).  
3. Admitted secondaries without a matching finalized direct create become
   `origin_state=FAILED` (`no_finalized_create`).  
4. Gate **`PUMPFUN_ORIGIN`** requires `origin_state == CONFIRMED`.  
5. With **zero** confirmed origins, **eligible list length = 0**.  
6. Selection requires two for INITIAL → `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`.

Cooldown-plane note: `first_failed_eligibility_gate` on merged rows remains
`NULL` because gates are evaluated in memory and **not rewritten** to the
merged-candidate row after origin verification. Runtime eligibility still
fails at `PUMPFUN_ORIGIN`. This is an **auditability gap**, not a second
eligibility path.

Cooldown-plane `origin_verification_state` on merged rows also remains `PENDING`
(insert-time value) while origin verification table shows `FAILED` /
`NOT_ATTEMPTED`. In-memory candidate state drives gates; DB merge column is
stale after origin stage.

### Gates that did **not** decide the empty pool

| Gate | Role in these pilots |
|---|---|
| COOLDOWN | Not reached as decider (zero origin-confirmed) |
| INFRASTRUCTURE_EXCLUSION | No evidence of SOL/USDC mint rejections as sole cause |
| DUPLICATE_CONFLICT | Not the empty-pool cause |
| VACANCY / BUDGET | Initial vacancies were (1,2); handoffs 0 |
| LIFECYCLE_MARKET / PumpSwap | No graduated-claim ambiguity path exercised for rejects |

---

## 3. Direct Pump Findings

### Evidence from live harness (redacted pilot JSON) + DB

| Fact | Pilot 1 | Pilot 2 |
|---|---|---|
| Direct observations in DB | 0 | 0 |
| Harness decoded creates | 0 | 0 |
| Continuity | GAPPED | GAPPED |
| Gap codes (harness) | FAILED_TRANSACTION×4 | FAILED_TRANSACTION×3 + NOT_SUPPORTED_CREATE×1 |
| Discovery work `DISCOVERY_PUMPFUN_LATEST` | SUCCEEDED / DIRECT_COMPLETE | SUCCEEDED / DIRECT_COMPLETE |
| Batch `pump_continuity_state` | UNKNOWN | UNKNOWN |

### Why Direct remained empty

| Question | Finding | Classification |
|---|---|---|
| Is the direct lane “broken” as ownership? | Work completes; Governor admits RPC kinds; empty create set is allowed | **not adapter crash** |
| Is cursor/cutoff wrong vs contract? | Harness used bounded 4-signature page and bind-to-page cutoff; still no successful create decode | **continuity/cutoff design + productivity** |
| Is market empty of creates? | Pump program traffic exists (signatures returned) but sample was not successful creates | **expected market composition on tiny sample** |
| Adapter scope? | `NOT_SUPPORTED_CREATE` shows some txs reach decode and fail supported-create shape | **adapter coverage / instruction-layout gap** |
| Do FAILED_TRANSACTION rows prove adapter bug? | Failed on-chain txs correctly yield no origin | **expected market emptiness / noise** |

**Confirmed:** without ≥2 mints with `PUMPFUN_ORIGIN_CONFIRMED`, two-or-none
**must** refuse activation. Secondary providers cannot substitute origin.

**Not claimed:** that a larger backfill would always produce two creates.

---

## 4. Tracker Findings (180-second rule)

| Fact | Both pilots |
|---|---|
| HTTP transport | 200 on trending + top (rerun preflight/result) |
| Observations persisted | **0** |
| Work state | SUCCEEDED / SOLANA_TRACKER_COMPLETE |

Interpretation:

- Free REST auth works.
- Row-level freshness (E.4B.1 / Tracker contract): pumpfun pools with
  `lastUpdated` older than **180s** contribute **nothing**.
- Empty observation set after filter is **factual empty**, not transport failure.

| Question | Finding | Classification |
|---|---|---|
| Is 180s applied as designed? | Yes — zero rows means all pumpfun-matching pools failed freshness or never matched market filter | **expected under contract** |
| Is list membership “stale” vs pool trade update? | Provider `lastUpdated` is pool-update ms; 1h lists often include older pool updates | **provider-contract / productivity mismatch risk** (not proven false) |
| Should threshold be widened in this audit? | **No** — policy change out of scope; would require contract redesign lane | n/a |

Tracker did not contribute mints to merge/origin in either pilot.

---

## 5. DexScreener / GeckoTerminal → Origin Verification

| Question | Answer |
|---|---|
| Did Dex/Gecko produce observations? | **Yes** (5 + 20-class counts) |
| Did those mints become merged candidates? | **Yes** (all secondary) |
| Did any reach origin admission? | **Yes** — 8 per pilot (`ORIGIN_VERIFY_ADMISSIONS`) |
| Did any confirm origin? | **No** — all admitted secondaries `FAILED` (`no_finalized_create`) |
| Did ceiling exclude useful candidates? | Ceiling excluded 16–17 secondaries from **attempted** verification, but even full admission would still fail without direct creates | **ceiling/productivity** secondary; **not** sole empty-pool cause |

**Confirmed:** secondary candidates **did** reach origin verification. They
failed because **direct finalized create evidence was absent**, consistent with
mint-scoped origin authority in the executor.

---

## 6. Pair / Lifecycle / Market Identity

| Question | Finding | Classification |
|---|---|---|
| Missing market/pair identity as empty-pool cause? | SOLANA_IDENTITY gate not the recorded stopper; secondary rows carried market identities | **not primary** |
| Lifecycle/PumpSwap graduation blocking? | No confirmed graduated claims requiring PumpSwap; pumpswap work completed without selecting | **not primary** |
| Cooldown excluding all? | No prior selection history for these pilot DBs | **not primary** |

---

## 7. Confirmed Root Causes vs Unknowns

### Confirmed root causes of `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`

1. **Zero direct finalized Pump creates** in the bounded live capture → zero
   mint-scoped origin authority.  
   Class: **expected market composition on tiny sample** + **continuity/cutoff
   productivity** + residual **adapter coverage** (`NOT_SUPPORTED_CREATE`).

2. **Zero Tracker observations after 180s row filter** → no tracker mints.  
   Class: **expected under adopted freshness contract** / possible
   **provider-contract productivity mismatch** for 1h list `lastUpdated`.

3. **All secondary candidates fail gate `PUMPFUN_ORIGIN`** because origin never
   reaches `CONFIRMED`.  
   Class: **eligibility-gate working as designed** (not a gate bug).

4. **Two-or-none** correctly refuses partial activation with eligible count 0.  
   Class: **expected contract behavior**.

### Not root causes (ruled out)

- Cleanup/terminalization (E.1) — second pilot terminalized cleanly.  
- Cooldown wipeout.  
- Selection RNG.  
- Governor denial of secondary lanes.  
- Complete absence of secondary market observations.

### Unknowns / auditability gaps

| Item | Classification |
|---|---|
| Whether a deeper finalized create backfill would have yielded ≥2 creates | **unknown / productivity** |
| Whether Tracker `lastUpdated` is the correct clock for list membership freshness | **provider-contract mismatch risk** (needs contract re-audit, not silent widen) |
| Full set of instruction layouts behind `NOT_SUPPORTED_CREATE` | **adapter defect / coverage gap** (needs bounded decode audit) |
| Gate results not written back to merged rows | **missing evidence / auditability** (implementation polish) |

### Contract contradiction?

**No.** Adopted design requires finalized Pump origin for eligibility. Live
secondaries cannot mint-confirm origin alone. Empty eligible pool under zero
creates is **contract-faithful**.

---

## 8. Minimum Roadmap-Compliant Repair Sequence

Do **not** weaken: finalized origin, freshness, exact identity, cooldown, fixed
gates, two-or-none, Governor/Scheduler ownership.

Recommended **audit → design → implement → proof** sequence:

| Order | Lane intent | Addresses |
|---|---|---|
| 1 | **Direct create-capture productivity audit + design** (bounded signature window, create-only filtering, supported instruction layouts, cutoff binding) | Zero creates / GAPPED sample |
| 2 | **Direct create-adapter decode coverage repair** (if audit proves missing layouts for true creates) | `NOT_SUPPORTED_CREATE` |
| 3 | **Tracker list-freshness contract re-audit** (whether `lastUpdated` is pool trade time vs list rank time; optional **contract** revision only if evidence warrants) | Tracker empty sets |
| 4 | **Eligibility auditability repair** (persist post-origin `origin_verification_state` + `first_failed_eligibility_gate` on merged rows) | DB/runtime drift for operators |
| 5 | Only then: **one reauthorized pilot** under E.2 preflight | Prove dual activation if live yield exists |

Optional later (not eligibility weakeners): multi-window post-handoff orchestrator
once two eligible tokens activate.

---

## 9. Money-Usefulness Contribution

This audit shows the empty two-slot outcome is **not** mysterious and **not** a
cleanup failure. Secondary market heat (Dex/Gecko) is present; **origin-backed**
candidates are not. Capital-protection research must not treat trending lists as
Pump.fun origin. Next work should improve **honest create capture and
auditability**, not force two activations from label-only mints.

---

## 10. What Remains Locked

- Implementation of the repair sequence (not authorized here)  
- Another pilot / V2-9.7F / V2-9.8  
- Weakening origin, freshness, cooldown, two-or-none  
- Retrieval, decisions, BUY/SELL/HOLD, positions, trades, PnL  
- Wallets, signing, live execution, paid APIs, scoring, embeddings  
- 12h/24h; 5m as main outcome  

---

## 11. Functionality Risks / Setbacks / Efficiency Blockers

- Bounded 4-tx direct samples are statistically weak on a busy program.  
- 1h Tracker lists under 180s pool-update freshness often contribute zero rows.  
- Origin admission ceiling (8) is moot while creates are zero, but becomes
  material once creates appear.  
- Stale DB fields for gate/origin after in-memory updates hinder operator funnel
  debugging without this audit.  
- Dual-token pilot PASS still requires live creates **and** multi-window runtime
  after activation.  
- Prior pilots’ residual historical state (first pilot incomplete cleanup) must
  not be resumed; always use a fresh target.

---

## 12. Verification Performed

| Check | Result |
|---|---|
| Read-only pilot DB inspection | both DBs |
| Static gate/origin contract cross-check | combined executor + Tracker normalizer |
| Source/network calls | **none** |
| DB mutation | **none** |
| Production code change | **none** |
| `git diff --check` on audit file | at commit |

## Stop Boundary

V2-9.7E.3 ends here. Do **not** start repairs, another pilot, V2-9.7F, or V2-9.8
from this audit alone.
