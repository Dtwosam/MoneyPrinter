"""Bounded Lane-4 proof: two-cycle terminal accounting/reporting.

Disposable migrated databases and filesystem artifacts only. Tests induce
underlying production rows and let canonical owners derive outcomes. They do
not run a campaign, provider, Scheduler runtime, or authoritative database.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Mapping

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import report_path_identity
from printer_v1.operator_cli.campaign_full_run_accounting import (
    FullRunAccountingError,
    OperationalLifecycleOwnershipContext,
    derive_cycle_terminal_accounting_result,
    derive_two_cycle_campaign_terminal_accounting,
    finalize_full_run_ownership_and_report,
)
from printer_v1.operator_cli.campaign_ownership import (
    bind_authoritative_run_id,
    campaign_scheduler_work_id,
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_window,
    project_campaign_scheduler_job,
    register_campaign_window_close,
    transition_state,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL,
    FourTokenFactoryAdapterError,
    derive_peer_cycle_stop_effect,
    resolve_peer_stop_origin_cycle_id,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    cycle_scoped_factory_step_ids,
)
from printer_v1.operator_cli.operational_memory_factory_command import report_only
from printer_v1.operator_cli.unified_terminal_closure import (
    TerminalClosureError,
    build_campaign_terminal_report,
    build_campaign_terminal_summary,
    write_campaign_terminal_report,
    write_campaign_terminal_summary,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignCycleAccountingRegistry,
    CampaignSixUnitError,
    CampaignSixUnitOwner,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import LocalValidationIdentity


NOW = "2026-08-23T12:00:00+00:00"
CAMPAIGN = "campaign-lane4-proof"
CAMPAIGN_RUN = "campaign-run-lane4-proof"
CONFIGURATION = "configuration-lane4-proof"
FACTORY_RUN = "factory-run-lane4-proof"
EXECUTION = "execution-lane4-proof"
REPORT_ID = "report-lane4-proof"
CYCLE_1 = "cycle-1-lane4-proof"
CYCLE_2 = "cycle-2-lane4-proof"

_EMPTY_FAULTS = json.dumps({"primary": None, "secondary": []})
_EMPTY_OBJECT = json.dumps({})


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


class Lane4ProofDB:
    """One disposable two-cycle campaign graph on a migrated SQLite file."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path
        self.db_path = tmp_path / "lane4-proof.sqlite3"
        self.execution_root = tmp_path / EXECUTION
        self.report_dir = self.execution_root / "reports"
        self.report_dir.mkdir(parents=True)
        self.summary_path = self.execution_root / "terminal-summary.json"
        apply_migrations(self.db_path)
        configuration = {
            "slots": 2,
            "execution_id": EXECUTION,
            "campaign_id": CAMPAIGN,
            "configuration_id": CONFIGURATION,
            "run_id": CAMPAIGN_RUN,
            "policy_version": "v2-9.8b",
            "db_target_identity": "isolated-lane4-proof",
            "operator_approved": True,
            "report_directory_identity": report_path_identity(self.report_dir),
        }
        create_campaign(
            self.db_path,
            campaign_id=CAMPAIGN,
            configuration_id=CONFIGURATION,
            configuration=configuration,
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-lane4-proof",
            proof_source_db_identity="source-lane4-proof",
            policy_version="v2-9.8b",
        )
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._ids = 0
        self._seed_factory_and_run()

    def close(self) -> None:
        self.connection.close()

    def _next_id(self) -> int:
        self._ids += 1
        return self._ids

    def _seed_factory_and_run(self) -> None:
        config = json.dumps({"standard_four_hour_campaign": True}, separators=(",", ":"))
        self.connection.execute(
            """INSERT INTO printer_memory_factory_runs(
                   run_id,run_status,window_kind,db_mode,config_hash,config_json,
                   started_at
               ) VALUES (?,'COMPLETED','WINDOW_15M','PROOF_ONLY',?,?,?)""",
            (FACTORY_RUN, "c" * 64, config, NOW),
        )
        create_campaign_run(
            self.connection,
            campaign_id=CAMPAIGN,
            run_id=CAMPAIGN_RUN,
            run_ordinal=1,
            now=NOW,
        )
        bind_authoritative_run_id(
            self.connection,
            campaign_run_id=CAMPAIGN_RUN,
            factory_run_id=FACTORY_RUN,
            now=NOW,
        )
        transition_state(
            self.connection,
            record_kind="campaign",
            identity=CAMPAIGN,
            expected_state="DRAFT",
            new_state="PREFLIGHT",
            now=NOW,
        )
        transition_state(
            self.connection,
            record_kind="campaign",
            identity=CAMPAIGN,
            expected_state="PREFLIGHT",
            new_state="RUNNING",
            now=NOW,
        )
        transition_state(
            self.connection,
            record_kind="run",
            identity=CAMPAIGN_RUN,
            expected_state="DRAFT",
            new_state="PREFLIGHT",
            now=NOW,
        )
        transition_state(
            self.connection,
            record_kind="run",
            identity=CAMPAIGN_RUN,
            expected_state="PREFLIGHT",
            new_state="RUNNING",
            now=NOW,
        )
        self.connection.commit()

    def context(self, cycle_id: str) -> OperationalLifecycleOwnershipContext:
        return OperationalLifecycleOwnershipContext(
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            cycle_id=cycle_id,
            configuration_id=CONFIGURATION,
            factory_run_id=FACTORY_RUN,
        )

    def derive_cycle(self, cycle_id: str) -> dict:
        return derive_cycle_terminal_accounting_result(
            self.connection,
            context=self.context(cycle_id),
        )

    def derive_campaign(self) -> dict:
        return derive_two_cycle_campaign_terminal_accounting(
            self.connection,
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            configuration_id=CONFIGURATION,
            factory_run_id=FACTORY_RUN,
        )

    def admit_cycle(self, cycle_id: str, ordinal: int, token_base: int) -> list[dict]:
        slots = []
        for ordinal_slot in (1, 2):
            token_id = self._next_id()
            pair_id = self._next_id()
            queue_id = self._next_id()
            mint = f"mint-{cycle_id}-{ordinal_slot}-{token_id}"
            pair_address = f"pair-{cycle_id}-{ordinal_slot}-{pair_id}"
            self.connection.execute(
                "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                (token_id, mint),
            )
            self.connection.execute(
                "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
                (pair_id, token_id, pair_address),
            )
            self.connection.execute(
                """INSERT INTO printer_tracking_queue(
                       id,token_id,pair_id,tracking_lane,tracking_action,
                       queue_status,source_status,data_quality_label
                   ) VALUES (?,?,?,'TRACK_NORMAL','COOLDOWN','COOLDOWN',
                             'COMPLETE','CLEAN_DATA')""",
                (queue_id, token_id, pair_id),
            )
            slots.append(
                {
                    "token_slot_id": f"{cycle_id}-slot-{ordinal_slot}",
                    "slot_ordinal": ordinal_slot,
                    "token_identity": f"token-{token_id}",
                    "token_row_id": token_id,
                    "mint_identity": mint,
                    "pair_identity": pair_address,
                    "pair_row_id": pair_id,
                    "lifecycle_identity": f"lifecycle-{cycle_id}-{ordinal_slot}",
                    "tracking_queue_id": queue_id,
                    "token_base": token_base,
                }
            )
        self.connection.commit()
        create_cycle_with_two_slots(
            self.connection,
            campaign_id=CAMPAIGN,
            run_id=CAMPAIGN_RUN,
            cycle_id=cycle_id,
            cycle_ordinal=ordinal,
            now=NOW,
            slots=slots,
        )
        return slots

    def _memory_window(
        self,
        *,
        token_id: int,
        pair_id: int,
        window_kind: str,
        clean: bool,
    ) -> int:
        memory_id = self._next_id()
        if clean:
            status, label, dnt = "CLEAN_MEMORY", "CLEAN_DATA", 0
        else:
            status, label, dnt = "DIRTY_MEMORY", "MISSING_CRITICAL_DATA", 1
        self.connection.execute(
            """INSERT INTO printer_memory_windows(
                   id,token_id,pair_id,window_kind,opened_at,memory_status,
                   data_quality_label,do_not_train
               ) VALUES (?,?,?,?,?,?,?,?)""",
            (memory_id, token_id, pair_id, window_kind, NOW, status, label, dnt),
        )
        return memory_id

    def _snapshot(self, token_id: int, pair_id: int) -> int:
        snapshot_id = self._next_id()
        self.connection.execute(
            """INSERT INTO printer_token_snapshots(
                   id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                   price_usd,liquidity_usd,source_status,data_quality_label
               ) VALUES (?,?,?,?,'TRACK_NORMAL','FACTORY',1.0,1000.0,
                         'COMPLETE','CLEAN_DATA')""",
            (snapshot_id, token_id, pair_id, NOW),
        )
        return snapshot_id

    def _step(
        self,
        *,
        cycle_id: str,
        token_id: int,
        pair_id: int,
        mint: str,
        pair_address: str,
        step_kind: str,
        memory_window_id: int | None,
        snapshot_id: int | None,
    ) -> int:
        job_id = self._next_id()
        step_key = f"{cycle_id}:{token_id}:{step_kind}:{job_id}"
        self.connection.execute(
            """INSERT INTO printer_scheduler_jobs(
                   id,job_name,job_kind,status,scheduled_for,finished_at
               ) VALUES (?,?,?,'SUCCEEDED',?,?)""",
            (job_id, step_key, step_kind, NOW, NOW),
        )
        self.connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                   run_id,step_key,step_kind,step_status,token_id,pair_id,
                   token_mint,pair_address,tracking_lane,scheduler_job_id,
                   snapshot_id,memory_window_id
               ) VALUES (?,?,?,'SUCCEEDED',?,?,?,?,'TRACK_NORMAL',?,?,?)""",
            (
                FACTORY_RUN,
                step_key,
                step_kind,
                token_id,
                pair_id,
                mint,
                pair_address,
                job_id,
                snapshot_id,
                memory_window_id,
            ),
        )
        return job_id

    def _own_job(
        self,
        *,
        cycle_id: str,
        slot_id: str,
        window_id: str,
        job_id: int,
        stage_id: str,
    ) -> None:
        project_campaign_scheduler_job(
            self.connection,
            scheduler_work_id=campaign_scheduler_work_id(CAMPAIGN, job_id),
            campaign_id=CAMPAIGN,
            run_id=CAMPAIGN_RUN,
            cycle_id=cycle_id,
            token_slot_id=slot_id,
            window_id=window_id,
            factory_run_id=FACTORY_RUN,
            work_intent=f"lifecycle:{stage_id}",
            deadline_at=NOW,
            scheduler_job_id=job_id,
            stage_id=stage_id,
            target_category="CAMPAIGN_WINDOW",
            target_identity=window_id,
            now=NOW,
        )

    def seed_complete_cycle(
        self,
        cycle_id: str,
        ordinal: int,
        *,
        clean: bool,
        token_local_failure_slot: int | None = None,
        terminal_state: str = "TERMINAL_COMPLETED",
        terminal_cause: str = "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
    ) -> list[dict]:
        slots = self.admit_cycle(cycle_id, ordinal, token_base=ordinal * 100)
        for slot in slots:
            token_id = int(slot["token_row_id"])
            pair_id = int(slot["pair_row_id"])
            slot_id = str(slot["token_slot_id"])
            mint = str(slot["mint_identity"])
            pair_address = str(slot["pair_identity"])
            memory_15m = self._memory_window(
                token_id=token_id,
                pair_id=pair_id,
                window_kind="WINDOW_15M",
                clean=clean,
            )
            memory_1h = self._memory_window(
                token_id=token_id,
                pair_id=pair_id,
                window_kind="WINDOW_1H",
                clean=clean,
            )
            close_job = None
            for index in range(8):
                snapshot_id = self._snapshot(token_id, pair_id)
                job_id = self._step(
                    cycle_id=cycle_id,
                    token_id=token_id,
                    pair_id=pair_id,
                    mint=mint,
                    pair_address=pair_address,
                    step_kind="SNAPSHOT",
                    memory_window_id=None,
                    snapshot_id=snapshot_id,
                )
                slot.setdefault("jobs_15m", []).append(job_id)
            snapshot_id = self._snapshot(token_id, pair_id)
            close_job = self._step(
                cycle_id=cycle_id,
                token_id=token_id,
                pair_id=pair_id,
                mint=mint,
                pair_address=pair_address,
                step_kind="WINDOW_CLOSE",
                memory_window_id=memory_15m,
                snapshot_id=snapshot_id,
            )
            slot["jobs_15m"].append(close_job)
            close_step_id = int(
                self.connection.execute(
                    "SELECT id FROM printer_memory_factory_run_steps "
                    "WHERE scheduler_job_id=?",
                    (close_job,),
                ).fetchone()[0]
            )
            window_15m = f"{cycle_id}:window-15m:{slot_id}"
            register_campaign_window_close(
                self.connection,
                campaign_id=CAMPAIGN,
                run_id=CAMPAIGN_RUN,
                cycle_id=cycle_id,
                factory_run_id=FACTORY_RUN,
                token_slot_id=slot_id,
                window_id=window_15m,
                close_step_id=close_step_id,
                memory_window_row_id=memory_15m,
                root_15m_lifecycle_identity=str(slot["lifecycle_identity"]),
                checkpoint_cutoff=NOW,
                terminal_window_state="CLEAN_PROMOTED" if clean else "DIRTY",
                terminal_cause="FIXTURE_15M_CLOSED",
                now=NOW,
            )
            continuation_jobs = []
            for index in range(12):
                snapshot_id = self._snapshot(token_id, pair_id)
                job_id = self._step(
                    cycle_id=cycle_id,
                    token_id=token_id,
                    pair_id=pair_id,
                    mint=mint,
                    pair_address=pair_address,
                    step_kind="CONTINUATION_SNAPSHOT",
                    memory_window_id=None,
                    snapshot_id=snapshot_id,
                )
                continuation_jobs.append(job_id)
            snapshot_id = self._snapshot(token_id, pair_id)
            continuation_close = self._step(
                cycle_id=cycle_id,
                token_id=token_id,
                pair_id=pair_id,
                mint=mint,
                pair_address=pair_address,
                step_kind="CONTINUATION_CLOSE",
                memory_window_id=memory_1h,
                snapshot_id=snapshot_id,
            )
            continuation_jobs.append(continuation_close)
            window_1h = f"{cycle_id}:window-1h:{slot_id}"
            persist_window(
                self.connection,
                window_id=window_1h,
                campaign_id=CAMPAIGN,
                run_id=CAMPAIGN_RUN,
                cycle_id=cycle_id,
                token_slot_id=slot_id,
                token_row_id=token_id,
                pair_row_id=pair_id,
                window_kind="WINDOW_1H",
                root_15m_lifecycle_identity=str(slot["lifecycle_identity"]),
                checkpoint_cutoff=NOW,
                predecessor_window_id=window_15m,
                memory_window_row_id=memory_1h,
                now=NOW,
            )
            transition_state(
                self.connection,
                record_kind="window",
                identity=window_1h,
                expected_state="PLANNED",
                new_state="CLEAN_PROMOTED" if clean else "DIRTY",
                terminal_cause="FIXTURE_1H_CLOSED",
                now=NOW,
            )
            stage_15m = (
                "WINDOW_15M_SLOT_1"
                if int(slot["slot_ordinal"]) == 1
                else "WINDOW_15M_SLOT_2"
            )
            for job_id in slot["jobs_15m"]:
                self._own_job(
                    cycle_id=cycle_id,
                    slot_id=slot_id,
                    window_id=window_15m,
                    job_id=job_id,
                    stage_id=stage_15m,
                )
            for job_id in continuation_jobs:
                self._own_job(
                    cycle_id=cycle_id,
                    slot_id=slot_id,
                    window_id=window_1h,
                    job_id=job_id,
                    stage_id="WINDOW_1H",
                )
            slot_terminal = "COOLDOWN"
            slot_cause = "OWNED_TERMINAL_WINDOW_COOLDOWN"
            if token_local_failure_slot == int(slot["slot_ordinal"]):
                slot_terminal = "FAILED"
                slot_cause = "TOKEN_LOCAL_INTEGRITY_FAILURE"
            transition_state(
                self.connection,
                record_kind="token_slot",
                identity=slot_id,
                expected_state="SELECTED",
                new_state=slot_terminal,
                terminal_cause=slot_cause,
                now=NOW,
            )
        self._seed_ineligible_progression(cycle_id, slots)
        transition_state(
            self.connection,
            record_kind="cycle",
            identity=cycle_id,
            expected_state="PLANNED",
            new_state=terminal_state,
            terminal_cause=terminal_cause,
            now=NOW,
        )
        self.connection.commit()
        return slots

    def seed_failed_cycle(self, cycle_id: str, ordinal: int, cause: str) -> None:
        self.admit_cycle(cycle_id, ordinal, token_base=ordinal * 100)
        transition_state(
            self.connection,
            record_kind="cycle",
            identity=cycle_id,
            expected_state="PLANNED",
            new_state="TERMINAL_FAILED",
            terminal_cause=cause,
            now=NOW,
        )
        self.connection.commit()

    def seed_active_cycle(self, cycle_id: str, ordinal: int) -> None:
        self.admit_cycle(cycle_id, ordinal, token_base=ordinal * 100)
        self.connection.commit()

    def seed_ambiguous_cycle(self, cycle_id: str, ordinal: int) -> None:
        self.connection.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                   cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                   created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?)""",
            (cycle_id, CAMPAIGN, CAMPAIGN_RUN, ordinal, "PLANNED", NOW, NOW),
        )
        self.connection.commit()

    def _seed_ineligible_progression(
        self,
        cycle_id: str,
        slots: list[dict],
        *,
        reason: str = "NO_WINDOW_1H_ELIGIBLE_CONTINUATION",
    ) -> None:
        attempt_id = f"progression-{cycle_id}"
        self.connection.execute(
            """INSERT INTO printer_memory_factory_standard_4h_progression_attempts(
                   progression_attempt_id,campaign_id,configuration_id,
                   campaign_run_id,factory_run_id,cycle_id,policy_version,
                   attempt_state,authority_evidence_json,first_terminal_cause,
                   fault_details_json,eligibility_completed_at,handoff_committed_at,
                   terminal_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                attempt_id,
                CAMPAIGN,
                CONFIGURATION,
                CAMPAIGN_RUN,
                FACTORY_RUN,
                cycle_id,
                "STANDARD_4H_PROGRESSION_V1",
                "HANDOFF_COMMITTED",
                _EMPTY_OBJECT,
                None,
                _EMPTY_FAULTS,
                NOW,
                NOW,
                NOW,
                NOW,
                NOW,
            ),
        )
        for slot in slots:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_standard_4h_progression_tokens(
                       progression_token_id,progression_attempt_id,campaign_id,
                       campaign_run_id,factory_run_id,cycle_id,slot_ordinal,
                       token_slot_id,token_identity,token_row_id,mint_identity,
                       pair_identity,pair_row_id,lifecycle_identity,
                       tracking_queue_id,tracking_lane,predecessor_window_1h_id,
                       predecessor_memory_window_id,token_disposition,
                       disposition_reasons_json,eligibility_evidence_json,
                       successor_window_4h_id,first_terminal_cause,
                       fault_details_json,evaluated_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"progression-token-{slot['token_slot_id']}",
                    attempt_id,
                    CAMPAIGN,
                    CAMPAIGN_RUN,
                    FACTORY_RUN,
                    cycle_id,
                    int(slot["slot_ordinal"]),
                    slot["token_slot_id"],
                    slot["token_identity"],
                    int(slot["token_row_id"]),
                    slot["mint_identity"],
                    slot["pair_identity"],
                    int(slot["pair_row_id"]),
                    slot["lifecycle_identity"],
                    int(slot["tracking_queue_id"]),
                    "TRACK_NORMAL",
                    None,
                    None,
                    "INELIGIBLE",
                    json.dumps([reason]),
                    _EMPTY_OBJECT,
                    None,
                    None,
                    _EMPTY_FAULTS,
                    NOW,
                    NOW,
                    NOW,
                ),
            )

    def set_campaign_shared_supervision(self, cause: str) -> None:
        self.connection.execute(
            """INSERT INTO printer_memory_factory_campaign_supervision(
                   supervision_id,campaign_id,configuration_id,run_id,owner_id,
                   supervision_state,terminal_status,first_terminal_cause,
                   heartbeat_at,lease_expires_at,lease_lock_path,
                   cleanup_completed_at,lease_released_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "supervision-lane4-proof",
                CAMPAIGN,
                CONFIGURATION,
                CAMPAIGN_RUN,
                "owner-lane4-proof",
                "TERMINAL",
                "FAILED",
                cause,
                NOW,
                NOW,
                str(self.root / "supervision.lease.lock"),
                NOW,
                NOW,
                NOW,
                NOW,
            ),
        )
        self.connection.commit()


