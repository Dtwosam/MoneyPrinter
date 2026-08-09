# Printer V1 V2-9.8B Post-DTW100 Selective WINDOW_4H Current-State Audit

## Verdict

```text
V2_9_8B_POST_DTW100_SELECTIVE_4H_CURRENT_STATE_AUDIT_COMPLETE_DESIGN_INPUT_READY_SEQUENCING_BLOCKED
```

The current repository contains proven, reusable `WINDOW_1H -> WINDOW_4H` cadence, continuity, closeout, E2Q, Lane Q, and E2Z/clean-promotion primitives. V2-9 Attempt 7 already proved one genuine current-run `WINDOW_4H` result end to end on an isolated proof database.

However, `WINDOW_4H` is **not operationally active in the current V2-9.8B two-token campaign**. The current public operational command keeps `WINDOW_4H` locked, the authoritative cadence policy keeps 4h real collection disabled, and no current campaign-owned post-1h orchestration layer derives/persists 1h-to-4h verdicts and schedules 0/1/2 selective 4h continuations.

This audit also corrects the proposed lane wording that preceded it: the active source stack does **not** authorize making 4h a standard continuation for both tokens. `WINDOW_15M -> WINDOW_1H` is now the standard first-hour lifecycle, but `WINDOW_1H -> WINDOW_4H` remains conditional/selective. Making 4h unconditional would require a separate policy-design/adoption decision; it must not be smuggled into implementation.

Finally, 4h implementation is sequencing-blocked by the still-open post-DTW100 first-hour one-use authorization/wrapper integration gap. That trust boundary must be designed, implemented, proved, rereadied, freshly authorized, independently reviewed, and operationally proved before a later 4h operational-integration implementation or authorization can proceed.

This lane is audit/readiness only. It creates no runtime, authorization, database mutation, source call, Scheduler work, memory, retrieval, paper decision, position, trade, audit, or PnL.

---

## 1. Baseline and scope

- Repository: `Dtwosam/MoneyPrinter`
- Verified starting branch: `agent/v2-9-8b-post-dtw100-first-hour-harness-reporting-alignment-implementation`
- Verified starting HEAD: `9f2fbab785fa527757d02469c78a5cf9b47eda9f`
- Starting branch vs exact HEAD: identical, `0` ahead / `0` behind
- Audit branch: `agent/v2-9-8b-post-dtw100-selective-4h-current-state-audit`
- Audit branch created exactly from `9f2fbab785fa527757d02469c78a5cf9b47eda9f`

Allowed in this lane:

- static source inspection;
- historical proof/closeout inspection;
- source-stack reconciliation;
- audit documentation.

Not allowed:

- production implementation;
- migration;
- authoritative DB mutation;
- provider/RPC calls;
- Central Scheduler runtime;
- memory generation;
- authorization creation;
- wrapper execution;
- `WINDOW_15M`, `WINDOW_1H`, or `WINDOW_4H` runtime;
- 12h/24h activation;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

---

## 2. Source stack applied

This audit used the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

It also inspected the just-in-time 4h and current-operation surfaces:

- `docs/printer-v1-v2-8-4h-readiness-review.md`
- `docs/printer-v1-v2-9-final-closeout.md`
- `docs/printer-v1-v2-9-7c-operational-memory-factory-design.md`
- `docs/printer-v1-v2-9-7b-2-timeframe-aware-safety-label-closeout.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-selective-1h-operational-rereadiness-audit.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-first-hour-harness-reporting-alignment-implementation-proof-closeout.md`
- `src/printer_v1/scheduler/token_local_continuation.py`
- `src/printer_v1/snapshots/cadence_policy.py`
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`
- `src/printer_v1/operator_cli/lane_i_4h_staged_memory_factory.py`
- `src/printer_v1/operator_cli/e2q_memory_window_audit.py`
- `src/printer_v1/operator_cli/lane_q_15m_window_integrity_guard.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
- `tests/test_v2_9_7d_4a_token_local_selective_continuation.py`

`docs/printer-v1-memory-growth-build-order-v2.md` is used as the active memory-growth build order inside the source stack, not as the sole source of truth.

The Solana Builder reference stack was consulted only for its subordination/freshness posture. It remains subordinate and cannot override the active Printer stack.

---

## 3. Roadmap correction: 4h is selective, not standard

The preceding proposed wording suggested a “Standard Four-Hour Lifecycle” that could make both tokens continue automatically to 4h. That does not align with the active source stack.

The Memory Factory Guide defines the campaign shape as:

