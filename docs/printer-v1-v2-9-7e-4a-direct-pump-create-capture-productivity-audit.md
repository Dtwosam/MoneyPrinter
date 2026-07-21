# V2-9.7E.4A Direct Pump Create-Capture Productivity Audit

**Status:** PASS  
**Lane:** V2-9.7E.4A — Direct Pump Create-Capture Productivity Audit  
**Boundary:** read-only audit only; no pilot, network, source fetching, code change, schema change, threshold change, or DB mutation  
**Date:** 2026-07-21  
**Baseline HEAD:** `295f4e6c7625b5de6d1db3621e033bd09628be28`

## Final Verdict

`V2_9_7E_4A_DIRECT_PUMP_CREATE_CAPTURE_PRODUCTIVITY_AUDIT_PASS`

PASS means the **exact create-capture outcome counts**, **transaction classifications**, and **confirmed root causes versus unknowns** for zero finalized Pump `create` confirmations in both V2-9.7E pilots are documented.

It does **not** authorize design implementation, decoder repair, another pilot, V2-9.7F, V2-9.8, or any weakening of finalized origin authority.

## Todo / Checklist

- [x] Verify HEAD `295f4e6…` (`git rev-parse HEAD`).
- [x] Read AGENTS.md / active source stack, E.3 funnel audit, direct Pump contract/adapter/continuity closeouts.
- [x] Read current Pump decoder, cursor, cutoff, backfill, and origin-verification owners.
- [x] Inspect both pilot DBs and harness artifacts read-only.
- [x] Classify GAPPED / FAILED_TX / NOT_SUPPORTED_CREATE / malformed / post-cutoff / missing-finality outcomes.
- [x] Separate confirmed root causes from unknowns; preserve origin authority.
- [x] Run focused decoder/continuity tests and static contract checks.
- [x] Write this audit; commit only this document.

## Method

Read-only evidence only:

| Source | Path / owner |
|---|---|
| Pilot 1 DB | `data/printer_v1_v2_9_7e_pilot.sqlite3` |
| Pilot 2 DB | `data/printer_v1_v2_9_7e_pilot_rerun.sqlite3` |
| Pilot 1 result | `operator-runs/v2-9-7e-pilot/V2_9_7E_PILOT_RESULT.json` |
| Pilot 2 result | `operator-runs/v2-9-7e-pilot-rerun/V2_9_7E_RERUN_RESULT.json` |
| Harness capture | `operator-runs/v2-9-7e-pilot/run_v2_9_7e_pilot.py` and rerun harness (`capture_live_fixtures`) |
| Decoder / continuity | `src/printer_v1/sources/pumpfun_direct.py` |
| Origin verification | `CombinedPumpfunCampaignExecutor._origin_and_pumpswap` / `_run_direct_lane` |
| Prior funnel audit | `docs/printer-v1-v2-9-7e-3-live-eligibility-funnel-audit.md` |
| Contract closeouts | `docs/printer-v1-v2-9-7d-7b-3a-direct-pump-contract-adoption-closeout.md`, `docs/printer-v1-v2-9-7d-7b-4a-direct-pump-adapter-continuity-closeout.md` |

No network calls. No writes to pilot DBs. No production code edits.

---

## 1. Evidence Summary — Both Pilots

### 1.1 Live harness create-capture (`live_capture`)

