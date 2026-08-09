import ast
import inspect
import sqlite3
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from printer_v1.contracts.enums import SourceStatus
from printer_v1.discovery import eligible_token_supply
from printer_v1.discovery.permanent_discovery_availability import (
    CONTRACT_BLOCKED,
    REASON_ABOVE_FLOOR_NOMINATION,
    StageBudget,
    process_protocol_confirmation_queue,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignSixUnitOwner,
    reconcile_full_run_owner_to_action_local,
)

NOW = "2026-08-09T00:00:00+00:00"
CAMPAIGN_ID = "dtw93-campaign"
RUN_ID = "dtw93-run"
CYCLE_ID = "dtw93-cycle"


def make_connection(count: int) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE printer_exact_market_states (
            network TEXT NOT NULL,
            mint_identity TEXT NOT NULL,
            pool_address TEXT NOT NULL,
            token_program_id TEXT NOT NULL DEFAULT 'UNRESOLVED_TOKEN_PROGRAM',
            pool_program_id TEXT NOT NULL DEFAULT 'UNRESOLVED_POOL_PROGRAM',
            base_mint TEXT NOT NULL,
            quote_mint TEXT NOT NULL DEFAULT 'UNKNOWN_QUOTE_MINT',
            venue TEXT NOT NULL DEFAULT 'pumpswap',
            current_state TEXT NOT NULL,
            current_reason TEXT NOT NULL,
            last_observed_at TEXT NOT NULL,
            last_visible_at TEXT,
            last_no_match_at TEXT,
            no_match_count INTEGER NOT NULL DEFAULT 0,
            no_match_streak INTEGER NOT NULL DEFAULT 0,
            next_lawful_action_at TEXT,
            latest_source_provenance_json TEXT NOT NULL DEFAULT '{}',
            contract_version TEXT NOT NULL DEFAULT 'TEST_PROTOCOL',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(network, mint_identity, pool_address)
        );
        CREATE TABLE printer_exact_market_state_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            network TEXT NOT NULL,
            mint_identity TEXT NOT NULL,
            pool_address TEXT NOT NULL,
            prior_state TEXT,
            new_state TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            next_lawful_action_at TEXT,
            source_provenance_json TEXT NOT NULL,
            contract_version TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
        """
    )
    for index in range(count):
        mint = f"Mint{index:02d}"
        pool = f"Pool{index:02d}"
        conn.execute(
            """INSERT INTO printer_exact_market_states(
                network,mint_identity,pool_address,base_mint,
                current_state,current_reason,last_observed_at,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                "solana-mainnet",
                mint,
                pool,
                mint,
                CONTRACT_BLOCKED,
                REASON_ABOVE_FLOOR_NOMINATION,
                NOW,
                NOW,
                NOW,
            ),
        )
    conn.commit()
    return conn


def execution_for(outcomes: list[str], *, failed: bool = False) -> SimpleNamespace:
    members = [] if failed else [
        {
            "mint": f"Mint{index:02d}",
            "pool": f"Pool{index:02d}",
            "batch_index": index,
            "owner": "ObservedProgram",
            "data_length": 256,
            "confirm_reason": outcome.lower(),
            "outcome": outcome,
        }
        for index, outcome in enumerate(outcomes)
    ]
    return SimpleNamespace(
        request_record=SimpleNamespace(id=101),
        response_record=None if failed else SimpleNamespace(id=201),
        failure_record=SimpleNamespace(id=301) if failed else None,
        normalized_result=SimpleNamespace(
            source_status=SourceStatus.COMPLETE,
            failure_type="TEST_SOURCE_FAILURE" if failed else None,
            normalized_payload={} if failed else {
                "members": members,
                "local_validation_steps": len(members),
            },
        ),
    )


def run_protocol(outcomes, *, failed=False, observer=None, sink=None):
    conn = make_connection(len(outcomes))
    execution = execution_for(outcomes, failed=failed)
    with (
        patch(
            "printer_v1.sources.contracts.build_governed_source_request",
            return_value=object(),
        ),
        patch(
            "printer_v1.sources.pumpswap_pool_account_batch."
            "build_pumpswap_pool_account_batch_adapter",
            return_value=object(),
        ),
        patch(
            "printer_v1.sources.governed_execution."
            "execute_source_request_with_governor",
            return_value=execution,
        ),
    ):
        report = process_protocol_confirmation_queue(
            conn,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            account_batch_transport=object(),
            stage_evidence_sink=sink,
            transport_identity_observer=None,
            local_validation_identity_observer=observer,
            stage_sequence=1,
            request_key_prefix="dtw93-protocol",
        )
    return report, conn


