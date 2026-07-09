# Printer V1 V2-2J Discovery/Selection Foundation Closeout

**Lane:** V2-2J — Discovery/Selection Foundation Closeout Report
**Type:** Documentation-only closeout
**Verdict:** `CLOSEOUT_COMPLETE_WITH_BLOCKERS`
**Date:** 2026-07-09
**Executor:** Claude Sonnet 4.6

---

## 1. Executive Verdict

**`CLOSEOUT_COMPLETE_WITH_BLOCKERS`**

The V2-2 Discovery/Selection Foundation has completed its core repair cycle.
Every structural contradiction identified in V2-2K has been addressed with a
design, implementation, verification, or bounded proof. The four major problem
areas — WATCH_ONLY/D1 quota handoff, pair market-age context metadata, cross-
batch selection rotation/cooldown, and same-token discovery persistence gate
reform — each reached a bounded proof verdict of `PROOF_PASS` or
`PROOF_PASS_WITH_BLOCKERS`.

The remaining blockers are documented, understood, and appropriate for carry-
forward into later explicitly approved lanes. They do not represent missing
correctness in what V2-2 designed and proved; they represent scope that was
intentionally deferred to preserve lane focus and avoid scope creep.

V2-3 remains paused pending operator acceptance of this closeout. The
recommended next lane is V2-3 design-only, with conservative conditions
stated in Section 8.

This closeout does not unlock V2-3, memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL. It is a
documentation consolidation only.

---

## 2. Source Stack Read

The following documents were read as the active source-of-truth stack:

| Document | Role |
|---|---|
| `AGENTS.md` | Highest authority |
| `docs/printer-v1-clean-master-spec.md` | Master specification |
| `docs/printer-v1-post-rc-build-order.md` | Post-RC lane order |
| `docs/printer-v1-memory-factory-guide.md` | Memory factory rules |
| `docs/printer-v1-current-state-memory-growth-audit.md` | Baseline state |
| `docs/printer-v1-memory-growth-build-order-v2.md` | V2 roadmap |

V2-2 lane artifacts read:

