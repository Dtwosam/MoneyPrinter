from __future__ import annotations

from pathlib import Path
import sys


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one exact replacement, found {count}")
    p.write_text(text.replace(old, new, 1))


def replace_count(path: str, old: str, new: str, expected: int) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} replacements, found {count}")
    p.write_text(text.replace(old, new))


def write_tests() -> None:
    Path("tests/test_v2_9_8b_refresh_coverage_carry.py").write_text(r'''from __future__ import annotations

from types import SimpleNamespace


def _coverage(request_id: int, suffix: str = "a") -> dict[str, object]:
    return {
        "source_request_id": request_id,
        "source_name": "dexscreener",
        "request_kind": "fresh_profiles",
        "logical_stage_id": f"campaign|run|cycle|REFRESH|{request_id}",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [["transport", request_id, suffix]],
    }


def test_completed_refresh_carries_stage_coverage_out_of_existing_owner(tmp_path):
    """Behavioral RED: a real completed refresh must carry its exact coverage."""
    from printer_v1.db import apply_migrations
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import REFRESH_COMPLETED
    from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
        PreLifecycleTemporalRefreshOwner,
    )

    db_path = tmp_path / "refresh-coverage.sqlite3"
    apply_migrations(db_path)
    entry = _coverage(42)

    def refresh_stage(
        connection,
        *,
        campaign_id,
        run_id,
        cycle_id,
        **kwargs,
    ):
        return {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "source_operations": 1,
            "provider_failures": 0,
            "channels_unavailable": (),
            "channels_attempted": ("dexscreener",),
            "channels_skipped": (),
            "stage_reports": {
                "dex": {"source_request_coverage": [entry]},
            },
        }

    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id="campaign",
        run_id="run",
        cycle_id="cycle",
        supervision_id="supervision",
        source_governor=SimpleNamespace(available=True),
        central_scheduler=SimpleNamespace(available=True),
        acquisition_started_at="2026-08-31T23:59:59+00:00",
        acquisition_deadline_at="2026-09-01T00:10:00+00:00",
        work_deadline_at="2026-09-01T00:20:00+00:00",
        refresh_stage=refresh_stage,
        waiter=lambda _seconds: False,
        refresh_interval_seconds=1,
    )
    outcome = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=4,
        now="2026-09-01T00:00:00+00:00",
    )

    assert outcome.status == REFRESH_COMPLETED
    payload = outcome.to_dict()
    assert [
        int(row["source_request_id"])
        for row in payload["source_request_coverage"]
    ] == [42]
''')


def append_green_tests() -> None:
    path = Path("tests/test_v2_9_8b_refresh_coverage_carry.py")
    text = path.read_text()
    text += r'''


def test_completed_refresh_progress_merges_prior_and_current_coverage():
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        _persist_completed_later_cycle_refresh_progress,
    )

    prior = _coverage(51)
    completed = _coverage(52)
    progress = {
        "source_operations_used": 3,
        "reserve_depth": 1,
        "source_request_coverage": [prior],
    }
    progress_by_cycle: dict[str, dict[str, object]] = {}
    updated = _persist_completed_later_cycle_refresh_progress(
        progress_by_cycle,
        progress_key="cycle-2",
        progress=progress,
        refresh_owner=object(),
        completed_source_operations=2,
        completed_source_request_coverage=(completed,),
    )
    assert updated["source_operations_used"] == 5
    assert [
        int(row["source_request_id"])
        for row in updated["source_request_coverage"]
    ] == [51, 52]
    assert progress_by_cycle["cycle-2"] is updated


def test_cooperative_waiting_branch_carries_partial_refresh_coverage_before_yield():
    import inspect
    from printer_v1.operator_cli import authoritative_live_operational_campaign as campaign

    source = inspect.getsource(campaign)
    waiting = source.index("if outcome.status == WAITING_FOR_ELIGIBLE_SUPPLY:")
    returned = source.index("return LaterCycleCandidateSupply(", waiting)
    merge = source.index('progress["source_request_coverage"] = (', waiting)
    assert waiting < merge < returned
    assert "outcome.source_request_coverage" in source[merge:returned]
'''
    path.write_text(text)


