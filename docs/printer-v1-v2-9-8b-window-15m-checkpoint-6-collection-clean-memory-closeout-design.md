# Printer V1 V2-9.8B WINDOW_15M Checkpoint 6 — Collection and Clean-Memory Closeout Repair Design

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_6_REPAIR_DESIGN_COMPLETE`

Baseline audit commit: `9bf0bf2f5b4b0b922d122f9a7361c942c5e7eaa1`

This design covers only the four blockers confirmed by the Checkpoint 6 audit. It authorizes deterministic RED fixtures and, after those REDs are proven, the smallest owner-level repair. It does not authorize a provider/public runtime, authoritative DB rewrite, 1h/4h proof, retrieval, decisions, financial capability, or Checkpoint 7.

## 1. Canonical owners

No new policy engine is introduced.

- Clean episode/fingerprint owner: `src/printer_v1/memory/clean_object_promotion.py`.
- Existing pure event-time 5m policy: `src/printer_v1/scheduler/support_only_5m_capture.py`.
- Existing event-time micro-event parser/classifier: `src/printer_v1/micro_event/parser.py` and `src/printer_v1/micro_event/classifier.py`.
- 5m persistence owner: `src/printer_v1/operator_cli/lane_x8_5m_support_integration.py`.
- Scheduler-owned WINDOW_15M composition seam: `src/printer_v1/operator_cli/one_command_15m_factory.py`.

The pure `support_only_5m_capture` contract already contains the adopted anti-look-ahead, exact identity, governed provenance, event-time cutoff, budget, and permanent non-authority rules. Checkpoint 6 integrates it; it does not replace or weaken it.

## 2. Repair A — exact outcome continuity into clean episode

For a **new** clean object:

1. `promote_clean_object()` reads the already-classified source window.
2. The source window must carry a non-empty categorical `outcome_label` other than `OUTCOME_UNKNOWN` before a new CLEAN_MEMORY episode can be created. Missing/unknown outcome fails closed as `WINDOW_OUTCOME_NOT_CLEAN_PROMOTION_ELIGIBLE`; no outcome is invented or recomputed.
3. The episode INSERT writes `episode_outcome_label` exactly equal to `printer_memory_windows.outcome_label`.
4. `_validate_complete_pair()` requires the episode outcome to equal the exact source-window outcome and the fingerprint payload outcome to equal the same value.

Historical incomplete clean objects are not rewritten. If an idempotent replay encounters a historical clean episode/fingerprint whose outcome continuity is incomplete or mismatched, it fails closed as a clean-object integrity error. A later explicitly approved historical-repair/migration lane would be required to alter old evidence.

## 3. Repair B — full categorical condition continuity into fingerprint

The episode's small provenance context remains small; it is not converted into a duplicate full-memory blob.

Fingerprint construction instead uses a **merged fingerprint context**:

1. start from the complete source-window `supporting_context_json`;
2. overlay the small episode provenance fields only when those fields are non-null;
3. pass that merged context to the canonical `build_memory_fingerprint_payload()`;
4. resolve token age, pair age, discovery label, market/chain/safety/liquidity/flow/chart/micro-event fields from the merged context;
5. keep `UNKNOWN` for genuinely unavailable categorical fields.

No score, rank, confidence, weighting, embedding, vector, inference, or synthetic context is introduced.

## 4. Repair C — event-time 5m support evaluation, independent of final 15m outcome

The current retrospective path is retired for operational-natural support creation.

### 4.1 Evaluation point

After a Scheduler-owned `SNAPSHOT` step succeeds, while the main 15m lifecycle is still active:

- read only this factory run/token/pair's successful snapshot stream;
- consider snapshots from the opening observation through the latest observation only when the latest observation is within the first 300 seconds;
- require at least two exact snapshots;
- build the existing micro-event payload from those snapshots;
- use existing categorical early-window classifiers only. No held-to-15m field and no final `printer_memory_windows.outcome_label` may participate.

### 4.2 Conservative trigger mapping

The event-time adapter may map only already-existing categorical `MicroEventMoveLabel` values:

- `MOVE_FAST_UP`, `MOVE_SPIKE_AND_HOLD` -> `FAST_COORDINATED_PUMP`;
- `MOVE_FAST_DOWN` -> `FAST_DUMP_OR_COLLAPSE`;
- `MOVE_WICK_ONLY`, `MOVE_SPIKE_AND_FADE` -> `WICK_OR_LATE_BUY_TRAP`;
- `MOVE_ROUND_TRIP` -> `FAST_BREAKDOWN_OR_RECLAIM`;
- `MOVE_NO_CLEAR_EVENT` / `MOVE_UNKNOWN` -> valid no-capture.

`EXIT_REALISM_CHANGE` and `LIQUIDITY_SHOCK` are not fabricated from fields that do not already prove those event-time categories. They remain unavailable to this adapter until an existing adopted categorical owner supplies them.

### 4.3 Exact support-policy request

The adapter builds the existing `SupportCaptureRequest` using:

- campaign id;
- campaign run id;
- cycle id;
- token slot id;
- token/mint/pair identities;
- root 15m lifecycle identity from the campaign token slot;
- deterministic prospective containing-main-window identity for this root lifecycle;
- exact triggering snapshot Scheduler work identity;
- trigger time == evidence cutoff == latest triggering snapshot time;
- exact triggering snapshots and governed source provenance;
- current token/lifecycle state and available bounded budgets;
- `future_main_window_outcome_used=False`.

The existing `evaluate_support_only_5m_capture()` remains final authority.

### 4.4 Durable freeze before 15m close

A `CAPTURE_SUPPORT` result is frozen in the **already-owned triggering snapshot run-step `result_json`** before that step terminalizes. This introduces no source call, no new Scheduler job, no polling loop, and no second scheduler owner.

The frozen record contains the exact policy result and identity/provenance needed for later materialization. Later snapshots do not overwrite the first valid frozen event-time capture for that token/root lifecycle.

A `VALID_NO_CAPTURE` or blocked evaluation does not create a support object and does not alter the main window.

## 5. Repair D — durable 5m support materialization and provenance

Once the real parent `printer_memory_windows` WINDOW_15M row exists, the close path may materialize **only** a previously frozen event-time `CAPTURE_SUPPORT`. It must never derive a trigger from the completed 15m outcome.

`capture_5m_support_evidence()` is extended with a validated frozen-support input and writes the following into the 5m row's `supporting_context_json`:

- `campaign_id`;
- `campaign_run_id`;
- `cycle_id`;
- `factory_run_id`;
- `token_slot_id`;
- exact token id and mint;
- exact pair id and pair address;
- `root_15m_lifecycle_id`;
- parent/containing main window id and kind;
- `trigger_family`;
- `trigger_time` and `evidence_cutoff`;
- exact triggering snapshot ids;
- exact Scheduler work identity and `scheduler_job_id` of the triggering snapshot job;
- governed source provenance for each triggering snapshot (`source_name`, request id, response id, Scheduler work identity, source/data quality);
- permanent support-only/non-authority flags.

The persistence owner revalidates token/pair/parent/snapshot identities before write. Any mismatch fails closed. No synthetic 5m Scheduler job is created; the already-terminal triggering snapshot Scheduler job is the durable scheduler provenance for the support evaluation.

The old synthetic `SUPPORT_5M` run-step is not required for new operational support. Historical rows remain untouched.

## 6. Continuation authority remains separate

The final 15m `NaturalEvidenceDispositionOwner` may continue to decide whether the token proceeds to WINDOW_1H from the completed main-window evidence.

It no longer decides whether 5m support should exist.

Therefore:

- 5m support cannot trigger continuation;
- absence/blocking of 5m support cannot stop an otherwise valid main 15m close or change its outcome;
- final 15m outcome cannot retroactively create or relabel 5m support;
- continuation and support remain two independent categorical outputs of different evidence cutoffs.

## 7. No schema migration

All required additional support provenance fits the existing `printer_memory_windows.supporting_context_json` and existing run-step `result_json` surfaces.

No migration is justified for these four blockers.

## 8. Deterministic RED requirements

Before production edits, one focused Checkpoint 6 test module must fail on the audit/design baseline for exactly these contracts:

1. clean episode outcome equals source-window outcome;
2. fingerprint preserves supplied categorical source-window condition context;
3. final 15m outcome alone cannot create a 5m support trigger, while an event-time categorical trigger can be frozen without using later evidence;
4. materialized 5m support survives DB reopen with exact campaign/run/cycle/root/trigger/snapshot/source/Scheduler provenance and rejects mismatch.

The proof runner must verify those tests fail on the pinned RED/pre-repair commit before accepting a GREEN result from the repair commit.

## 9. Minimum GREEN verification

Required after implementation:

- new Checkpoint 6 tests;
- `tests/test_v2_9_7d_4b_conditional_support_only_5m_capture.py`;
- `tests/test_post_rc_lane_e2z_clean_memory_creation.py`;
- directly affected clean-object/fingerprint tests;
- directly affected Lane X8 5m persistence tests;
- directly affected one-command 15m close/natural-disposition tests;
- directly affected E2Q/Lane Q/U2 tests only if production edits touch their contracts;
- Python compile/import checks for changed modules;
- `git diff --check`;
- exact changed-file manifest;
- static lock scan confirming no new retrieval/decision/trade/live/paid/scoring/vector capability.

No broad repository suite is required unless the repair expands beyond the named owners.

## 10. Money-usefulness contribution

This repair makes a clean 15m memory useful as a future learning object rather than merely valid storage: the clean episode says what happened, the fingerprint retains the categorical conditions in which it happened, and early support evidence represents only what Printer could have known at that early time.

## 11. What improves

- exact outcome continuity across window -> episode -> fingerprint;
- richer but still categorical clean fingerprints;
- no hindsight-created early support evidence;
- event-time 5m trigger proof through the already-adopted policy;
- complete durable support ownership/provenance without another Scheduler owner;
- deterministic replay/audit of support evidence after process memory is gone.

## 12. What remains locked

This design does not unlock source expansion, public runtime by itself, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, wallets, private keys, signing, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors, 1h/4h/12h/24h activation, or Checkpoint 7.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

1. Historical null-outcome/sparse-fingerprint clean objects remain historical evidence and may fail stricter idempotent validation; they are not silently repaired.
2. Event-time 5m evaluation is intentionally conservative. Some meaningful events may receive no support object rather than be inferred from future evidence.
3. The event-time adapter must use only already-governed persisted snapshots/source identities; missing request/response provenance blocks support, not the main 15m lifecycle.
4. Support materialization occurs after the parent main-window row exists, but its trigger decision is immutable frozen event-time evidence. A later close must not reinterpret it.
5. No extra Scheduler job means support provenance points to the exact triggering snapshot job. Tests must prove that linkage remains reconstructible after DB reopen.
6. Existing compressed/fixture proof modes must not be silently redefined as production event-time truth; compatibility changes, if required, stay fixture-only and cannot weaken the operational contract.
7. The 900-second duration, E2Q, Lane Q, U2, source budget, Scheduler ownership, terminal cleanup, and financial/retrieval locks remain unchanged.

## 14. Stop condition

Stop and do not close Checkpoint 6 if any RED does not reproduce on the pre-repair commit, any new GREEN fails, an unrelated failure cannot be classified, support starts influencing continuation, historical rows are rewritten, a migration becomes necessary without a new design review, or any locked capability changes.

Checkpoint 7 must not begin from this design.