@pytest.fixture
def proof_db(tmp_path: Path):
    db = Lane4ProofDB(tmp_path)
    try:
        yield db
    finally:
        db.close()


def test_both_cycles_success_is_derived_from_exact_owned_graphs(proof_db: Lane4ProofDB) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)

    cycle_one = proof_db.derive_cycle(CYCLE_1)
    cycle_two = proof_db.derive_cycle(CYCLE_2)
    aggregate = proof_db.derive_campaign()
    cycle_one_steps = cycle_scoped_factory_step_ids(
        proof_db.connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        cycle_id=CYCLE_1,
    )
    cycle_two_steps = cycle_scoped_factory_step_ids(
        proof_db.connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        cycle_id=CYCLE_2,
    )

    assert cycle_one["execution_outcome"] == "TERMINAL_SUCCESS", cycle_one.get(
        "incomplete_reasons"
    )
    assert cycle_two["execution_outcome"] == "TERMINAL_SUCCESS", cycle_two.get(
        "incomplete_reasons"
    )
    assert cycle_one["cycle_id"] == CYCLE_1
    assert cycle_two["cycle_id"] == CYCLE_2
    assert aggregate["execution_outcome"] == "TERMINAL_SUCCESS"
    assert aggregate["accounting_complete"] is True
    assert set(cycle_one_steps).isdisjoint(cycle_two_steps)
    assert cycle_one_steps
    assert cycle_two_steps


