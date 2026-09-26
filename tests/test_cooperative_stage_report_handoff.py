"""Prior stage reports and measured coverage remain independent across yields."""
from contextlib import closing
import sqlite3

import pytest

from printer_v1.discovery.eligible_token_supply import run_persistent_eligible_token_supply
from printer_v1.discovery.permanent_discovery_availability import StageBudget
from printer_v1.sources.measured_transport import canonical_transport_identity_key
from tests.test_v2_9_8b_later_cycle_mint_market_replay_repair import (
    _db, _record_request, _identity, _scope,
    NOW, EXECUTION_ID, CAMPAIGN_ID, RUN_ID, CYCLE_ID, MINT,
)


@pytest.mark.parametrize("reported,covered,expected", [
    (True, True, "MEASURED"),
    (False, True, "BLOCKED"),
    (True, False, "BLOCKED"),
    ("foreign", True, "BLOCKED"),
])
def test_resumed_quantum_requires_both_prior_reports_and_coverage(
    tmp_path, reported, covered, expected,
):
    scope = _scope()
    identity = _identity(MINT)
    with closing(_db(tmp_path)) as connection:
        request_id = _record_request(
            connection, request_key=f"{scope.request_key_root}-mint-batch-r1",
            response_status="COMPLETE", identity=identity,
        )
    coverage = {
        "source_request_id": request_id,
        "source_name": "dexscreener",
        "request_kind": "candidate_market_batch",
        "logical_stage_id": f"{CAMPAIGN_ID}|{RUN_ID}|{CYCLE_ID}|MINT_MARKET_BATCH|1",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [list(canonical_transport_identity_key(identity))],
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("This resumed zero-work quantum must not call a transport")

    result = run_persistent_eligible_token_supply(
        tmp_path / "replay.sqlite3", cycle_seed="stage-report-handoff",
        migration_transport=forbidden, now=NOW,
        discovery_request_key_prefix=scope.request_key_root,
        front_door_request_key_prefix=scope.request_key_root,
        execution_id=EXECUTION_ID, campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID, cycle_id=CYCLE_ID, campaign_source_request_scope=scope,
        permanent_availability=True, cooperative_resume=True,
        cooperative_quantum=True, cooperative_phase="AUXILIARY_LIQUIDITY_BACKUP",
        cooperative_stage_budget=StageBudget.permanent_discovery_default(),
        prior_source_request_coverage=[coverage] if covered else [],
        prior_stage_reported_request_ids=(
            [request_id + 100] if reported == "foreign" else [request_id] if reported else []
        ),
        persist_terminal_certificate=False,
    )
    measurement = result.diagnostics["freeze_ready_measurement"]
    assert measurement["status"] == expected, measurement
    assert measurement["freeze_ready_depth"] == 0  # No eligible tokens were seeded.
    with closing(sqlite3.connect(
        f"file:{tmp_path / 'replay.sqlite3'}?mode=ro", uri=True,
    )) as connection:
        assert connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0] == 1