def apply_patch() -> None:
    temporal = "src/printer_v1/discovery/pre_lifecycle_temporal_acquisition.py"
    replace_once(
        temporal,
        "    promoted_observation_eligible: tuple[Mapping[str, Any], ...] = ()\n    reserve_depth_before: int = 0\n",
        "    promoted_observation_eligible: tuple[Mapping[str, Any], ...] = ()\n    source_request_coverage: tuple[Mapping[str, Any], ...] = ()\n    reserve_depth_before: int = 0\n",
    )
    replace_once(
        temporal,
        "            \"promoted_observation_eligible_count\": len(\n                self.promoted_observation_eligible\n            ),\n            \"reserve_depth_before\": self.reserve_depth_before,\n",
        "            \"promoted_observation_eligible_count\": len(\n                self.promoted_observation_eligible\n            ),\n            \"source_request_coverage\": [\n                dict(item) for item in self.source_request_coverage\n            ],\n            \"reserve_depth_before\": self.reserve_depth_before,\n",
    )

    owner = "src/printer_v1/operator_cli/pre_lifecycle_persistent_refresh_owner.py"
    replace_once(
        owner,
        "def bounded_interruptible_wait(seconds: float, abort_event: threading.Event | None) -> bool:\n    if seconds <= 0:\n        return bool(abort_event is not None and abort_event.is_set())\n    return bool((abort_event if abort_event is not None else threading.Event()).wait(timeout=seconds))\n\nclass PreLifecycleTemporalRefreshOwner:\n",
        '''def bounded_interruptible_wait(seconds: float, abort_event: threading.Event | None) -> bool:\n    if seconds <= 0:\n        return bool(abort_event is not None and abort_event.is_set())\n    return bool((abort_event if abort_event is not None else threading.Event()).wait(timeout=seconds))\n\n\ndef _refresh_stage_source_request_coverage(\n    stage: Mapping[str, Any],\n) -> tuple[Mapping[str, Any], ...]:\n    \"\"\"Return only exact stage-produced coverage from one refresh quantum.\"\"\"\n    from printer_v1.discovery.permanent_discovery_availability import (\n        collect_stage_source_request_coverage,\n    )\n\n    reports = stage.get(\"stage_reports\") or {}\n    if not isinstance(reports, Mapping):\n        raise PreLifecycleTemporalRefreshError(\n            \"PRE_LIFECYCLE_REFRESH_STAGE_REPORTS_INVALID\"\n        )\n    coverage: list[dict[str, Any]] = []\n    for report in reports.values():\n        if not isinstance(report, Mapping):\n            raise PreLifecycleTemporalRefreshError(\n                \"PRE_LIFECYCLE_REFRESH_STAGE_REPORT_INVALID\"\n            )\n        coverage.extend(collect_stage_source_request_coverage(report))\n    return tuple(dict(item) for item in coverage)\n\n\nclass PreLifecycleTemporalRefreshOwner:\n''',
    )
    replace_once(
        owner,
        "            unavailable=tuple(str(x) for x in stage.get('channels_unavailable',()))\n            for key,expected in (('campaign_id',self.campaign_id),('run_id',self.run_id),('cycle_id',self.cycle_id)):\n",
        "            unavailable=tuple(str(x) for x in stage.get('channels_unavailable',()))\n            coverage=_refresh_stage_source_request_coverage(stage)\n            for key,expected in (('campaign_id',self.campaign_id),('run_id',self.run_id),('cycle_id',self.cycle_id)):\n",
    )
    replace_count(
        owner,
        "channels_skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) if isinstance(x,Mapping)),reserve_depth_before=reserve_depth",
        "channels_skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) if isinstance(x,Mapping)),source_request_coverage=coverage,reserve_depth_before=reserve_depth",
        2,
    )

    campaign = "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"
    replace_once(
        campaign,
        "def _persist_completed_later_cycle_refresh_progress(\n",
        '''def _merge_later_cycle_refresh_source_request_coverage(\n    progress: Mapping[str, Any],\n    completed: Sequence[Mapping[str, Any]] | None,\n) -> list[dict[str, Any]]:\n    \"\"\"Merge exact refresh coverage into the existing cooperative carrier.\"\"\"\n    from printer_v1.discovery.eligible_token_supply import (\n        merge_cumulative_source_request_coverage,\n    )\n\n    return merge_cumulative_source_request_coverage(\n        progress.get(\"source_request_coverage\") or (),\n        completed or (),\n    )\n\n\ndef _persist_completed_later_cycle_refresh_progress(\n''',
    )
    replace_once(
        campaign,
        "    refresh_owner: Any,\n    completed_source_operations: int,\n) -> dict[str, Any]:\n",
        "    refresh_owner: Any,\n    completed_source_operations: int,\n    completed_source_request_coverage: Sequence[Mapping[str, Any]] | None = None,\n) -> dict[str, Any]:\n",
    )
    replace_once(
        campaign,
        "        \"source_operations_used\": prior_operations + completed_operations,\n        # The refresh owner reports the pre-revalidation reserve depth. Preserve\n",
        "        \"source_operations_used\": prior_operations + completed_operations,\n        \"source_request_coverage\": _merge_later_cycle_refresh_source_request_coverage(\n            progress, completed_source_request_coverage\n        ),\n        # The refresh owner reports the pre-revalidation reserve depth. Preserve\n",
    )
    replace_once(
        campaign,
        "                            progress[\"next_governed_request_worst_case_seconds\"] = (\n                                outcome.next_governed_request_worst_case_seconds\n                            )\n",
        "                            progress[\"source_request_coverage\"] = (\n                                _merge_later_cycle_refresh_source_request_coverage(\n                                    progress, outcome.source_request_coverage\n                                )\n                            )\n                            progress[\"next_governed_request_worst_case_seconds\"] = (\n                                outcome.next_governed_request_worst_case_seconds\n                            )\n",
    )
    replace_once(
        campaign,
        "                                completed_source_operations=int(\n                                    outcome.source_operations\n                                ),\n",
        "                                completed_source_operations=int(\n                                    outcome.source_operations\n                                ),\n                                completed_source_request_coverage=(\n                                    outcome.source_request_coverage\n                                ),\n",
    )
    append_green_tests()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"tests", "patch"}:
        raise SystemExit("usage: assistant_refresh_coverage_patch.py tests|patch")
    if sys.argv[1] == "tests":
        write_tests()
    else:
        apply_patch()