```text
... WINDOW_15M closeout
-> selective WINDOW_1H continuation
-> conditional WINDOW_4H continuation
...
```

Its timeframe policy further requires selective continuation and says not every token should receive every timeframe.

The V2-9.7C operational design likewise defines:

```text
... selective per-token WINDOW_1H
-> conditional per-token WINDOW_4H
...
```

and explicitly says Printer never tracks every timeframe for every token.

The current committed policy implementation has since amended only the first transition:

```text
WINDOW_15M -> WINDOW_1H = standard first-hour lifecycle
WINDOW_1H -> WINDOW_4H = selective and learning-need-gated
```

Therefore the roadmap-compliant interpretation is:

1. every otherwise-valid activated token receives the standard first hour;
2. after a valid clean 1h predecessor, each token is independently evaluated for 4h;
3. zero, one, or two tokens may continue to 4h;
4. a normal no-learning-need result may stop after 1h;
5. hard evidence/safety/identity/continuity/budget failures block continuation;
6. no token receives 4h merely because it existed for one hour or performed well/poorly.

Classification: `ACTIVE_POLICY_SELECTIVE_4H`.

A future proposal to make 4h standard for every otherwise-valid token would be a **policy change**, not a harmless runtime simplification. It would require its own audit/design/adoption justification, including source/scheduler capacity and corpus-value consequences, before implementation.

---

## 4. Current pure 1h-to-4h continuation policy

The authoritative pure evaluator already supports:

- `CONTINUE_TO_WINDOW_4H`
- `STOP_AFTER_WINDOW_1H`
- `BLOCK_CONTINUATION`

For `WINDOW_1H -> WINDOW_4H`, allowed categorical learning needs are:

- `TRANSITION`
- `SURVIVAL`
- `COLLAPSE`
- `REVIVAL`
- `DISTRIBUTION`
- `LIQUIDITY_DETERIORATION`

No learning need produces the normal `STOP_AFTER_WINDOW_1H` verdict.

Before the learning-need branch is reached, the same hard gates remain mandatory:

- exact campaign/configuration/token-slot/token/mint/pair/lifecycle/predecessor identity;
- campaign running/eligible;
- shared DB, lease, and integrity health;
- exact supported transition;
- token not cancelled/terminal;
- eligible tracking state;
- predecessor closed;
- predecessor `CLEAN_MEMORY`;
- predecessor `CLEAN_DATA`;
- predecessor not `do_not_train`;
- evidence eligible and complete;
- freshness within contract;
- governed provenance traceable;
- mandatory safety context present and acceptable;
- continuous predecessor continuity;
- campaign and token budget availability.

Focused tests already prove a two-token 1h-to-4h selective example in which token A stops normally and token B continues.

Classification: `CORE_POLICY_READY_AS_COMMITTED`.

### Missing operational ownership

The pure evaluator is not itself a campaign runtime. Current V2-9.8B operational code does not contain a post-first-hour owner that:

1. loads both authoritative clean 1h predecessor objects;
2. derives the supported 4h learning-need category from current committed evidence without hindsight/scoring;
3. persists immutable token-local 1h-to-4h continuation decisions;
4. creates 0/1/2 campaign `WINDOW_4H` successor identities;
5. advances campaign token-slot state to `WINDOW_4H_CONTINUING` only for valid continuations;
6. schedules the resulting two-token-aware 4h work through Central Scheduler;
7. binds Source Governor accounting and terminal reporting to those exact decisions.

This is the principal 4h campaign-integration gap.

Classification: `MISSING_V2_9_8B_OPERATIONAL_4H_OWNER`.

---

## 5. Proven 4h cadence and continuity foundation

The current cadence policy already contains deterministic 4h contracts.

### TRACK_FAST

- continuation duration after the 1h close: `10,800s`
- target interval: `180s`
- dirty-above gap: `225s`
- hard block above: `360s`
- expected snapshots: `61`
- full anchored duration required
- forced closing snapshot required
- real collection enabled: `false`

### TRACK_NORMAL

- continuation duration after the 1h close: `10,800s`
- target interval: `360s`
- dirty-above gap: `450s`
- hard block above: `720s`
- expected snapshots: `31`
- full anchored duration required
- forced closing snapshot required
- real collection enabled: `false`

The fixed deadline is the exact 1h predecessor close plus 10,800 seconds. Delayed planning or delayed first work must not reset the clock.

This means a token that completes the first hour and then continues through the 4h horizon receives roughly three additional hours of observation; 4h is the total lifecycle horizon, not “1h plus another full 4h.”

