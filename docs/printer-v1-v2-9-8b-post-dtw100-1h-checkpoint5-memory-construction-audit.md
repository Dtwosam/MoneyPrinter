# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 5 Genuine Memory-Construction Audit

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_5_MEMORY_CONSTRUCTION_AUDIT_BLOCKED_PIPELINE_SCOPE_OUTCOME_AND_INTEGRITY_ALIGNMENT_REQUIRED`

The canonical clean-object promotion machinery is already timeframe-aware and reusable for a genuine `WINDOW_1H`, but the current operational first-hour close does not yet compose through the full current E2Q -> Lane Q/U2 -> E2Z -> episode+fingerprint path.

A bounded design/implementation/proof repair is required before Checkpoint 5 can close.

## Baseline and scope

- Baseline: `20fdce5532c3ee7c2578d312dd214e05b93ee8e9` — Checkpoint-4 exact-closeout PASS.
- Branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint5-memory-construction`.
- Starting state: the exact first-hour physical `printer_memory_windows` row exists, is bound to its exact campaign `WINDOW_1H`, its closing evidence reached the fixed deadline, and the campaign window is `CLOSE_PENDING`.
- Scope: E2Q classification, Lane Q integrity, Lane U2 coverage, explicit Lane-K pipeline scope, E2Z clean-object promotion, episode/fingerprint identity, outcome labeling, and idempotency.

No live runtime, source fetching, authoritative-DB operation, authorization, 4h activation, retrieval, paper decision, position, trade, audit, PnL, wallet, signing, or execution occurred.

## What is already healthy and reusable

### E2Q genuinely supports WINDOW_1H

`audit_15m_memory_window()` is historically named but currently accepts `WINDOW_15M` and genuine `WINDOW_1H`. Its 1h path verifies exact target identity, closed state, supporting snapshot identity, token/pair equality, predecessor continuity, fixed first-hour duration/anchors, and genuine-1h targeting before it marks the row as an E2Q clean candidate.

The function name should not be refactored in this checkpoint; current behavior is the relevant contract.

### Lane U2 is already window-kind generic

`persist_coverage_for_windows()` reads the window kind and tracking lane, resolves the shared cadence policy through `get_policy(window_kind, tracking_lane)`, evaluates the exact stored snapshot range, and persists coverage/gap truth. No separate 1h coverage engine is needed.

### E2Z and atomic clean-object promotion are timeframe-aware

`create_clean_memory_from_window()` permits `WINDOW_15M`, `WINDOW_1H`, and `WINDOW_4H` after the required clean-candidate gates.

`promote_clean_object()` creates the episode kind dynamically as:

`{window_kind}_CLEAN_MEMORY`

and verifies exact `window_id`, `token_id`, `pair_id`, `window_kind`, outcome, clean quality, and exactly one canonical `STATIC_CONDITION_SUMMARY` fingerprint. Existing complete objects replay as `ALREADY_EXISTS`; incomplete or conflicting objects fail closed under one savepoint.

The fingerprint payload itself stores exact `window_kind`, outcome, episode/window/token/pair identity, tracking lane, and categorical context. No separate 1h fingerprint implementation is needed.

### The generic outcome classifier already supports WINDOW_1H

`printer_v1.memory.outcomes.classify_episode_outcome()` is generic for main window kinds. It excludes only 5m/support windows and can classify 1h snapshot paths into the existing categorical outcome vocabulary without scores, ranks, probabilities, or weights.

A new 1h outcome classifier would duplicate working policy and is not justified.

## Blocker 1 — the real 1h close row has no outcome label

`lane_e2o_1h_window_close._insert_1h_memory_window()` currently inserts the physical 1h row without `outcome_label`.

The 15m close path later derives and persists an outcome before Lane K promotion. The current 1h close path instead runs E2Q and Lane K immediately without an equivalent outcome derivation step.

Atomic promotion correctly refuses a window with missing or `OUTCOME_UNKNOWN` outcome. Therefore a real operational 1h close cannot reliably produce its clean episode/fingerprint merely because direct fixture tests can pre-populate an outcome manually.

### Required semantics

The first-hour outcome must describe the continuous first-hour lifecycle, not merely the final 45-minute segment. The 1h role is continuation/failure memory showing whether the first 15m move survived or failed.

The current-run ledger already owns the required exact evidence:

- 15m `SNAPSHOT` rows;
- the exact 15m `WINDOW_CLOSE` snapshot;
- 1h `CONTINUATION_SNAPSHOT` rows;
- the exact current `CONTINUATION_CLOSE` snapshot.

The repair should compose those exact current-run token/pair snapshots, de-duplicate by snapshot identity, order by captured time/id, and pass the complete first-hour path to the existing generic outcome classifier.

No historical or other-token snapshot may enter the path.

## Blocker 2 — Lane K explicit scope is still sourced from 15m-only E2X

`run_e2z_pipeline(..., candidate_window_ids=[window_id])` appears scoped, but Step 1 first calls `build_e2x_15m_clean_memory_eligibility_report()` and then intersects the E2X `WINDOW_15M` candidate set with the requested ids.

E2X is explicitly and correctly a strict 15m eligibility module. Therefore an exact `WINDOW_1H` id supplied by the operational close is absent from `all_eligible_ids` before Lane Q, U2, or E2Z can evaluate it.

This is a pipeline-scope integration defect, not an E2X defect. E2X should remain 15m-only.

### Required semantics

Under an explicit exact operational window scope, the requested ids themselves should enter the individual integrity path. Lane Q/U2/E2Z remain the fail-closed eligibility authorities. Global/unscoped 15m corpus mode should continue to use E2X/E2Y unchanged.

## Blocker 3 — Lane Q omits WINDOW_1H from its duration map

