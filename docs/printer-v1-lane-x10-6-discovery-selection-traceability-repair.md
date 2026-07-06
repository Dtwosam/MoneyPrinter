# Printer V1 Lane X10.6 â€” Discovery Selection Traceability + Smart Memory-Value Selection Repair

**Type:** implementation + audit â€” new module, new tests, no runtime, no source fetching, no DB mutation.

---

## 1. Commit / Tag Anchor

| Field | Value |
|-------|-------|
| Prerequisite commit | `d89ecb3` â€” Add Lane X10.5 discovery selection audit |
| Prerequisite tag | `printer-v1-lane-x10-5-discovery-selection-audit` |
| Lane X10.5 verdict | PARTIAL_READY_WITH_GAPS / NOT_READY_FOR_AUTOMATED_SELECTION |
| Date built | 2026-07-06 |

---

## 2. Why This Lane Exists

Lane X10.5 found that the existing X5 proof run lacked an explainable, traceable selection record:

| Gap found in X10.5 | Required repair |
|---|---|
| WIF had WATCH_ONLY in DB but was run as TRACK_FAST (no override record) | Explicit WATCH_ONLYâ†’TRACK_FAST override with `manual_override_reason` required |
| ANSEM had no discovery candidate row | `no_discovery_origin=True` + manual override required |
| ANSEM had pair drift (2 pairs for 1 token) | `pair_drift_acknowledged=True` + manual override required |
| No DB bridge from X6 selection to X5 token list | Selection batch artifact produced by X10.6 |
| No explanation of why these 5 tokens were chosen over others | Event-kind + context-tag labels added to each candidate |
| No diversity signal (all large/popular) | Batch balance assessment added (informational, not a gate) |

---

## 3. What Was Built

### New module: `src/printer_v1/operator_cli/lane_x10_6_selection_traceability.py`

Adds the following on top of Lane X6 (does not replace or duplicate X6):

#### 3.1 Qualitative Event-Kind Labels (10 constants, NOT scores)

| Constant | Meaning |
|---|---|
| `MICRO_CAP_FAST_EVENT` | Micro-cap token with meaningful fast activity worth capturing |
| `MIGRATION_EVENT` | Token that has migrated pair (e.g., Pump.fun â†’ Raydium) |
| `NEW_PAIR_EVENT` | New pair for an existing or newly-seen token |
| `LIQUIDITY_DECAY_EVENT` | Declining or thin liquidity with absent volume |
| `HIGH_ACTIVITY_NO_FOLLOW_THROUGH` | High txns/volume but price did not follow through |
| `REVIVAL_EVENT` | Cooled/dead token with new observable activity |
| `HOT_PAIR_REFERENCE` | Large, well-known pair used as reference baseline memory |
| `SOCIAL_ATTENTION_ADVISORY` | Operator-flagged social attention (advisory only, not source-of-truth) |
| `SAFETY_RISK_MEMORY` | Safety-risk token retained for audit memory, not for decisions |
| `AMBIGUOUS_MEMORY_CANDIDATE` | No clear event type; useful as baseline or holdover |

These are NOT buy signals, scores, rankings, alpha labels, or confidence values.
`TRACK_FAST` means "capture high-detail memory quickly," not "buy."

#### 3.2 Context Tags (8 constants, NOT blocking alone)

| Constant | Applied when |
|---|---|
| `MICRO_CAP` | FDV below threshold (default $500k) |
| `THIN_LIQUIDITY` | Liquidity below threshold (default $5k) |
| `EXIT_REALISM_UNKNOWN` | Liquidity is zero or absent |
| `HIGH_VOLATILITY` | Large price move in recent 5m or 1h |
| `POSSIBLE_WICK_PUMP` | Large 5m spike that did not persist into 1h |
| `POSSIBLE_LATE_BUY_TRAP` | Very large 24h move already baked in |
| `POSSIBLE_SNIPER_OR_BUNDLE_RISK` | Operator-supplied advisory flag |
| `HOLDER_CONCENTRATION_RISK` | Operator-supplied advisory flag |