def test_cycle_two_failure_does_not_rewrite_cycle_one_success(proof_db: Lane4ProofDB) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_failed_cycle(CYCLE_2, 2, cause="CYCLE_TWO_LOCAL_FAILURE")

    cycle_one = proof_db.derive_cycle(CYCLE_1)
    cycle_two = proof_db.derive_cycle(CYCLE_2)
    aggregate = proof_db.derive_campaign()

    assert cycle_one["execution_outcome"] == "TERMINAL_SUCCESS"
    assert cycle_two["execution_outcome"] == "CYCLE_FAILED"
    assert cycle_two["primary_fault"]["cause"] == "CYCLE_TWO_LOCAL_FAILURE"
    assert cycle_one["primary_fault"] is None
    assert aggregate["execution_outcome"] == "CYCLE_FAILED"
    assert aggregate["campaign_pass_eligible"] is False


def test_failed_cycle_one_leaves_already_successful_cycle_two_untouched(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    proof_db.seed_failed_cycle(CYCLE_1, 1, cause="CYCLE_ONE_LOCAL_FAILURE")
    before = proof_db.connection.execute(
        "SELECT cycle_state,first_terminal_cause FROM "
        "printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (CYCLE_2,),
    ).fetchone()

    with pytest.raises(FourTokenFactoryAdapterError, match="not an exact active"):
        derive_peer_cycle_stop_effect(
            proof_db.connection,
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            configuration_id=CONFIGURATION,
            factory_run_id=FACTORY_RUN,
            target_cycle_id=CYCLE_2,
            origin_cycle_id=CYCLE_1,
        )
    after = proof_db.connection.execute(
        "SELECT cycle_state,first_terminal_cause FROM "
        "printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (CYCLE_2,),
    ).fetchone()
    cycle_two = proof_db.derive_cycle(CYCLE_2)

    assert before["cycle_state"] == after["cycle_state"] == "TERMINAL_COMPLETED"
    assert before["first_terminal_cause"] == after["first_terminal_cause"]
    assert cycle_two["execution_outcome"] == "TERMINAL_SUCCESS"
    assert CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL not in {
        after["first_terminal_cause"]
    }


def test_failed_cycle_one_peer_stops_only_active_incomplete_cycle_two(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_failed_cycle(CYCLE_1, 1, cause="CYCLE_ONE_LOCAL_FAILURE")
    proof_db.seed_active_cycle(CYCLE_2, 2)

    target = proof_db.derive_cycle(CYCLE_2)
    origin = proof_db.derive_cycle(CYCLE_1)
    effect = derive_peer_cycle_stop_effect(
        proof_db.connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        configuration_id=CONFIGURATION,
        factory_run_id=FACTORY_RUN,
        target_cycle_id=CYCLE_2,
        origin_cycle_id=CYCLE_1,
    )
    selected = resolve_peer_stop_origin_cycle_id(
        proof_db.connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        configuration_id=CONFIGURATION,
        factory_run_id=FACTORY_RUN,
        target_cycle_id=CYCLE_2,
        admitted_cycle_ids=(CYCLE_1, CYCLE_2),
    )

    assert origin["execution_outcome"] == "CYCLE_FAILED"
    assert target["execution_outcome"] == "ACTIVE_INCOMPLETE"
    assert effect["cause"] == CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL
    assert effect["origin_scope"] == "CYCLE"
    assert effect["effect_scope"] == "CAMPAIGN"
    assert effect["origin_fault"]["cause"] == "CYCLE_ONE_LOCAL_FAILURE"
    assert effect["cause"] != effect["origin_fault"]["cause"]
    assert selected == CYCLE_1


def test_ambiguous_cycle_two_is_not_peer_stopped(proof_db: Lane4ProofDB) -> None:
    proof_db.seed_failed_cycle(CYCLE_1, 1, cause="CYCLE_ONE_LOCAL_FAILURE")
    proof_db.seed_ambiguous_cycle(CYCLE_2, 2)

    target = proof_db.derive_cycle(CYCLE_2)
    selected = resolve_peer_stop_origin_cycle_id(
        proof_db.connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        configuration_id=CONFIGURATION,
        factory_run_id=FACTORY_RUN,
        target_cycle_id=CYCLE_2,
        admitted_cycle_ids=(CYCLE_1, CYCLE_2),
    )
    with pytest.raises(
        FourTokenFactoryAdapterError,
        match="interrupted or ambiguous",
    ):
        derive_peer_cycle_stop_effect(
            proof_db.connection,
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            configuration_id=CONFIGURATION,
            factory_run_id=FACTORY_RUN,
            target_cycle_id=CYCLE_2,
            origin_cycle_id=CYCLE_1,
        )
    row = proof_db.connection.execute(
        "SELECT cycle_state,first_terminal_cause FROM "
        "printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (CYCLE_2,),
    ).fetchone()
    aggregate = proof_db.derive_campaign()

    assert target["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert selected is None
    assert row["cycle_state"] == "PLANNED"
    assert row["first_terminal_cause"] is None
    assert aggregate["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert aggregate["requires_review"] is True
    assert aggregate["campaign_pass_eligible"] is False


def test_token_local_failure_does_not_fan_out_to_peer_token_or_cycle(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(
        CYCLE_1, 1, clean=True, token_local_failure_slot=1
    )
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)

    cycle_one = proof_db.derive_cycle(CYCLE_1)
    peer = next(
        item for item in cycle_one["tokens"] if item["slot_ordinal"] == 2
    )
    failed = next(
        item for item in cycle_one["tokens"] if item["slot_ordinal"] == 1
    )
    aggregate = proof_db.derive_campaign()

    assert failed["token_outcome"] == "TOKEN_LOCAL_FAILURE"
    assert peer["token_outcome"] != "TOKEN_LOCAL_FAILURE"
    assert peer["token_outcome"] != "CYCLE_FAILED"
    assert cycle_one["execution_outcome"] == "TERMINAL_SUCCESS"
    assert aggregate["execution_outcome"] == "TERMINAL_SUCCESS"
    assert aggregate["cycles"][1]["execution_outcome"] == "TERMINAL_SUCCESS"


def test_campaign_shared_supervision_fault_is_not_cycle_local(
    proof_db: Lane4ProofDB,
) -> None:
    cause = "SUPERVISION_LEASE_RENEWAL_UNCONFIRMED"
    proof_db.seed_failed_cycle(CYCLE_1, 1, cause=cause)
    proof_db.seed_failed_cycle(CYCLE_2, 2, cause=cause)
    proof_db.set_campaign_shared_supervision(cause)

    cycle_one = proof_db.derive_cycle(CYCLE_1)
    aggregate = proof_db.derive_campaign()

    assert cycle_one["primary_fault"]["origin_scope"] == "CAMPAIGN"
    assert cycle_one["primary_fault"]["effect_scope"] == "CAMPAIGN"
    assert cycle_one["primary_fault"]["cause"] == cause
    assert aggregate["execution_outcome"] == "CAMPAIGN_FAILED"
    assert aggregate["first_cause"]["origin_scope"] == "CAMPAIGN"


def test_honest_non_clean_quality_does_not_become_execution_failure(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=False)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)

    cycle_one = proof_db.derive_cycle(CYCLE_1)
    cycle_two = proof_db.derive_cycle(CYCLE_2)
    aggregate = proof_db.derive_campaign()
    report = build_campaign_terminal_report(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        report_id=REPORT_ID,
        factory_run_id=FACTORY_RUN,
        execution_id=EXECUTION,
        terminal_accounting=aggregate,
        lifecycle_started=True,
        reconciliation={"cleanup_complete": True},
    )

    assert cycle_one["execution_outcome"] == "TERMINAL_SUCCESS"
    assert cycle_one["quality_outcome"] == "NON_CLEAN"
    assert cycle_two["execution_outcome"] == "TERMINAL_SUCCESS"
    assert cycle_two["quality_outcome"] == "CLEAN"
    assert aggregate["execution_outcome"] == "TERMINAL_SUCCESS"
    assert aggregate["quality_outcome"] == "MIXED"
    assert report["terminal_accounting"]["quality_outcome"] == "MIXED"
    assert report["cycles"][0]["quality_outcome"] == "NON_CLEAN"


def test_cycle_two_accounting_rejects_cycle_one_owned_substitute(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_active_cycle(CYCLE_2, 2)

    cycle_one_steps = cycle_scoped_factory_step_ids(
        proof_db.connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        cycle_id=CYCLE_1,
    )
    cycle_two_steps = cycle_scoped_factory_step_ids(
        proof_db.connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        cycle_id=CYCLE_2,
    )
    cycle_two = proof_db.derive_cycle(CYCLE_2)

    assert cycle_one_steps
    assert cycle_two_steps == ()
    assert "CYCLE_SCOPED_FACTORY_STEP_OWNERSHIP_MISSING" in cycle_two[
        "incomplete_reasons"
    ]
    assert cycle_two["factory_step_ids"] == []


def test_missing_cycle_two_progression_cannot_pass(proof_db: Lane4ProofDB) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    proof_db.connection.execute(
        "DELETE FROM printer_memory_factory_standard_4h_progression_tokens "
        "WHERE cycle_id=?",
        (CYCLE_2,),
    )
    proof_db.connection.execute(
        "DELETE FROM printer_memory_factory_standard_4h_progression_attempts "
        "WHERE cycle_id=?",
        (CYCLE_2,),
    )
    proof_db.connection.commit()

    cycle_two = proof_db.derive_cycle(CYCLE_2)
    aggregate = proof_db.derive_campaign()

    assert cycle_two["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert "STANDARD_FOUR_HOUR_TERMINAL_ACCOUNTING_INCOMPLETE" in cycle_two[
        "incomplete_reasons"
    ]
    assert aggregate["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert aggregate["campaign_pass_eligible"] is False


def test_earlier_primary_is_preserved_against_later_cycle_fault(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_failed_cycle(CYCLE_1, 1, cause="EARLIER_CYCLE_ONE_PRIMARY")
    proof_db.seed_failed_cycle(CYCLE_2, 2, cause="SAFE_STOP_PREFLIGHT_FAILED")
    transition_state(
        proof_db.connection,
        record_kind="run",
        identity=CAMPAIGN_RUN,
        expected_state="RUNNING",
        new_state="TERMINAL_FAILED",
        terminal_cause="EARLIER_CYCLE_ONE_PRIMARY",
        now=NOW,
    )

    aggregate = proof_db.derive_campaign()
    secondary_causes = [
        str(item.get("cause") or "") for item in aggregate["secondary_faults"]
    ]

    assert aggregate["first_cause"]["cause"] == "EARLIER_CYCLE_ONE_PRIMARY"
    assert "SAFE_STOP_PREFLIGHT_FAILED" in secondary_causes
    assert aggregate["first_cause"]["cause"] != "SAFE_STOP_PREFLIGHT_FAILED"


def test_canonical_two_cycle_report_uses_derived_campaign_identity(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    accounting = proof_db.derive_campaign()
    report = build_campaign_terminal_report(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        report_id=REPORT_ID,
        factory_run_id=FACTORY_RUN,
        execution_id=EXECUTION,
        terminal_accounting=accounting,
        lifecycle_started=True,
        reconciliation={"cleanup_complete": True},
    )

    identity = report["identity"]
    assert identity == {
        "campaign_id": CAMPAIGN,
        "configuration_id": CONFIGURATION,
        "campaign_run_id": CAMPAIGN_RUN,
        "factory_run_id": FACTORY_RUN,
        "execution_id": EXECUTION,
        "report_id": REPORT_ID,
    }
    assert "cycle_id" not in identity
    assert report["terminal_accounting"]["required_cycle_ordinals"] == [1, 2]
    assert [item["cycle_ordinal"] for item in report["cycles"]] == [1, 2]
    assert report["terminal_accounting"]["execution_outcome"] == (
        accounting["execution_outcome"]
    )
    assert report["terminal_accounting"]["quality_outcome"] == (
        accounting["quality_outcome"]
    )
    assert report["terminal_accounting"]["accounting_complete"] is True
    assert "first_cause" in report["terminal_accounting"]
    assert "secondary_faults" in report["terminal_accounting"]


def _write_canonical_report(proof_db: Lane4ProofDB, accounting: dict) -> tuple[dict, dict]:
    report = build_campaign_terminal_report(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        report_id=REPORT_ID,
        factory_run_id=FACTORY_RUN,
        execution_id=EXECUTION,
        terminal_accounting=accounting,
        lifecycle_started=True,
        reconciliation={"cleanup_complete": True, "lease_released": True},
    )
    jobs_before = int(
        proof_db.connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0]
    )
    written = write_campaign_terminal_report(
        proof_db.db_path,
        proof_db.report_dir,
        report_id=REPORT_ID,
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        report=report,
        now=datetime.fromisoformat(NOW),
    )
    jobs_after = int(
        proof_db.connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0]
    )
    assert jobs_before == jobs_after
    return report, written


def test_report_write_is_idempotent_and_rejects_divergent_payload(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    accounting = proof_db.derive_campaign()
    report, first = _write_canonical_report(proof_db, accounting)
    second = write_campaign_terminal_report(
        proof_db.db_path,
        proof_db.report_dir,
        report_id=REPORT_ID,
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        report=report,
        now=datetime.fromisoformat(NOW),
    )
    divergent = dict(report)
    divergent["elapsed_seconds"] = 9.0

    assert first["artifact_created"] is True
    assert second["artifact_created"] is False
    assert first["report_hash"] == second["report_hash"]
    with pytest.raises(TerminalClosureError, match="already differs"):
        write_campaign_terminal_report(
            proof_db.db_path,
            proof_db.report_dir,
            report_id=REPORT_ID,
            campaign_id=CAMPAIGN,
            configuration_id=CONFIGURATION,
            report=divergent,
            now=datetime.fromisoformat(NOW),
        )


def test_terminal_summary_is_canonical_projection_and_immutable(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    accounting = proof_db.derive_campaign()
    report, written = _write_canonical_report(proof_db, accounting)
    summary = build_campaign_terminal_summary(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        execution_id=EXECUTION,
        report_id=REPORT_ID,
        terminal_accounting=accounting,
        report_result=written,
        cleanup={"cleanup_complete": True, "lease_released": True, "active_work": 0},
    )
    first = write_campaign_terminal_summary(proof_db.summary_path, summary=summary)
    second = write_campaign_terminal_summary(proof_db.summary_path, summary=summary)
    changed = dict(summary)
    changed["campaign_execution_outcome"] = "CYCLE_FAILED"

    assert summary["configuration_id"] == CONFIGURATION
    assert [item["cycle_ordinal"] for item in summary["cycles"]] == [1, 2]
    assert summary["campaign_execution_outcome"] == accounting["execution_outcome"]
    assert summary["report_hash"] == written["report_hash"]
    assert summary["terminal_report_path"] == written["artifact_path"]
    assert summary["restart_created"] is False
    assert summary["successor_created"] is False
    assert first["artifact_created"] is True
    assert second["artifact_created"] is False
    with pytest.raises(TerminalClosureError, match="already differs"):
        write_campaign_terminal_summary(proof_db.summary_path, summary=changed)
    assert report["identity"]["campaign_run_id"] == CAMPAIGN_RUN


def test_summary_failure_does_not_rewrite_durable_report(proof_db: Lane4ProofDB) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    accounting = proof_db.derive_campaign()
    report, written = _write_canonical_report(proof_db, accounting)
    artifact = Path(written["artifact_path"])
    before = artifact.read_text(encoding="utf-8")
    report_row = proof_db.connection.execute(
        "SELECT report_hash,report_json FROM printer_memory_factory_campaign_reports "
        "WHERE report_id=?",
        (REPORT_ID,),
    ).fetchone()
    proof_db.summary_path.write_text('{"campaign_execution_outcome":"FOREIGN"}', encoding="utf-8")
    summary = build_campaign_terminal_summary(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        execution_id=EXECUTION,
        report_id=REPORT_ID,
        terminal_accounting=accounting,
        report_result=written,
        cleanup={"cleanup_complete": True, "lease_released": True, "active_work": 0},
    )

    with pytest.raises(TerminalClosureError, match="already differs"):
        write_campaign_terminal_summary(proof_db.summary_path, summary=summary)
    after_row = proof_db.connection.execute(
        "SELECT report_hash,report_json FROM printer_memory_factory_campaign_reports "
        "WHERE report_id=?",
        (REPORT_ID,),
    ).fetchone()

    assert artifact.read_text(encoding="utf-8") == before
    assert after_row["report_hash"] == report_row["report_hash"]
    assert after_row["report_json"] == report_row["report_json"]
    assert json.loads(before)["terminal_accounting"] == report["terminal_accounting"]


def test_report_only_returns_persisted_aggregate_without_writes(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    accounting = proof_db.derive_campaign()
    _, written = _write_canonical_report(proof_db, accounting)
    summary = build_campaign_terminal_summary(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        execution_id=EXECUTION,
        report_id=REPORT_ID,
        terminal_accounting=accounting,
        report_result=written,
        cleanup={"cleanup_complete": True, "lease_released": True, "active_work": 0},
    )
    write_campaign_terminal_summary(proof_db.summary_path, summary=summary)
    db_hash_before = hashlib.sha256(proof_db.db_path.read_bytes()).hexdigest()
    jobs_before = int(
        proof_db.connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0]
    )

    replayed = report_only(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        db_path=proof_db.db_path,
        artifact_root=proof_db.root,
    )

    assert replayed["status"] == "REPORT_ONLY_COMPLETE"
    assert replayed["source_calls"] == 0
    assert replayed["scheduler_runtime_calls"] == 0
    assert replayed["database_writes"] == 0
    assert replayed["terminal_accounting"]["execution_outcome"] == (
        accounting["execution_outcome"]
    )
    assert [item["cycle_id"] for item in replayed["cycles"]] == [CYCLE_1, CYCLE_2]
    assert hashlib.sha256(proof_db.db_path.read_bytes()).hexdigest() == db_hash_before
    assert (
        int(
            proof_db.connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
            ).fetchone()[0]
        )
        == jobs_before
    )


def test_report_only_blocks_missing_report_and_mismatched_summary(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    accounting = proof_db.derive_campaign()
    summary = build_campaign_terminal_summary(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        execution_id=EXECUTION,
        report_id=REPORT_ID,
        terminal_accounting=accounting,
        report_result={
            "report_id": REPORT_ID,
            "report_hash": "a" * 64,
            "artifact_path": str(proof_db.report_dir / f"{REPORT_ID}.json"),
            "report_rows": 1,
        },
        cleanup={"cleanup_complete": True, "lease_released": True, "active_work": 0},
    )
    write_campaign_terminal_summary(proof_db.summary_path, summary=summary)

    missing_report = report_only(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        db_path=proof_db.db_path,
        artifact_root=proof_db.root,
    )
    _, written = _write_canonical_report(proof_db, accounting)
    mismatched = dict(summary)
    mismatched["report_hash"] = "b" * 64
    proof_db.summary_path.write_text(
        json.dumps(mismatched, sort_keys=True),
        encoding="utf-8",
    )
    mismatched_replay = report_only(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        db_path=proof_db.db_path,
        artifact_root=proof_db.root,
    )
    del written

    assert missing_report["status"] == "REPLAY_BLOCKED"
    assert missing_report["block_reason"] == "EXACT_TERMINAL_REPORT_MISSING"
    assert missing_report["database_writes"] == 0
    assert mismatched_replay["status"] == "REPLAY_BLOCKED"
    assert "LANE4_SUMMARY_REPORT_HASH_MISMATCH" in str(
        mismatched_replay.get("block_reason")
    )


def test_six_unit_registered_set_must_equal_admitted_cycles(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    owner = CampaignSixUnitOwner(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        cycle_id=CYCLE_1,
        started_at=NOW,
    )
    ledger = CampaignActionLocalLedger(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        cycle_id=CYCLE_1,
        lifecycle_started=True,
    )

    with pytest.raises(FullRunAccountingError, match="admitted cycles"):
        finalize_full_run_ownership_and_report(
            proof_db.connection,
            context=proof_db.context(CYCLE_1),
            owner=owner,
            action_local=ledger,
            execution_id=EXECUTION,
            supervision_id="supervision-lane4-proof",
            launch_git_provenance=_provenance(),
            db_target_identity="isolated-lane4-proof",
            runtime_terminal_status="TERMINAL_COMPLETED",
            cleanup_result={"cleanup_complete": True, "lease_released": True},
            forbidden_capability_deltas={
                "retrieval_queries": 0,
                "paper_decisions": 0,
                "paper_trades": 0,
            },
            now=NOW,
        )

    registry = CampaignCycleAccountingRegistry(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        initial_cycle_id=CYCLE_1,
        started_at=NOW,
    )
    registry.register_authoritative_cycle(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        cycle_id=CYCLE_2,
        started_at=NOW,
    )
    projection = registry.campaign_projection()
    assert projection.registered_cycle_ids == (CYCLE_1, CYCLE_2)
    cycle_two_owner = projection.owner_for_cycle(CYCLE_2)
    cycle_one_stage = f"{CAMPAIGN}|{CAMPAIGN_RUN}|{CYCLE_1}|WINDOW_15M_SLOT_1|2"
    foreign_evidence = seal_campaign_stage_evidence(
        stage_id=cycle_one_stage,
        stage_kind="WINDOW_15M_SLOT_1",
        stage_sequence=2,
        stage_terminal_status="COMPLETED",
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
        cycle_id=CYCLE_1,
        sealed_at=NOW,
        evidence={
            "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
            "transport_operations": [],
            "local_validations": 1,
            "scheduler_work_items": 0,
            "lifecycle_reservations": 0,
        },
        local_validation_identities=[
            LocalValidationIdentity(
                stage_id=cycle_one_stage,
                subject_identity=f"{CYCLE_1}:subject",
                validation_kind="TEST_VALIDATION",
                validation_ordinal=1,
            )
        ],
    )
    with pytest.raises(CampaignSixUnitError, match="cycle_id"):
        cycle_two_owner.ingest_stage_evidence(foreign_evidence)


def test_partial_durable_state_cannot_be_converted_into_pass(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_ambiguous_cycle(CYCLE_2, 2)
    transition_state(
        proof_db.connection,
        record_kind="run",
        identity=CAMPAIGN_RUN,
        expected_state="RUNNING",
        new_state="TERMINAL_COMPLETED",
        terminal_cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        now=NOW,
    )
    jobs_before = int(
        proof_db.connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0]
    )
    aggregate = proof_db.derive_campaign()
    jobs_after = int(
        proof_db.connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0]
    )
    report_count = int(
        proof_db.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
        ).fetchone()[0]
    )

    assert jobs_before == jobs_after
    assert aggregate["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert aggregate["campaign_pass_eligible"] is False
    assert report_count == 0


def test_ordinal_three_duplicate_and_identity_mismatch_fail_closed(
    proof_db: Lane4ProofDB,
) -> None:
    proof_db.seed_complete_cycle(CYCLE_1, 1, clean=True)
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    proof_db.connection.execute(
        """INSERT INTO printer_memory_factory_campaign_cycles(
               cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
               created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?)""",
        ("cycle-3-forbidden", CAMPAIGN, CAMPAIGN_RUN, 3, "PLANNED", NOW, NOW),
    )
    proof_db.connection.commit()

    with pytest.raises(FullRunAccountingError, match="authorized ordinals"):
        derive_cycle_terminal_accounting_result(
            proof_db.connection,
            context=OperationalLifecycleOwnershipContext(
                campaign_id=CAMPAIGN,
                campaign_run_id=CAMPAIGN_RUN,
                cycle_id="cycle-3-forbidden",
                configuration_id=CONFIGURATION,
                factory_run_id=FACTORY_RUN,
            ),
        )
    with pytest.raises(FullRunAccountingError, match="more than two"):
        proof_db.derive_campaign()

    foreign = sqlite3.connect(":memory:")
    foreign.row_factory = sqlite3.Row
    foreign.executescript(
        """
        CREATE TABLE printer_memory_factory_campaign_runs(
            campaign_id TEXT, run_id TEXT, authoritative_run_id TEXT,
            run_state TEXT, first_terminal_cause TEXT, terminal_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_configurations(
            campaign_id TEXT, configuration_id TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_cycles(
            campaign_id TEXT, run_id TEXT, cycle_id TEXT, cycle_ordinal INTEGER,
            cycle_state TEXT, first_terminal_cause TEXT, terminal_at TEXT
        );
        """
    )
    foreign.execute(
        "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?,?,?,?,?)",
        (CAMPAIGN, CAMPAIGN_RUN, "foreign-factory", "RUNNING", None, None),
    )
    foreign.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations VALUES (?,?)",
        (CAMPAIGN, CONFIGURATION),
    )
    with pytest.raises(FullRunAccountingError, match="binding mismatch"):
        derive_two_cycle_campaign_terminal_accounting(
            foreign,
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            configuration_id=CONFIGURATION,
            factory_run_id=FACTORY_RUN,
        )


def test_single_summary_writer_and_cycle_three_remain_locked() -> None:
    from printer_v1.operator_cli import operational_memory_factory_command as command
    from printer_v1.operator_cli import unified_terminal_closure as closure

    command_source = Path(command.__file__).read_text(encoding="utf-8")
    closure_source = Path(closure.__file__).read_text(encoding="utf-8")
    assert command_source.count("write_campaign_terminal_summary(") >= 1
    assert "Path.write_text" not in command_source.split("write_campaign_terminal_summary")[0]
    assert "def write_campaign_terminal_summary(" in closure_source
    assert command_source.count("terminal-summary.json") >= 1
    assert "REQUIRED_MULTI_CYCLE_ORDINALS = (1, 2)" in Path(
        "src/printer_v1/operator_cli/campaign_full_run_accounting.py"
    ).read_text(encoding="utf-8")


def test_d_token_local_drained_does_not_erase_independent_progression_ambiguity(
    proof_db: Lane4ProofDB,
) -> None:
    """Ambiguity must remain ambiguous: Fix 1 must not elevate to CANCELLED_STOPPED."""
    from printer_v1.operator_cli.standard_4h_progression import (
        persist_progression_primary_fault,
    )

    slots = proof_db.seed_complete_cycle(
        CYCLE_1, 1, clean=True, token_local_failure_slot=1
    )
    peer_slot_id = str(slots[1]["token_slot_id"])
    # Keep activity ACTIVE_INCOMPLETE so a pre-Fix-1 gate that admitted
    # INTERRUPTED_AMBIGUOUS would still attempt the drained token-local projection.
    proof_db.connection.execute(
        """UPDATE printer_memory_factory_campaign_token_slots
           SET token_state='SELECTED',
               first_terminal_cause=NULL,
               terminal_at=NULL,
               updated_at=?
           WHERE token_slot_id=?""",
        (NOW, peer_slot_id),
    )
    proof_db.connection.execute(
        """UPDATE printer_memory_factory_campaign_cycles
           SET cycle_state='PLANNED',
               first_terminal_cause=NULL,
               terminal_at=NULL,
               updated_at=?
           WHERE cycle_id=?""",
        (NOW, CYCLE_1),
    )
    # Terminal progression rows are immutable on UPDATE; replace the seeded
    # HANDOFF_COMMITTED attempt with a fresh WAITING row so the progression
    # owner can persist INTERRUPTED_REVIEW.
    attempt_id = f"progression-{CYCLE_1}"
    proof_db.connection.execute(
        "DELETE FROM printer_memory_factory_standard_4h_progression_tokens "
        "WHERE progression_attempt_id=?",
        (attempt_id,),
    )
    proof_db.connection.execute(
        "DELETE FROM printer_memory_factory_standard_4h_progression_attempts "
        "WHERE progression_attempt_id=?",
        (attempt_id,),
    )
    proof_db.connection.execute(
        """INSERT INTO printer_memory_factory_standard_4h_progression_attempts(
               progression_attempt_id,campaign_id,configuration_id,
               campaign_run_id,factory_run_id,cycle_id,policy_version,
               attempt_state,authority_evidence_json,first_terminal_cause,
               fault_details_json,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            attempt_id,
            CAMPAIGN,
            CONFIGURATION,
            CAMPAIGN_RUN,
            FACTORY_RUN,
            CYCLE_1,
            "STANDARD_4H_PROGRESSION_V1",
            "WAITING_FOR_PREDECESSORS",
            _EMPTY_OBJECT,
            None,
            _EMPTY_FAULTS,
            NOW,
            NOW,
        ),
    )
    for slot in slots:
        proof_db.connection.execute(
            """INSERT INTO printer_memory_factory_standard_4h_progression_tokens(
                   progression_token_id,progression_attempt_id,campaign_id,
                   campaign_run_id,factory_run_id,cycle_id,slot_ordinal,
                   token_slot_id,token_identity,token_row_id,mint_identity,
                   pair_identity,pair_row_id,lifecycle_identity,
                   tracking_queue_id,tracking_lane,predecessor_window_1h_id,
                   predecessor_memory_window_id,token_disposition,
                   disposition_reasons_json,eligibility_evidence_json,
                   successor_window_4h_id,first_terminal_cause,
                   fault_details_json,evaluated_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f"progression-token-{slot['token_slot_id']}",
                attempt_id,
                CAMPAIGN,
                CAMPAIGN_RUN,
                FACTORY_RUN,
                CYCLE_1,
                int(slot["slot_ordinal"]),
                slot["token_slot_id"],
                slot["token_identity"],
                int(slot["token_row_id"]),
                slot["mint_identity"],
                slot["pair_identity"],
                int(slot["pair_row_id"]),
                slot["lifecycle_identity"],
                int(slot["tracking_queue_id"]),
                "TRACK_NORMAL",
                None,
                None,
                "WAITING_FOR_PREDECESSOR",
                json.dumps(["WAITING_FOR_INDEPENDENT_AMBIGUITY_FIXTURE"]),
                _EMPTY_OBJECT,
                None,
                None,
                _EMPTY_FAULTS,
                None,
                NOW,
                NOW,
            ),
        )
    proof_db.connection.commit()
    persist_progression_primary_fault(
        proof_db.connection,
        progression_attempt_id=attempt_id,
        cause="TEST_INDEPENDENT_AMBIGUITY",
        state="INTERRUPTED_REVIEW",
        now=NOW,
    )
    proof_db.connection.commit()

    result = proof_db.derive_cycle(CYCLE_1)

    assert result["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert result["requires_review"] is True
    assert result["execution_outcome"] != "CANCELLED_STOPPED"
    primary = result.get("primary_fault") or {}
    assert str(primary.get("cause") or "") == "TEST_INDEPENDENT_AMBIGUITY"
    assert str(primary.get("cause") or "") != "TOKEN_LOCAL_TERMINAL_FAILURE"
    progression = result.get("standard_four_hour_terminal") or {}
    progression_faults = progression.get("fault_details") or {}
    progression_primary = progression_faults.get("primary") or {}
    assert str(progression_primary.get("cause") or "") == "TEST_INDEPENDENT_AMBIGUITY"
    assert any(
        item.get("token_outcome") == "TOKEN_LOCAL_FAILURE"
        for item in result.get("tokens") or ()
    )


def test_e_token_local_failure_plus_genuine_global_fault_global_wins(
    proof_db: Lane4ProofDB,
) -> None:
    """Coexistence: durable campaign-global terminal blocks token-local projection."""
    global_cause = "SUPERVISION_LEASE_RENEWAL_UNCONFIRMED"
    slots = proof_db.admit_cycle(CYCLE_1, 1, token_base=100)
    failed_slot_id = str(slots[0]["token_slot_id"])
    transition_state(
        proof_db.connection,
        record_kind="token_slot",
        identity=failed_slot_id,
        expected_state="SELECTED",
        new_state="FAILED",
        terminal_cause="TOKEN_LOCAL_TERMINAL_FAILURE",
        now=NOW,
    )
    # Peer remains SELECTED → ACTIVE_INCOMPLETE; work/steps absent → drained.
    proof_db.seed_complete_cycle(CYCLE_2, 2, clean=True)
    proof_db.set_campaign_shared_supervision(global_cause)

    cycle_one = proof_db.derive_cycle(CYCLE_1)
    cycle_two = proof_db.derive_cycle(CYCLE_2)
    aggregate = proof_db.derive_campaign()

    assert any(
        item.get("token_outcome") == "TOKEN_LOCAL_FAILURE"
        for item in cycle_one.get("tokens") or ()
    )
    assert cycle_one["execution_outcome"] == "ACTIVE_INCOMPLETE"
    assert cycle_one["execution_outcome"] != "CANCELLED_STOPPED"
    assert cycle_one["execution_outcome"] != "TERMINAL_SUCCESS"
    assert cycle_two["execution_outcome"] == "TERMINAL_SUCCESS"

    assert aggregate["execution_outcome"] == "CAMPAIGN_FAILED"
    assert aggregate["execution_outcome"] != "TERMINAL_SUCCESS"
    first_cause = aggregate.get("first_cause") or {}
    assert str(first_cause.get("origin_scope") or "") == "CAMPAIGN"
    assert str(first_cause.get("effect_scope") or "") == "CAMPAIGN"
    assert str(first_cause.get("cause") or "") == global_cause
    assert str(first_cause.get("cause") or "") != "TOKEN_LOCAL_TERMINAL_FAILURE"
    assert "SAFE_STOP_SOURCE_FAILURE" not in str(first_cause.get("cause") or "")
    assert aggregate["campaign_pass_eligible"] is False
    secondary_causes = {
        str(item.get("cause") or "")
        for item in (aggregate.get("secondary_faults") or ())
        if isinstance(item, Mapping)
    }
    assert "CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL" not in secondary_causes
    assert "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED" not in {
        str(first_cause.get("cause") or ""),
        *(secondary_causes),
    }