Classification: `CADENCE_CONTRACT_PROVEN_BUT_REAL_COLLECTION_DISABLED`.

---

## 6. Historical one-token 4h runtime owner

`one_token_4h_runtime.py` contains a genuine current-run 1h-to-4h proof-era implementation. It already provides reusable primitives for:

- exact current-run predecessor resolution;
- fixed-deadline 4h planning;
- policy-derived FAST/NORMAL snapshot counts;
- Central Scheduler job creation;
- projected scheduler-capacity checks;
- exact token/pair/lane targeting;
- close-step uniqueness;
- chained continuity evaluation;
- cadence evaluation;
- dirty/block terminal behavior;
- 4h candidate-window persistence;
- E2Q -> Lane Q -> E2Z quality/promotion order.

But this module explicitly says real collection remains disabled and requires `explicit_proof_mode=True`.

Its ordinary shape is one-token. Its historical `compressed_two_token_proof` path is a proof-specific compatibility path requiring one exact continuation identity; it is not the current campaign-owned 0/1/2 selective continuation architecture.

Classification: `PROVEN_REUSABLE_PRIMITIVES_NOT_CURRENT_OPERATIONAL_AUTHORITY`.

A future implementation should reuse or extract these proven primitives where safe. It should **not** promote the historical proof runner into a parallel production owner.

---

## 7. Historical Lane I classifier is not runtime authority

`lane_i_4h_staged_memory_factory.py` remains a pure dictionary classifier. It:

- performs no Scheduler work;
- performs no Source Governor work;
- performs no DB runtime orchestration;
- models a standalone 240-minute 4h evidence attempt;
- retains historical assumptions predating the chained current-run 1h-to-4h foundation.

The V2-8 readiness review already concluded that it must be preserved for historical fixture compatibility rather than expanded into the current runtime.

Classification: `HISTORICAL_FIXTURE_ONLY_FOR_OPERATIONAL_DESIGN`.

---

## 8. E2Q, Lane Q, E2Z, and safety are no longer the 4h blocker

### E2Q

Current E2Q admits genuine `WINDOW_4H` and requires:

- anchored boundaries and governed snapshot anchors;
- at least `10,800s` continuation duration;
- exact continuity metadata;
- exact token/pair targeting at start/end anchors;
- non-blocked continuity.

12h/24h remain unsupported.

### Lane Q

The legacy module name remains 15m-oriented, but current code supports `WINDOW_4H` with a `10,800s` minimum and uses the authoritative cadence evaluator. In the approved proof path it can evaluate the disabled 4h policy without enabling production collection.

### E2Z / clean promotion

V2-9 Attempt 7 proved the quality chain through:

```text
E2Q clean candidate
-> Lane Q valid
-> Lane K completed
-> E2Z clean promotion
```

and created a genuine `WINDOW_4H_CLEAN_MEMORY` episode.

### Safety reporting

V2-9.7B.2 later made effective safety reporting timeframe-neutral for accepted 15m, 1h, and 4h evidence without broadening the safety acceptance predicate.

Classification: `QUALITY_AND_SAFETY_FOUNDATION_PROVEN`.

Do not reopen old E2Q/Lane-Q/safety repairs unless a new current defect is demonstrated.

---

## 9. What V2-9 Attempt 7 actually proved

V2-9 final closeout established one real isolated TRACK_FAST lifecycle:

- 15m: `16/16`
- 1h continuation: `24/24`
- 4h continuation: `61/61`
- clean 1h-to-4h transition;
- fixed 4h deadline with zero drift;
- exact anchored 10,800-second 4h continuation;
- complete launcher supervision and cleanup;
- E2Q/Lane Q/E2Z clean promotion;
- one `WINDOW_4H_CLEAN_MEMORY` episode;
- Source Governor/Scheduler ceilings preserved;
- persistent DB isolation preserved;
- all retrieval and financial deltas zero.

That closes the question “can the proven primitives create one real clean 4h memory?” with **yes**.

It does **not** prove:

- two-token operational 4h fairness;
- current V2-9.8B campaign integration;
- 0/1/2 selective successor handling;
- current post-DTW98 end-to-end source accounting;
- current one-use authorization for first-hour or 4h operation;
- generalized persistent-corpus 4h readiness.

Classification: `ONE_TOKEN_4H_CORE_PROOF_PASS_NOT_GENERALIZED_OPERATIONAL_PROOF`.

---

## 10. Current public operational command still locks 4h

