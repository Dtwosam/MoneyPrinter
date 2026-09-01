from __future__ import annotations

from pathlib import Path
import re
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

import pytest


def _coverage(request_id: int, suffix: str = "a") -> dict[str, object]:
    return {
        "source_request_id": request_id,
        "source_name": "dexscreener",
        "request_kind": "fresh_profiles",
        "logical_stage_id": f"campaign|run|cycle|REFRESH|{request_id}",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "transport_identity_keys": [["transport", request_id, suffix]],
    }


def test_temporal_refresh_outcome_carries_exact_stage_coverage():
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
        TemporalRefreshOutcome,
    )

    entry = _coverage(41)
    outcome = TemporalRefreshOutcome(
        status="REFRESH_COMPLETED",
        source_request_coverage=(entry,),
    )
    assert outcome.source_request_coverage == (entry,)
    assert outcome.to_dict()["source_request_coverage"] == [entry]


def test_refresh_owner_extracts_stage_produced_coverage_without_synthesis():
    from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
        _refresh_stage_source_request_coverage,
    )

    entry = _coverage(42)
    stage = {
        "stage_reports": {
            "dex": {"source_request_coverage": [entry]},
            "empty": {"source_requests": 0},
        }
    }
    assert _refresh_stage_source_request_coverage(stage) == (entry,)


def test_refresh_progress_merges_prior_and_completed_coverage_exactly():
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        _merge_later_cycle_refresh_source_request_coverage,
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
    assert [row["source_request_id"] for row in updated["source_request_coverage"]] == [51, 52]
    assert progress_by_cycle["cycle-2"] is updated

    conflict = _coverage(51, "different")
    with pytest.raises(Exception, match="CUMULATIVE_SOURCE_REQUEST_COVERAGE_CONFLICT"):
        _merge_later_cycle_refresh_source_request_coverage(
            progress,
            (conflict,),
        )


def test_cooperative_waiting_branch_merges_refresh_coverage_before_return():
    import inspect
    from printer_v1.operator_cli import authoritative_live_operational_campaign as campaign

    source = inspect.getsource(campaign)
    waiting = source.index("if outcome.status == WAITING_FOR_ELIGIBLE_SUPPLY:")
    returned = source.index("return LaterCycleCandidateSupply(", waiting)
    merge = source.index(
        'progress["source_request_coverage"] = (',
        waiting,
    )
    assert waiting < merge < returned
    assert "outcome.source_request_coverage" in source[merge:returned]
''')


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


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"tests", "patch"}:
        raise SystemExit("usage: assistant_refresh_coverage_patch.py tests|patch")
    if sys.argv[1] == "tests":
        write_tests()
    else:
        apply_patch()
