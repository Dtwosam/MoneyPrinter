# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 5 Memory-Construction Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_5_MEMORY_CONSTRUCTION_REPAIR_DESIGN_PASS`

Implement one bounded alignment repair around the existing generic outcome classifier, Lane Q/U2, Lane K explicit operational scope, and atomic E2Z clean-object owner. Do not create a new memory engine, outcome vocabulary, coverage engine, or fingerprint implementation.

## Baseline

Design baseline: `c0f4fa076c4cc9dd34ce0e73e44a16f6d33bf636`.

Audit verdict:

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_5_MEMORY_CONSTRUCTION_AUDIT_BLOCKED_PIPELINE_SCOPE_OUTCOME_AND_INTEGRITY_ALIGNMENT_REQUIRED`

## Canonical owners

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
  - exact current-run first-hour snapshot composition;
  - operational close ordering before E2Q/Lane K.
- `src/printer_v1/memory/outcomes.py`
  - reuse unchanged: generic categorical main-window outcome classifier.
- `src/printer_v1/operator_cli/lane_q_15m_window_integrity_guard.py`
  - existing window integrity owner; add first-hour continuation duration support only.
- `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py`
  - explicit operational scope wiring; retain global E2X/E2Y behavior unchanged.
- `src/printer_v1/operator_cli/e2z_clean_memory_creation.py`
  - require exact Lane-Q proof for `WINDOW_1H`; reuse atomic promotion unchanged.
- `src/printer_v1/memory/clean_object_promotion.py`
  - reuse unchanged for one episode + one canonical fingerprint transaction.

No schema, migration, source adapter, Scheduler, retry path, or new memory table.

## Repair 1 — compose the exact full-first-hour outcome

Add a small factory helper that takes:

- current `run_id`;
- exact `token_id`;
- exact `pair_id`;
- current `CONTINUATION_CLOSE` snapshot id.

It must read only current-run main-lifecycle snapshot identities from successful or current-running steps of these kinds:

- `SNAPSHOT`;
- `WINDOW_CLOSE`;
- `CONTINUATION_SNAPSHOT`;
- current `CONTINUATION_CLOSE` supplied explicitly.

Rules:

1. require exact token/pair identity on every included snapshot;
2. never query by token/pair alone without the run ledger;
3. de-duplicate snapshot ids;
4. order by `captured_at`, then id;
5. require at least the clean predecessor/continuation boundary evidence needed to form a path;
6. include the current close snapshot even though the current close run-step has not yet terminalized;
7. call existing `classify_episode_outcome("WINDOW_1H", snapshots)`;
8. persist the resulting categorical label on the exact physical `WINDOW_1H` row before E2Q/Lane K;
9. store audit provenance in `supporting_context_json`: exact snapshot ids/count and full-path start/end timestamps;
10. if the result is `OUTCOME_UNKNOWN`, preserve it honestly; E2Z must refuse clean promotion.

Do not copy the 15m `_attach_context_and_gate_window()` implementation. It is 15m-specific and owns 15m context semantics. Only reuse the generic outcome classifier and exact-run ledger principles.

### Semantic rule

The physical `WINDOW_1H` row's snapshot range remains the continuation segment for cadence/coverage. The semantic first-hour `outcome_label` is based on the continuous first-hour lifecycle: clean 15m predecessor evidence plus remaining-45m continuation evidence.

This distinction is intentional and must be proven.

## Repair 2 — explicit Lane-K scope bypasses only E2X/E2Y population discovery

Current global mode remains unchanged:

`E2X 15m candidate review -> Lane Q -> U2 -> E2Y reporting -> E2Z`

For `candidate_window_ids` explicit operational scope:

1. normalize/de-duplicate exact positive ids as today;
2. set `all_eligible_ids = explicit_scope` directly;
3. set E2X status/reporting to a categorical `NOT_APPLICABLE_EXPLICIT_WINDOW_SCOPE` marker;
4. do not call E2X as eligibility authority for the scoped ids;
5. run every scoped id through Lane Q and Lane U2;
6. keep E2Y non-authoritative/not-applicable exactly as current explicit mode intends;
7. only Lane-Q-valid and U2-nonblocked ids reach E2Z;
8. E2Z retains the final per-window clean-candidate gate.

This does not weaken explicit 15m operation: Lane Q/U2/E2Z remain mandatory and exact. Add regression proof that explicit 15m clean promotion still works and dirty/unaudited explicit rows still block.

## Repair 3 — add WINDOW_1H to Lane Q duration law

Add exactly:

`WINDOW_1H: 2700`

beside the existing 15m and 4h duration floors.

Rationale: the physical first-hour continuation window begins at the exact clean 15m close and ends at the fixed first-hour deadline, so its own elapsed contract is 2700 seconds. The semantic episode outcome joins the predecessor path separately; Lane Q must not require a second 3600 seconds.

Do not change 15m or 4h floors, identity gates, closed-state gates, snapshot-link gates, E2Q-audited gates, or quality gates.

## Repair 4 — one Lane-Q requirement for 1h E2Z

Generalize the existing E2Z long-window Lane-Q validation helper so:

- `WINDOW_1H` and `WINDOW_4H` require a supplied Lane-Q report;
- the exact requested window id must appear in `valid_window_ids`;
- it must not appear in `blocked_window_ids`;
- Lane-Q status must be PASS;
- 15m behavior remains unchanged.

Lane K must pass its actual `lane_q_guard` object to `create_clean_memory_from_window()` for each eligible exact window.

Direct 1h E2Z without Lane-Q proof must return `E2Z_CREATION_BLOCKED`, create zero episode/fingerprint rows, and preserve all locks.

Do not duplicate Lane Q checks inside E2Z; validate only the exact report identity/status.

## Repair 5 — atomic clean object remains unchanged

No production change is planned in `clean_object_promotion.py` or `fingerprints.py` unless focused RED proves a current defect.

Expected successful 1h result:

- physical source window: exact `WINDOW_1H` id;
- episode kind: `WINDOW_1H_CLEAN_MEMORY`;
- episode `window_kind`: `WINDOW_1H`;
- memory status/quality: `CLEAN_MEMORY`;
- `do_not_train=0`;
- exact non-unknown outcome from source window;
- exactly one `STATIC_CONDITION_SUMMARY` fingerprint;
- fingerprint exact episode/window/token/pair/window-kind/outcome identity;
- repeat promotion: same episode/fingerprint, `ALREADY_EXISTS`.

An incomplete pre-existing clean object or fingerprint mismatch remains an atomic integrity blocker.

## Operational close ordering after repair

Within `_execute_continuation_close()` after successful physical row creation:

1. physical `WINDOW_1H` row exists and is exact-linked;
2. derive/persist full-first-hour outcome from current-run ledger + current close snapshot;
3. run E2Q;
4. commit E2Q/outcome state required by path-based Lane-K connection;
5. call Lane K with exact `candidate_window_ids=[window_id]`;
6. Lane K: exact scope -> Lane Q -> U2 -> E2Z;
7. E2Z atomically creates/verifies episode + fingerprint;
8. return the pipeline result to the existing close finalizer.

Checkpoint 5 does not terminalize campaign window/token states; Checkpoint 6 owns terminal reconciliation.

## TDD / focused proof

Create one checkpoint-specific offline composition test module. Valid RED must prove current production fails for the audited reasons, not fixture construction.

Minimum proof:

1. exact full-first-hour snapshot composer rejects cross-run/cross-token/cross-pair contamination and returns chronologically ordered de-duplicated current-run snapshots;
2. outcome classification uses both the 15m predecessor path and 45m continuation path;
3. one trajectory where the first 15m materially pumps but first-hour end returns produces a path-aware outcome from the complete first hour, demonstrating the 45m suffix alone is not the authority;
4. genuine 2700-second first-hour continuation passes Lane Q; insufficient duration blocks;
5. explicit `WINDOW_1H` Lane-K scope reaches Lane Q/U2/E2Z even though E2X remains 15m-only;
6. direct 1h E2Z without Lane-Q report blocks with zero clean object mutation;
7. clean exact 1h pipeline creates exactly one `WINDOW_1H_CLEAN_MEMORY` episode and one canonical fingerprint;
8. replay returns the same episode/fingerprint with no duplicate;
9. unknown outcome, dirty/do-not-train, Lane-Q-blocked, or coverage-blocked 1h cannot promote;
10. global/unscoped E2X/E2Y remains 15m-only and unchanged;
11. Checkpoints 1-4, current 15m explicit promotion, existing 4h Lane-Q/E2Z, atomic clean-object, and locked-capability regressions remain green.

Use risk-based verification; no full repository suite is required.

## Money-usefulness contribution

The first-hour memory will represent what happened from the beginning of the main lifecycle through the true first-hour close, rather than learning only from the final 45-minute suffix. That is necessary to distinguish survival, failed pumps, round-trips, dumps, and revivals relative to the original 15m move.

## What remains locked

No live first-hour execution, authorization/wrapper, 4h activation, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, live wallet/private keys/real funds/execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- Current-run first-hour composition must never widen into a historical token/pair query.
- E2X/E2Y are intentionally left 15m-specific; explicit scope must not accidentally become an unguarded shortcut.
- A real first-hour path can still produce `OUTCOME_UNKNOWN`; clean promotion must fail closed rather than manufacture a label.
- Categorical context may remain UNKNOWN where no governed 1h fact exists. Outcome provenance must not relabel stale predecessor context as fresh 1h evidence.
- Lane K currently mutates coverage and clean objects through a path-based DB connection. Existing transaction boundaries/idempotency must remain unchanged.

## Stop condition

After implementation, focused proof, durable closeout, and exact-closeout-HEAD verification pass, close Checkpoint 5. Only then begin Checkpoint 6 — first-hour lifecycle terminal reconciliation.