| Metric | Pilot 1 | Pilot 2 |
|---|---:|---:|
| Program targeted | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` | same |
| Signature page size used | **4** (`getSignaturesForAddress` limit=4) | **4** |
| Signature pages used | **1** | **1** |
| `signature_count` | **4** | **4** |
| `getTransaction` attempts | **4** (one per row) | **4** |
| `decoded_count` (finalized creates) | **0** | **0** |
| `create_mints` | `[]` | `[]` |
| Continuity label | `GAPPED` | `GAPPED` |
| `cutoff_slot` | `434320459` | `434327198` |
| Cutoff binding | max slot of returned page | max slot of returned page |
| Capture error | none | none |
| `transaction_unavailable` / null tx gaps | **0** | **0** |
| `malformed_signature_row` | **0** | **0** |
| `post_cutoff` | **0** | **0** |
| `getTransaction_failed` | **0** | **0** |
| `MISSING_FINALITY` | **0** | **0** |
| `UNSUPPORTED_VERSION` (`create_v2`) | **0** | **0** |
| `FAILED_TRANSACTION` | **4** | **3** |
| `NOT_SUPPORTED_CREATE` | **0** | **1** |

Combined across both pilots: **8** signatures fetched, **8** transaction decodes attempted, **0** finalized `create` observations, **7× FAILED_TRANSACTION**, **1× NOT_SUPPORTED_CREATE**.

### 1.2 Campaign / DB outcomes (create-related)

| Metric | Pilot 1 | Pilot 2 |
|---|---:|---:|
| Direct provider observations (`solana_rpc` / `LATEST_PUMPFUN`) | **0** | **0** |
| `DISCOVERY_PUMPFUN_LATEST` work | SUCCEEDED / `DIRECT_COMPLETE` | SUCCEEDED / `DIRECT_COMPLETE` |
| Batch `pump_cursor_slot` / `pump_cursor_signature` | `NULL` / `NULL` | `NULL` / `NULL` |
| Batch `pump_continuity_state` | `UNKNOWN` | `UNKNOWN` |
| Origin CONFIRMED | **0** | **0** |
| Origin ADMITTED + FAILED (`no_finalized_create`) | **8** | **8** |
| Origin NOT_ADMITTED_CEILING | **16** | **17** |
| Terminal selection cause | `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` | same |

**Interpretation:** direct work is allowed to complete with an empty create set. Empty create set is the create-capture productivity failure that empties the eligible two-slot pool (see E.3). Provider labels never substituted for origin.

---

## 2. Outcome Counts and Transaction Classifications

### 2.1 Classification dictionary (decoder + harness)

| Code | Meaning in current owners | Continuity impact (fixture owner) |
|---|---|---|
| `FAILED_TRANSACTION` | Signature `err != null` and/or `meta.err != null` | Continuity fault → contributes to `GAPPED` |
| `NOT_SUPPORTED_CREATE` | Finalized successful tx with Pump program activity but **no** supported `create` discriminator | **Not** a continuity fault in fixture owner; still no observation |
| `UNSUPPORTED_VERSION` | Transaction version not `legacy`/`0`, **or** Pump `create_v2` discriminator present | Continuity fault |
| `MISSING_FINALITY` | Reference not `confirmationStatus=finalized` | Continuity fault |
| `POST_CUTOFF` | Slot above immutable cycle cutoff | Rejected; no admission |
| `MALFORMED_TRANSACTION` | Bad envelope / keys / accounts / PDA / ATA | Continuity fault |
| `UNAVAILABLE_HISTORY` | Null/missing transaction body or block time | Continuity fault |
| `GAPPED` (cycle label) | Any continuity fault in cycle (failed tx, incomplete interval, ceiling, disconnect, etc.) | Cursor **does not** advance |

Harness labels continuity `GAPPED` whenever **any** gap code is recorded (including `FAILED_TRANSACTION` on non-create traffic). That is harsher than the fixture rule that treats pure `NOT_SUPPORTED_CREATE` as non-fault.

### 2.2 Exact pilot gap tallies

| Gap / outcome | Pilot 1 | Pilot 2 | Combined |
|---|---:|---:|---:|
| `FAILED_TRANSACTION` | 4 | 3 | **7** |
| `NOT_SUPPORTED_CREATE` | 0 | 1 | **1** |
| Malformed row | 0 | 0 | **0** |
| Post-cutoff | 0 | 0 | **0** |
| Missing finality | 0 | 0 | **0** |
| Unavailable / null transaction | 0 | 0 | **0** |
| Unsupported version / `create_v2` | 0 | 0 | **0** |
| Successful finalized `create` | 0 | 0 | **0** |
| Total signatures decoded | 4 | 4 | **8** |

### 2.3 Were sampled signatures actual Pump creation transactions?

| Finding | Evidence | Confidence |
|---|---|---|
| Signatures came from **Pump Program address history** | Harness calls `getSignaturesForAddress(PUMP_PROGRAM_ID, …)` | **Confirmed** |
| They were **not** proven successful `create` instructions | Zero successful `decode_finalized_create` | **Confirmed** |
| Majority were **failed on-chain transactions** | 7/8 `FAILED_TRANSACTION` | **Confirmed** (err on signature row and/or meta) |
| At least one was a **successful non-create** Pump interaction | 1/8 `NOT_SUPPORTED_CREATE` (pilot 2) | **Confirmed** shape; exact instruction (buy/sell/etc.) **not** retained in harness artifacts |
| Any were `create_v2` | Would surface as `UNSUPPORTED_VERSION`; count 0 | **Not observed** in these samples |
| Raw instruction bytes / account graphs retained | Harness stores only gap **codes**, not transaction bodies | **Not available** for deeper offline reclassification |

**Conclusion:** the sample was **real Pump Program traffic**, not wrong-program noise, but it was **not a create-rich sample**. Zero of eight rows were finalized supported creates.

---

## 3. Signature Retrieval Targeting

| Question | Finding |
|---|---|
| Correct program ID? | **Yes** — official Pump Program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` (pinned IDL commit `9c82f61…`, SHA-256 `b90bc471…`) |
| Commitment? | `finalized` on signature page and `getTransaction` |
| Encoding / version envelope? | `encoding=json`, `maxSupportedTransactionVersion=0` (matches adopted legacy + v0) |
| Create-only filter at RPC layer? | **No** — program-level signature stream includes all Pump instructions (create, trade, etc.) and failed attempts |
| Live `logsSubscribe` create stream used in pilots? | **No** — harness used only one signature page + per-sig `getTransaction` |