Tags do not block selection by themselves. They are for traceability and operator audit context.

#### 3.3 Market-Cap Neutrality Logic

- A 30k FDV token CAN qualify for `MICRO_CAP_FAST_EVENT` if it shows a fast, observable, source-governed activity worth capturing.
- A large-cap token without an active event is NOT automatically TRACK_FAST â€” it is classified as `HOT_PAIR_REFERENCE`, `AMBIGUOUS_MEMORY_CANDIDATE`, or another event kind.
- Low market cap is not automatically good. High market cap is not automatically safe.
- Market cap appears as a context tag (`MICRO_CAP`) for traceability â€” it is not a selection gate by itself.

#### 3.4 Manual Override Gating

A candidate is rejected unless it carries explicit override fields when any of the following are true:

| Condition | Required fields |
|---|---|
| `watch_only_to_track_fast_override=True` OR `db_lane_before_selection=WATCH_ONLY` + `selected_lane_for_batch=TRACK_FAST` | `manual_override=True` + `manual_override_reason` |
| `no_discovery_origin=True` | `manual_override=True` + `manual_override_reason` |
| `same_token_new_pair=True` OR `is_new_pair_for_existing_token=True` OR `pair_drift_acknowledged=True` | `manual_override=True` + `manual_override_reason` + `pair_drift_acknowledged=True` |

Override detection is bi-directional: it fires on the explicit flag OR on the lane-field mismatch (WATCH_ONLY + TRACK_FAST), whichever is present.

#### 3.5 Selection Batch Artifact (`build_selection_batch`)

Main public function. Returns a complete traceability record with:

**Per-candidate fields (selected):**
- `event_kind` â€” qualitative event label
- `context_tags` â€” list of risk/context labels
- `inclusion_reason` â€” human-readable string (event_kind:action:priority_reason:context_tags:manual_override)
- `rejection_reason` â€” None
- `included` â€” True
- `manual_override`, `manual_override_reason`
- `watch_only_to_track_fast_override`, `no_discovery_origin`, `pair_drift_acknowledged`
- `db_lane_before_selection`, `selected_lane_for_batch`
- `source_trace` â€” dict with `discovery_candidate_id`, `source_request_id`, `source_response_id`, `source_channel`, `priority_reason`
- `operator_approved`

**Per-candidate fields (rejected):**
- All of the above, plus:
- `included` â€” False
- `rejection_reason` â€” explains why (missing override, pair drift unacknowledged, missing mint)

**Batch-level fields:**
- `selected_count`, `rejected_count`, `candidate_count_input`
- `override_required_count`, `override_missing_count`
- `pair_drift_pending_acknowledgment`
- `manual_overrides` â€” list of all override records
- `pair_drift_items` â€” list of all pair drift records (acknowledged or not)
- `event_kind_summary` â€” count by event kind (only selected candidates)
- `batch_balance` â€” coverage across 4 event-kind groups (informational only)
- `proposed_x5_token_list_path` â€” path to operator-supplied X5 JSON (if any)
- `run_started_at`, `run_finished_at`

**Invariant fields (always present):**
- `automated_selection_locked` â€” always True
- `discovery_is_intake_not_alpha` â€” always True
- `selection_is_memory_value_based_not_buy_probability` â€” always True
- `hard_locks` â€” all hard-lock booleans
- `buy_enabled`, `sell_enabled`, `hold_enabled` â€” always False
- `paper_decisions_created`, `positions_created`, `trade_events_created`, `pnl_created` â€” always 0

#### 3.6 Batch Balance Assessment (`assess_batch_balance`)

Informational assessment of whether the selected batch covers four broad event-kind groups:

| Group | Event kinds |
|---|---|
| Liquid/reference | HOT_PAIR_REFERENCE |
| Fast/micro | MICRO_CAP_FAST_EVENT, NEW_PAIR_EVENT, MIGRATION_EVENT |
| Risk/decay | SAFETY_RISK_MEMORY, LIQUIDITY_DECAY_EVENT, HIGH_ACTIVITY_NO_FOLLOW_THROUGH |
| Ambiguous/advisory | AMBIGUOUS_MEMORY_CANDIDATE, SOCIAL_ATTENTION_ADVISORY, REVIVAL_EVENT |

