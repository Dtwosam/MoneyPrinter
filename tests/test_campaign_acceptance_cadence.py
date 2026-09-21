"""Acceptance must validate each frozen lane, not a NORMAL-only pair total."""
import pytest

from printer_v1.operator_cli.campaign_full_run_accounting import evaluate_campaign_acceptance_gate


def _report(lanes=("TRACK_NORMAL", "TRACK_NORMAL")):
    # Literal fixture counts include every non-close observation: 8 NORMAL,
    # 15 FAST. The closing observation is represented separately.
    return {"selection_and_lifecycle": {"selected_tokens": [
        {"token_id": n, "pair_id": 100 + n, "tracking_lane": lane,
         "cadence": {"tracking_lane": lane,
                     "expected_snapshot_steps": count,
                     "planned_snapshot_steps": count,
                     "actual_snapshot_steps": count,
                     "coverage_status": "COMPLETE",
                     "missing_snapshot_steps": 0,
                     "succeeded_close_count": 1}}
        for n, (lane, count) in enumerate(
            ((lane, 15 if lane == "TRACK_FAST" else 8) for lane in lanes), 1)
    ]}}


def _complete(report):
    return evaluate_campaign_acceptance_gate(report)["checks"]["cadence_coverage_and_close_complete"]


@pytest.mark.parametrize("lanes", [
    ("TRACK_NORMAL", "TRACK_NORMAL"),
    ("TRACK_NORMAL", "TRACK_FAST"),
    ("TRACK_FAST", "TRACK_NORMAL"),
    ("TRACK_FAST", "TRACK_FAST"),
])
def test_complete_lane_specific_cadence_is_accepted(lanes):
    assert _complete(_report(lanes))


@pytest.mark.parametrize("field,value", [
    ("actual_snapshot_steps", 7), ("actual_snapshot_steps", 9),
    ("planned_snapshot_steps", 7), ("planned_snapshot_steps", 9),
    ("expected_snapshot_steps", 7), ("expected_snapshot_steps", 9),
    ("succeeded_close_count", 0), ("succeeded_close_count", 2),
    ("missing_snapshot_steps", 1), ("coverage_status", "INCOMPLETE"),
    ("tracking_lane", "TRACK_FAST"), ("tracking_lane", "UNKNOWN"),
    ("actual_snapshot_steps", "8"), ("actual_snapshot_steps", 8.5),
    ("missing_snapshot_steps", False),
])
def test_incomplete_or_conflicting_cadence_fails_closed(field, value):
    report = _report()
    report["selection_and_lifecycle"]["selected_tokens"][0]["cadence"][field] = value
    assert not _complete(report)


@pytest.mark.parametrize("field", [
    "expected_snapshot_steps", "planned_snapshot_steps", "actual_snapshot_steps",
    "missing_snapshot_steps", "succeeded_close_count", "tracking_lane",
])
def test_missing_cadence_evidence_fails_closed(field):
    report = _report()
    del report["selection_and_lifecycle"]["selected_tokens"][0]["cadence"][field]
    assert not _complete(report)


def test_equal_pair_total_cannot_hide_one_missing_and_one_extra_snapshot():
    report = _report()
    selected = report["selection_and_lifecycle"]["selected_tokens"]
    selected[0]["cadence"]["actual_snapshot_steps"] = 7
    selected[1]["cadence"]["actual_snapshot_steps"] = 9
    assert not _complete(report)


@pytest.mark.parametrize("lane", [None, "UNKNOWN", "TRACK_ARCHIVED"])
def test_selected_lane_must_be_known_and_match_cadence(lane):
    report = _report()
    report["selection_and_lifecycle"]["selected_tokens"][0]["tracking_lane"] = lane
    assert not _complete(report)


@pytest.mark.parametrize("lanes,counts", [
    (("TRACK_NORMAL", "TRACK_FAST"), (8, 15)),
    (("TRACK_FAST", "TRACK_FAST"), (15, 15)),
])
def test_durable_finalizer_accepts_complete_mixed_and_fast_cadence(lanes, counts):
    # This fixture seeds terminal observations. It proves finalizer wiring, not
    # acquisition or natural clean-memory production (covered separately).
    from tests.test_v2_9_8b_full_run_accounting_semantics_correction import _SemanticsFixture

    case = _SemanticsFixture()
    case.TRACKING_LANES = dict(zip((1, 2), lanes))
    case.SNAPSHOT_COUNTS = dict(zip((1, 2), counts))
    case.setUp()
    try:
        result = case._finalize()
        assert result["verdict"] == "CAMPAIGN_PASS", result["blocked_reasons"]
        selected = result["report"]["selection_and_lifecycle"]["selected_tokens"]
        assert [item["cadence"]["actual_snapshot_steps"] for item in selected] == list(counts)
        assert [item["cadence"]["tracking_lane"] for item in selected] == list(lanes)
    finally:
        case.tearDown()