class DTW93LocalValidationObserverTests(unittest.TestCase):
    def test_owner_and_action_local_validation_sets_reconcile(self):
        outcomes = [
            "ACCOUNT_NOT_FOUND",
            "BASE_MINT_MISMATCH",
            "POOL_OWNER_MISMATCH",
        ]
        owner = CampaignSixUnitOwner(
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            started_at=NOW,
        )
        action = CampaignActionLocalLedger(
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
        )
        events = []

        def observer(identity):
            events.append(("observer", identity.as_dict()))
            action.observe_local_validation(identity)

        def sink(evidence):
            events.append(("sink", evidence["stage_id"]))
            owner.ingest_stage_evidence(evidence)

        report, conn = run_protocol(outcomes, observer=observer, sink=sink)
        self.addCleanup(conn.close)
        self.assertEqual(report["local_validation_steps"], 3)
        self.assertEqual(
            owner.local_validation_identities,
            action.local_validation_identities,
        )
        self.assertEqual(
            [kind for kind, _ in events],
            ["observer"] * 3 + ["sink"],
        )
        reconciled = reconcile_full_run_owner_to_action_local(
            owner,
            action,
            required_stage_kinds=("PROTOCOL_CONFIRMATION",),
        )
        self.assertTrue(reconciled["equal"], reconciled)

    def test_bound_identity_fields_and_ordinals_are_exact(self):
        outcomes = [
            "ACCOUNT_NOT_FOUND",
            "BASE_MINT_MISMATCH",
            "POOL_DATA_UNDECODABLE",
        ]
        observed = []
        sealed = []
        report, conn = run_protocol(
            outcomes,
            observer=observed.append,
            sink=sealed.append,
        )
        self.addCleanup(conn.close)
        stage_id = (
            f"{CAMPAIGN_ID}|{RUN_ID}|{CYCLE_ID}|PROTOCOL_CONFIRMATION|1"
        )
        self.assertEqual(report["local_validation_steps"], 3)
        self.assertEqual(len(observed), 3)
        self.assertEqual(len(sealed), 1)
        for index, (identity, outcome) in enumerate(
            zip(observed, outcomes), start=1
        ):
            payload = identity.as_dict()
            self.assertEqual(payload["stage_id"], stage_id)
            self.assertEqual(
                payload["subject_identity"],
                f"Mint{index - 1:02d}:Pool{index - 1:02d}",
            )
            self.assertEqual(
                payload["validation_kind"],
                f"PUMPSWAP_ACCOUNT_{outcome}",
            )
            self.assertEqual(payload["validation_ordinal"], index)
        self.assertEqual(
            sealed[0]["local_validation_identities"],
            [identity.as_dict() for identity in observed],
        )

    def test_source_failure_before_member_validation_emits_no_callback(self):
        observed = []
        sealed = []
        report, conn = run_protocol(
            ["ACCOUNT_NOT_FOUND"],
            failed=True,
            observer=observed.append,
            sink=sealed.append,
        )
        self.addCleanup(conn.close)
        self.assertEqual(report["source_requests"], 1)
        self.assertEqual(report["local_validation_steps"], 0)
        self.assertEqual(observed, [])
        self.assertEqual(sealed, [])

    def test_early_and_residual_protocol_calls_forward_observer(self):
        source = textwrap.dedent(
            inspect.getsource(
                eligible_token_supply.run_persistent_eligible_token_supply
            )
        )
        tree = ast.parse(source)
        protocol_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Name
            ):
                continue
            if node.func.id in {
                "_early_protocol",
                "process_protocol_confirmation_queue",
            }:
                protocol_calls.append(node)
        self.assertEqual(len(protocol_calls), 2)
        for call in protocol_calls:
            keywords = {kw.arg: kw.value for kw in call.keywords}
            self.assertIn("local_validation_identity_observer", keywords)
            value = keywords["local_validation_identity_observer"]
            self.assertIsInstance(value, ast.Name)
            self.assertEqual(
                value.id,
                "local_validation_identity_observer",
            )

    def test_observer_does_not_change_source_or_transport_totals(self):
        outcomes = ["ACCOUNT_NOT_FOUND", "POOL_OWNER_MISMATCH"]
        baseline_sealed = []
        baseline, conn1 = run_protocol(outcomes, sink=baseline_sealed.append)
        self.addCleanup(conn1.close)
        observed = []
        repaired_sealed = []
        repaired, conn2 = run_protocol(
            outcomes,
            observer=observed.append,
            sink=repaired_sealed.append,
        )
        self.addCleanup(conn2.close)
        for field in (
            "source_requests",
            "transport_operations",
            "batch_count",
            "source_request_ids",
            "source_response_ids",
            "source_failure_ids",
        ):
            self.assertEqual(repaired[field], baseline[field], field)
        self.assertEqual(len(observed), 2)


if __name__ == "__main__":
    unittest.main()