Program-level targeting is correct. Productivity suffers because **latest program signatures are not create-biased**.

---

## 4. Cursor / Backfill / Cutoff Findings

### 4.1 Adopted contract ceilings (fixture owner)

| Ceiling | Adopted value |
|---|---:|
| Signature backfill pages | **2** |
| Rows per page | **16** |
| Max signatures potentially enumerated | **32** |
| Max `getTransaction` decodes | **16** |
| Governed backfill requests | **2** |
| Governed transaction requests | **16** |

### 4.2 What the pilots actually used

| Item | Pilot harness | Contract full path |
|---|---|---|
| Pages | **1** | up to **2** |
| Limit per page | **4** | up to **16** |
| Decode budget | **4** | up to **16** |
| Live session + unsubscribe | **not used** | optional fixture path |
| Cutoff source | **max slot of returned page** (“bind-to-page”) | immutable `getSlot` finalized cutoff, then reject post-cutoff |
| Prior contiguous cursor | none (`UNKNOWN`) | required for `CONTIGUOUS` advance |
| Cursor advance | none (`pump_cursor_*` NULL) | only after full CONTIGUOUS interval |

### 4.3 Ordering, races, post-cutoff

| Risk | Pilot evidence |
|---|---|
| Post-cutoff race emptying the sample | **Avoided by design** in harness (cutoff = max page slot → 0 post-cutoff rejections) |
| Ordering preventing creates | Not evidenced; all rows admitted then failed decode class |
| Contiguous boundary advance from wrong edge | No advance occurred; prior boundary absent → `UNKNOWN` is correct for first cycles |
| Incomplete two-page backfill forcing `GAPPED` | Pilots never attempted two pages; harness `GAPPED` was driven by decode gap codes |

**Confirmed:** pilot create yield was measured under a **deliberately tiny under-sample** of the adopted ceilings (4 vs up to 16 decode slots, 1 vs 2 pages).  
**Not claimed:** that exhausting 2×16/16 would always produce ≥2 creates.

---

## 5. Decoder Coverage Findings

