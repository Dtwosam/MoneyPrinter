from printer_v1.discovery.selection_batch import (
    build_qualified_random_active_selection,
    build_trajectory_coverage_report,
)


def candidate(index: int, **overrides):
    row = {
        "token_mint": f"Mint{index:02d}",
        "pair_address": f"Pair{index:02d}",
        "source_response_id": index + 1,
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "tracking_lane": "TRACK_NORMAL",
        "primary_bucket": "A1",
        "volume_24h": 10_000.0,
        "liquidity_usd": 20_000.0,
    }
    row.update(overrides)
    return row


def identities(report):
    return [(row["token_mint"], row["pair_address"]) for row in report["selected_candidates"]]


def test_selection_is_reproducible_and_ignores_manual_bucket_markers():
    pool = [candidate(index, primary_bucket="D1") for index in range(8)]
    first = build_qualified_random_active_selection(pool, target_size=4, seed="proof-seed")
    second = build_qualified_random_active_selection(list(reversed(pool)), target_size=4, seed="proof-seed")
    assert first["selection_ready"] is True
    assert identities(first) == identities(second)
    assert all(row["primary_bucket"] != "D1" for row in first["selected_candidates"])
    assert first["old_quota_diagnostic"]["hard_gate"] is False


def test_different_seeds_may_select_different_valid_samples():
    pool = [candidate(index) for index in range(10)]
    assert identities(build_qualified_random_active_selection(pool, target_size=4, seed="A")) != identities(
        build_qualified_random_active_selection(pool, target_size=4, seed="B")
    )


def test_unsafe_inactive_audit_only_and_duplicate_candidates_never_enter_pool():
    pool = [
        candidate(1),
        candidate(2, tracking_lane="WATCH_ONLY", audit_only=True),
        candidate(3, source_status="FAILED"),
        candidate(4, data_quality_label="DIRTY_DATA"),
        candidate(5, token_mint="Mint01"),
    ]
    report = build_qualified_random_active_selection(pool, target_size=1, seed="safe")
    assert report["eligible_pool_size"] == 1
    assert identities(report) == [("Mint01", "Pair01")]
    assert len(report["rejected_candidates"]) == 4


def test_too_few_eligible_candidates_stops_without_selection():
    report = build_qualified_random_active_selection([], target_size=2, seed="safe-stop")
    assert report["selection_ready"] is False
    assert report["selected_candidates"] == []
    assert report["eligible_pool_size"] == 0


def test_trajectory_report_is_categorical_and_read_only():
    observations = [candidate(1), candidate(1, primary_bucket="A1", volume_24h=1.0, txns_1h=0)]
    report = build_trajectory_coverage_report(observations)
    assert report["read_only"] is True
    assert report["exact_pairs_with_repeated_observations"] == 1
    assert set(report["trajectory_counts"]) == {
        "consolidation", "continuation", "death_inactivity", "dumping_decay",
        "failed_pump", "liquidity_removal", "revival",
    }
