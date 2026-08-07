from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = (
    ROOT / "scripts" / "v2_9_8b_checkpoint8_controlling_public_composition_proof.py"
)


def _load_harness(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _terminal() -> dict[str, object]:
    return {
        "execution_id": "exec-c8",
        "campaign_id": "campaign-c8",
        "campaign_acceptance_verdict": "CAMPAIGN_PASS",
        "campaign_pass": True,
        "report": {
            "campaign_id": "campaign-c8",
            "run_id": "run-c8",
        },
    }


def _replay() -> dict[str, object]:
    return {
        "status": "REPORT_ONLY_PASS",
        "campaign_id": "campaign-c8",
        "run_id": "run-c8",
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
        "replay_new_source_calls": 0,
        "replay_new_scheduler_calls": 0,
        "replay_database_writes": 0,
    }


def _prepared(harness, tmp_path: Path, *, git_head: str = "a" * 40):
    return harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-execution-entry",
        git_head=git_head,
    )


def test_git_entry_validation_requires_exact_head_and_clean_tracked_tree(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_execution_git_entry")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "c8@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Checkpoint 8"], cwd=repo, check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip()

    assert harness.validate_checkpoint8_git_entry(repo, expected_head=head) == head

    tracked.write_text("dirty\n", encoding="utf-8")
    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CHECKPOINT8_TRACKED_WORKTREE_NOT_CLEAN",
    ):
        harness.validate_checkpoint8_git_entry(repo, expected_head=head)

    subprocess.run(["git", "checkout", "--", "tracked.txt"], cwd=repo, check=True)
    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CHECKPOINT8_GIT_HEAD_MISMATCH",
    ):
        harness.validate_checkpoint8_git_entry(repo, expected_head="f" * 40)


def test_public_sequence_claims_sentinel_before_exact_campaign_and_replay_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _load_harness("checkpoint8_execution_sequence_order")
    prepared = _prepared(harness, tmp_path)
    events: list[str] = []
    run_kwargs: list[dict[str, object]] = []
    replay_kwargs: list[dict[str, object]] = []

    original_claim = harness.claim_controlling_attempt_sentinel

    def claim(*args, **kwargs):
        events.append("sentinel")
        return original_claim(*args, **kwargs)

    def run_campaign(**kwargs):
        events.append("campaign")
        run_kwargs.append(dict(kwargs))
        return _terminal()

    def replay(**kwargs):
        events.append("replay")
        replay_kwargs.append(dict(kwargs))
        return _replay()

    monkeypatch.setattr(harness, "claim_controlling_attempt_sentinel", claim)
    monkeypatch.setattr(harness, "run_operational_campaign", run_campaign, raising=False)
    monkeypatch.setattr(harness, "report_only", replay, raising=False)

    result = harness.execute_checkpoint8_public_sequence(
        prepared,
        git_head="a" * 40,
    )

    assert events == ["sentinel", "campaign", "replay"]
    assert run_kwargs == [
        {
            "operator_approved": True,
            "disposable_proof": prepared.runtime,
        }
    ]
    assert replay_kwargs == [
        {
            "campaign_id": "campaign-c8",
            "run_id": "run-c8",
            "db_path": Path(prepared.runtime.plan.resolved_db_path).resolve(),
            "artifact_root": Path(
                prepared.runtime.plan.resolved_artifact_root
            ).resolve(),
        }
    ]
    assert Path(result.sentinel_path).is_file()
    assert result.terminal == _terminal()
    assert result.replay == _replay()
    assert result.network_attempt_count == 0


def test_second_public_sequence_is_blocked_before_second_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _load_harness("checkpoint8_execution_one_shot")
    prepared = _prepared(harness, tmp_path)
    run_count = 0

    def run_campaign(**kwargs):
        nonlocal run_count
        del kwargs
        run_count += 1
        return _terminal()

    monkeypatch.setattr(harness, "run_operational_campaign", run_campaign, raising=False)
    monkeypatch.setattr(harness, "report_only", lambda **kwargs: _replay(), raising=False)

    harness.execute_checkpoint8_public_sequence(prepared, git_head="a" * 40)
    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CONTROLLING_ATTEMPT_ALREADY_CONSUMED",
    ):
        harness.execute_checkpoint8_public_sequence(prepared, git_head="a" * 40)
    assert run_count == 1