Pinned create authority remains:

- Supported create discriminator: `181ec828051c0777`
- Rejected `create_v2` discriminator: `d6904cec5f8b31b4` → `UNSUPPORTED_VERSION`
- Inner instructions scanned via `meta.innerInstructions`
- Versioned v0 ALT keys via `meta.loadedAddresses` (writable + readonly)
- Optional `CreateEvent` / Anchor CPI wrapper as corroboration only
- Require exactly one supported `create`; account PDAs/ATAs/fixed identities validated

| Coverage question | Finding | Classification |
|---|---|---|
| Inner instructions missed by design? | **No** — decoder merges top-level + inner | not root cause of pilots |
| Versioned txs / ALTs unsupported by design? | **No** — v0 + loaded addresses supported; harness requests version 0 | not root cause of pilots |
| Event-only creates accepted? | **No** by contract (instruction required); events optional corroboration | intentional |
| `create_v2` creates lost? | Intentional unsupported gap; **0** pilot rows hit this code | **residual unknown** for market share outside sample |
| Successful non-create labeled correctly? | **Yes** — pilot 2 `NOT_SUPPORTED_CREATE` | expected market composition |
| Failed txs labeled correctly? | **Yes** — 7× `FAILED_TRANSACTION` | expected; not adapter crash |
| Implementation defect in pure decoder? | Focused fixture tests **15 passed**; static contract checks PASS | **not** decoder crash for these pilots |

**Decoder coverage is not the primary explanation for zero creates in these two pilots.** The sample almost never reached a successful create-shaped instruction. Residual risk remains that a larger, create-bearing sample could expose `create_v2` or another layout as the next hard gap.

---

## 6. Secondary-Mint Origin Lookup

Executor origin stage (`_origin_and_pumpswap`):

1. Direct creates already on the merged candidate become `CONFIRMED` / `NOT_REQUIRED`.
2. Secondary mints (Dex/Gecko/Tracker labels) are ranked; at most **`ORIGIN_VERIFY_ADMISSIONS = 8`** admitted.
3. Admitted secondaries confirm **only** if `fixtures.origin_proofs[mint]` is a matching confirmed create proof.
4. Otherwise: `FAILED` with `no_finalized_create`.
5. **No** mint-scoped `getSignaturesForAddress(mint)` historical origin fetch exists in the combined path.
6. Provider labels remain `provider_label_unverified_until_direct: true` and never become origin authority.

Pilot DB confirms:

- transaction_signature / program_id / slot on origin rows: **all NULL** for failed admissions
- 8 ADMITTED+FAILED and 16–17 ceiling exclusions per pilot
- Merged rows still show insert-time `origin_verification_state=PENDING` (auditability gap from E.3; not an alternate eligibility path)

**Confirmed:** secondary-mint “origin verification” is a **mint-match against the same-cycle direct create set**, not a historical mint creation lookup. With zero direct creates, **all** secondary admissions must fail. That is **authority-preserving**, not a silent provider bypass.

---

## 7. Public RPC Retention

| Observation | Pilot evidence |
|---|---|
| Null `getTransaction` result | **0** |
| Transport failure codes | **0** |
| Unavailable history codes | **0** |
| Signatures returned for program | **yes** (4+4) |

**Confirmed for these pilots:** public RPC retention / null history was **not** the main limitation.  
**Still true as general risk** (contract closeouts): retention is not guaranteed for deeper historical mint lookups if a later design adds them.

---

## 8. Root-Cause Classification

### 8.1 Confirmed root causes of zero finalized creates

