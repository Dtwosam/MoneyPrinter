# Printer V1 V2-9.8B WINDOW_15M Checkpoint 6 — Collection and Clean-Memory Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_6_COLLECTION_CLEAN_MEMORY_CLOSEOUT_PASS`

Checkpoint 6 is complete through audit, design, implementation, bounded deterministic proof, and closeout.

- Checkpoint 5 baseline: `e5409431cb13cb169af5ae8ab1b32611c8af951b`
- Checkpoint 6 audit commit: `9bf0bf2f5b4b0b922d122f9a7361c942c5e7eaa1`
- Checkpoint 6 design commit: `8f148f4d6789931ca324e9b7594e456793c2c744`
- Fail-first contract commit: `dc00cbc6c9e56691377c279728a9c915c700bbe2`
- Repair commit: `2dd42f6fc64f5864e69be03ac8ca8f848bcae243`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-6-collection-clean-memory-closeout`
- Linear: `DTW-32`

No provider/RPC/WebSocket call, public Printer runtime, authoritative database mutation, memory retrieval, paper decision, BUY/SELL/HOLD, position, trade, paper-trade audit, PnL, live wallet/key/execution, paid API, embedding/vector, longer-window activation, or Checkpoint 7 work occurred.

## Four confirmed blockers repaired

### 1. `CLEAN_EPISODE_OUTCOME_NOT_PERSISTED`

The source `WINDOW_15M` already held the truthful categorical outcome before E2Q/E2Z promotion, but the atomic clean-object owner created the canonical `CLEAN_MEMORY` episode with `episode_outcome_label = NULL`.

Repair:

- new clean promotion requires a non-empty, non-`OUTCOME_UNKNOWN` source-window outcome;
- the exact source-window outcome is written into the new clean episode;
- idempotent validation requires episode outcome == source-window outcome;
- fingerprint outcome is also required to equal that exact outcome.

No outcome is recomputed, scored, ranked, inferred from future evidence, or invented.

### 2. `CLEAN_FINGERPRINT_CONTEXT_COLLAPSED_TO_MINIMAL_EPISODE_CONTEXT`

The non-empty minimal episode provenance context shadowed the richer source-window condition context, causing supported categorical fingerprint dimensions to collapse to `UNKNOWN`.

Repair:

- fingerprint construction now starts from the real source-window context;
- operational shared 15m section labels and context labels are resolved into the existing categorical fingerprint sections;
- episode provenance metadata overlays the condition context instead of replacing it;
- genuinely unavailable fields remain explicit `UNKNOWN`.

No score, weighting, confidence value, embedding, vector, or inferred synthetic condition was added.

### 3. `SUPPORT_5M_TRIGGER_LOOKAHEAD_FROM_15M_OUTCOME`

The old natural-disposition path used the already-completed 15m outcome to decide whether to retrospectively create support from the first five minutes.

Repair:

- final 15m natural disposition no longer invokes retrospective `_capture_same_stream_5m_support()`;
- the already-adopted support-only 5m policy is evaluated from event-time snapshot evidence inside the existing Scheduler-owned snapshot work;
- the frozen support result records `future_main_window_outcome_used = false`;
- final 15m disposition remains continuation/stop authority only and cannot create an earlier trigger after the fact.

No new Scheduler job, new polling loop, new source request, retry system, or cadence was introduced.

### 4. `SUPPORT_5M_DURABLE_OWNERSHIP_LINKAGE_INCOMPLETE`

The old support row preserved token/pair/parent-window/run/snapshot linkage but not the complete adopted trigger and ownership/provenance graph.

Repair:

- the event-time support result freezes campaign, campaign run, cycle, factory run, token slot, token/mint, pair, root 15m lifecycle, containing main-window identity, Scheduler work/job, trigger family, trigger time/evidence cutoff, triggering snapshot identities, and governed source provenance;
- materialization validates this frozen object against the exact token/pair/run/snapshots before writing;
- durable support context retains that frozen ownership/provenance after process memory disappears;
- support remains `WINDOW_5M_MICRO_EVENT`, support-only, and non-authoritative for retrieval or financial actions.

No schema migration or authoritative historical-row backfill was performed.

## Fail-first proof

The pinned RED commit `dc00cbc6c9e56691377c279728a9c915c700bbe2` reproduced all four contracts before repair:

- clean episode outcome was `NULL` instead of the source-window `SHORT_TERM_PUMP`;
- rich fingerprint fields collapsed to `UNKNOWN`;
- `_natural_disposition_schedule()` still called retrospective `_capture_same_stream_5m_support()`;
- `capture_5m_support_evidence()` did not accept/validate a frozen support-capture provenance object.

The RED pytest report contained multiple subtest failures for the fingerprint dimension, but the four named contract tests were all independently observed and required by the runner before implementation could proceed.

## Bounded GREEN proof

The controlling local fail-closed execution produced:

- `CHECKPOINT6_FOUR_REDS_CONFIRMED`
- `CHECKPOINT6_EXACT_REPAIR_EDIT_PASS`
- `229 passed, 5 deselected, 116 subtests passed`
- `CHECKPOINT6_LEGACY_E11_NO_SUPPLY_TESTS_DESELECTED_EXACTLY_FIVE`
- `CHECKPOINT6_FOCUSED_GREEN_PASS`
- `CHECKPOINT6_ANTI_LOOKAHEAD_STATIC_PASS`
- `CHECKPOINT6_EXACT_MANIFEST_PASS`
- `CHECKPOINT6_REPAIR_COMMIT=2dd42f6fc64f5864e69be03ac8ca8f848bcae243`
- `CHECKPOINT6_CLEAN_MEMORY_REPAIR_GREEN_PASS`
- `CHECKPOINT6_CHECKPOINT7_NOT_STARTED`

`py_compile` and `git diff --check` were mandatory earlier gates in the same fail-closed runner.

The focused bundle covered:

- the new Checkpoint 6 RED→GREEN contracts;
- adopted conditional support-only 5m policy tests;
- E2Z clean-memory creation;
- Lane X8 support-only 5m integration;
- the reachable historical E.11 operational lifecycle tests outside the exact legacy no-supply exclusions.

## Exact repair manifest

The repair commit contains exactly seven files relative to the proof-runner head:

- modified `src/printer_v1/memory/clean_object_promotion.py`;
- modified `src/printer_v1/operator_cli/checkpoint6_event_time_5m.py`;
- modified `src/printer_v1/operator_cli/lane_x8_5m_support_integration.py`;
- modified `src/printer_v1/operator_cli/one_command_15m_factory.py`;
- modified `tests/test_post_rc_lane_e2z_clean_memory_creation.py` to satisfy the already-required truthful clean-outcome fixture contract;
- deleted `scripts/Run-Checkpoint6-CleanMemoryRepair.sh`;
- deleted `scripts/Run-Checkpoint6-CleanMemoryRepair-V2.sh`.

No unrelated production file changed in the repair commit.

## Five classified historical E.11 tests

The first GREEN attempt produced `229 passed, 5 failed, 116 subtests passed`. All five failures were traced to the already-known superseded E.11 no-supply fixture path: the tests invoke the historical owner with `graduated_supply=None` and `migration_transport=None`, then fail at `supply.holder_reserve_candidates` before their asserted lifecycle behavior is reached.

The exact five nodes were therefore deselected from the Checkpoint 6 proof only:

1. `NaturalOperationalLifecycleProofTests::test_governed_secondary_enrichment_flows_through_existing_normalizers`
2. `NaturalOperationalLifecycleProofTests::test_natural_two_token_operational_campaign_full_proof`
3. `NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer`
4. `TwoTerminalCloseBarrierTests::test_both_terminal_closes_resolve_with_no_deferred_markers`
5. `TwoTerminalCloseBarrierTests::test_first_close_alone_schedules_no_continuation`

No Checkpoint 6 production change was made to preserve or revive that superseded pre-admission path. This remains historical test debt for a separately approved lane if ever needed.

## Money-usefulness contribution

Checkpoint 6 improves the quality of the data Printer will eventually learn from, without activating learning/retrieval yet:

- a clean episode now says exactly what happened;
- its fingerprint preserves the conditions under which it happened;
- support-only 5m evidence records only what was knowable at the event-time cutoff;
- support provenance remains auditable after process memory disappears.

This makes later clean-memory comparison more truthful and useful while keeping all downstream decision capability locked.

## What this checkpoint improves

- exact outcome continuity from closed 15m window to clean episode and fingerprint;
- categorical context continuity from real 15m evidence into fingerprint conditions;
- anti-look-ahead correctness for support-only 5m evidence;
- durable support ownership/provenance and replayability;
- fail-closed clean-object outcome integrity;
- continued separation between support evidence and main-window/continuation authority.

## What this checkpoint still does not unlock

Checkpoint 6 does not unlock:

- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- live wallet, private keys, signing, execution, or real funds;
- paid API dependency;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors;
- `WINDOW_1H` proof rerun or `WINDOW_4H`/`WINDOW_12H`/`WINDOW_24H` activation;
- Checkpoint 7.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently unlock retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Five historical E.11 no-supply tests remain superseded test debt. They are not evidence that the current memory-admitted Checkpoint 6 path is broken.
2. Historical authoritative rows with null episode outcomes or sparse fingerprints were not rewritten. A later explicit migration/repair policy would be required to alter historical evidence.
3. Event-time support depends on the existing Scheduler-owned snapshot path having sufficient clean governed evidence by the trigger cutoff. If not, the correct result is no capture / blocked support, not a later retrospective trigger.
4. Stronger support provenance increases fail-closed rejection of incomplete/mismatched frozen support objects; this is intentional and should not be weakened for convenience.
5. GitHub has no configured status checks for the repair commit; the controlling evidence is the fail-closed local deterministic proof plus remote commit/diff verification.

## Closeout boundary

Checkpoint 6 is complete.

The next roadmap step, if separately started, is Checkpoint 7. This closeout does not authorize or begin it.