`is_balanced=True` if all 4 groups have â‰¥ 1 candidate.
An unbalanced batch is not rejected â€” the operator decides whether to add candidates.
A zero-candidate batch is valid and produces `is_balanced=False` with note "batch is empty but valid."

---

## 4. Hard Locks

All hard locks from Lane X6 are preserved. Additional locks added:

| Lock | Value |
|---|---|
| `no_buy_sell_hold` | True |
| `no_paper_decisions` | True |
| `no_positions` | True |
| `no_pnl` | True |
| `no_retrieval_activation` | True |
| `no_live_trading` | True |
| `no_paid_api` | True |
| `no_wallet_private_key` | True |
| `no_scoring_ranking_confidence` | True |
| `no_weighted_logic` | True |
| `no_source_governor_bypass` | True |
| `no_central_scheduler_bypass` | True |
| `no_discovery_automation` | True |
| `no_live_source_fetching` | True |
| `no_embeddings_vectors` | True |
| `no_1h_4h_12h_24h_collection` | True |
| `no_5m_main_window` | True |
| `no_trade_events` | True |
| `no_paper_trade_audits` | True |
| `no_token_pair_mixing` | True |

---

## 5. X10.5 Gap Resolution

| X10.5 gap | X10.6 resolution |
|---|---|
| WIF WATCH_ONLYâ†’TRACK_FAST not recorded | `watch_only_to_track_fast_override` + lane-field mismatch detection; rejected without override |
| ANSEM no discovery row | `no_discovery_origin=True` required; rejected without override |
| ANSEM pair drift not acknowledged | `pair_drift_acknowledged=True` required; rejected without override |
| No event explanation for any token | `event_kind` label on every candidate |
| No risk context on any token | `context_tags` list on every candidate |
| No batch diversity signal | `batch_balance` assessment on every batch |
| No source trace IDs | `source_trace` dict on every candidate |
| No DB bridge from X6 to X5 | `build_selection_batch` produces bridging artifact |

---

## 6. Test Coverage

**File:** `tests/test_post_lane10_lane_x10_6_discovery_selection_traceability.py`

**105 tests, 0 failures.**

| Test class | Tests | Coverage area |
|---|---|---|
| `TestClassifyContextTags` | 18 | All 8 context tags, healthy-token baseline, multi-tag, threshold |
| `TestClassifyEventKind` | 16 | All 10 event kinds, priority order, no-buy-signal, fallback |
| `TestMarketCapNeutrality` | 7 | Micro-cap with/without activity; large-cap not auto-TRACK_FAST; no scoring |
| `TestValidateManualOverride` | 9 | Watch-only upgrade, no-origin, pair-drift, missing fields |
| `TestAssessBatchBalance` | 6 | Empty, balanced, gaps, counts, revival covers group |
| `TestBuildSelectionBatchGates` | 7 | Approval gate, db_path gate, backup gate, zero candidates, hard locks, financial fields |
| `TestBuildSelectionBatchRouting` | 10 | Accept/reject routing for all override scenarios, pair-drift, missing mint, mixed batch |
| `TestSelectedCandidateSchema` | 10 | All required fields on selected candidates including source_trace, override fields |
| `TestBatchSummaryFields` | 8 | event_kind_summary, batch_balance, manual_overrides, pair_drift_items, timestamps |
| `TestProposedTokenListPath` | 2 | Path recorded in output; None by default |
| `TestWIFScenario` | 4 | WIF rejected without override, selected with override, HOT_PAIR_REFERENCE kind, no micro-cap tag |
| `TestANSEMScenario` | 2 | ANSEM rejected without override, selected with double override |
| `TestContextTagThresholdOverrides` | 4 | Custom threshold parameters respected |

---

## 7. Files Changed

