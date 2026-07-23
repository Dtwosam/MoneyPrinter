"""V2-9.7E.40/.41 full-pilot admission proof (graduation-only, supersedes 900s).

Fixture-only. Proves that the canonical FULL_PILOT path (``run_operational``)
now admits candidates by exact PumpSwap graduation (V2-9.7E.41 graduation-only
law) instead of the retired 900-second maturity boundary: bonding-curve /
unpaired creates of ANY age are pending discovery only and block with
``BLOCKED_INSUFFICIENT_GRADUATED_POOL`` before any holder, snapshot, lifecycle or
memory work, while confirmed origins are staged into the durable
prospective-origin registry as pending discovery evidence. No provider is
contacted: ``pump_transport`` is a transport-shaped fake and
``secondary_transport`` is ``None``.
"""

from __future__ import annotations

from datetime import datetime
import sqlite3
import unittest

from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    BLOCKED_INSUFFICIENT_GRADUATED_POOL,
    GRADUATION_ELIGIBLE,
    GRADUATION_PENDING_DISCOVERY,
    AuthoritativeLiveOperationalCampaignOwner,
    _graduated_admission,
)
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.sources.pumpfun_origin import load_due_staged_origins

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_14_two_token_operational_pilot_runner as e14
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    ActivationResult,
    OriginLifecycleResult,
)
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport
from test_v2_9_7e_5_pump_origin_acquisition_architecture import (
    create_transaction,
    signature_row,
)


GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

NOW_EPOCH = int(datetime.fromisoformat(e8.NOW).timestamp())
YOUNG_BT = NOW_EPOCH - 60      # 60s old bonding-curve create
OLD_BT = NOW_EPOCH - 10_000    # ~2.7h old bonding-curve create (age is irrelevant)


def _transport(specs):
    """specs: list of (block_time, mint_label). Returns a fake pump transport."""
    txs = {}
    rows = []
    mints = []
    for i, (block_time, label) in enumerate(specs):
        sig = f"e40Sig{i}"
        slot = 900 + i
        tx, mint = create_transaction(sig, slot, block_time, mint_label=label)
        txs[sig] = tx
        rows.append(signature_row(sig, slot))
        mints.append(mint)
    return _FakePumpTransport(list(reversed(rows)), txs), mints