`lane_q_15m_window_integrity_guard._MIN_ELAPSED_BY_WINDOW` currently contains:

- `WINDOW_15M: 900`
- `WINDOW_4H: 10800`

but no `WINDOW_1H`.

A genuine first-hour row therefore reaches Lane Q as `unsupported_window_kind` even though:

- E2Q recognizes it;
- cadence policy recognizes it;
- Lane U2 recognizes it;
- E2Z recognizes it.

The current first-hour continuation segment's authoritative elapsed target is 2700 seconds from the clean 15m close to the fixed first-hour deadline. Lane Q should use that existing continuation-window contract, not invent a 3600-second second-stage duration.

## Blocker 4 — direct WINDOW_1H E2Z does not require Lane-Q proof

E2Z currently requires an exact successful Lane-Q report for `WINDOW_4H`, but not for `WINDOW_1H`.

Once Lane Q supports 1h, allowing direct 1h promotion without that exact coverage/integrity proof would create two promotion standards:

- production Lane-K path: Lane Q/U2 checked;
- direct E2Z call: E2Q marker and row fields only.

For one canonical clean-memory contract, `WINDOW_1H` should require the same exact-window Lane-Q PASS evidence before atomic promotion. Lane K should pass its actual Lane-Q report into E2Z. Existing direct fixture tests must be updated to supply the real proof rather than bypass it.

This requirement does not create a new gate; it binds an already-existing integrity gate to the 1h promotion owner.

## Important non-blockers

- Atomic episode+fingerprint creation does not need rewriting.
- Episode kind is already dynamic and will be `WINDOW_1H_CLEAN_MEMORY`.
- Fingerprint identity is already timeframe-aware.
- Lane U2 does not need a separate 1h implementation.
- No schema or migration is required.
- No new source request is required.
- No new Scheduler work is required.
- No new scoring/ranking/confidence/weighted logic is required.

## Required repair direction

1. derive and persist the exact full-first-hour categorical outcome from the current-run ledger before E2Q/Lane K promotion;
2. keep E2X/E2Y unchanged for global 15m mode, but make Lane K's explicit exact-window scope enter Lane Q directly rather than intersecting with E2X's 15m-only population;
3. add `WINDOW_1H: 2700` to Lane Q's main-window elapsed map;
4. pass the actual Lane-Q report from Lane K into each E2Z call;
5. require exact Lane-Q PASS for direct `WINDOW_1H` E2Z, matching the established 4h integrity pattern;
6. prove atomic creation of exactly one `WINDOW_1H_CLEAN_MEMORY` episode plus exactly one canonical fingerprint, then prove idempotent replay creates neither duplicate;
7. prove dirty/blocked/unknown-outcome/coverage-failed 1h rows cannot become clean objects.

## Money-usefulness contribution

This repair is directly money-useful because the first-hour episode must tell Printer what actually happened across the whole first hour after the token entered the memory lifecycle. A label derived only from the last 45 minutes could misclassify a first-15m pump followed by a round-trip, survival, or dump.

The full first-hour path plus strict coverage/integrity gating makes future comparisons more representative and reduces false clean memories.

It still provides no profitability proof and unlocks no financial action.

## What this checkpoint improves after repair

- full-first-hour categorical outcome truth;
- one exact explicit operational route from E2Q through Lane Q/U2 to E2Z;
- exact 1h duration support in Lane Q;
- one consistent Lane-Q requirement for 1h clean promotion;
- atomic timeframe-aware episode+fingerprint creation and replay safety.

## What remains locked

No live first-hour run, one-shot authorization/wrapper, 4h activation, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, wallet/private keys/real funds/live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof required

Focused RED/GREEN proof must establish at minimum:

- current exact 1h scoped pipeline fails before repair for the audited reasons;
- the full first-hour outcome consumes only exact current-run token/pair 15m+continuation snapshots and includes the current close snapshot;
- a path that pumps in the first 15m then returns by 1h can be labeled from the complete path rather than from the 45m suffix alone;
- Lane Q accepts a genuine 2700-second `WINDOW_1H` continuation row and still blocks insufficient duration/identity/coverage;
- Lane K explicit 1h scope reaches Lane Q/U2/E2Z without broadening global E2X/E2Y;
- E2Z refuses direct 1h promotion without exact Lane-Q PASS;
- clean 1h promotion creates one exact `WINDOW_1H_CLEAN_MEMORY` episode and one canonical fingerprint;
- replay is `ALREADY_EXISTS` with the same episode/fingerprint;
- existing 15m, 4h, Checkpoints 1-4, and locked-capability regressions remain green under risk-based verification.

## Functionality Risks / Setbacks / Efficiency Blockers

- Full-first-hour outcome composition must use the exact current-run ledger; a broad token/pair DB query could leak historical snapshots into the outcome.
- The current physical `WINDOW_1H` snapshot range remains the 45-minute continuation segment for cadence/coverage. Outcome composition is intentionally broader: it represents the semantic first-hour lifecycle by joining the clean predecessor path and continuation path. These roles must not be conflated.
- E2X and E2Y are historically 15m-specific and should not be generalized merely to make 1h pass.
- Requiring Lane-Q proof for direct 1h E2Z may expose stale tests that manually pre-populate 1h rows. Repair the fixtures/proof path; do not weaken the gate.
- Fingerprint categorical context may remain partially `UNKNOWN` where no governed fact exists. Do not fabricate 1h context or reinterpret predecessor facts as newly observed 1h facts.

## Next permitted action

Design the bounded Checkpoint-5 pipeline/outcome/integrity repair, then implement with focused TDD proof. Do not begin Checkpoint 6 until Checkpoint 5 closes PASS.