| File | Action |
|---|---|
| `src/printer_v1/operator_cli/lane_x10_6_selection_traceability.py` | CREATED |
| `tests/test_post_lane10_lane_x10_6_discovery_selection_traceability.py` | CREATED |
| `docs/printer-v1-lane-x10-6-discovery-selection-traceability-repair.md` | CREATED |

**Files NOT touched:**
- `src/printer_v1/operator_cli/lane_x6_discovery_selection_repair.py` â€” unchanged
- `src/printer_v1/operator_cli/lane_x5_five_token_runner.py` â€” unchanged
- All DB migration files â€” unchanged
- `AGENTS.md` â€” unchanged

---

## 8. Test Run Summary

| Suite | Tests | Result |
|---|---|---|
| Lane X10.6 (new) | 105 | PASS |
| Lane X6 (regression) | 150 | PASS |
| Lane X5 (regression) | 174 | PASS |

---

## 9. Risks and Concerns

### R1: This module does not write to DB
`build_selection_batch` produces a dict artifact only. It does not persist the selection batch to any DB table. A future lane (X11 or X12) would need to add a `printer_selection_batches` table to persist the output if operator traceability in the DB is required.

### R2: Operator must supply override fields manually
The reject-on-missing-override logic requires the operator to explicitly set `manual_override=True`, `manual_override_reason`, and (where applicable) `pair_drift_acknowledged=True`. There is no auto-detection of "should this have an override?"; the operator must know their candidate and set the fields. This is intentional: automated override is a contradiction.

### R3: Event-kind classification is deterministic but not exhaustive
The 10-rule priority chain covers the most common memecoin event patterns observed in the X5 proof. Edge cases will fall through to `AMBIGUOUS_MEMORY_CANDIDATE`. This is expected and by design.

### R4: Balance assessment is advisory only
A batch that passes all candidate-level gates but fails balance (e.g., 5 HOT_PAIR_REFERENCE tokens) is still `LANE_X10_6_COMPLETED`. The operator decides whether to add diverse candidates. This module reports gaps; it does not enforce diversity.

### R5: Social attention advisory is operator-flag only
`SOCIAL_ATTENTION_ADVISORY` fires only when `candidate.get("social_attention_advisory") is True`. It does not read any live social or Grok source. Grok/X research is advisory only and must not become source-of-truth.

---

## 10. Memory-Useful Verdict

**YES** â€” This lane produces memory-useful output. The `build_selection_batch` artifact explains:
- Why each token was chosen or rejected
- What type of memory event each token represents
- What risk context applies to each token
- Whether any tokens required operator override
- Whether the batch has diverse event-kind coverage

This context will inform future retrieval, clean-memory comparison, and manual operator audits.

---

## 11. Discovery Locked Verdict

**CONFIRMED LOCKED.** No discovery automation was enabled. No source fetching occurred. No alpha labels or buy-probability signals were added. Selection is memory-value based, not trade-decision based.

---

## 12. Lane X11 Proceed Verdict

**PROCEED to Lane X11 â€” 1h Activation Readiness (documentation / review only).**

Prerequisites confirmed:
- X10.5 gaps (WIF, ANSEM, no-origin, pair-drift, no-traceability) are resolved by X10.6
- 105 X10.6 tests pass
- 150 X6 regression tests pass
- All financial and retrieval locks remain at zero
- No DB mutations in this lane

Lane X11 scope:
- Review 1h snapshot cadence requirements and memory-window identity rules
- Define dirty-memory gates for WINDOW_1H
- Define how WINDOW_15M and WINDOW_1H interact
- Do NOT run real 1h collection before Lane X11 approval
- Preserve all locks: BUY/SELL/HOLD, paper decisions, positions, PnL, retrieval remain off
- 4h / 12h / 24h remain disabled until 1h is proven
- WINDOW_5M_MICRO_EVENT remains support-only

---

## 13. Summary

Lane X10.6 adds a structured, deterministic, audit-ready selection traceability layer to the Printer V1 discovery pipeline. Every selection decision is now labelled, overridden, pair-drift-acknowledged, source-traced, and balance-assessed â€” without introducing scoring, ranking, buy signals, or automated discovery. The operator remains in full control of the X5 token list composition.
