from pathlib import Path

path = Path("src/printer_v1/operator_cli/operational_campaign_recovery.py")
text = path.read_text(encoding="utf-8")
old = '''        for index, row in enumerate(queues):
            if tuple(row) != (
                int(contract.expected_queue_ids[index]),
                "TRACK_NORMAL",
                "PROMOTE_TO_TRACK_NORMAL",
                "combined_discovery_handoff",
                "QUEUED",
                "COMPLETE",
                "CLEAN_DATA",
                None,
            ):
                raise OperationalCampaignRecoveryError(
                    "historical tracking queue state drifted"
                )

        zero_counts = {
'''
new = '''        for index, row in enumerate(queues):
            if tuple(row) != (
                int(contract.expected_queue_ids[index]),
                "TRACK_NORMAL",
                "PROMOTE_TO_TRACK_NORMAL",
                "combined_discovery_handoff",
                "QUEUED",
                "COMPLETE",
                "CLEAN_DATA",
                None,
            ):
                raise OperationalCampaignRecoveryError(
                    "historical tracking queue state drifted"
                )

        nonterminal_discovery_batches = 0
        if _historical_table_exists(connection, "printer_discovery_batches"):
            nonterminal_discovery_batches = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_batches "
                    "WHERE campaign_id=? AND run_id=? "
                    "AND batch_state NOT LIKE 'TERMINAL_%'",
                    (contract.campaign_id, contract.run_id),
                ).fetchone()[0]
            )
        if nonterminal_discovery_batches:
            raise OperationalCampaignRecoveryError(
                "historical nonterminal discovery batch exists"
            )

        zero_counts = {
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one preflight insertion point, found {text.count(old)}")
path.write_text(text.replace(old, new, 1).rstrip() + "\n", encoding="utf-8")
