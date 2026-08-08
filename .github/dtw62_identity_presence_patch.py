from pathlib import Path

path = Path("scripts/v2_9_8b_checkpoint8_independent_inspection.py")
text = path.read_text(encoding="utf-8")

old_terminal = '''        report_payload = _json_dict(report_json, "REPORT_HASH_MISMATCH")
        report_evidence = report_payload.get("full_run_terminal_evidence")
        report_evidence = (
            report_evidence if isinstance(report_evidence, dict) else report_payload
        )
        report_identity = report_evidence.get("identity")
        report_identity = report_identity if isinstance(report_identity, dict) else {}
        outer_report_identity = report_payload.get("identity")
        outer_report_identity = (
            outer_report_identity if isinstance(outer_report_identity, dict) else {}
        )

        expected_identity = {
            "campaign_id": campaign_id,
            "campaign_run_id": campaign_run_id,
            "configuration_id": configuration_id,
            "cycle_id": cycle_id,
            "factory_run_id": factory_run_id,
            "supervision_id": supervision_id,
        }
        for key, expected in expected_identity.items():
            aliases = (key, "run_id") if key == "campaign_run_id" else (key,)
            values = [
                _text(identity.get(alias))
                for identity in (report_identity, outer_report_identity)
                for alias in aliases
                if identity.get(alias) not in (None, "")
            ]
            if values and any(value != expected for value in values):
                raise Checkpoint8IndependentInspectionError(
                    "TERMINAL_REPORT_IDENTITY_MISMATCH"
                )

        execution_id = _text(report_identity.get("execution_id")) or _text(
            outer_report_identity.get("execution_id")
        ) or _text(replay_identity.get("execution_id"))
        if not execution_id:
            raise Checkpoint8IndependentInspectionError(
                "TERMINAL_REPORT_IDENTITY_MISMATCH"
            )
'''

new_terminal = '''        report_payload = _json_dict(report_json, "REPORT_HASH_MISMATCH")
        report_evidence = report_payload.get("full_run_terminal_evidence")
        if not isinstance(report_evidence, dict):
            raise Checkpoint8IndependentInspectionError(
                "TERMINAL_REPORT_IDENTITY_MISSING"
            )
        report_identity = report_evidence.get("identity")
        if not isinstance(report_identity, dict):
            raise Checkpoint8IndependentInspectionError(
                "TERMINAL_REPORT_IDENTITY_MISSING"
            )
        outer_report_identity = report_payload.get("identity")
        outer_report_identity = (
            outer_report_identity if isinstance(outer_report_identity, dict) else {}
        )

        expected_identity = {
            "campaign_id": campaign_id,
            "campaign_run_id": campaign_run_id,
            "configuration_id": configuration_id,
            "cycle_id": cycle_id,
            "factory_run_id": factory_run_id,
            "supervision_id": supervision_id,
        }
        for key in (*expected_identity, "execution_id"):
            if not _text(report_identity.get(key)):
                raise Checkpoint8IndependentInspectionError(
                    "TERMINAL_REPORT_IDENTITY_MISSING"
                )
        for key, expected in expected_identity.items():
            if _text(report_identity.get(key)) != expected:
                raise Checkpoint8IndependentInspectionError(
                    "TERMINAL_REPORT_IDENTITY_MISMATCH"
                )

        execution_id = _text(report_identity.get("execution_id"))
        outer_expected_identity = {**expected_identity, "execution_id": execution_id}
        for key, expected in outer_expected_identity.items():
            aliases = (key, "run_id") if key == "campaign_run_id" else (key,)
            values = [
                _text(outer_report_identity.get(alias))
                for alias in aliases
                if outer_report_identity.get(alias) not in (None, "")
            ]
            if values and any(value != expected for value in values):
                raise Checkpoint8IndependentInspectionError(
                    "TERMINAL_REPORT_IDENTITY_MISMATCH"
                )
'''

assert old_terminal in text
text = text.replace(old_terminal, new_terminal, 1)

old_replay = '''    replay_evidence = replay.get("full_run_terminal_evidence")
    replay_evidence = replay_evidence if isinstance(replay_evidence, dict) else {}
    replay_identity = replay_evidence.get("identity")
    replay_identity = replay_identity if isinstance(replay_identity, dict) else {}
    if replay_identity:
        if (
            str(replay_identity.get("campaign_id") or "").strip() != campaign_id
            or str(replay_identity.get("campaign_run_id") or "").strip()
            != campaign_run_id
        ):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISMATCH"
            )

    if reconstructed_identity:
        for key in (
            "configuration_id",
            "cycle_id",
            "factory_run_id",
            "supervision_id",
            "execution_id",
        ):
            expected = str(reconstructed_identity.get(key) or "").strip()
            observed = str(replay_identity.get(key) or "").strip()
            if expected and observed and observed != expected:
                raise Checkpoint8IndependentInspectionError(
                    "REPORT_REPLAY_IDENTITY_MISMATCH"
                )
'''