The current V2-9.8B public command remains 15m-rooted.

Ordinary mode locks:

```text
WINDOW_1H
WINDOW_4H
WINDOW_12H
WINDOW_24H
```

The current first-hour proof policy opens the 1h continuation path but still locks:

```text
WINDOW_4H
WINDOW_12H
WINDOW_24H
```

No public `selective-4h` or campaign 4h operational mode was found.

The cadence policy independently keeps 4h `enabled_for_real_collection=False`.

Classification: `EXPECTED_LOCKED_OPERATIONAL_STATE`.

Any future 4h activation needs an explicit approved integration lane; it must not be enabled by simply flipping the cadence boolean or removing `WINDOW_4H` from a lock tuple.

---

## 11. Current one-use execution authority blocks jumping ahead to 4h

The post-DTW100 first-hour rereadiness audit already found that the hardened one-use execution-authority chain is implemented only for ordinary 15m operation.

The still-open first-hour gap includes:

- mode-specific final authorization package;
- exact Git/DB binding;
- create-once application marker;
- Git-provenance manifest integration;
- child-terminal binding;
- exactly-one child invocation;
- permanent non-reusability;
- current 900s pre-lifecycle + 3900s lifecycle = 4800s first-hour wall-time binding;
- current end-to-end Source Governor/Scheduler accounting.

The standard-first-hour policy/harness work completed after that audit did **not** implement this trust boundary.

Therefore the project must not jump directly from an offline first-hour policy PASS to 4h operational implementation or authorization.

Classification: `SEQUENCING_BLOCKER_FIRST_HOUR_EXECUTION_AUTHORITY_NOT_CLOSED`.

---

## 12. Source and Scheduler budget audit

Historical 4h phase-local ceilings exist and are useful design inputs:

| Lane | 4h expected snapshots | Historical phase request ceiling | Historical scheduler ceiling |
|---|---:|---:|---:|
| `TRACK_FAST` | 61 | 69 | 64 |
| `TRACK_NORMAL` | 31 | 39 | 34 |

The proof-era one-token cumulative lifecycle helper also derives historical one-token totals across discovery + 15m + 1h + 4h.

These values are **not sufficient as current V2-9.8B two-token authorization ceilings**.

Reasons:

1. post-DTW98 added a separate 900-second pre-lifecycle temporal-acquisition stage;
2. the current first hour is standard for both otherwise-valid active tokens;
3. selective 4h may produce zero, one, or two continuations;
4. two simultaneous 4h continuations require campaign fairness and shared-ceiling accounting not proven by the one-token runtime;
5. current discovery/acquisition operation accounting must be included from its present owners;
6. context/holder fallback accounting must remain Source-Governed and exact-target;
7. cleanup/reporting reserve and Scheduler ownership must be derived from the current campaign graph, not copied from July proof wording.

A later 4h design must therefore derive and freeze at least these distinct cases:

- zero 4h continuations;
- one FAST continuation;
- one NORMAL continuation;
- two FAST continuations;
- two NORMAL continuations;
- mixed FAST/NORMAL continuations if current campaign state can legitimately contain that combination.

No design may simply double historical one-token ceilings and call the result authoritative without tracing all current owners.

Classification: `CURRENT_END_TO_END_4H_BUDGET_DERIVATION_REQUIRED`.

---

## 13. Required future campaign integration boundary

After the first-hour execution-authority sequence is closed and operationally proved, the smallest roadmap-compliant 4h design should address:

1. **Selective decision owner**
   - exact clean 1h predecessors;
   - no outcome-as-quality confusion;
   - categorical learning-need derivation only;
   - no score/rank/confidence/weight;
   - 0/1/2 independent token verdicts.

2. **Immutable campaign persistence**
   - exact predecessor campaign window and memory window;
   - exact token/mint/pair/lifecycle;
   - persisted `CONTINUE_TO_WINDOW_4H`, `STOP_AFTER_WINDOW_1H`, or `BLOCK_CONTINUATION`;
   - immutable first evaluation and replay-safe behavior.

3. **Campaign window/state integration**
   - create `WINDOW_4H` only for `CONTINUE_TO_WINDOW_4H`;
   - token-slot states `WINDOW_1H_CLOSED -> WINDOW_4H_CONTINUING -> WINDOW_4H_CLOSED`;
   - no successor for STOP/BLOCK.

4. **Central Scheduler fairness**
   - exact policy-derived 61/31 jobs per continuing token;
   - earliest close deadline and no-starvation behavior;
   - shared failure vs token-local failure semantics;
   - zero orphaned jobs after terminalization.