| # | Cause | Class | Evidence |
|---|---|---|---|
| 1 | **Operational under-sampling** of the direct lane (limit=4, one page, four decodes) far below adopted 2×16/16 ceilings | **request ceilings / operational design** | both harnesses |
| 2 | **Program-level latest signatures are not create-rich** (failed txs + non-create successes dominate the tiny sample) | **market sampling** | 7 FAILED + 1 NOT_SUPPORTED_CREATE; 0 creates |
| 3 | **Secondary origin cannot invent creates**; match-only against empty create set | **continuity/origin design (correct)** | origin table all FAILED/NOT_ATTEMPTED; executor path |
| 4 | **No mint-scoped historical create fetch** for admitted secondaries | **design gap for secondary productivity** (not authority weakening) | executor code + NULL signatures |
| 5 | Harness **GAPPED** labeling on any decode miss, including expected failed/non-create market rows | **continuity labeling productivity** | harness `continuity = GAPPED if gaps` |

### 8.2 Ruled out as primary causes of these two pilots

| Claim | Status |
|---|---|
| Wrong Pump Program targeting | **Ruled out** |
| RPC null retention on sampled signatures | **Ruled out** (for these 8) |
| Post-cutoff race emptying admissions | **Ruled out** (bind-to-page cutoff) |
| Missing finality on sample | **Ruled out** (no such codes) |
| Decoder crash / missing inner/ALT support for standard create | **Ruled out** for sample; tests green |
| Provider labels substituting for origin | **Ruled out** (authority held) |
| Adapter “broken” ownership (work never completes) | **Ruled out** (`DIRECT_COMPLETE` with empty set allowed) |

### 8.3 Unknowns (honest)

| Unknown | Class |
|---|---|
| Would full **2 pages × 16 / 16 decodes** produce ≥2 creates in similar market windows? | productivity unknown |
| Live **share of `create` vs `create_v2`** among successful creations | decoder-coverage residual |
| Exact instruction(s) behind the single `NOT_SUPPORTED_CREATE` | unknown (body not retained) |
| Whether a create-filtered RPC strategy (logs/mentions) is feasible under free public RPC + Governor ceilings without paid infra | design unknown |
| Whether mint-scoped historical origin for admitted secondaries is retention-feasible under free RPC | design/retention unknown |

### 8.4 Problem-type summary (required categories)

| Category | Role in zero creates |
|---|---|
| Market sampling | **Primary** — latest program traffic ≠ creates |
| Continuity/cutoff design | **Secondary** — bind-to-page avoided race but pilots never exercised real cutoff/cursor productivity; GAPPED over-labels |
| Decoder coverage | **Residual / not primary** for these samples; `create_v2` still intentional hard gap |
| RPC history retention | **Not primary** here |
| Request ceilings | **Primary operational** — pilots used 4≪16/32 capacity |
| Implementation defect | **Partial** — harness under-samples adopted ceilings; origin stage lacks mint-scoped historical path by design, not by crash |
| Unknown | Deeper yield under full ceilings; modern create instruction mix |

**Overall judgment:** zero create confirmations were **expected under the pilot harness’s tiny program-level sample** and **authority-correct origin matching**, not evidence that finalized origin authority should be weakened.

---

## 9. Minimum Design Questions for the Next Lane

The next lane must be **design-only** (no pilot, no production decoder unlock without explicit follow-on). Minimum questions:

1. **Sampling strategy:** How should direct capture prefer create-bearing signatures (logs filter, larger page walk with early-stop on N creates, skip `err!=null` before `getTransaction`) without exceeding governed ceilings?
2. **Operational ceilings:** Must live/operator harnesses use the full adopted 2×16/16 path (or a documented subset with proven yield) rather than ad-hoc `limit=4`?
3. **Cutoff binding:** Keep immutable `getSlot` cutoff vs bind-to-page? How are post-cutoff races reported without emptying legitimate finalized creates?
4. **Cursor advancement:** When is the first trusted contiguous boundary established from cold `UNKNOWN` without inventing completeness?
5. **Create-only vs program-all:** Is program-wide latest history an acceptable primary create source, or only a support path?
6. **`create_v2` policy:** Measure live prevalence; if dominant, require explicit later adoption lane — **never** silent accept.
7. **Secondary origin productivity:** Should admitted secondaries gain a **bounded mint-scoped finalized create lookup** under Governor/Scheduler ceilings, still mint-exact and fail-closed?
8. **Evidence retention:** Should harness/production persist redacted decode classifications (discriminator class, err presence) for audits without storing full raw RPC dumps?
9. **Continuity semantics:** Align harness `GAPPED` with fixture rules so pure `NOT_SUPPORTED_CREATE` does not look like a continuity emergency.
10. **Success criteria for a later pilot:** Minimum ≥2 distinct mints with `PUMPFUN_ORIGIN_CONFIRMED` from finalized creates before two-slot activation is attempted again.

