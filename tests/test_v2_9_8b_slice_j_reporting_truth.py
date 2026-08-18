"""Slice J — reporting truth characterization over the real report-only seam.

This is intentionally proof-only.  It copies the committed authoritative corpus,
uses a real stored terminal campaign/report as evidence, materializes only the
matching report artifact in a temporary directory, and exercises the public
``report_only`` function.  No source, Scheduler, lifecycle, promotion, or DB
write work is permitted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.final_campaign_report import (
    FinalCampaignReportError,
    assemble_final_campaign_report,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    ALREADY_EXISTS_IDEMPOTENT,
    CLEAN_PROMOTED,
    DIRTY_OR_BLOCKED,
    NO_PROMOTION,
)
from printer_v1.operator_cli.unified_terminal_closure import REPORT_ARTIFACT_SUFFIX
from printer_v1.safety.composite import (
    SAFETY_CONTEXT_ACCEPTABLE,
    SAFETY_CONTEXT_BLOCKED,
    SAFETY_CONTEXT_UNKNOWN,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE = ROOT / "data" / "printer_v1.sqlite3"
PROMOTION_STATES = frozenset(
    {CLEAN_PROMOTED, DIRTY_OR_BLOCKED, ALREADY_EXISTS_IDEMPOTENT, NO_PROMOTION}
)
SAFETY_STATES = frozenset(
    {SAFETY_CONTEXT_ACCEPTABLE, SAFETY_CONTEXT_BLOCKED, SAFETY_CONTEXT_UNKNOWN}
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stored_terminal_candidates(db: Path) -> list[dict[str, object]]:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT report_id,campaign_id,configuration_id,report_json
               FROM printer_memory_factory_campaign_reports
               WHERE report_kind='TERMINAL' AND report_state='REPORT_TERMINAL'
               ORDER BY rowid DESC"""
        ).fetchall()
        candidates: list[dict[str, object]] = []
        for row in rows:
            try:
                stored = json.loads(str(row["report_json"]))
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(stored, dict):
                continue
            identity = stored.get("identity")
            if not isinstance(identity, dict):
                continue
            run_id = str(identity.get("run_id") or "")
            if not run_id or not isinstance(stored.get("full_run_terminal_evidence"), dict):
                continue
            config = connection.execute(
                """SELECT configuration_json
                   FROM printer_memory_factory_campaign_configurations
                   WHERE campaign_id=? AND configuration_id=?""",
                (row["campaign_id"], row["configuration_id"]),
            ).fetchone()
            if config is None:
                continue
            try:
                configuration = json.loads(str(config["configuration_json"]))
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(configuration, dict):
                continue
            report_directory_identity = str(
                configuration.get("report_directory_identity") or ""
            )
            if not report_directory_identity:
                continue
            candidates.append(
                {
                    "report_id": str(row["report_id"]),
                    "campaign_id": str(row["campaign_id"]),
                    "configuration_id": str(row["configuration_id"]),
                    "run_id": run_id,
                    "report_json": str(row["report_json"]),
                    "report_directory_identity": report_directory_identity,
                }
            )
        return candidates
    finally:
        connection.close()


class SliceJReportingTruthTests(unittest.TestCase):
    def test_public_report_only_preserves_promotion_and_safety_truth(self) -> None:
        self.assertTrue(AUTHORITATIVE.is_file(), "authoritative corpus fixture missing")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "printer_v1.sqlite3"
            shutil.copy2(AUTHORITATIVE, db)
            before_hash = _sha256(db)
            candidates = _stored_terminal_candidates(db)
            self.assertTrue(
                candidates,
                "no stored modern terminal report with full-run evidence was found",
            )

            successful: tuple[dict[str, object], dict[str, object], object] | None = None
            failures: list[str] = []
            for index, candidate in enumerate(candidates):
                artifact_root = root / f"artifacts-{index}"
                report_dir = artifact_root / "exact" / "reports"
                report_dir.mkdir(parents=True)
                artifact = report_dir / (
                    str(candidate["report_id"]) + REPORT_ARTIFACT_SUFFIX
                )
                artifact.write_text(str(candidate["report_json"]), encoding="utf-8")

                # Only the historical filesystem identity is adapted to this
                # disposable temp directory.  Report replay, identity, hashes,
                # durable reconstruction, accounting, and acceptance remain real.
                expected_directory_identity = str(
                    candidate["report_directory_identity"]
                )
                with patch.object(
                    command,
                    "report_path_identity",
                    side_effect=lambda path, expected=expected_directory_identity: expected,
                ):
                    replay = command.report_only(
                        campaign_id=str(candidate["campaign_id"]),
                        run_id=str(candidate["run_id"]),
                        db_path=db,
                        artifact_root=artifact_root,
                    )
                if replay.get("status") != "REPLAYED":
                    failures.append(
                        f"{candidate['campaign_id']}/{candidate['run_id']}:"
                        f"{replay.get('block_reason') or replay.get('status')}"
                    )
                    continue
                try:
                    assembled = assemble_final_campaign_report(
                        db,
                        campaign_id=str(candidate["campaign_id"]),
                        configuration_id=str(candidate["configuration_id"]),
                        run_id=str(candidate["run_id"]),
                    )
                except FinalCampaignReportError as exc:
                    failures.append(
                        f"{candidate['campaign_id']}/{candidate['run_id']}:"
                        f"final-report:{exc}"
                    )
                    continue
                successful = (candidate, replay, assembled)
                break

            self.assertIsNotNone(
                successful,
                "no exact stored campaign satisfied public replay + final-report truth: "
                + "; ".join(failures[:8]),
            )
            candidate, replay, assembled = successful  # type: ignore[misc]
            report = assembled.report

            promotions = report.get("promotion_outcomes_b1")
            safety_contexts = report.get("safety_contexts_b2")
            self.assertIsInstance(promotions, list)
            self.assertTrue(promotions)
            self.assertIsInstance(safety_contexts, list)
            self.assertTrue(safety_contexts)

            promotion_values = {
                str(item.get("promotion_status")) for item in promotions
            }
            safety_values = {
                str(
                    (item.get("effective_safety_context") or {}).get(
                        "effective_safety_context_result"
                    )
                )
                for item in safety_contexts
            }
            self.assertTrue(promotion_values <= PROMOTION_STATES)
            self.assertTrue(safety_values <= SAFETY_STATES)
            self.assertTrue(PROMOTION_STATES.isdisjoint(SAFETY_STATES))
            self.assertTrue(promotion_values.isdisjoint(SAFETY_STATES))
            self.assertTrue(safety_values.isdisjoint(PROMOTION_STATES))

            # Public report-only remains a zero-work action over this exact
            # campaign.  The authoritative corpus copy must remain byte-identical.
            self.assertEqual(replay["status"], "REPLAYED")
            self.assertEqual(replay["source_calls"], 0)
            self.assertEqual(replay["scheduler_runtime_calls"], 0)
            self.assertEqual(replay["database_writes"], 0)
            self.assertEqual(replay["replay_new_source_calls"], 0)
            self.assertEqual(replay["replay_new_scheduler_calls"], 0)
            self.assertFalse(replay["fallback_used"])
            self.assertEqual(
                replay["requested_identity"],
                {
                    "campaign_id": str(candidate["campaign_id"]),
                    "run_id": str(candidate["run_id"]),
                },
            )
            self.assertEqual(_sha256(db), before_hash)
            self.assertFalse(report["git_provenance_recaptured"])


if __name__ == "__main__":
    unittest.main()