5. **Source Governor accounting**
   - current acquisition + first-hour + 4h end-to-end envelope;
   - opening/closing context and quote calls;
   - safety/holder fallback caps;
   - no independent loop, retries, or endpoint rotation beyond already-approved contracts.

6. **Quality closeout**
   - reuse current continuity, E2Q, Lane Q, and E2Z owners;
   - exact 4h context-ready gate;
   - clean/dirty/blocked truth preserved.

7. **Reporting**
   - distinguish normal STOP from hard BLOCK from CONTINUE;
   - report actual 0/1/2 persisted 4h windows;
   - report quality promotion from authoritative clean objects rather than source-window shorthand;
   - report-only replay adds no work.

8. **Execution authority**
   - mode-distinct one-use authorization;
   - exact Git/DB/quiescence binding;
   - create-once marker before launch;
   - manifest and child-terminal binding;
   - no cross-mode authorization reuse;
   - no retry/rerun/restart/resume/successor.

9. **Window locks**
   - 12h/24h remain locked;
   - 5m remains support-only;
   - retrieval and financial capabilities remain locked.

This audit does not approve that design yet; it defines the evidence-backed subjects a later design must solve.

---

## 14. Money-usefulness contribution

Selective 4h memory is useful because it can spend the most expensive medium-term observation budget on unresolved survival, collapse, revival, distribution, liquidity-deterioration, and transition questions instead of automatically extending every token.

That improves future memory by adding medium-term outcome coverage while limiting source pressure and preserving negative/failure lessons. It does not mean 4h continuation is a BUY signal, a quality score, or a prediction that a token is good.

The standard first hour and selective 4h serve different purposes:

- first hour: broad, unbiased early lifecycle observation for every otherwise-valid activated token;
- 4h: bounded, conditional medium-term follow-through when a declared unresolved learning need remains and all hard gates pass.

---

## 15. What this audit improves

- Corrects the proposed “standard 4h for both tokens” drift before implementation.
- Reconciles current policy with the Memory Factory Guide and V2-9.7C campaign design.
- Confirms 4h cadence/continuity/E2Q/Lane Q/E2Z foundations remain present and proven.
- Separates historical one-token proof machinery from current V2-9.8B operational authority.
- Identifies the missing current campaign-owned 1h-to-4h integration layer.
- Identifies current two-token/end-to-end budget derivation as future design work.
- Preserves the first-hour one-use authorization gap as a mandatory sequencing dependency.

---

## 16. What this audit still does not unlock

- no 4h design adoption;
- no 4h implementation;
- no 4h cadence activation;
- no first-hour or 4h authorization;
- no operational 1h or 4h run;
- no automatic 4h continuation for both tokens;
- no 12h/24h activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions;
- no trade events;
- no paper trade audits;
- no PnL;
- no live execution, wallet, private key, signing, or real funds;
- no paid API;
- no score/rank/confidence/weighted system;
- no embeddings/vectors.

---

## 17. Proof/test needed before any future 4h completion

No new runtime proof belongs in this audit.

A later 4h implementation lane should use focused offline/temp-DB proof first and demonstrate at minimum:

- clean 1h predecessor -> 4h CONTINUE for each allowed learning-need family;
- valid no-learning-need -> STOP after 1h without 4h window creation;
- hard-gate failure -> BLOCK without 4h window creation;
- 0/1/2 continuation persistence and idempotency;
- two-token fairness and mixed token-local outcomes;
- policy-derived FAST/NORMAL cadence and fixed deadlines;
- current end-to-end source and Scheduler ceilings;
- E2Q/Lane Q/E2Z agreement and idempotent clean promotion;
- dirty/blocked evidence never promoted clean;
- interruption/cleanup/replay creates no duplicate work;
- 12h/24h and all retrieval/financial surfaces remain zero-delta.

Only after design, implementation, focused proof, closeout, and fresh read-only rereadiness could a later exact-head one-use authorization sequence even be considered.

---

## 18. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality Risks

