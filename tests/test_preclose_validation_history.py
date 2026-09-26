"""Yielded pre-close jobs retain each validation occurrence for owner accounting."""
import json

import pytest

from printer_v1.operator_cli.one_command_15m_factory import _prior_preclose_validation_records


def _step(records):
    return {
        "step_kind": "WINDOW_CLOSE_PRE_CLOSE_CRITICAL",
        "step_key": "t1_window_close_pre_close_critical",
        "scheduler_job_id": 27,
        "result_json": json.dumps({"local_validations": records}),
    }


def _records():
    return [
        {
            "scheduler_job_id": 27,
            "step_key": "t1_window_close_pre_close_critical",
            "subject_identity": "t1_window_close_pre_close_critical",
            "validation_kind": kind,
            "validation_ordinal": 27000 + ordinal,
        }
        for ordinal, kind in enumerate(
            ["IMMUTABLE_IDENTITY_VALIDATED", "CADENCE_DUE_VALIDATED", "BUDGET_CAPACITY_VALIDATED"] * 2,
            start=1,
        )
    ]


def test_previous_claims_keep_distinct_occurrences_and_are_not_deduplicated():
    records = _records()
    restored = _prior_preclose_validation_records(_step(records))
    assert restored == records
    assert len(restored) == 6
    assert len({row["validation_ordinal"] for row in restored}) == 6
    assert _prior_preclose_validation_records(_step([])) == []


@pytest.mark.parametrize("field,value", [
    ("scheduler_job_id", 99),
    ("step_key", "other"),
    ("subject_identity", "other"),
    ("validation_ordinal", 27001),
])
def test_foreign_or_duplicate_history_fails_closed(field, value):
    records = _records()
    records[-1][field] = value
    with pytest.raises(ValueError, match="PRE_CLOSE_VALIDATION_HISTORY_INVALID"):
        _prior_preclose_validation_records(_step(records))
