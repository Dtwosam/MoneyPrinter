from pathlib import Path

path = Path("scripts/v2_9_8b_checkpoint8_independent_inspection.py")
text = path.read_text(encoding="utf-8")

old = '''    requested_identity = replay.get("requested_identity")
    if isinstance(requested_identity, dict):
        if replay.get("status") != "REPLAYED" or replay.get("mode") != "REPORT_ONLY":
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
        if (
            str(requested_identity.get("campaign_id") or "").strip() != campaign_id
            or str(requested_identity.get("run_id") or "").strip()
            != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
    else:
        if (
            str(replay.get("campaign_id") or "").strip() != campaign_id
            or str(replay.get("run_id") or "").strip() != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
'''

new = '''    requested_identity = replay.get("requested_identity")
    if reconstructed_identity is not None:
        if not isinstance(requested_identity, dict):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_REQUESTED_IDENTITY_MISSING"
            )
        requested_campaign_id = str(
            requested_identity.get("campaign_id") or ""
        ).strip()
        requested_run_id = str(requested_identity.get("run_id") or "").strip()
        if not requested_campaign_id or not requested_run_id:
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_REQUESTED_IDENTITY_MISSING"
            )
        if replay.get("status") != "REPLAYED" or replay.get("mode") != "REPORT_ONLY":
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
        if (
            requested_campaign_id != campaign_id
            or requested_run_id != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
    elif isinstance(requested_identity, dict):
        if replay.get("status") != "REPLAYED" or replay.get("mode") != "REPORT_ONLY":
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
        if (
            str(requested_identity.get("campaign_id") or "").strip() != campaign_id
            or str(requested_identity.get("run_id") or "").strip()
            != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
    else:
        if (
            str(replay.get("campaign_id") or "").strip() != campaign_id
            or str(replay.get("run_id") or "").strip() != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )
'''

assert old in text
text = text.replace(old, new, 1)
compile(text, str(path), "exec")
path.write_text(text, encoding="utf-8")
