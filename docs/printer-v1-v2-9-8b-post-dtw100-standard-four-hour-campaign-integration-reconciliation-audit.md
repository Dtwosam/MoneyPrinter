# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Campaign Integration Reconciliation Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_CAMPAIGN_INTEGRATION_RECONCILIATION_READY_FOR_FOCUSED_OFFLINE_PROOF`

Static/read-only reconciliation against the adopted Standard Four-Hour Lifecycle Policy and Campaign-Integration Design finds no remaining production implementation gap before the required overall bounded offline composition proof.

The implementation is **not yet overall-lane PASS** from this audit alone. One exact-HEAD focused integration proof must consolidate the independently passed policy, handoff/planning, collection/state/accounting/fairness, close/memory/terminal and historical regression contracts before the full implementation/proof closeout can pass.

This audit authorizes no source fetching, Scheduler/runtime execution, authoritative DB mutation, real 4h collection, memory generation, operational authorization, activation, 12h/24h, retrieval, decision, position, trade, PnL, wallet, signing or execution.

## Baseline

Audit baseline:

`786950e9b98677e97f55996507ae1f2145c8eb5e`

This baseline includes the independently proven standard 4h close/memory/terminal repair and its closeout.

## Adopted contract reconciliation

### 1. Standard observation policy through 4h — implemented

`token_local_continuation.py` now treats both:

- `WINDOW_15M -> WINDOW_1H`;
- `WINDOW_1H -> WINDOW_4H`

as standard bounded observation transitions after all hard identity/evidence/safety/continuity/campaign gates pass.

`learning_need` and outcome labels no longer qualify either transition. Token budget remains a hard gate. Unsupported transitions remain blocked. `WINDOW_5M_MICRO_EVENT` cannot authorize a main transition.

Focused policy tests already cover standard no-learning-need continuation, equal authority for quiet/transition outcomes, token-budget failure, 5m non-authority and real-4h lock preservation.

### 2. Policy-derived two-token capacity — implemented

`standard_two_token_lifecycle_budget` derives the full two-token lifecycle ceilings from the committed 15m/1h/4h policies rather than hardcoding the design totals.

Current exact derived targets remain:

- FAST + FAST: 230 requests / 210 Scheduler rows;
- FAST + NORMAL: 182 / 162;
- NORMAL + NORMAL: 134 / 114.

Per-token 4h phase ceilings remain policy-bound and real collection remains disabled.

### 3. Exact campaign-owned 1h -> 4h handoff — implemented

B1 proved exact two-token campaign handoff from reconciled first-hour state:

- exact campaign/run/cycle/token-slot/token/pair identity;
- exact terminal/bound physical first-hour predecessor;
- exact campaign `WINDOW_4H` successor identity;
- exact predecessor/root lifecycle linkage;
- token `WINDOW_1H_CLOSED -> WINDOW_4H_CONTINUING`;
- atomic/idempotent handoff and fail-closed identity conflict.

### 4. Long-window planning + Scheduler ownership — implemented

B2 composes in one transaction:

- both campaign 4h successors;
- policy-derived FAST/NORMAL long-step counts;
- canonical Scheduler jobs;
- exact V2 stage-scoped campaign Scheduler-work ownership;
- complete identity/count read-back.

The planner explicitly rejects any `WINDOW_12H`/`WINDOW_24H` campaign window in the standard 4h plan and creates no later successor.

Mixed FAST/NORMAL currently plans 61 + 31 long work rows with one close per token.

### 5. Collection state / accounting / fairness — implemented

The passed collection checkpoint established:

- exact `PLANNED -> COLLECTING -> CLOSE_PENDING` campaign 4h state truth from Scheduler claims;
- long-window lifecycle reservation observations matching existing request projections;
- canonical Source Governor/Scheduler execution owners preserved;
- token-local 4h failure/cancellation isolation;
- shared 4h safe-stop reconciliation;
- categorical due-work fairness;
- long close priority;
- no scoring/ranking/confidence/weighted policy.

### 6. Physical 4h close and clean-memory path — reused and completed

The physical pipeline remains the existing proven path:

`physical WINDOW_4H -> shared 4h context -> full current-run outcome -> E2Q -> Lane Q -> E2Z`

The later repair added the missing full current-run 4h outcome boundary before promotion while leaving E2Q/Lane-Q/E2Z and the clean-object eligibility gate unchanged.

Outcome inclusion is governed by exact current-run run-step snapshot identity, not broad historical timestamps.

### 7. Campaign successful terminal reconciliation — implemented

Successful physical 4h results now bind to the exact campaign window before Scheduler success is committed.

Categorical outcomes are:

- `CLEAN_PROMOTED`;
- `ALREADY_EXISTS_IDEMPOTENT`;
- `DIRTY`;
- `NO_PROMOTION`.

Failure/cancel outcomes remain:

- `BLOCKED -> FAILED`;
- `CANCELLED -> MANUAL_REVIEW`.

Successful token slots end at `WINDOW_4H_CLOSED`. Exact replay is idempotent and conflicting memory/state/cause fails closed.

### 8. Standard two-window terminal reporting — implemented

The standard campaign terminal validator is authoritative only when exact B2 standard 4h ownership exists. Historical one-token validation remains unchanged otherwise.

For each token independently it validates its own lane/cadence expectation, owned close, Scheduler/campaign-work truth, bound physical memory, campaign terminal outcome and token-slot state.

Campaign closeout additionally requires zero active owned 4h work and zero nonterminal campaign 4h windows.

This prevents the old one-close/one-lane proof validator from misclassifying the standard two-token campaign.

### 9. No automatic 12h successor — implemented/locked

The standard 4h planner explicitly checks that no 12h/24h campaign window exists as part of its plan, and no standard 4h success path creates later-window work.

Cadence policy for real 4h remains disabled. 12h/24h remain disabled and outside this lane.

### 10. Historical one-token proof compatibility — retained

The old one-token physical 4h owner and historical validator remain available when standard B2 ownership is absent.

Its clean create/replay regression was aligned to the now-explicit full-path outcome-before-E2Z boundary without changing the expected behavior. Exact-head repair proof passed that regression.

## Remaining proof obligation

The adopted design requires a focused offline composition proof before implementation/proof closeout.

No new production behavior is required to perform it.

The proof must consolidate on one exact durable HEAD:

- standard 15m->1h and 1h->4h policy/hard-gate tests;
- policy-derived FAST/FAST, FAST/NORMAL and NORMAL/NORMAL ceilings;
- exact two-token B1 handoff;
- B2 two-token planning/Scheduler ownership/idempotency/atomic rollback;
- collection-state, reservations, fairness, close priority, token-local failure and shared-stop tests;
- 4h full-path outcome, clean/dirty/no-promotion/replay, campaign terminal reconciliation and mixed-lane terminal validation;
- directly affected first-hour close/outcome regressions;
- historical one-token 4h close/create/replay regression;
- explicit real 4h/12h/24h capability locks;
- explicit assertion that standard planning creates no 12h/24h campaign windows;
- no provider/source/runtime execution.

A broad unrelated repository suite is not required. This is a major lane closeout proof, so consolidating all directly affected standard-four-hour and first-hour boundary tests is appropriate under the risk-based verification policy.

## Money-usefulness contribution

The implementation now observes otherwise-valid tokens through a standardized first-four-hour evidence horizon without selecting on early price behavior, while preserving evidence quality, exact identity, bounded resources, fair service, source accounting and truthful clean/dirty/no-promotion outcomes.

That reduces behavior-conditioned sampling bias and improves future corpus coverage for delayed pump, collapse, survival, revival, distribution, round trip and liquidity deterioration patterns. It does not prove profitability or authorize any paper action.

## What this audit improves

- confirms the adopted design is implemented across all sub-boundaries rather than merely as isolated helpers;
- avoids an unnecessary new production patch;
- makes the remaining obligation proof consolidation, not runtime activation;
- preserves the no-12h boundary and real-4h activation lock.

## What remains locked

- overall lane PASS until the focused integration proof/closeout passes;
- real `WINDOW_4H` collection;
- operational standard-4h rereadiness;
- activation change/proof;
- fresh exact-HEAD one-use authorization;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, audits, PnL;
- wallets, private keys, signing, live execution, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Two full 4h token lifecycles remain materially more expensive than the historical one-continuer proof; operational rereadiness must re-evaluate actual authoritative-run ceilings before activation.
- The standard path spans several proven owners; the overall proof must prove they remain mutually compatible on one exact HEAD.
- Physical quality work commits before later campaign reconciliation; a later campaign binding fault cannot erase physical evidence and must be reported honestly.
- `OUTCOME_UNKNOWN` remains intentionally non-promotable.
- Partial or ambiguous B2 ownership must fail closed rather than fall back to the historical validator.
- No 12h work may be added merely because 4h now closes correctly.

## Next permitted step

Run one read-only/bounded **Standard Four-Hour Campaign Integration Offline Proof** on the exact durable implementation HEAD.

If that proof passes, write the overall Standard Four-Hour Campaign Integration Implementation/Proof Closeout. Only after that closeout passes may a separate operational standard-four-hour rereadiness audit begin.
