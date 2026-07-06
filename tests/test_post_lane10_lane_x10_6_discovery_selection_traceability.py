"""Tests for Lane X10.6 — Discovery Selection Traceability.

Validates:
- Event-kind classification (deterministic, no scoring)
- Context tag assignment (deterministic, no scoring)
- Market-cap neutrality (micro-cap can be TRACK_FAST, large-cap can be WATCH_ONLY)
- Manual override gating (WATCH_ONLY→TRACK_FAST, no-origin, pair-drift)
- Pair drift explicit acknowledgment requirement
- Batch balance assessment
- Main build_selection_batch function: selected/rejected routing, output schema
- Hard locks in output (all financial and trading fields must be False / zero)
- Operator-approval gate
- Zero-candidate valid outcome
"""

import unittest

from src.printer_v1.operator_cli.lane_x10_6_selection_traceability import (
    ALL_CONTEXT_TAGS,
    ALL_EVENT_KINDS,
    EVENT_AMBIGUOUS_MEMORY_CANDIDATE,
    EVENT_HIGH_ACTIVITY_NO_FOLLOW_THROUGH,
    EVENT_HOT_PAIR_REFERENCE,
    EVENT_LIQUIDITY_DECAY_EVENT,
    EVENT_MICRO_CAP_FAST_EVENT,
    EVENT_MIGRATION_EVENT,
    EVENT_NEW_PAIR_EVENT,
    EVENT_REVIVAL_EVENT,
    EVENT_SAFETY_RISK_MEMORY,
    EVENT_SOCIAL_ATTENTION_ADVISORY,
    LANE_X10_6_STATUS_BLOCKED,
    LANE_X10_6_STATUS_COMPLETED,
    TAG_EXIT_REALISM_UNKNOWN,
    TAG_HIGH_VOLATILITY,
    TAG_MICRO_CAP,
    TAG_POSSIBLE_LATE_BUY_TRAP,
    TAG_POSSIBLE_WICK_PUMP,
    TAG_THIN_LIQUIDITY,
    TAG_HOLDER_CONCENTRATION_RISK,
    TAG_POSSIBLE_SNIPER_OR_BUNDLE_RISK,
    assess_batch_balance,
    build_selection_batch,
    classify_context_tags,
    classify_event_kind,
    validate_manual_override,
)

_MICRO_CAP_FDV = 50_000.0   # clearly below 500k threshold
_LARGE_CAP_FDV = 10_000_000.0   # clearly above threshold


def _cand(
    mint="MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    pair="PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    *,
    fdv_usd=_MICRO_CAP_FDV,
    liquidity_usd=10_000.0,
    price_change_5m=0.0,
    price_change_1h=0.0,
    price_change_24h=0.0,
    volume_5m=0.0,
    volume_1h=0.0,
    volume_24h=5_000.0,
    txns_5m=0,
    txns_1h=0,
    txns_24h=0,
    chain="solana",
    discovery_action="TRACK_FAST",
    source_channel="dexscreener",
    priority_reason="test_reason",
    is_revival=False,
    safety_risk=False,
    social_attention_advisory=False,
    pair_is_migration=False,
    same_token_new_pair=False,
    is_new_pair_for_existing_token=False,
    possible_sniper_or_bundle_risk=False,
    holder_concentration_risk=False,
    manual_override=False,
    manual_override_reason="",
    watch_only_to_track_fast_override=False,
    no_discovery_origin=False,
    pair_drift_acknowledged=False,
    db_lane_before_selection="TRACK_FAST",
    selected_lane_for_batch="TRACK_FAST",
    _db_candidate_id=None,
    source_request_id=None,
    source_response_id=None,
) -> dict:
    return {
        "token_mint": mint,
        "pair_address": pair,
        "chain": chain,
        "fdv_usd": fdv_usd,
        "liquidity_usd": liquidity_usd,
        "price_change_5m": price_change_5m,
        "price_change_1h": price_change_1h,
        "price_change_24h": price_change_24h,
        "volume_5m": volume_5m,
        "volume_1h": volume_1h,
        "volume_24h": volume_24h,
        "txns_5m": txns_5m,
        "txns_1h": txns_1h,
        "txns_24h": txns_24h,
        "discovery_action": discovery_action,
        "source_channel": source_channel,
        "priority_reason": priority_reason,
        "is_revival": is_revival,
        "safety_risk": safety_risk,
        "social_attention_advisory": social_attention_advisory,
        "pair_is_migration": pair_is_migration,
        "same_token_new_pair": same_token_new_pair,
        "is_new_pair_for_existing_token": is_new_pair_for_existing_token,
        "possible_sniper_or_bundle_risk": possible_sniper_or_bundle_risk,
        "holder_concentration_risk": holder_concentration_risk,
        "manual_override": manual_override,
        "manual_override_reason": manual_override_reason,
        "watch_only_to_track_fast_override": watch_only_to_track_fast_override,
        "no_discovery_origin": no_discovery_origin,
        "pair_drift_acknowledged": pair_drift_acknowledged,
        "db_lane_before_selection": db_lane_before_selection,
        "selected_lane_for_batch": selected_lane_for_batch,
        "_db_candidate_id": _db_candidate_id,
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
    }