def test_network_attempt_consumes_attempt_and_blocks_second_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _load_harness("checkpoint8_execution_network_failure")
    prepared = _prepared(harness, tmp_path)
    run_count = 0

    def network_attempt(**kwargs):
        nonlocal run_count
        del kwargs
        run_count += 1
        socket.create_connection(("203.0.113.1", 443), timeout=0.01)
        raise AssertionError("network tripwire did not fire")

    monkeypatch.setattr(harness, "run_operational_campaign", network_attempt, raising=False)
    monkeypatch.setattr(harness, "report_only", lambda **kwargs: _replay(), raising=False)

    with pytest.raises(
        harness.Checkpoint8NetworkTripwireError,
        match="CHECKPOINT8_EXTERNAL_NETWORK_ATTEMPT_FORBIDDEN",
    ):
        harness.execute_checkpoint8_public_sequence(prepared, git_head="a" * 40)

    assert (tmp_path / "checkpoint8-controlling-attempt.json").is_file()

    monkeypatch.setattr(harness, "run_operational_campaign", lambda **kwargs: _terminal(), raising=False)
    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CONTROLLING_ATTEMPT_ALREADY_CONSUMED",
    ):
        harness.execute_checkpoint8_public_sequence(prepared, git_head="a" * 40)
    assert run_count == 1


def test_fixture_operation_counter_counts_actual_fixture_calls(tmp_path: Path) -> None:
    harness = _load_harness("checkpoint8_execution_fixture_counter")
    prepared = _prepared(harness, tmp_path)
    materialized = harness.proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    assert harness.checkpoint8_fixture_transport_operation_count(prepared.runtime) == 0
    materialized.top_level_transports["pump_transport"].json_rpc({"method": "fixture"})
    assert harness.checkpoint8_fixture_transport_operation_count(prepared.runtime) == 1


def test_freeze_rejects_zero_fixture_operations(tmp_path: Path) -> None:
    harness = _load_harness("checkpoint8_execution_freeze_zero_fixture")
    prepared = _prepared(harness, tmp_path)
    sentinel = harness.claim_controlling_attempt_sentinel(
        tmp_path,
        proof_id=prepared.runtime.plan.proof_id,
        git_head="a" * 40,
    )
    sequence = SimpleNamespace(
        sentinel_path=sentinel,
        terminal=_terminal(),
        replay=_replay(),
        network_attempt_count=0,
        network_attempts=(),
    )
    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CHECKPOINT8_FIXTURE_TRANSPORT_OPERATION_COUNT_REQUIRED",
    ):
        harness.freeze_checkpoint8_controlling_proof_summary(prepared, sequence)


def test_frozen_summary_captures_post_run_safety_and_zero_replay_work(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_execution_freeze_summary")
    prepared = _prepared(harness, tmp_path)
    materialized = harness.proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    materialized.top_level_transports["pump_transport"].json_rpc({"method": "fixture"})
    sentinel = harness.claim_controlling_attempt_sentinel(
        tmp_path,
        proof_id=prepared.runtime.plan.proof_id,
        git_head="a" * 40,
    )
    sequence = SimpleNamespace(
        sentinel_path=sentinel,
        terminal=_terminal(),
        replay=_replay(),
        network_attempt_count=0,
        network_attempts=(),
    )

    summary_path = harness.freeze_checkpoint8_controlling_proof_summary(
        prepared,
        sequence,
    )
    assert Path(summary_path).is_file()
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert payload["proof_id"] == prepared.runtime.plan.proof_id
    assert payload["git_head"] == "a" * 40
    assert payload["campaign_id"] == "campaign-c8"
    assert payload["run_id"] == "run-c8"
    assert payload["campaign_acceptance_verdict"] == "CAMPAIGN_PASS"
    assert payload["network_attempt_count"] == 0
    assert payload["fixture_transport_operation_count"] == 1
    assert payload["replay_zero_work"] is True
    assert payload["post_run_evidence"]["integrity_check"] == "ok"
    assert payload["post_run_evidence"]["foreign_key_violations"] == 0
    assert all(
        value == 0
        for value in payload["post_run_evidence"]["protected_capability_deltas"].values()
    )
    assert all(
        value == 0
        for value in payload["post_run_evidence"]["longer_window_counts"].values()
    )
    assert len(payload["frozen_evidence_sha256"]) == 64


def test_harness_ast_has_exactly_one_public_campaign_call_and_one_replay_call() -> None:
    source = HARNESS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert called.count("run_operational_campaign") == 1
    assert called.count("report_only") == 1


def test_main_is_wired_to_the_single_entry_sequence() -> None:
    harness = _load_harness("checkpoint8_execution_main_wiring")
    source = HARNESS_PATH.read_text(encoding="utf-8")
    assert "CHECKPOINT8_CONTROLLING_PROOF_ENTRY_NOT_YET_WIRED" not in source
    tree = ast.parse(source)
    main_node = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "main"
    )
    called = {
        node.func.id
        for node in ast.walk(main_node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {
        "validate_checkpoint8_git_entry",
        "prepare_checkpoint8_controlling_entry",
        "execute_checkpoint8_public_sequence",
        "freeze_checkpoint8_controlling_proof_summary",
    }.issubset(called)
    assert callable(harness.main)


def test_execution_harness_does_not_call_independent_inspector() -> None:
    source = HARNESS_PATH.read_text(encoding="utf-8")
    assert "v2_9_8b_checkpoint8_independent_inspection" not in source
    assert "independent_inspection" not in source
