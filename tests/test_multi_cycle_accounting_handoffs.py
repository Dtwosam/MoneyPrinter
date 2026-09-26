"""Selection accounting is observed at the consumed Cycle-2 handoff."""
import pytest

from printer_v1.operator_cli.one_command_15m_factory import _observe_consumed_cycle_selection
from tests.test_v2_9_8b_lane4_multi_cycle_terminal_accounting_bounded_proof import (
    Lane4ProofDB, CAMPAIGN, CAMPAIGN_RUN, CYCLE_1, CYCLE_2,
)


@pytest.fixture
def selected_pair(tmp_path):
    fixture = Lane4ProofDB(tmp_path)
    fixture.admit_cycle(CYCLE_1, 1, 100)
    fixture.admit_cycle(CYCLE_2, 2, 200)
    try:
        yield fixture
    finally:
        fixture.close()


def _observe(fixture, cycle_id, observer):
    _observe_consumed_cycle_selection(
        fixture.connection, campaign_id=CAMPAIGN, campaign_run_id=CAMPAIGN_RUN,
        cycle_id=cycle_id, observer=observer,
    )


def test_consumed_pair_emits_exact_job_and_slots_without_writes(selected_pair):
    records = []
    before = selected_pair.connection.total_changes
    _observe(selected_pair, CYCLE_2, records.append)
    assert selected_pair.connection.total_changes == before
    assert len(records) == 1
    record = records[0]
    assert record["cycle_id"] == CYCLE_2
    assert record["stage_id"].split("|")[2] == CYCLE_2
    assert [slot["slot_ordinal"] for slot in record["slots"]] == [1, 2]
    assert len(record["scheduler_work_identities"]) == 1
    assert record["scheduler_work_identities"][0]["target_identity"] == "lane4-bounded-consumed-attempt"


def test_missing_consumed_pair_never_manufactures_selection_evidence(selected_pair):
    with pytest.raises(ValueError, match="CYCLE2_SELECTION_ACCOUNTING_IDENTITY_MISSING"):
        _observe(selected_pair, CYCLE_1, lambda record: pytest.fail(str(record)))


def test_non_succeeded_selection_job_blocks_before_observation(selected_pair):
    selected_pair.connection.execute(
        "UPDATE printer_scheduler_jobs SET status='FAILED' WHERE job_kind='PRE_ADMISSION_DISCOVERY_SELECTION'"
    )
    with pytest.raises(ValueError, match="CYCLE2_SELECTION_ACCOUNTING_JOB_NOT_SUCCEEDED"):
        _observe(selected_pair, CYCLE_2, lambda record: pytest.fail(str(record)))


def test_generic_transports_keep_measurement_cycle_without_changing_identity():
    from printer_v1.sources.campaign_six_unit_accounting import (
        CampaignActionLocalLedger, CampaignSixUnitOwner,
        reconcile_full_run_owner_to_action_local,
    )
    from printer_v1.sources.measured_transport import canonical_transport_identity_key
    from tests.test_v2_9_8b_e_per_cycle_six_unit_accounting import (
        _transport_evidence, CAMPAIGN_ID, RUN_ID,
    )

    ledger = CampaignActionLocalLedger(campaign_id=CAMPAIGN_ID, run_id=RUN_ID)
    for cycle in (CYCLE_1, CYCLE_2):
        evidence = _transport_evidence(cycle, 1, transport_stage="FRESH_POOL_NOMINATION")
        original = evidence["transport_operations"][0]
        measured = {**original, "cycle_id": cycle}
        assert canonical_transport_identity_key(measured) == canonical_transport_identity_key(original)
        ledger.observe_transport(measured)
        owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN_ID, run_id=RUN_ID, cycle_id=cycle)
        owner.ingest_stage_evidence(evidence)
        sliced = ledger.slice_for_cycle(cycle)
        assert len(sliced.transport_identities) == 1
        assert reconcile_full_run_owner_to_action_local(owner, sliced, required_stage_kinds=())["equal"] is True
        sliced.observe_transport(measured)
        assert reconcile_full_run_owner_to_action_local(owner, sliced, required_stage_kinds=())["equal"] is False
    assert len(ledger.transport_identities) == 2


def test_cycle_provenance_conflict_is_rejected():
    from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger, CampaignSixUnitError
    ledger = CampaignActionLocalLedger(campaign_id=CAMPAIGN, run_id=CAMPAIGN_RUN)
    with pytest.raises(CampaignSixUnitError, match="ACTION_LOCAL_TRANSPORT_CYCLE_CONFLICT"):
        ledger.observe_transport({"stage": f"{CAMPAIGN}|{CAMPAIGN_RUN}|{CYCLE_1}|STAGE|1", "cycle_id": CYCLE_2})
    assert ledger.transport_identities == []