def _run(
    candidates: list[dict],
    *,
    operator_approved: bool = True,
    db_path: str = ":memory:",
    backup_path: str = "backup.sqlite3",
    **kwargs,
) -> dict:
    return build_selection_batch(
        db_path,
        backup_path,
        operator_approved=operator_approved,
        candidate_list_override=candidates,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Context tag classification
# ---------------------------------------------------------------------------

class TestClassifyContextTags(unittest.TestCase):

    def test_micro_cap_tag_when_fdv_below_threshold(self):
        tags = classify_context_tags(_cand(fdv_usd=100_000.0))
        self.assertIn(TAG_MICRO_CAP, tags)

    def test_no_micro_cap_tag_when_fdv_above_threshold(self):
        tags = classify_context_tags(_cand(fdv_usd=_LARGE_CAP_FDV))
        self.assertNotIn(TAG_MICRO_CAP, tags)

    def test_thin_liquidity_when_below_threshold(self):
        tags = classify_context_tags(_cand(liquidity_usd=1_000.0))
        self.assertIn(TAG_THIN_LIQUIDITY, tags)

    def test_no_thin_liquidity_when_above_threshold(self):
        tags = classify_context_tags(_cand(liquidity_usd=50_000.0))
        self.assertNotIn(TAG_THIN_LIQUIDITY, tags)

    def test_exit_realism_unknown_when_zero_liquidity(self):
        tags = classify_context_tags(_cand(liquidity_usd=0.0))
        self.assertIn(TAG_EXIT_REALISM_UNKNOWN, tags)

    def test_exit_realism_unknown_when_no_liquidity_field(self):
        c = dict(_cand())
        del c["liquidity_usd"]
        tags = classify_context_tags(c)
        self.assertIn(TAG_EXIT_REALISM_UNKNOWN, tags)

    def test_high_volatility_large_5m_spike(self):
        tags = classify_context_tags(_cand(price_change_5m=50.0))
        self.assertIn(TAG_HIGH_VOLATILITY, tags)

    def test_high_volatility_large_1h_move(self):
        tags = classify_context_tags(_cand(price_change_1h=-90.0))
        self.assertIn(TAG_HIGH_VOLATILITY, tags)

    def test_no_high_volatility_small_moves(self):
        tags = classify_context_tags(_cand(price_change_5m=5.0, price_change_1h=5.0))
        self.assertNotIn(TAG_HIGH_VOLATILITY, tags)

    def test_possible_wick_pump_large_5m_no_1h_persistence(self):
        tags = classify_context_tags(_cand(price_change_5m=80.0, price_change_1h=3.0))
        self.assertIn(TAG_POSSIBLE_WICK_PUMP, tags)

    def test_no_wick_pump_when_1h_also_large(self):
        tags = classify_context_tags(_cand(price_change_5m=80.0, price_change_1h=60.0))
        self.assertNotIn(TAG_POSSIBLE_WICK_PUMP, tags)

    def test_possible_late_buy_trap_large_24h_move(self):
        tags = classify_context_tags(_cand(price_change_24h=300.0))
        self.assertIn(TAG_POSSIBLE_LATE_BUY_TRAP, tags)

    def test_no_late_buy_trap_moderate_24h(self):
        tags = classify_context_tags(_cand(price_change_24h=50.0))
        self.assertNotIn(TAG_POSSIBLE_LATE_BUY_TRAP, tags)

    def test_sniper_bundle_risk_operator_flag(self):
        tags = classify_context_tags(_cand(possible_sniper_or_bundle_risk=True))
        self.assertIn(TAG_POSSIBLE_SNIPER_OR_BUNDLE_RISK, tags)

    def test_holder_concentration_risk_operator_flag(self):
        tags = classify_context_tags(_cand(holder_concentration_risk=True))
        self.assertIn(TAG_HOLDER_CONCENTRATION_RISK, tags)

    def test_returns_list_type(self):
        tags = classify_context_tags(_cand())
        self.assertIsInstance(tags, list)

    def test_all_tags_are_known_constants(self):
        c = _cand(
            fdv_usd=100_000.0,
            liquidity_usd=0.0,
            price_change_5m=80.0,
            price_change_1h=-90.0,
            price_change_24h=300.0,
            possible_sniper_or_bundle_risk=True,
            holder_concentration_risk=True,
        )
        tags = classify_context_tags(c)
        for tag in tags:
            self.assertIn(tag, ALL_CONTEXT_TAGS)

    def test_no_tags_for_healthy_token(self):
        tags = classify_context_tags(_cand(
            fdv_usd=_LARGE_CAP_FDV,
            liquidity_usd=100_000.0,
            price_change_5m=2.0,
            price_change_1h=5.0,
            price_change_24h=10.0,
        ))
        self.assertEqual(tags, [])

    def test_multiple_tags_can_apply_simultaneously(self):
        tags = classify_context_tags(_cand(
            fdv_usd=50_000.0,
            liquidity_usd=0.0,
            price_change_5m=80.0,
            price_change_24h=300.0,
        ))
        self.assertIn(TAG_MICRO_CAP, tags)
        self.assertIn(TAG_EXIT_REALISM_UNKNOWN, tags)
        self.assertGreater(len(tags), 1)


# ---------------------------------------------------------------------------
# Event-kind classification
# ---------------------------------------------------------------------------

class TestClassifyEventKind(unittest.TestCase):

    def test_safety_risk_wins_first(self):
        ek = classify_event_kind(_cand(safety_risk=True, is_revival=True, pair_is_migration=True))
        self.assertEqual(ek, EVENT_SAFETY_RISK_MEMORY)

    def test_revival_event(self):
        ek = classify_event_kind(_cand(is_revival=True))
        self.assertEqual(ek, EVENT_REVIVAL_EVENT)

    def test_migration_event_via_flag(self):
        ek = classify_event_kind(_cand(pair_is_migration=True))
        self.assertEqual(ek, EVENT_MIGRATION_EVENT)

    def test_migration_event_via_source_channel(self):
        ek = classify_event_kind(_cand(source_channel="PUMPSWAP_MIGRATION"))
        self.assertEqual(ek, EVENT_MIGRATION_EVENT)

    def test_new_pair_event_via_flag(self):
        ek = classify_event_kind(_cand(same_token_new_pair=True))
        self.assertEqual(ek, EVENT_NEW_PAIR_EVENT)

    def test_new_pair_event_via_is_new_pair_field(self):
        ek = classify_event_kind(_cand(is_new_pair_for_existing_token=True))
        self.assertEqual(ek, EVENT_NEW_PAIR_EVENT)

    def test_micro_cap_fast_event_small_fdv_with_activity(self):
        ek = classify_event_kind(_cand(
            fdv_usd=50_000.0,
            price_change_5m=50.0,
            txns_5m=20,
            volume_5m=2_000.0,
        ))
        self.assertEqual(ek, EVENT_MICRO_CAP_FAST_EVENT)

    def test_micro_cap_fast_event_via_1h_activity(self):
        ek = classify_event_kind(_cand(
            fdv_usd=200_000.0,
            price_change_1h=60.0,
            txns_1h=50,
            volume_1h=5_000.0,
        ))
        self.assertEqual(ek, EVENT_MICRO_CAP_FAST_EVENT)

    def test_no_micro_cap_fast_event_without_activity(self):
        ek = classify_event_kind(_cand(fdv_usd=50_000.0, price_change_5m=0.0, txns_5m=0))
        self.assertNotEqual(ek, EVENT_MICRO_CAP_FAST_EVENT)

    def test_no_micro_cap_fast_event_for_large_cap(self):
        ek = classify_event_kind(_cand(
            fdv_usd=_LARGE_CAP_FDV,
            price_change_5m=50.0,
            txns_5m=20,
            volume_5m=2_000.0,
        ))
        self.assertNotEqual(ek, EVENT_MICRO_CAP_FAST_EVENT)

    def test_high_activity_no_follow_through(self):
        ek = classify_event_kind(_cand(
            fdv_usd=_LARGE_CAP_FDV,
            txns_5m=50,
            volume_1h=10_000.0,
            price_change_5m=3.0,
            price_change_1h=5.0,
        ))
        self.assertEqual(ek, EVENT_HIGH_ACTIVITY_NO_FOLLOW_THROUGH)

    def test_liquidity_decay_event(self):
        ek = classify_event_kind(_cand(
            liquidity_usd=1_000.0,
            volume_24h=100.0,
            fdv_usd=_LARGE_CAP_FDV,
        ))
        self.assertEqual(ek, EVENT_LIQUIDITY_DECAY_EVENT)

    def test_hot_pair_reference_very_large_cap(self):
        ek = classify_event_kind(_cand(
            fdv_usd=_LARGE_CAP_FDV,
            liquidity_usd=500_000.0,
            volume_24h=50_000_000.0,
        ))
        self.assertEqual(ek, EVENT_HOT_PAIR_REFERENCE)

    def test_social_attention_advisory_operator_flag(self):
        ek = classify_event_kind(_cand(
            social_attention_advisory=True,
            fdv_usd=_LARGE_CAP_FDV / 3,
        ))
        self.assertEqual(ek, EVENT_SOCIAL_ATTENTION_ADVISORY)

    def test_ambiguous_fallback_for_generic_token(self):
        ek = classify_event_kind(_cand(
            fdv_usd=200_000.0,
            liquidity_usd=15_000.0,
            price_change_5m=2.0,
            price_change_1h=3.0,
            txns_5m=2,
            txns_1h=5,
        ))
        self.assertEqual(ek, EVENT_AMBIGUOUS_MEMORY_CANDIDATE)

    def test_event_kind_is_one_of_known_constants(self):
        for cand in [
            _cand(safety_risk=True),
            _cand(is_revival=True),
            _cand(pair_is_migration=True),
            _cand(same_token_new_pair=True),
            _cand(fdv_usd=50_000.0, price_change_5m=50.0, txns_5m=20, volume_5m=2_000.0),
            _cand(fdv_usd=_LARGE_CAP_FDV, txns_5m=50, volume_1h=10_000.0),
            _cand(liquidity_usd=1_000.0, volume_24h=100.0),
            _cand(fdv_usd=_LARGE_CAP_FDV, volume_24h=50_000_000.0, liquidity_usd=500_000.0),
            _cand(social_attention_advisory=True, fdv_usd=100_000.0),
            _cand(),
        ]:
            ek = classify_event_kind(cand)
            self.assertIn(ek, ALL_EVENT_KINDS, msg=f"Unknown event kind: {ek}")


# ---------------------------------------------------------------------------
# Market-cap neutrality
# ---------------------------------------------------------------------------

class TestMarketCapNeutrality(unittest.TestCase):
    """Micro-cap with fast event = TRACK_FAST.
    Large-cap without active event = not TRACK_FAST event kind.
    Neither cap level is automatically TRACK_FAST.
    """

    def test_micro_cap_with_fast_event_classifies_as_micro_cap_fast_event(self):
        ek = classify_event_kind(_cand(
            fdv_usd=30_000.0,
            price_change_5m=40.0,
            txns_5m=15,
            volume_5m=1_000.0,
        ))
        self.assertEqual(ek, EVENT_MICRO_CAP_FAST_EVENT)

    def test_micro_cap_without_fast_event_is_not_micro_cap_fast_event(self):
        ek = classify_event_kind(_cand(fdv_usd=30_000.0))
        self.assertNotEqual(ek, EVENT_MICRO_CAP_FAST_EVENT)

    def test_micro_cap_without_fast_event_falls_through_to_ambiguous_or_other(self):
        ek = classify_event_kind(_cand(fdv_usd=30_000.0))
        self.assertIn(ek, ALL_EVENT_KINDS)

    def test_large_cap_with_no_fast_event_can_be_hot_pair_reference(self):
        ek = classify_event_kind(_cand(
            fdv_usd=_LARGE_CAP_FDV,
            liquidity_usd=500_000.0,
            volume_24h=50_000_000.0,
        ))
        self.assertEqual(ek, EVENT_HOT_PAIR_REFERENCE)

    def test_large_cap_is_not_automatically_micro_cap_fast_event(self):
        ek = classify_event_kind(_cand(
            fdv_usd=_LARGE_CAP_FDV,
            price_change_5m=50.0,
            txns_5m=20,
            volume_5m=2_000.0,
        ))
        self.assertNotEqual(ek, EVENT_MICRO_CAP_FAST_EVENT)

    def test_no_scoring_in_tags(self):
        tags = classify_context_tags(_cand(fdv_usd=30_000.0))
        for tag in tags:
            self.assertNotIn("score", tag.lower())
            self.assertNotIn("rank", tag.lower())
            self.assertNotIn("confidence", tag.lower())

    def test_no_buy_signal_in_event_kind(self):
        ek = classify_event_kind(_cand(
            fdv_usd=30_000.0,
            price_change_5m=50.0,
            txns_5m=20,
            volume_5m=2_000.0,
        ))
        self.assertNotIn("buy", ek.lower())
        self.assertNotIn("sell", ek.lower())
        self.assertNotIn("alpha", ek.lower())


# ---------------------------------------------------------------------------
# Manual override validation
# ---------------------------------------------------------------------------

class TestValidateManualOverride(unittest.TestCase):

    def test_no_override_required_for_plain_candidate(self):
        required, missing = validate_manual_override(_cand())
        self.assertFalse(required)
        self.assertIsNone(missing)

    def test_watch_only_upgrade_requires_override(self):
        c = _cand(watch_only_to_track_fast_override=True)
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNotNone(missing)

    def test_watch_only_override_satisfied_when_fields_present(self):
        c = _cand(
            watch_only_to_track_fast_override=True,
            manual_override=True,
            manual_override_reason="WIF elevated: high 5m activity spike observed",
        )
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNone(missing)

    def test_no_discovery_origin_requires_override(self):
        c = _cand(no_discovery_origin=True)
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNotNone(missing)

    def test_no_discovery_origin_satisfied_when_fields_present(self):
        c = _cand(
            no_discovery_origin=True,
            manual_override=True,
            manual_override_reason="ANSEM registered via X5 list, no discovery row",
        )
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNone(missing)

    def test_pair_drift_requires_override(self):
        c = _cand(same_token_new_pair=True)
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNotNone(missing)

    def test_pair_drift_acknowledged_requires_override_and_reason(self):
        c = _cand(
            pair_drift_acknowledged=True,
            manual_override=True,
            manual_override_reason="ANSEM pair drift confirmed; original pair still active",
        )
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNone(missing)

    def test_missing_manual_override_reason_string_blocks(self):
        c = _cand(
            watch_only_to_track_fast_override=True,
            manual_override=True,
            manual_override_reason="",
        )
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNotNone(missing)

    def test_missing_manual_override_bool_blocks(self):
        c = _cand(
            no_discovery_origin=True,
            manual_override=False,
            manual_override_reason="some reason",
        )
        required, missing = validate_manual_override(c)
        self.assertTrue(required)
        self.assertIsNotNone(missing)


# ---------------------------------------------------------------------------
# Batch balance assessment
# ---------------------------------------------------------------------------

class TestAssessBatchBalance(unittest.TestCase):

    def _sel(self, event_kind: str) -> dict:
        return {"event_kind": event_kind}

    def test_empty_batch_is_not_balanced_but_valid(self):
        result = assess_batch_balance([])
        self.assertFalse(result["is_balanced"])
        self.assertIn("empty", result["balance_note"])

    def test_all_four_groups_covered_is_balanced(self):
        selected = [
            self._sel(EVENT_HOT_PAIR_REFERENCE),
            self._sel(EVENT_MICRO_CAP_FAST_EVENT),
            self._sel(EVENT_SAFETY_RISK_MEMORY),
            self._sel(EVENT_AMBIGUOUS_MEMORY_CANDIDATE),
        ]
        result = assess_batch_balance(selected)
        self.assertTrue(result["is_balanced"])
        self.assertEqual(result["coverage_gaps"], [])

    def test_missing_liquid_reference_noted_in_gaps(self):
        selected = [
            self._sel(EVENT_MICRO_CAP_FAST_EVENT),
            self._sel(EVENT_SAFETY_RISK_MEMORY),
            self._sel(EVENT_AMBIGUOUS_MEMORY_CANDIDATE),
        ]
        result = assess_batch_balance(selected)
        self.assertFalse(result["is_balanced"])
        self.assertTrue(any("liquid" in g.lower() for g in result["coverage_gaps"]))

    def test_event_kind_counts_reflect_selections(self):
        selected = [
            self._sel(EVENT_MICRO_CAP_FAST_EVENT),
            self._sel(EVENT_MICRO_CAP_FAST_EVENT),
            self._sel(EVENT_HOT_PAIR_REFERENCE),
        ]
        result = assess_batch_balance(selected)
        self.assertEqual(result["event_kind_counts"][EVENT_MICRO_CAP_FAST_EVENT], 2)
        self.assertEqual(result["event_kind_counts"][EVENT_HOT_PAIR_REFERENCE], 1)

    def test_revival_covers_ambiguous_group(self):
        selected = [
            self._sel(EVENT_HOT_PAIR_REFERENCE),
            self._sel(EVENT_MICRO_CAP_FAST_EVENT),
            self._sel(EVENT_LIQUIDITY_DECAY_EVENT),
            self._sel(EVENT_REVIVAL_EVENT),
        ]
        result = assess_batch_balance(selected)
        self.assertTrue(result["is_balanced"])

    def test_balance_is_informational_not_a_gate(self):
        result = assess_batch_balance([self._sel(EVENT_HOT_PAIR_REFERENCE)])
        self.assertFalse(result["is_balanced"])
        self.assertIn("is_balanced", result)


# ---------------------------------------------------------------------------
# build_selection_batch — gate and structural tests
# ---------------------------------------------------------------------------

class TestBuildSelectionBatchGates(unittest.TestCase):

    def test_blocked_without_operator_approval(self):
        result = _run([], operator_approved=False)
        self.assertEqual(result["lane_x10_6_status"], LANE_X10_6_STATUS_BLOCKED)
        self.assertIn("operator_approved", " ".join(result["blocked_reasons"]))

    def test_blocked_without_db_path(self):
        result = build_selection_batch(
            None, "backup.sqlite3",
            operator_approved=True,
            candidate_list_override=[],
        )
        self.assertEqual(result["lane_x10_6_status"], LANE_X10_6_STATUS_BLOCKED)

    def test_blocked_without_backup_proof_path(self):
        result = build_selection_batch(
            ":memory:", None,
            operator_approved=True,
            candidate_list_override=[],
        )
        self.assertEqual(result["lane_x10_6_status"], LANE_X10_6_STATUS_BLOCKED)

    def test_zero_candidates_is_valid_completed_result(self):
        result = _run([])
        self.assertEqual(result["lane_x10_6_status"], LANE_X10_6_STATUS_COMPLETED)
        self.assertEqual(result["selected_count"], 0)
        self.assertEqual(result["rejected_count"], 0)

    def test_hard_locks_always_present(self):
        result = _run([])
        self.assertIn("hard_locks", result)
        locks = result["hard_locks"]
        self.assertTrue(locks.get("no_buy_sell_hold"))
        self.assertTrue(locks.get("no_paper_decisions"))
        self.assertTrue(locks.get("no_positions"))
        self.assertTrue(locks.get("no_pnl"))
        self.assertTrue(locks.get("no_scoring_ranking_confidence"))

    def test_financial_fields_are_zero(self):
        result = _run([_cand()])
        self.assertFalse(result["buy_enabled"])
        self.assertFalse(result["sell_enabled"])
        self.assertFalse(result["hold_enabled"])
        self.assertEqual(result["paper_decisions_created"], 0)
        self.assertEqual(result["positions_created"], 0)
        self.assertEqual(result["trade_events_created"], 0)
        self.assertEqual(result["pnl_created"], 0)

    def test_automated_selection_locked(self):
        result = _run([_cand()])
        self.assertTrue(result["automated_selection_locked"])
        self.assertTrue(result["discovery_is_intake_not_alpha"])
        self.assertTrue(result["selection_is_memory_value_based_not_buy_probability"])


# ---------------------------------------------------------------------------
# build_selection_batch — candidate routing
# ---------------------------------------------------------------------------

class TestBuildSelectionBatchRouting(unittest.TestCase):

    def test_plain_candidate_is_selected(self):
        result = _run([_cand()])
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["rejected_count"], 0)

    def test_watch_only_without_override_is_rejected(self):
        c = _cand(
            watch_only_to_track_fast_override=True,
            manual_override=False,
            manual_override_reason="",
        )
        result = _run([c])
        self.assertEqual(result["selected_count"], 0)
        self.assertEqual(result["rejected_count"], 1)
        self.assertIn("manual_override_required", result["rejected_candidates"][0]["rejection_reason"])

    def test_watch_only_with_override_is_selected(self):
        c = _cand(
            watch_only_to_track_fast_override=True,
            manual_override=True,
            manual_override_reason="WIF elevated: activity spike confirmed",
        )
        result = _run([c])
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["rejected_count"], 0)

    def test_no_discovery_origin_without_override_is_rejected(self):
        c = _cand(
            no_discovery_origin=True,
            manual_override=False,
        )
        result = _run([c])
        self.assertEqual(result["rejected_count"], 1)

    def test_no_discovery_origin_with_override_is_selected(self):
        c = _cand(
            no_discovery_origin=True,
            manual_override=True,
            manual_override_reason="ANSEM registered directly in X5 list",
        )
        result = _run([c])
        self.assertEqual(result["selected_count"], 1)

    def test_pair_drift_without_acknowledgment_is_rejected(self):
        c = _cand(
            same_token_new_pair=True,
            pair_drift_acknowledged=False,
            manual_override=False,
        )
        result = _run([c])
        self.assertEqual(result["rejected_count"], 1)
        self.assertIn("pair_drift", result["rejected_candidates"][0]["rejection_reason"])

    def test_pair_drift_with_acknowledgment_is_selected(self):
        c = _cand(
            same_token_new_pair=True,
            pair_drift_acknowledged=True,
            manual_override=True,
            manual_override_reason="ANSEM pair drift: new pair confirmed same token",
        )
        result = _run([c])
        self.assertEqual(result["selected_count"], 1)

    def test_missing_mint_is_rejected(self):
        c = _cand(mint="")
        result = _run([c])
        self.assertEqual(result["rejected_count"], 1)
        self.assertIn("missing_token_mint", result["rejected_candidates"][0]["rejection_reason"])

    def test_multiple_candidates_mix_of_selected_and_rejected(self):
        good = _cand(mint="MintGoodAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        bad = _cand(
            mint="MintBadAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB",
            watch_only_to_track_fast_override=True,
            manual_override=False,
        )
        result = _run([good, bad])
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["rejected_count"], 1)

    def test_override_missing_count_reflects_rejected_override_cases(self):
        c = _cand(
            watch_only_to_track_fast_override=True,
            manual_override=False,
        )
        result = _run([c])
        self.assertGreater(result["override_missing_count"], 0)


