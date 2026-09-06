"""Returned campaign terminals must drive wrapper-bound child exit truth."""

from __future__ import annotations

import pytest

from printer_v1.operator_cli import operational_memory_factory_command as public
from printer_v1.operator_cli import window_15m_child_terminal as child_terminal


def test_wrapper_bound_exit_code_uses_explicit_campaign_pass() -> None:
    assert public._wrapper_bound_campaign_exit_code({"campaign_pass": True}) == 0
    assert public._wrapper_bound_campaign_exit_code({"campaign_pass": False}) == 1


@pytest.mark.parametrize("payload", ({}, {"campaign_pass": None}, {"campaign_pass": 1}))
def test_wrapper_bound_exit_code_fails_closed_without_boolean_campaign_pass(
    payload,
) -> None:
    with pytest.raises(
        public.OperationalMemoryFactoryError,
        match="WRAPPER_BOUND_CAMPAIGN_PASS_MISSING_OR_INVALID",
    ):
        public._wrapper_bound_campaign_exit_code(payload)


def test_main_emits_blocked_child_terminal_for_returned_pre_lifecycle_block(
    monkeypatch,
) -> None:
    for name in public.GIT_PROVENANCE_MANIFEST_ENV_VARS:
        monkeypatch.setenv(name, "fixture-binding")

    binding = object()
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        child_terminal,
        "resolve_child_terminal_binding",
        lambda _environment: binding,
    )
    monkeypatch.setattr(
        child_terminal,
        "write_child_terminal_envelope",
        lambda **kwargs: captured.update(kwargs) or {},
    )
    monkeypatch.setattr(
        public,
        "_resolve_git_provenance_authorization",
        lambda _mode: object(),
    )
    monkeypatch.setattr(
        public,
        "run_four_token_standard_four_hour_campaign",
        lambda **_kwargs: {
            "status": "OPERATIONAL_CAMPAIGN_PRE_LIFECYCLE_TERMINAL",
            "campaign_id": "campaign-returned-block",
            "run_id": "campaign-returned-block-run",
            "execution_id": "returned-block-execution",
            "first_terminal_cause": "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH",
            "lifecycle_started": False,
            "campaign_acceptance_verdict": "HONEST_BLOCKED",
            "campaign_pass": False,
        },
    )

    exit_code = public.main(
        [public.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE, "--operator-approved"]
    )

    assert exit_code == 1
    assert captured["binding"] is binding
    assert captured["exit_code"] == 1
    assert captured["success"] is False
    assert captured["mode"] == public.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE
    assert captured["source"]["campaign_pass"] is False