class FullPilotGraduationAdmissionProofTests(e8._IntegrationBase):
    def _run(self, transport):
        owner = AuthoritativeLiveOperationalCampaignOwner()
        return owner.run_operational(
            command=self.command,
            pump_transport=transport,
            secondary_transport=None,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e40-admission-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs={},
        )

    def _forbidden_and_lifecycle_counts(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            def count(sql):
                return int(connection.execute(sql).fetchone()[0])
            return {
                "run_steps": count(
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
                ),
                "memory_windows": count(
                    "SELECT COUNT(*) FROM printer_memory_windows"
                ),
                "episodes": count("SELECT COUNT(*) FROM printer_episodes"),
                "decisions": count("SELECT COUNT(*) FROM printer_paper_decisions"),
                "positions": count("SELECT COUNT(*) FROM printer_paper_positions"),
                "window15m_jobs": count(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_name LIKE 'window15m:%'"
                ),
                "registry": count(
                    "SELECT COUNT(*) FROM "
                    "printer_pumpfun_finalized_origin_registry"
                ),
            }
        finally:
            connection.close()

    # -- bonding-curve creates are pending discovery only, block regardless of age

    def test_young_bonding_curve_creates_block_graduated_pool(self) -> None:
        transport, _mints = _transport([(YOUNG_BT, "youngA"), (YOUNG_BT, "youngB")])
        result = self._run(transport)

        self.assertFalse(result.lifecycle_started)
        self.assertEqual(result.lifecycle["run_status"], "NOT_STARTED")
        self.assertEqual(
            result.lifecycle["stop_reason"], BLOCKED_INSUFFICIENT_GRADUATED_POOL
        )
        self.assertEqual(result.lifecycle["run_id"], "run")
        self.assertEqual(result.activation.activated_slots, ())
        self.assertIsNone(result.activation.selection_batch_id)

        admission = result.lifecycle["full_pilot_admission"]
        self.assertEqual(admission["eligibility_rule"], "GRADUATION_ONLY")
        self.assertEqual(admission["candidate_universe"], 2)
        self.assertEqual(admission["graduated_candidate_count"], 0)
        self.assertEqual(
            admission["graduation_state_counts"][GRADUATION_PENDING_DISCOVERY], 2
        )
        # Age is context, never eligibility.
        for rec in admission["candidates"]:
            self.assertEqual(rec["graduation_state"], GRADUATION_PENDING_DISCOVERY)
            self.assertFalse(rec["selectable"])
            self.assertEqual(rec["token_age_context"], "AGE_IS_CONTEXT_NOT_ELIGIBILITY")

        counts = self._forbidden_and_lifecycle_counts()
        for key in (
            "run_steps",
            "memory_windows",
            "episodes",
            "decisions",
            "positions",
            "window15m_jobs",
        ):
            self.assertEqual(counts[key], 0)
        # Both confirmed origins are staged as pending discovery evidence.
        self.assertEqual(counts["registry"], 2)

    def test_old_bonding_curve_creates_still_block(self) -> None:
        # A bonding-curve token several hours old remains ineligible: graduation,
        # not age, is eligibility.
        transport, _mints = _transport([(OLD_BT, "oldA"), (OLD_BT, "oldB")])
        result = self._run(transport)
        self.assertFalse(result.lifecycle_started)
        self.assertEqual(
            result.lifecycle["stop_reason"], BLOCKED_INSUFFICIENT_GRADUATED_POOL
        )
        admission = result.lifecycle["full_pilot_admission"]
        self.assertEqual(admission["graduated_candidate_count"], 0)
        self.assertEqual(self._forbidden_and_lifecycle_counts()["window15m_jobs"], 0)

    def test_confirmed_origins_staged_as_pending_discovery(self) -> None:
        transport, mints = _transport([(YOUNG_BT, "pendA"), (OLD_BT, "pendB")])
        self._run(transport)
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            # The pending-discovery reload mechanics still function (age context),
            # but these origins are never selectable without graduation.
            due = load_due_staged_origins(
                connection,
                evaluated_epoch=NOW_EPOCH,
                maturity_seconds=900,
                exclude_mints=(),
            )
            due_mints = {m.lower() for m in (row["mint"] for row in due)}
            self.assertIn(mints[1].lower(), due_mints)  # OLD is age-due context
        finally:
            connection.close()


class GraduatedAdmissionUnitTests(unittest.TestCase):
    """`_graduated_admission` admits only graduation-confirmed candidates."""

    def _proof(self, mint: str, block_time: int) -> FixtureOriginProof:
        return FixtureOriginProof(
            mint=mint,
            signature=f"sig-{mint}",
            slot=1,
            block_time=block_time,
            bonding_curve=f"curve-{mint}",
            associated_bonding_curve="ata",
            creator_address="creator",
            confirmed=True,
        )

    def test_one_second_old_graduated_token_is_admissible(self) -> None:
        # A token confirmed graduated one second ago is eligible; a bonding-curve
        # token of any age is not. Age is context, graduation is eligibility.
        just_graduated = self._proof("gradApump", NOW_EPOCH - 1)
        bonding_hours_old = self._proof("bondBpump", NOW_EPOCH - 10_000)
        graduated, decisions = _graduated_admission(
            (just_graduated, bonding_hours_old),
            graduation_proofs={
                "gradApump": FixturePumpSwapProof(
                    mint="gradApump", pool_address="poolA"
                ),
            },
            candidate_cap=3,
        )
        self.assertEqual({p.mint for p in graduated}, {"gradApump"})
        states = {p.mint: s for p, s in decisions}
        self.assertEqual(states["gradApump"], GRADUATION_ELIGIBLE)
        self.assertEqual(states["bondBpump"], GRADUATION_PENDING_DISCOVERY)

    def test_ambiguous_and_wrong_owner_and_mismatch_fail_closed(self) -> None:
        proofs = (
            self._proof("ambApump", NOW_EPOCH - 5),
            self._proof("ownBpump", NOW_EPOCH - 5),
            self._proof("mixCpump", NOW_EPOCH - 5),
        )
        graduated, decisions = _graduated_admission(
            proofs,
            graduation_proofs={
                "ambApump": FixturePumpSwapProof(
                    mint="ambApump", pool_address="p", confirmed=False, ambiguous=True
                ),
                "ownBpump": FixturePumpSwapProof(
                    mint="ownBpump", pool_address="p", program_id="WRONGprogram"
                ),
                "mixCpump": FixturePumpSwapProof(
                    mint="DIFFERENTMINT", pool_address="p"
                ),
            },
            candidate_cap=3,
        )
        self.assertEqual(graduated, ())
        states = {p.mint: s for p, s in decisions}
        self.assertEqual(states["ambApump"], "AMBIGUOUS_MARKET")
        self.assertEqual(states["ownBpump"], "MARKET_IDENTITY_INVALID")
        self.assertEqual(states["mixCpump"], "MARKET_IDENTITY_INVALID")

    def test_candidate_cap_bounds_graduated(self) -> None:
        proofs = tuple(self._proof(f"g{i}pump", NOW_EPOCH - 5) for i in range(5))
        graduation = {
            f"g{i}pump": FixturePumpSwapProof(mint=f"g{i}pump", pool_address=f"p{i}")
            for i in range(5)
        }
        graduated, _ = _graduated_admission(
            proofs, graduation_proofs=graduation, candidate_cap=3
        )
        self.assertEqual(len(graduated), 3)


class _BlockedFakeOwner:
    """Owner returning the pre-lifecycle graduation-block terminal (no factory run)."""

    def __init__(self, run_id: str = "pilot-run") -> None:
        self._run_id = run_id
        self.calls = 0

    def run_operational(self, *, command, **_kwargs):
        self.calls += 1
        return OriginLifecycleResult(
            activation=ActivationResult(
                terminal_status=BLOCKED_INSUFFICIENT_GRADUATED_POOL,
                first_terminal_cause=BLOCKED_INSUFFICIENT_GRADUATED_POOL,
                activated_slots=(),
                selection_batch_id=None,
            ),
            lifecycle={
                "run_id": self._run_id,
                "run_status": "NOT_STARTED",
                "stop_reason": BLOCKED_INSUFFICIENT_GRADUATED_POOL,
                "first_terminal_cause": BLOCKED_INSUFFICIENT_GRADUATED_POOL,
                "lifecycle_started": False,
                "forbidden_deltas": {},
                "pending_or_running_run_steps": 0,
                "running_jobs_after_stop": 0,
                "full_pilot_admission": {"graduated_candidate_count": 0},
            },
            lifecycle_started=False,
        )


class _ActivationFailedFakeOwner:
    """Owner whose driver fails activation: no run identity, no lifecycle."""

    def run_operational(self, *, command, **_kwargs):
        return OriginLifecycleResult(
            activation=ActivationResult(
                terminal_status="FAILED",
                first_terminal_cause="NO_ATOMIC_ACTIVATION",
                activated_slots=(),
                selection_batch_id=None,
            ),
            lifecycle={
                "run_status": "NOT_STARTED",
                "stop_reason": "NO_ATOMIC_ACTIVATION",
                "first_terminal_cause": "NO_ATOMIC_ACTIVATION",
                "lifecycle_started": False,
                "forbidden_deltas": {},
            },
            lifecycle_started=False,
        )


class BlockedFullPilotThroughRunnerTests(e14._PilotRunnerBase):
    """The live pilot runner must terminate a pre-lifecycle block cleanly."""

    def test_pre_lifecycle_block_terminates_cleanly(self) -> None:
        owner = _BlockedFakeOwner()
        result, _owner, _paths = self._run(owner=owner, execution_id="e40-block-1")

        self.assertEqual(owner.calls, 1)
        self.assertEqual(result["status"], "PILOT_TERMINAL")
        self.assertFalse(result["lifecycle_started"])
        self.assertEqual(result["run_status"], "NOT_STARTED")
        self.assertEqual(result["stop_reason"], BLOCKED_INSUFFICIENT_GRADUATED_POOL)
        self.assertEqual(
            result["first_terminal_cause"], BLOCKED_INSUFFICIENT_GRADUATED_POOL
        )
        self.assertIsNotNone(result["terminal_status"])
        self.assertTrue(result["one_proof_lock_released"])
        self.assertTrue(result["replay_deterministic"])
        self.assertEqual(result["replay_new_source_calls"], 0)
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])
        self.assertEqual(
            result["full_pilot_admission"], {"graduated_candidate_count": 0}
        )

    def test_activation_failed_terminates_cleanly(self) -> None:
        owner = _ActivationFailedFakeOwner()
        result, _owner, _paths = self._run(owner=owner, execution_id="e40-actfail-1")
        self.assertEqual(result["status"], "PILOT_TERMINAL")
        self.assertFalse(result["lifecycle_started"])
        self.assertEqual(result["stop_reason"], "NO_ATOMIC_ACTIVATION")
        self.assertIsNotNone(result["terminal_status"])
        self.assertTrue(result["one_proof_lock_released"])
        self.assertEqual(result["replay_new_source_calls"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