# ---------------------------------------------------------------------------
# build_selection_batch — selected candidate schema
# ---------------------------------------------------------------------------

class TestSelectedCandidateSchema(unittest.TestCase):

    def _selected(self) -> dict:
        result = _run([_cand()])
        return result["selected_candidates"][0]

    def test_event_kind_in_selected_candidate(self):
        s = self._selected()
        self.assertIn("event_kind", s)
        self.assertIn(s["event_kind"], ALL_EVENT_KINDS)

    def test_context_tags_in_selected_candidate(self):
        s = self._selected()
        self.assertIn("context_tags", s)
        self.assertIsInstance(s["context_tags"], list)

    def test_inclusion_reason_set(self):
        s = self._selected()
        self.assertIn("inclusion_reason", s)
        self.assertIsNotNone(s["inclusion_reason"])

    def test_rejection_reason_none_for_selected(self):
        s = self._selected()
        self.assertIsNone(s["rejection_reason"])

    def test_included_true_for_selected(self):
        s = self._selected()
        self.assertTrue(s["included"])

    def test_source_trace_fields(self):
        c = _cand(_db_candidate_id=42, source_request_id="req-001", source_response_id="resp-002")
        result = _run([c])
        s = result["selected_candidates"][0]
        self.assertIn("source_trace", s)
        st = s["source_trace"]
        self.assertEqual(st["discovery_candidate_id"], 42)
        self.assertEqual(st["source_request_id"], "req-001")
        self.assertEqual(st["source_response_id"], "resp-002")

    def test_manual_override_fields_present(self):
        c = _cand(
            watch_only_to_track_fast_override=True,
            manual_override=True,
            manual_override_reason="test reason",
        )
        result = _run([c])
        s = result["selected_candidates"][0]
        self.assertTrue(s["manual_override"])
        self.assertEqual(s["manual_override_reason"], "test reason")
        self.assertTrue(s["watch_only_to_track_fast_override"])

    def test_no_discovery_origin_in_schema(self):
        c = _cand(
            no_discovery_origin=True,
            manual_override=True,
            manual_override_reason="no origin reason",
        )
        result = _run([c])
        s = result["selected_candidates"][0]
        self.assertTrue(s["no_discovery_origin"])

    def test_db_lane_before_selection_preserved(self):
        c = _cand(db_lane_before_selection="WATCH_ONLY", watch_only_to_track_fast_override=True,
                  manual_override=True, manual_override_reason="r")
        result = _run([c])
        s = result["selected_candidates"][0]
        self.assertEqual(s["db_lane_before_selection"], "WATCH_ONLY")

    def test_chain_defaults_to_solana(self):
        s = self._selected()
        self.assertEqual(s["chain"], "solana")