1. **Policy drift toward all-token 4h.** Treating 4h like the newly standardized first hour would violate the current Memory Factory selective-continuation law and could waste scarce source/Scheduler capacity.
2. **Pure policy mistaken for runtime.** `token_local_continuation.py` can decide 1h-to-4h inputs but does not own current campaign persistence, scheduling, or source work.
3. **Historical proof runner promoted as production.** `one_token_4h_runtime.py` is proven and valuable but remains proof-era, one-token-oriented, and explicitly disabled for real collection.
4. **Learning-need producer ambiguity.** The current operational campaign lacks a post-1h owner that derives/persists 4h learning need from authoritative evidence; implementation must not invent hindsight labels.
5. **Budget undercount.** Historical 69/39 and 64/34 phase ceilings do not by themselves cover the current post-DTW98 two-token one-shot lifecycle.
6. **Two-token 4h contention.** A both-continue case can multiply long-window work and needs explicit campaign fairness and shared-ceiling proof.
7. **Authorization bypass.** Building 4h before the first-hour one-use authority is closed would extend an already-known trust-boundary gap.

### Setbacks

1. Existing 4h operational primitives were built around a one-token isolated proof, so current campaign integration is not a simple feature flag.
2. Several useful long-window modules retain historical names or compatibility surfaces; renaming them is unnecessary unless a future design proves it is required.
3. The active Memory Factory Guide still contains older language describing 1h itself as selective even though the newer committed first-hour policy made 15m-to-1h standard. This documentation drift should be reconciled only in an appropriate policy/documentation lane; it does not authorize changing 4h selectivity.

### Efficiency Blockers

1. A two-token 4h worst-case envelope is materially larger than the already-proven first-hour envelope and must be re-derived from current owners before authorization.
2. Free/public source reliability remains a practical multi-hour constraint; source failure must stay honest and fail closed rather than trigger retries or hidden fallback expansion.
3. Until a current campaign 4h owner exists, existing 4h proof primitives cannot contribute persistent operational corpus growth.

---

## 19. Correct sequencing after this audit

This audit must not jump directly into 4h implementation.

The next roadmap-compliant dependency is the still-open first-hour execution-authority lane, updated to reflect the now-standard first-hour policy:

```text
V2-9.8B Post-DTW100 First-Hour One-Shot Authorization / Wrapper Integration Design
```

That design should preserve the existing mode-specific one-use safety properties while reconciling any older `selective-1h-*` compatibility names with the current standard-first-hour behavior. It must stop after design before implementation.

Expected sequence after that:

1. first-hour one-shot authorization/wrapper design;
2. first-hour minimal implementation;
3. focused offline proof + closeout;
4. fresh post-implementation read-only rereadiness;
5. fresh exact-HEAD/DB one-use authorization preparation;
6. independent authorization review/closeout;
7. exactly one manually started first-hour operational proof;
8. independent first-hour runtime closeout;
9. only then: selective 4h operational-integration design using this audit;
10. later 4h implementation, focused proof, rereadiness, authorization, and one bounded operational proof in their own approved sequence.

No authorization is created by this audit.

---

## 20. Files changed

- `docs/printer-v1-v2-9-8b-post-dtw100-selective-4h-current-state-audit.md`

## 21. What was built

- One read-only/static current-state audit and roadmap correction for post-DTW100 selective `WINDOW_4H` work.
- A current blocker/readiness map separating proven 4h primitives from missing V2-9.8B operational integration.
- A sequencing handoff back to the unresolved first-hour one-use execution-authority lane.

## 22. What was not touched

- production code;
- tests;
- migrations;
- authoritative DB;
- source/provider/RPC execution;
- Central Scheduler runtime;
- memory generation;
- authorization packages;
- one-shot wrappers;
- lifecycle runtime;
- retrieval or financial functions.

## 23. Tests/checks

Risk-based verification for this audit is static only:

- exact Git baseline comparison;
- active source-stack inspection;
- current 1h-to-4h policy inspection;
- current cadence/runtime/quality-gate inspection;
- historical V2-8/V2-9 proof reconciliation;
- current operational command/wrapper lock inspection;
- focused test-source inspection for selective 1h-to-4h behavior;
- final branch diff verification after this document is committed.

No runtime test is justified or permitted in this audit-only lane.

## 24. Final status

```text
AUDIT: COMPLETE
4H_CORE_PRIMITIVES: PROVEN_AND_REUSABLE
1H_TO_4H_POLICY: SELECTIVE
CURRENT_V2_9_8B_4H_OPERATIONAL_OWNER: MISSING
WINDOW_4H_REAL_COLLECTION: DISABLED
CURRENT_4H_END_TO_END_BUDGET: RE-DERIVATION_REQUIRED
FIRST_HOUR_ONE_USE_AUTHORITY: SEQUENCING_BLOCKER
RETRIEVAL_AND_FINANCIAL_LOCKS: PRESERVED
```
