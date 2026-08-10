# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 4 Close-Boundary Implementation / Focused Proof Closeout

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_4_CLOSE_BOUNDARY_IMPLEMENTATION_FOCUSED_PROOF_PASS`

Checkpoint 4 is complete for the offline current-state composition boundary. The existing first-hour close machinery remains canonical; the repair makes the close boundary truthful by aligning campaign state with the real close job, binding the exact physical `WINDOW_1H` row at close time, and requiring actual closing evidence to reach the fixed first-hour deadline.

This PASS does not authorize a live first-hour run, source fetching, authoritative-DB operation, one-shot authorization, or any later capability.

## Baseline and lane boundary

- Checkpoint-3 closeout baseline: `61473b57da334def1ad52ae97d1f11c74bf93f41`.
- Checkpoint-4 branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint4-close-boundary`.
- Audit commit: `495b14221c1e2a68d04425c1056db37e91c03ee7`.
- Repair-design commit: `2142afdce32137ee5109d169c60ae28a92dfa52a`.
- Starting boundary: the exact owned `WINDOW_1H` is already `COLLECTING`, with the remaining-45m collection path owned by Central Scheduler and Source Governor.
- Scope: real close-job boundary, fixed first-hour deadline, physical 1h row creation/binding, close failure isolation, and shared close-freshness policy.

No discovery/selection work, live provider call, Scheduler runtime proof, authoritative DB mutation, authorization, wrapper execution, 4h activation, retrieval, decision, position, trade, audit, or PnL work occurred.

## Audit result

The audit found that the underlying close components were reusable and correctly scheduled, but four close-truth gaps blocked completion:

1. the exact campaign `WINDOW_1H` did not enter `CLOSE_PENDING` when its real `CONTINUATION_CLOSE` job was claimed;
2. the physical `printer_memory_windows` `WINDOW_1H` row could exist without immediate binding to its exact campaign window;
3. a token-local `CONTINUATION_CLOSE` failure could leave the campaign window nonterminal;
4. the fixed 2700-second deadline was stored as metadata without proving the actual closing snapshot had reached it, and the existing forced-closing-snapshot freshness contract was not enabled for `WINDOW_1H`.

No second close engine, source path, Scheduler, schema, or migration was required.

## Repair implementation

Primary implementation commit:

`bf6d69c04823923297a5a97250cfbbbeb35cb7d6` — `Enforce truthful first-hour close boundary`

Diff review then found one missed token-local exception branch. The branch was corrected before final GREEN:

`287f64a8579f798e4e4055847ecfafaea4757664` — `Cover first-hour close exception terminalization`

The follow-up diff was exactly one production file and four lines.