| Document | Lane | Verdict |
|---|---|---|
| `docs/printer-v1-v2-2k-...audit.md` | V2-2K | AUDIT_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2l-...design.md` | V2-2L | DESIGN_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2n-...bounded-proof.md` | V2-2N | PROOF_PASS_WITH_BLOCKERS |
| `docs/printer-v1-v2-2n-1-...proof.md` | V2-2N.1 | PROOF_PASS |
| `docs/printer-v1-v2-2p-3-...verification.md` | V2-2P.3 | VERIFICATION_PASS |
| `docs/printer-v1-v2-2q-...audit.md` | V2-2Q | AUDIT_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2r-...design.md` | V2-2R | DESIGN_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2t-...proof.md` | V2-2T | PROOF_PASS |
| `docs/printer-v1-v2-2u-...design.md` | V2-2U | DESIGN_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2v-...implementation.md` | V2-2V | IMPLEMENTATION_COMPLETE_WITH_BLOCKERS |
| `docs/printer-v1-v2-2v-1-...verification.md` | V2-2V.1 | VERIFICATION_PASS_WITH_BLOCKERS |
| `docs/printer-v1-v2-2w-...proof.md` | V2-2W | PROOF_PASS_WITH_BLOCKERS |

---

## 3. Lane Timeline and Artifact Map

The extended V2-2 Discovery/Selection Foundation work spans V2-2K through V2-2W:

| Lane | Type | Commit | Verdict |
|---|---|---|---|
| V2-2K | Practical coverage diagnostic audit | `2cd7940` | AUDIT_COMPLETE_WITH_BLOCKERS |
| V2-2L | WATCH_ONLY/D1 quota handoff design | `da584d9` | DESIGN_COMPLETE_WITH_BLOCKERS |
| V2-2M | Audit-only handoff implementation | `0fc06a0` + `e70c605` | IMPLEMENTATION |
| V2-2N | WATCH_ONLY handoff bounded proof | `04cb35f` | PROOF_PASS_WITH_BLOCKERS |
| V2-2N.1 | D1/selection-batch audit-only follow-up | (doc commit) | PROOF_PASS |
| V2-2O | Token-age evidence repair design | (doc commit) | DESIGN |
| V2-2P/P.1/P.2/P.3 | Pair market-age context impl + verification | `d879627` `ff8251d` `165bf6e` `09d4ea0` `be70309` | VERIFICATION_PASS |
| V2-2Q | Fair-chance / selection rotation audit | `b460ce1` | AUDIT_COMPLETE_WITH_BLOCKERS |
| V2-2R | Fair-chance / selection rotation design | `a1257a0` | DESIGN_COMPLETE_WITH_BLOCKERS |
| V2-2S/S.1/S.2/S.3 | Cross-batch selection cooldown impl + verification | `22d0e51` `f120f1e` `8914697` `0870307` | IMPLEMENTATION + VERIFIED |
| V2-2T | Cross-batch selection rotation proof | `6d616cf` | PROOF_PASS |
| V2-2U | Discovery persistence gate reform design | `fe60ba6` | DESIGN_COMPLETE_WITH_BLOCKERS |
| V2-2V | Discovery persistence gate reform implementation | `147d4b7` | IMPLEMENTATION_COMPLETE_WITH_BLOCKERS |
| V2-2V.1 | Discovery gate reform verification | `0d3e6c2` | VERIFICATION_PASS_WITH_BLOCKERS |
| V2-2W | Discovery gate reform bounded proof | `a5350e8` | PROOF_PASS_WITH_BLOCKERS |

---

## 4. What V2-2K Through V2-2W Accomplished

### 4.1 V2-2K — Practical Coverage Diagnostic Audit

V2-2K ran a bounded three-request, two-provider, three-channel live discovery
cycle against a proof DB and measured end-to-end pipeline coverage.

Key findings:

- **70 raw candidates** across eight asset classes. GeckoTerminal persisted 20;
  DexScreener persisted 0 (generic query dominated by non-Solana and STNP events).
- **All 70 candidates** had `token_age_seconds = null` (100% AGE_UNKNOWN).
- **0 of 70** had native 15m price/volume fields.
- **13 raw WATCH_ONLY candidates** were present but rejected before persistence,
  meaning a 6+ batch could never satisfy the `MISSING_WATCH_ONLY` quota.
- **3 raw D1 candidates** existed but were also blocked before persistence,
  meaning `MISSING_D1_DEAD_TOKEN` quota violations were guaranteed on normal runs.
- This established a **structural quota contradiction**: WATCH_ONLY was required
  by quota but removed before any WATCH_ONLY candidate could reach selection.
- A3 remained blocked (token age required). A4 remained helper-only.
- PumpPortal and PumpSwap channels remained NOT_READY.

Verdict: `AUDIT_COMPLETE_WITH_BLOCKERS`. V2-2K proved Printer is safe but cannot
produce a quota-valid balanced selection batch under the pre-repair architecture.

### 4.2 WATCH_ONLY/D1 Audit-Only Handoff (V2-2L through V2-2N.1)

V2-2L designed a two-layer candidate pool architecture (L2 audit-only pool)
that captures WATCH_ONLY and D1 candidates at the pre-persistence rejection
boundary and makes them available for quota satisfaction without active tracking.

V2-2M implemented the handoff. V2-2M.2 repaired eligibility guards.

V2-2N proved on a live isolated proof DB that:
- 7 eligible WATCH_ONLY candidates entered the transient audit-only pool;
- 1 WATCH_ONLY candidate satisfied the quota minimum;
- 0 WATCH_ONLY candidates were persisted as active tracking;
- all source trace and rejection reasons were preserved end to end;
- audit-only candidates created zero active tracking, scheduler, memory,
  retrieval, paper, or financial rows.

V2-2N.1 closed the D1 gap with a deterministic fixture proof demonstrating:
- eligible D1 candidates enter the audit-only pool and change quota from
  `FAIL` to `PASS` when both WATCH_ONLY and D1 are present;
- unsafe D1/WATCH_ONLY candidates (FAILED source status, DIRTY_DATA quality)
  are blocked and cannot create a fake quota pass;
- a persisted V2-2C selection batch correctly distinguishes 6 ACTIVE_TRACKING
  from 2 AUDIT_ONLY items in `candidate_metadata_json`.

### 4.3 Pair Market-Age Context Metadata (V2-2P/P.1/P.2/P.3)

V2-2O designed a token-age evidence design with T1/T2/T3 source tiers.

V2-2P implemented pair market-age context as separate categorical metadata
(not a token-age substitute). V2-2P.3 verified the metadata handoff:
- `pair_age_context_label` and `token_age_evidence_tier` survive
  `build_batch_item()` and selection-batch DB persistence;
- `derive_age_bucket()` still reads only `token_age_seconds` — pair age
  cannot substitute for token age at any gate;
- A3 and recent-active tiers remain blocked when token age is unknown.

The pair age context result: pair age is now correctly visible as categorical
audit metadata without polluting the age-bucket or token-age derivation.

### 4.4 Fair-Chance / Selection Rotation (V2-2Q through V2-2T)

V2-2Q audited the cross-batch repetition problem and confirmed:
- discovery over-blocked (permanent existing-mint exclusion);
- selection under-controlled (no cross-batch cooldown);
- no measured cross-batch repetition prevention in the audited path.

V2-2R designed six categorical rotation rules:
- Rule 1: token-level 3-batch selection cooldown;
- Rule 2: pair-level 3-batch selection cooldown;
- Rule 3: source/channel concentration soft warning (60% cap, 3-batch window);
- Rule 4: category concentration soft warning (50% cap, 3-batch window);
- Rule 5: evidence freshness gate with `STALE_EVIDENCE_RESELECT` label;
- Rule 6: fair-aging single slot for candidates absent from 6 recent batches.

V2-2R also defined the `printer_selection_rotation_state` table, a 7-category
duplicate/resurfacing taxonomy (EXACT_DUPLICATE, DUPLICATE_RECYCLE,
STNP_UNRESOLVED, MIGRATION, REVIVAL, DISTINCT_NEW_EVIDENCE, PAIR_DRIFT), and
a two-tier discovery persistence policy.

V2-2S/S.1/S.2/S.3 implemented and verified cross-batch selection cooldown
(Rules 1 and 2). Migration 026 created `printer_selection_rotation_state`.

V2-2T proved Rules 1 and 2 on an isolated fixture proof DB across 6 scenarios
(36/36 checks pass):
- token blocked at batches 2 and 3 after selection, allowed at batch 4;
- pair-level cooldown independent of token-level cooldown;
- `MAX(last_selected_batch_seq)` prevents multi-pair mints from being
  evaluated against stale older pair rows;
- cooldown-rejected candidates do not update rotation state;
- rotation state persists and increments correctly on re-selection;
- zero rows in memory, retrieval, paper, financial, or source tables.

### 4.5 Discovery Persistence Gate Reform (V2-2U through V2-2W)

V2-2U designed the Tier 2 lifecycle-aware discovery persistence pre-check.
The flat "block all existing mints" gate was replaced with a two-tier policy:

- **Tier 1** (unchanged): EXACT_DUPLICATE, STNP_UNRESOLVED, PAIR_DRIFT,
  DUPLICATE_RECYCLE unconditionally blocked.
- **Tier 2** (new): MIGRATION, REVIVAL, DISTINCT_NEW_EVIDENCE conditionally
  allowed before the flat rejection fires.

V2-2V implemented four new helpers in `commands.py`:
`_load_returning_mint_lifecycle_statuses()`, `_load_last_discovery_fingerprint()`,
`_fingerprint_change_type()`, `_classify_returning_candidate()`.
`_select_discovery_candidates()` was extended with `db_path_or_conn` (defaults
to `None` for backward compatibility).

V2-2V.1 verified the insertion point, all three Tier 2 paths, Tier 1 hard
blocks, and reporting fields. Confirmed B-PERSIST-1 is a documentation wording
issue only (V2-2S already writes `last_evidence_fingerprint_json` to rotation
state; V2-2V correctly reads `printer_discovery_candidates` for
DISTINCT_NEW_EVIDENCE since the discovery gate must not depend on a prior
selection batch having run).

V2-2W proved all three Tier 2 paths on an isolated deterministic fixture DB:
- MIGRATION: same-token/new-pair on migration channel → ALLOWED;
  existing pair or non-migration STNP → blocked;
- REVIVAL: ARCHIVED + reviving activity → ALLOWED;
  QUEUED or dead-activity cases → blocked;
- DISTINCT_NEW_EVIDENCE: meaningful fingerprint change → ALLOWED;
  no historical payload or pair-age-only change → blocked;
- Tier 1 hard blocks: non-Solana, missing pair, STNP drift → blocked before
  Tier 2 fires;
- selection-cooldown separation confirmed: Tier 2 discovery allowance and
  selection cooldown (Rules 1/2) are independent gates;
- zero downstream deltas across all memory, retrieval, paper, financial,
  source, and scheduler tables.

---

## 5. What Is Now Proven

| Proven capability | Lane(s) | Proof type |
|---|---|---|
| Audit-only WATCH_ONLY representation in selection batch | V2-2N, V2-2N.1 | Live + deterministic fixture |
| Audit-only D1 representation in selection batch | V2-2N.1 | Deterministic fixture |
| Source trace and rejection reason survive audit-only selection | V2-2N, V2-2N.1 | Live + fixture |
| Unsafe audit-only candidates (FAILED, DIRTY) cannot satisfy quota | V2-2N, V2-2N.1 | Tested |
| Audit-only candidates create zero active tracking/scheduler rows | V2-2N, V2-2N.1 | Row-delta lock |
| Pair market-age context does not substitute for token age | V2-2P.3 | Static + tests |
| `pair_age_context_label` and `token_age_evidence_tier` survive selection persistence | V2-2P.3 | DB persistence test |
| Cross-batch token-level selection cooldown (3-batch window) | V2-2T | 36-check fixture proof |
| Cross-batch pair-level selection cooldown | V2-2T | 36-check fixture proof |
| Multi-pair MAX(last_selected_batch_seq) safety | V2-2T | Fixture proof |
| Cooldown-rejected candidates do not update rotation state | V2-2T | Fixture proof |
| MIGRATION Tier 2 allowance (migration channel + new pair) | V2-2W | Deterministic fixture |
| REVIVAL Tier 2 allowance (ARCHIVED/COOLDOWN + ACTIVITY_REVIVING) | V2-2W | Deterministic fixture |
| DISTINCT_NEW_EVIDENCE Tier 2 allowance (meaningful fingerprint change) | V2-2W | Deterministic fixture |
| Tier 1 hard blocks intact after Tier 2 added | V2-2W | Deterministic fixture |
| Tier 2 discovery and selection cooldown are independent gates | V2-2W | Fixture proof |
| Row-delta locks in all bounded proofs | V2-2N, V2-2T, V2-2W | Row-delta tables |
| Backward compatibility (no db_path_or_conn → flat gate unchanged) | V2-2V test suite | 45 targeted tests |

---

## 6. What Remains Blocked

The following blockers are documented, understood, and suitable for carry-forward.
None were introduced by V2-2K through V2-2W; all existed before V2-2K or were
explicitly deferred to later designated lanes.

### 6.1 Token Creation Age (CRITICAL CARRY-FORWARD)

- `token_age_seconds` is null for 100% of candidates in V2-2K live audit (70/70).
- No current live READY single-response discovery source provides token creation age.
- All 70 candidates remain `AGE_UNKNOWN` / `UNKNOWN_TIER_5`.
- V2-2O designed a T1/T2/T3 token-age evidence design. That design designated
  approved future source tiers but has not been implemented or proved.
- `token_age_evidence_tier` remains `None` in all current discovery candidates.
- **Blocked capabilities:** A3 (requires `token_age_seconds` and negative 1h price
  change), recent-active tier, age-bucket-based prioritization.
- **Required future lane:** token-age evidence implementation and proof.

### 6.2 Native/Staged 15m Price/Volume Fields

- `price_change_15m` and `volume_15m` are missing for 100% of candidates.
- These cannot be fabricated from 5m or 1h fields.
- Real 15m change/volume values require staged governed snapshots, not a single
  discovery payload.
- **Required future lane:** staged snapshot derivation design and implementation.

### 6.3 A3 Blocked

- A3 requires `token_age_seconds` below the "recent token" threshold and known
  negative 1h price change.
- Blocked until token-age evidence is resolved.

### 6.4 A4 Helper-Only

- A4 requires comparing prior and current candidate evidence at a context-aware
  call site.
- No main-path prior-context integration exists.
- Future approved work must wire A4 safely.

### 6.5 Source Expansion Paused

- PumpPortal launch and migration streams: NOT_READY in V2-2K.
- PumpSwap pool confirmation and migration reference: NOT_READY in V2-2K.
- DexScreener generic query productivity remains limited (zero persisted
  in V2-2K due to non-Solana noise and STNP clusters).
- Migration channel evidence supply (PUMPFUN_MIGRATION, PUMPSWAP_GRADUATED,
  PUMPSWAP_MIGRATION_POOL_REFERENCE) therefore has no live READY feed for
  the MIGRATION Tier 2 path to exercise under real conditions.
- **Required future lane:** separate bounded transport implementation/proof per
  source when operator approves.

### 6.6 `_fingerprint_change_type()` Same-Group Reporting Nuance

- `_fingerprint_change_type()` can report `primary_bucket_group_crossing`
  whenever `old_bucket != new_bucket`, even for same-group bucket changes.
- The safety gate (`fingerprint_change_is_meaningful()`) is called first and
  correctly blocks same-group changes; the allowance decision is correct.
- The reporting label may be over-broad on candidates already allowed by
  activity-bucket or source-channel change when primary bucket also changed
  within the same group.
- **Status:** non-blocking reporting nuance. Does not affect any gate, score,
  memory row, retrieval, paper, or financial path.

### 6.7 No Live Discovery Capacity Proof for V2-2V Tier 2 Gate

- V2-2W used deterministic fixture candidates, not a live source response.
- The Tier 2 gate has not been exercised against a real GeckoTerminal or
  DexScreener response that contains actual returning mints.
- V2-2T (selection cooldown) also used fixtures.
- V2-2N (WATCH_ONLY handoff) used a live proof run but in a narrower scope.
- **Status:** acceptable for current closeout. The deterministic fixture proof
  demonstrates correctness of the gate mechanics. A live integration proof is
  desirable but not required for V2-3 design-only to proceed.

### 6.8 V2-2R Rules 3/4/5/6 Not Implemented

- V2-2R designed 6 selection rotation rules. V2-2S/V2-2T implemented and proved
  Rules 1 and 2 (token/pair cooldown).
- Rules 3/4 (source/category soft warnings), Rule 5 (evidence freshness gate
  enforcement as a selection-path policy), and Rule 6 (fair-aging) remain
  unimplemented.
- **Status:** non-blocking carry-forward. Rules 1 and 2 address the most immediate
  cross-batch repetition risk. Rules 3-6 are improvements for a future V2-2 follow-up
  or a V2-2 polish lane after V2-3 design.

### 6.9 No V2-3 Activation

V2-3 remains paused pending operator acceptance of this closeout.

---

## 7. Safety and Lock Confirmations

The following invariants were confirmed intact across every V2-2K through V2-2W
lane:

| Safety gate | Status |
|---|---|
| Solana-only (non-Solana rejected before Tier 2) | INTACT |
| Paper-trading-only system | INTACT |
| No live wallet/private keys/real funds/live execution | INTACT |
| No paid API dependency introduced | INTACT |
| No retrieval activation | INTACT |
| No paper decisions created | INTACT |
| No BUY/SELL/HOLD paths changed | INTACT |
| No positions, trades, paper trade audits, PnL | INTACT |
| No dirty memory in retrieval or decisions | INTACT |
| No scoring/ranking/confidence/weighted logic | INTACT |
| No embeddings/vectors | INTACT |
| Source Governor not bypassed | INTACT |
| Central Scheduler not bypassed | INTACT |
| `WINDOW_5M_MICRO_EVENT` remains support-only | INTACT |
| WATCH_ONLY silent promotion gate (`check_watch_only_promotion_gate()`) | INTACT |
| Pair age not copied to `token_age_seconds` | INTACT |
| Audit-only candidates excluded from `printer_tracking_queue` | PROVEN |
| Audit-only candidates excluded from `printer_scheduler_jobs` | PROVEN |
| Row-delta locks zero across memory/retrieval/paper tables in all proofs | PROVEN |
| Persistent DB hash unchanged across all proof runs | CONFIRMED |

---

## 8. Money-Usefulness Contribution

V2-2K through V2-2W collectively improve the quality, balance, and fairness of
Printer's discovery/selection input before any memory is generated. Each
contribution is upstream evidence quality only — not a trading signal, token
ranking, confidence measure, or BUY probability.

**Improved negative/dead-token learning:** Audit-only WATCH_ONLY/D1 handoff
ensures that dead-token and watch-only lessons are not silently discarded at the
pre-persistence gate. A batch that includes one WATCH_ONLY and one D1 minimum
(by quota) contains protective-learning evidence alongside active-tracking
candidates.

**Reduced repeated-token bias:** Cross-batch token/pair selection cooldown
(3-batch window, Rules 1/2) prevents the same popular token from dominating
successive batches. Without Rules 1/2, the same GeckoTerminal top-page tokens
could be selected in every batch, producing a corpus biased toward a narrow
trending set.

**Improved dead/watch-only negative-learning coverage:** Before V2-2L through
V2-2N.1, a 6+ batch always failed `MISSING_D1_DEAD_TOKEN` and
`MISSING_WATCH_ONLY` quota violations because those candidate types were
structurally excluded before selection. After the repair, quota can be honestly
satisfied when the governed source universe contains eligible WATCH_ONLY and D1
candidates.

**Allows legitimate migration/revival/distinct-evidence resurfacing:** The Tier 2
persistence gate reform (V2-2U through V2-2W) lifts the permanent block on
migration-channel candidates with genuinely new pairs, archived/cooldown tokens
that show renewed activity, and same-pair tokens whose evidence has changed
meaningfully. This enables Printer to learn from market evolution events (token
migrations, revivals, liquidity state changes) that the flat gate previously
suppressed.

**Why this still does not produce trading decisions:** All V2-2 work is upstream
of memory generation. Discovery/selection determines which tokens enter the
tracking queue. It does not generate memory windows, does not activate retrieval,
does not create paper decisions, and does not unlock BUY/SELL/HOLD. Trading
decisions require clean memory, retrieval, and conservative decision lanes that
remain paused and explicitly locked.

---

## 9. What This Closeout Does Not Unlock

This closeout report and the V2-2J lane explicitly do not unlock:

- V2-3 implementation (V2-3 design-only is recommended; implementation is V2-4)
- V2-4 one-command memory factory
- Token-age evidence (requires a separate approved lane)
- Source expansion (PumpPortal, PumpSwap, DexScreener query improvement)
- Runtime/scheduler execution
- Memory generation or memory-window creation
- Retrieval activation
- Paper trading or paper decisions
- BUY/SELL/HOLD
- Paper positions, trade events, paper trade audits, or PnL
- Live trading, wallet, private keys, or real funds
- Any paid API dependency
- Scoring, ranking, confidence, or weighted logic
- Embeddings or vectors

---

## 10. Functionality Risks / Setbacks / Efficiency Blockers

| Risk or blocker | Effect | Mitigation / status |
|---|---|---|
| Token age 100% unknown | A3 blocked; age-bucket priority unavailable; discovery input quality limited | Documented carry-forward; V2-2O design exists; separate future lane required |
| Native 15m fields missing | Real 15m classification unavailable at discovery time | Documented; requires staged snapshot derivation in separate lane |
| A3 permanently blocked until token-age resolved | Fast-event classification incomplete; A1-only in practice | Non-blocking for V2-3 design; flagged for V2-4 implementation review |
| A4 helper-only | Failed-pump context comparison not wired | Design gap for future lane; helper exists but no production call site |
| Migration channels NOT_READY for live supply | MIGRATION Tier 2 path has no live feed to exercise | Tier 2 gate is correct; live proof awaits source expansion approval |
| DexScreener query productivity weak | Zero persisted candidates in V2-2K; generic query dominated by non-Solana and STNP | Query improvement is future scope; Solana and STNP gates block unsafe rows safely |
| PumpPortal/PumpSwap NOT_READY | Revival and migration lesson supply limited | Separate transport implementation lane required after operator approval |
| V2-2R Rules 3/4/5/6 unimplemented | Source/category concentration not capped; evidence freshness not enforced as policy; fair-aging not active | Rules 1/2 address the most critical repetition risk; Rules 3-6 are future V2-2 polish |
| `_fingerprint_change_type()` reporting nuance | Over-broad `primary_bucket_group_crossing` label in some DISTINCT_NEW_EVIDENCE cases | Non-blocking; safety gate (`fingerprint_change_is_meaningful()`) is correct; carry-forward note |
| No live Tier 2 gate capacity proof | V2-2W used deterministic fixtures only; live returning-mint exercise has not been run | Acceptable for closeout; deterministic proof demonstrates correctness; live exercise desirable in future proof lane |
| Selection table absent from persistent live DB pre-V2-2S | Cross-batch rotation required migration 025 (selection batch) and 026 (rotation state) | Applied in V2-2S implementation; tables now present in proof DBs and live DB migration state |
| Source concentration still GeckoTerminal-dominant | All persisted candidates in recent live proofs from GeckoTerminal; DexScreener contributed zero | Documented in V2-2K; soft warning (Rule 3) is designed but not yet implemented |

---

## 11. Proof Summary Table

| Proof | Scope | Verdict |
|---|---|---|
| V2-2N live WATCH_ONLY handoff | Live GeckoTerminal run on isolated proof DB | PROOF_PASS_WITH_BLOCKERS |
| V2-2N.1 D1 selection-batch fixture | Deterministic fixture, D1 quota satisfaction | PROOF_PASS |
| V2-2P.3 pair age metadata verification | Static + test suite | VERIFICATION_PASS |
| V2-2T cross-batch cooldown fixture | 36/36 checks on isolated fixture DB | PROOF_PASS |
| V2-2V.1 Tier 2 gate verification | Static + test suite (415 tests) | VERIFICATION_PASS_WITH_BLOCKERS |
| V2-2W Tier 2 gate bounded proof | Deterministic fixture, 7 proof scenarios | PROOF_PASS_WITH_BLOCKERS |

---

## 12. Next Recommended Lane

**Recommended: V2-3 — One-Command Memory Factory Automation Design (design-only)**

### Reasoning

V2-3 is a pure documentation/design lane. It cannot cause runtime harm, DB
mutation, or financial lock violations. The V2-2 foundation has now:

1. Resolved the WATCH_ONLY/D1 quota structural contradiction.
2. Verified pair market-age context metadata flows correctly without substituting
   for token age.
3. Implemented and proved cross-batch selection cooldown.
4. Implemented and proved the Tier 2 discovery persistence gate reform.

These are the four structural blockers V2-2K identified. All four have been
addressed with design + implementation + bounded proof (or verification).

The remaining carry-forward blockers (token-age, A3/A4, source expansion,
V2-2R Rules 3-6, live Tier 2 capacity proof) are real but are either:
- designated for their own future approved lanes and do not affect the V2-3
  factory design structure; or
- improvements that can be addressed in a V2-2 polish lane after V2-3 design,
  or explicitly modeled as constraints in the V2-3 design (e.g., the design
  acknowledges that discovery input is AGE_UNKNOWN-dominated until token-age
  is resolved).

V2-3 design-only answers the question: what is the one-command flow from
discovery to 15m memory? It does not require token-age to be solved to answer
that design question.

### Conservative Conditions on V2-3

V2-3 design must:

1. Remain design/documentation only — no implementation, no DB mutation, no
   source fetching, no runtime execution.
2. Explicitly document that discovery input quality is limited by AGE_UNKNOWN
   tokens, missing 15m fields, and GeckoTerminal concentration.
3. Scope its target flow to `WINDOW_15M` only (per build-order Section 5,
   `V2-3` and `V2-4` target `WINDOW_15M only`).
4. Preserve all V2 common locks (Source Governor, Central Scheduler, no
   retrieval, no paper decisions, no BUY/SELL/HOLD, no positions, no PnL).
5. Not treat V2-3 design as an implicit unlock of any carry-forward blocker.
6. Recommend token-age evidence design as a prerequisite before V2-4
   implementation if the operator wants a full-quality discovery input for
   the factory.

### Why Not Option B (Token-Age Evidence Design) First?

Token-age evidence (V2-2O design exists) is important but:
- V2-3 design does not require token-age to be resolved.
- Token-age is a discovery input quality issue, not a factory design
  architecture issue.
- Delaying V2-3 design until token-age is solved risks indefinite pause of
  the one-command factory design while waiting for an external data source.
- The V2-2O design already exists and can be referenced in V2-3's constraints.

Token-age evidence implementation and proof should be recommended before V2-4
(implementation), not before V2-3 (design).

### Why Not Option C (Another V2-2 Follow-Up) First?

No unresolved blocker in V2-2K through V2-2W requires a mandatory V2-2 repair
before V2-3 design. The remaining items are:
- Rules 3-6 (improvements, not correctness failures);
- live Tier 2 capacity proof (desirable, but deterministic fixture proof
  demonstrates gate mechanics correctly);
- source expansion (separate approved lane; does not block design).

The V2-2W verdict of `PROOF_PASS_WITH_BLOCKERS` is sufficient for V2-3 design
to proceed. The blockers are carry-forward notes, not stop conditions.

---

## 13. Whether V2-3 Remains Paused

**V2-3 remains paused until the operator explicitly accepts this V2-2J closeout.**

Upon operator acceptance, V2-3 may proceed as a design-only lane subject to the
conservative conditions in Section 12. V2-3 implementation (V2-4) must not start
until V2-3 design is operator-accepted.

Token-age evidence implementation, source expansion, memory generation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL
remain locked regardless of V2-3 progress.

---

## 14. Git Checks

Run immediately before committing this doc:

```
git diff --check      → CLEAN (LF→CRLF warning only, no whitespace errors)
git status --short    → closeout doc only; all other changes untracked/not staged
git diff --stat       → no modified tracked files
git diff --name-only  → no modified tracked files
```

Committed files: `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md` only.

Not committed: `data/`, `operator-runs/`, proof DBs, temp files, unrelated lane
output `.txt` files.

---

## 15. Closeout Verdict

```
CLOSEOUT_VERDICT: CLOSEOUT_COMPLETE_WITH_BLOCKERS
LANES_COVERED: V2-2K through V2-2W
CORE_STRUCTURAL_CONTRADICTIONS_RESOLVED: 4 of 4
REMAINING_BLOCKERS: Documented and appropriate for carry-forward
SAFETY_LOCKS: All intact
V2-3_STATUS: PAUSED pending operator acceptance of this closeout
RECOMMENDED_NEXT_LANE: V2-3 design-only after operator accepts
TOKEN_AGE_STATUS: Unresolved; separate future lane before V2-4
SOURCE_EXPANSION_STATUS: Paused
MEMORY_GENERATION: Locked
RETRIEVAL: Locked
PAPER_DECISIONS: Locked
BUY_SELL_HOLD: Locked
POSITIONS_TRADES_AUDITS_PNL: Locked
```