# ---------------------------------------------------------------------------
# build_selection_batch — batch summary fields
# ---------------------------------------------------------------------------

class TestBatchSummaryFields(unittest.TestCase):

    def test_event_kind_summary_present(self):
        result = _run([_cand()])
        self.assertIn("event_kind_summary", result)
        self.assertIn(EVENT_AMBIGUOUS_MEMORY_CANDIDATE, result["event_kind_summary"])

    def test_event_kind_summary_counts_selected_candidates(self):
        c1 = _cand(mint="MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        c2 = _cand(mint="MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")
        result = _run([c1, c2])
        total = sum(result["event_kind_summary"].values())
        self.assertEqual(total, result["selected_count"])

    def test_batch_balance_present(self):
        result = _run([_cand()])
        self.assertIn("batch_balance", result)
        balance = result["batch_balance"]
        self.assertIn("is_balanced", balance)
        self.assertIn("balance_note", balance)
        self.assertIn("coverage_gaps", balance)

    def test_manual_overrides_list_populated(self):
        c = _cand(
            watch_only_to_track_fast_override=True,
            manual_override=True,
            manual_override_reason="WIF spike",
        )
        result = _run([c])
        self.assertEqual(len(result["manual_overrides"]), 1)
        self.assertEqual(result["manual_overrides"][0]["manual_override_reason"], "WIF spike")

    def test_pair_drift_items_populated(self):
        c = _cand(
            same_token_new_pair=True,
            pair_drift_acknowledged=True,
            manual_override=True,
            manual_override_reason="drift ok",
        )
        result = _run([c])
        self.assertGreater(len(result["pair_drift_items"]), 0)

    def test_pair_drift_pending_nonzero_when_unacknowledged(self):
        c = _cand(same_token_new_pair=True, pair_drift_acknowledged=False, manual_override=False)
        result = _run([c])
        self.assertGreater(result["pair_drift_pending_acknowledgment"], 0)

    def test_pair_drift_pending_zero_when_acknowledged(self):
        c = _cand(
            same_token_new_pair=True,
            pair_drift_acknowledged=True,
            manual_override=True,
            manual_override_reason="confirmed",
        )
        result = _run([c])
        self.assertEqual(result["pair_drift_pending_acknowledgment"], 0)

    def test_run_started_and_finished_timestamps_present(self):
        result = _run([])
        self.assertIn("run_started_at", result)
        self.assertIn("run_finished_at", result)
        self.assertIsNotNone(result["run_started_at"])
        self.assertIsNotNone(result["run_finished_at"])

    def test_candidate_count_input_matches_supplied_list(self):
        result = _run([_cand(), _cand(mint="Mint2BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")])
        self.assertEqual(result["candidate_count_input"], 2)


# ---------------------------------------------------------------------------
# build_selection_batch — proposed token list path
# ---------------------------------------------------------------------------

class TestProposedTokenListPath(unittest.TestCase):

    def test_proposed_token_list_path_recorded_in_output(self):
        result = _run([], proposed_x5_token_list_path="data/x5_tokens.json")
        self.assertEqual(result["proposed_x5_token_list_path"], "data/x5_tokens.json")

    def test_proposed_token_list_path_none_by_default(self):
        result = _run([])
        self.assertIsNone(result["proposed_x5_token_list_path"])


# ---------------------------------------------------------------------------
# Real-world scenario: WIF WATCH_ONLY → TRACK_FAST
# ---------------------------------------------------------------------------

class TestWIFScenario(unittest.TestCase):
    """Simulate the WIF gap found in X10.5 audit:
    WIF had WATCH_ONLY in DB but was run as TRACK_FAST in the proof.
    Should be selectable with explicit override.
    """

    def _wif_cand(self, *, with_override: bool) -> dict:
        return _cand(
            mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            pair="2eMyABpUX3WByeDjQrF8cjhsEBNoBGFwVBDmGxTn2MG1",
            fdv_usd=800_000_000.0,
            liquidity_usd=20_000_000.0,
            price_change_5m=2.5,
            price_change_1h=5.0,
            price_change_24h=8.0,
            volume_24h=15_000_000.0,
            db_lane_before_selection="WATCH_ONLY",
            selected_lane_for_batch="TRACK_FAST",
            watch_only_to_track_fast_override=with_override,
            manual_override=with_override,
            manual_override_reason="WIF elevated: X10.5 audit — proof-run used TRACK_FAST" if with_override else "",
            source_channel="dexscreener",
            discovery_action="WATCH_ONLY",
            _db_candidate_id=7,
        )

    def test_wif_rejected_without_override(self):
        result = _run([self._wif_cand(with_override=False)])
        self.assertEqual(result["rejected_count"], 1)
        self.assertIn("manual_override_required", result["rejected_candidates"][0]["rejection_reason"])

    def test_wif_selected_with_override(self):
        result = _run([self._wif_cand(with_override=True)])
        self.assertEqual(result["selected_count"], 1)
        s = result["selected_candidates"][0]
        self.assertTrue(s["watch_only_to_track_fast_override"])
        self.assertEqual(s["db_lane_before_selection"], "WATCH_ONLY")

    def test_wif_classified_as_hot_pair_reference(self):
        ek = classify_event_kind(self._wif_cand(with_override=True))
        self.assertEqual(ek, EVENT_HOT_PAIR_REFERENCE)

    def test_wif_has_no_micro_cap_tag(self):
        tags = classify_context_tags(self._wif_cand(with_override=True))
        self.assertNotIn(TAG_MICRO_CAP, tags)


# ---------------------------------------------------------------------------
# Real-world scenario: ANSEM no-discovery-origin + pair drift
# ---------------------------------------------------------------------------

class TestANSEMScenario(unittest.TestCase):
    """ANSEM had no discovery candidate row and pair drift in the X10.5 audit.
    Must require double override (no_discovery_origin + pair_drift_acknowledged).
    """

    def _ansem_cand(self, *, with_override: bool) -> dict:
        return _cand(
            mint="2Ab8rjQCgbaB3y4WDdMDCnAaRpKM5T2TKNpGjgPH5dJe",
            pair="FnzKY6GHkgppbSmTgLEzAJtKTDQqNWYnBdtCMbGsP4Jn",
            fdv_usd=5_000_000.0,
            liquidity_usd=80_000.0,
            discovery_action="TRACKING",
            db_lane_before_selection="TRACKING",
            no_discovery_origin=True,
            same_token_new_pair=True,
            pair_drift_acknowledged=with_override,
            manual_override=with_override,
            manual_override_reason="ANSEM: no discovery row; pair drift confirmed same token" if with_override else "",
            _db_candidate_id=None,
        )

    def test_ansem_rejected_without_override(self):
        result = _run([self._ansem_cand(with_override=False)])
        self.assertEqual(result["rejected_count"], 1)

    def test_ansem_selected_with_override(self):
        result = _run([self._ansem_cand(with_override=True)])
        self.assertEqual(result["selected_count"], 1)
        s = result["selected_candidates"][0]
        self.assertTrue(s["no_discovery_origin"])
        self.assertTrue(s["pair_drift_acknowledged"])
        self.assertTrue(s["manual_override"])


# ---------------------------------------------------------------------------
# Context-tag threshold overrides
# ---------------------------------------------------------------------------

class TestContextTagThresholdOverrides(unittest.TestCase):

    def test_custom_micro_cap_threshold(self):
        # Token with fdv=200k is not micro-cap at default 500k threshold;
        # but at a custom threshold of 100k it should not be either.
        tags = classify_context_tags(
            _cand(fdv_usd=200_000.0),
            micro_cap_fdv_threshold=100_000.0,
        )
        self.assertNotIn(TAG_MICRO_CAP, tags)

    def test_custom_micro_cap_threshold_above_fdv_adds_tag(self):
        tags = classify_context_tags(
            _cand(fdv_usd=200_000.0),
            micro_cap_fdv_threshold=500_000.0,
        )
        self.assertIn(TAG_MICRO_CAP, tags)

    def test_custom_thin_liquidity_threshold(self):
        tags = classify_context_tags(
            _cand(liquidity_usd=3_000.0),
            thin_liquidity_threshold=2_000.0,
        )
        self.assertNotIn(TAG_THIN_LIQUIDITY, tags)

    def test_custom_thin_liquidity_threshold_above_liquidity_adds_tag(self):
        tags = classify_context_tags(
            _cand(liquidity_usd=3_000.0),
            thin_liquidity_threshold=5_000.0,
        )
        self.assertIn(TAG_THIN_LIQUIDITY, tags)


if __name__ == "__main__":
    unittest.main()