new_replay = '''    replay_evidence = replay.get("full_run_terminal_evidence")
    if reconstructed_identity is not None:
        if not isinstance(replay_evidence, dict):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISSING"
            )
        replay_identity = replay_evidence.get("identity")
        if not isinstance(replay_identity, dict):
            raise Checkpoint8IndependentInspectionError(
                "REPORT_REPLAY_IDENTITY_MISSING"
            )
        expected_replay_identity = {
            "campaign_id": campaign_id,
            "campaign_run_id": campaign_run_id,
            "configuration_id": str(
                reconstructed_identity.get("configuration_id") or ""
            ).strip(),
            "cycle_id": str(reconstructed_identity.get("cycle_id") or "").strip(),
            "factory_run_id": str(
                reconstructed_identity.get("factory_run_id") or ""
            ).strip(),
            "supervision_id": str(
                reconstructed_identity.get("supervision_id") or ""
            ).strip(),
            "execution_id": str(
                reconstructed_identity.get("execution_id") or ""
            ).strip(),
        }
        for key, expected in expected_replay_identity.items():
            observed = str(replay_identity.get(key) or "").strip()
            if not observed:
                raise Checkpoint8IndependentInspectionError(
                    "REPORT_REPLAY_IDENTITY_MISSING"
                )
            if not expected or observed != expected:
                raise Checkpoint8IndependentInspectionError(
                    "REPORT_REPLAY_IDENTITY_MISMATCH"
                )
    else:
        replay_evidence = (
            replay_evidence if isinstance(replay_evidence, dict) else {}
        )
        replay_identity = replay_evidence.get("identity")
        replay_identity = replay_identity if isinstance(replay_identity, dict) else {}
        if replay_identity:
            if (
                str(replay_identity.get("campaign_id") or "").strip() != campaign_id
                or str(replay_identity.get("campaign_run_id") or "").strip()
                != campaign_run_id
            ):
                raise Checkpoint8IndependentInspectionError(
                    "REPORT_REPLAY_IDENTITY_MISMATCH"
                )
'''

assert old_replay in text
text = text.replace(old_replay, new_replay, 1)

old_expectation = '''    authorization = replay_evidence.get("authorization_and_invocation")
    authorization = authorization if isinstance(authorization, dict) else {}
    proof_expectation = authorization.get("proof_expectation")
    proof_expectation = (
        proof_expectation if isinstance(proof_expectation, dict) else {}
    )
    expectation_manifest = str(
        proof_expectation.get("fixture_composition_manifest_sha256") or ""
    ).strip()
    if expectation_manifest:
        manifest_values.append(expectation_manifest)
    if any(value != manifest for value in manifest_values):
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_MANIFEST_IDENTITY_MISMATCH"
        )
    proof_id = str(frozen_summary.get("proof_id") or "").strip()
    expectation_proof_id = str(proof_expectation.get("proof_id") or "").strip()
    if expectation_proof_id and expectation_proof_id != proof_id:
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_MANIFEST_IDENTITY_MISMATCH"
        )
'''

new_expectation = '''    authorization = replay_evidence.get("authorization_and_invocation")
    if reconstructed_identity is not None and not isinstance(authorization, dict):
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_PROOF_EXPECTATION_IDENTITY_MISSING"
        )
    authorization = authorization if isinstance(authorization, dict) else {}
    proof_expectation = authorization.get("proof_expectation")
    if reconstructed_identity is not None and not isinstance(proof_expectation, dict):
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_PROOF_EXPECTATION_IDENTITY_MISSING"
        )
    proof_expectation = (
        proof_expectation if isinstance(proof_expectation, dict) else {}
    )
    expectation_manifest = str(
        proof_expectation.get("fixture_composition_manifest_sha256") or ""
    ).strip()
    proof_id = str(frozen_summary.get("proof_id") or "").strip()
    expectation_proof_id = str(proof_expectation.get("proof_id") or "").strip()
    if reconstructed_identity is not None and (
        not expectation_manifest or not expectation_proof_id
    ):
        raise Checkpoint8IndependentInspectionError(
            "REPORT_REPLAY_PROOF_EXPECTATION_IDENTITY_MISSING"
        )
    if expectation_manifest:
        manifest_values.append(expectation_manifest)
    if any(value != manifest for value in manifest_values):
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_MANIFEST_IDENTITY_MISMATCH"
        )
    if expectation_proof_id and expectation_proof_id != proof_id:
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_MANIFEST_IDENTITY_MISMATCH"
        )
'''

assert old_expectation in text
text = text.replace(old_expectation, new_expectation, 1)

compile(text, str(path), "exec")
path.write_text(text, encoding="utf-8")