Do **not** answer these by loosening finalized origin, allowing provider labels as origin, or skipping two-or-none.

---

## 10. Money-Usefulness Contribution

This audit protects capital-research quality by showing:

- Trending/active **provider lists alone do not create Pump origin**.
- Failed and non-create Pump program traffic must **not** become launch memory.
- Empty create capture is a **productivity problem under a tiny sample and correct fail-closed origin**, not a reason to force two-slot activation.
- Spending the next effort on **honest create-capture design** (and only then optional decoder/layout adoption) is higher value than rerunning the same under-sampled pilot.

No paper profit, ranking, or decision unlock is implied.

---

## 11. What Remains Locked

- Design implementation and any decoder/runtime change  
- Another pilot / V2-9.7F / V2-9.8  
- Weakening finalized origin authority or two-or-none  
- Provider-label origin substitution  
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL  
- Wallets, keys, live execution, paid APIs, scoring/ranking/confidence, embeddings/vectors  
- Dirty-memory training paths; 5m as main outcome; 12h/24h expansion  

---

## 12. Functionality Risks / Setbacks / Efficiency Blockers

1. **Busy program history** makes small unfiltered signature samples create-poor; pilots proved this at n=4.  
2. **Full 32/16 ceilings still may be insufficient** during extreme traffic — unproven; design must plan for honest `GAPPED`/`UNKNOWN`.  
3. **`create_v2` intentional gap** may become the next hard wall once samples include real creates.  
4. **Secondary mint historical origin** may hit free RPC retention walls even if designed carefully.  
5. **Harness/production gap evidence is code-only** today; deep reclassification of live failures needs better bounded evidence retention.  
6. **Tracker 180s emptiness** (E.3) remains a separate productivity issue and must not be “fixed” by weakening origin.  
7. **Origin admission ceiling (8)** is moot at zero creates but will matter once creates appear.  
8. Re-running pilots without fixing create-capture productivity will **waste budget** and reproduce `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`.

---

## 13. Verification Performed

| Check | Result |
|---|---|
| `git rev-parse HEAD` = `295f4e6…` | PASS |
| Read-only pilot DB inspection | both DBs |
| Read-only pilot JSON / harness inspection | both pilots |
| Static decoder + origin contract consistency | PASS |
| Focused tests: `tests/test_v2_9_7d_7b_4a_direct_pump_adapter.py`, `tests/test_pumpfun_direct_create_contract_fixture.py` | **15 passed** |
| Network / source fetch | **none** |
| DB mutation / production code change | **none** |
| `git diff --check` | on commit of this document |

## Exact Recommended Next Lane

**`V2-9.7E.4B — Direct Pump Create-Capture Productivity Design`**

Design-only. Specify create-preferring sampling, operational use of adopted ceilings, cutoff/cursor productivity rules, optional bounded mint-scoped secondary origin lookup **without** weakening finalized origin, and evidence retention for decode classes. No implementation, no pilot, no V2-9.7F, no V2-9.8 in that lane.

Optional subsequent lanes (only after 4B design PASS and operator authorization), unchanged in spirit from E.3:

1. Decoder coverage repair / `create_v2` adoption **if** design+evidence requires it  
2. Tracker freshness contract re-audit  
3. Eligibility auditability repair  
4. One reauthorized pilot under E.2 preflight  

## Stop Boundary

V2-9.7E.4A ends here. Do **not** begin design, implementation, decoder changes, pilot rerun, V2-9.7F, or V2-9.8 from this audit alone.