Production changes are limited to:

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/lane_e2o_1h_window_close.py`
- `src/printer_v1/snapshots/cadence_policy.py`

The implementation:

- advances only the exact owned `WINDOW_1H` from `COLLECTING` to `CLOSE_PENDING` when `CONTINUATION_CLOSE` is claimed;
- binds the exact successful physical `WINDOW_1H` row to the exact campaign window before Scheduler success, reusing `bind_window_memory_row_id()`;
- requires a successful continuation close to return a non-null `memory_window_id`;
- blocks only the affected token's exact campaign window when a continuation close fails, including unexpected-exception paths;
- computes observed closing-snapshot lateness relative to the immutable `15m close + 2700s` deadline;
- creates no `WINDOW_1H` row when the closing snapshot precedes that deadline;
- preserves the fixed first-hour target instead of drifting `window_end_at` to the observed close;
- records the observed closing timestamp and lateness in close context/result;
- enables the existing shared `require_full_anchored_duration` and `require_forced_closing_snapshot` controls for both first-hour FAST and NORMAL cadence policies;
- leaves all 1h snapshot counts, intervals, gap thresholds, close-late threshold, Scheduler jobs, and Source Governor budgets unchanged.

No new collector, retry loop, table, migration, scoring/ranking/confidence/weighting system, embedding, or vector system was introduced.

## Valid RED proof

RED test commit:

`528ac065ee4105393832c50edbe1a84d53488687` — `Test truthful first-hour close boundary`

Disposable PR: #103, closed unmerged.

Workflow evidence:

- run: `31348728331`
- job: `93335456104`
- compile: PASS
- tests: 105 total; 101 passed; exactly 4 intended Checkpoint-4 failures

The failures were the designed gaps: missing close-pending owner, early close incorrectly creating a 1h row, missing exact close-row bind path, and disabled 1h forced-close controls. The other 101 directly affected tests stayed green, so no hidden baseline regression was used as RED evidence.

## GREEN proof and test-assertion correction

First GREEN ran on exact production head `287f64a8579f798e4e4055847ecfafaea4757664`.

Disposable PR: #106, closed unmerged.

Result:

- compile: PASS
- 104/105 tests passed
- the only failure was a test assertion requiring `closing_snapshot_precedes_fixed_deadline` as an exact list element while the production result truthfully returned `closing_snapshot_precedes_fixed_deadline: offset=-1.000s`.

The production behavior was correct: the early close was blocked and no 1h row was created. Therefore production was not weakened. Only the assertion was corrected to check the documented reason prefix:

`094b90a1d41f40f5aff939ab6bf8f576b504c722` — `Fix checkpoint 4 early-close reason assertion`

Final GREEN disposable PR: #107, closed unmerged.

Workflow evidence:

- run: `31349296076`
- job: `93336995082`
- compile: PASS
- tests: `105/105 PASS`
- GitHub log: `Ran 105 tests in 451.347s` / `OK`

The focused proof includes:

- Checkpoint-4 close-boundary tests;
- Checkpoint-3 remaining-45m collection tests;
- Checkpoint-2 continuation-initialization tests;
- Checkpoint-1 clean-15m-to-1h handoff tests;
- standard first-hour harness/reporting alignment;
- operational first-hour harness;
- directly affected campaign Scheduler-ownership schema/contract tests;
- shared snapshot cadence/continuity tests.

The Checkpoint-4 tests prove:

1. close claim advances only the exact token's first-hour campaign window to `CLOSE_PENDING`;
2. a closing snapshot one second before the immutable first-hour deadline is blocked and creates zero `WINDOW_1H` rows;
3. an exact-deadline close is accepted, records zero lateness, and binds the exact physical row to the exact campaign window while keeping close/audit state separation;
4. the shared 1h forced-close policy treats exact-deadline close as PASS, +61 seconds as DIRTY, and +240 seconds as BLOCKED under the existing NORMAL cadence thresholds.

## Money-usefulness contribution

Printer's first-hour corpus is useful only if a claimed full-first-hour memory actually contains evidence through that boundary. This repair prevents early evidence from masquerading as a complete first-hour observation and makes the campaign graph identify the exact physical close row at the moment the row exists.

That improves historical-memory truth and future comparison quality. It does not prove profitability or authorize any paper decision or trade behavior.

## What this checkpoint improves

- Real-time `COLLECTING -> CLOSE_PENDING` campaign truth.
- Exact campaign-window-to-physical-memory-window binding at successful close.
- Token-local first-hour close failure remains token-local.
- Fixed first-hour deadline is now backed by actual closing-snapshot evidence.
- First-hour cadence reuses the established forced-close freshness machinery instead of relying on metadata alone.
- Existing 15m/shared owners are reused rather than duplicated.

## What this checkpoint still does not unlock

- no live first-hour execution;
- no first-hour one-shot authorization or wrapper;
- no provider/source fetching;
- no authoritative DB mutation or operational memory generation;
- no 4h activation;
- no 12h/24h work;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions, trade events, paper-trade audits, or PnL;
- no live wallet, private keys, real funds, signing, or execution;
- no paid APIs, scoring, ranking, confidence, weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and has no independent continuation, memory, retrieval, decision, or financial authority.

## Proof still required before operational use

Checkpoint 5 must audit the complete genuine-first-hour memory-construction path after the close row exists: E2Q, Lane Q/integrity, E2Z, episode creation, canonical fingerprint creation, promotion/idempotency, and exact campaign binding/state progression. Checkpoint 4 deliberately does not declare that downstream path ready simply because the close boundary is now truthful.

After all first-hour checkpoints pass, a fresh full-chain rereadiness review is still required before any one-use authorization is prepared.

## Functionality Risks / Setbacks / Efficiency Blockers

- The current close runtime proceeds directly into downstream E2Q/E2Z processing; Checkpoint 5 must verify that this composition is still correct under current contracts.
- Historical 1h fixtures that close before the fixed deadline may now fail. Such failures must be classified honestly as stale fixtures or genuine contract defects; thresholds must not be widened merely to preserve old tests.
- First-hour forced-close freshness is now stricter, so real late closes may become DIRTY/BLOCKED. That is intentional evidence-quality protection, not a reason to weaken the cadence policy.
- Campaign memory-row binding occurs before Scheduler success and after successful row creation. Reordering this later could create phantom bindings or successful unowned close rows.
- The focused proof remains deterministic/offline and does not prove wall-clock provider behavior.

## Next checkpoint

`V2-9.8B Post-DTW100 1h Checkpoint 5 — Genuine First-Hour Memory Construction`

Checkpoint 5 must begin with audit-only inspection of current E2Q, Lane Q/integrity, E2Z, episode/fingerprint, promotion, and idempotency behavior. Any blocker must follow design -> implementation -> focused proof -> closeout before moving to Checkpoint 6. No live run, authorization, source fetch, or financial capability is authorized by this closeout.
