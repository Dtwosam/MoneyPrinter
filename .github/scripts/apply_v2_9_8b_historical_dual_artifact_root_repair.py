from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


recovery = Path("src/printer_v1/operator_cli/operational_campaign_recovery.py")
fixture = Path("tests/test_v2_9_8b_historical_four_token_reconciliation.py")

replace_once(
    recovery,
    '''_HISTORICAL_FOUR_TOKEN_ARTIFACT_SHA256 = {\n    "application-marker.json": "1e0038b4515156244dad586d6d90692857dc53ab12f7df67d4b03a981ea4665c",\n    "git-provenance-manifest.json": "ee76043850f7569fe21d05f2770e51ac64e5de36f39362c962f09f7b7ae73f18",\n    "wrapper-terminal.json": "36312b244b335fa951e3ed9aa6799ce2e3cb15a8a2c46a6e127409e40108ccc3",\n    "child-terminal.json": "5b96652d5473120d28f1e1730c1843715fa27888af85640a774a00b0d2acd0fd",\n    "child-stderr.txt": "eab9a9236a3735658915db3a8e5bff934ae65a46d8b81caf61f6176fc4b7f504",\n    "terminal-summary.json": "21d0e6fe4046e69b15a3239caea26703c280a8303302dc85c3bd63ec3a41d7c1",\n}\n''',
    '''_HISTORICAL_FOUR_TOKEN_ARTIFACT_SHA256 = {\n    "application-marker.json": "1e0038b4515156244dad586d6d90692857dc53ab12f7df67d4b03a981ea4665c",\n    "git-provenance-manifest.json": "ee76043850f7569fe21d05f2770e51ac64e5de36f39362c962f09f7b7ae73f18",\n    "wrapper-terminal.json": "36312b244b335fa951e3ed9aa6799ce2e3cb15a8a2c46a6e127409e40108ccc3",\n    "child-terminal.json": "5b96652d5473120d28f1e1730c1843715fa27888af85640a774a00b0d2acd0fd",\n    "child-stderr.txt": "eab9a9236a3735658915db3a8e5bff934ae65a46d8b81caf61f6176fc4b7f504",\n    "terminal-summary.json": "21d0e6fe4046e69b15a3239caea26703c280a8303302dc85c3bd63ec3a41d7c1",\n}\n_HISTORICAL_APPLICATION_ARTIFACT_NAMES = (\n    "application-marker.json",\n    "git-provenance-manifest.json",\n    "wrapper-terminal.json",\n    "child-terminal.json",\n    "child-stderr.txt",\n)\n_HISTORICAL_EXECUTION_ARTIFACT_NAMES = ("terminal-summary.json",)\n''',
    "artifact ownership constants",
)

replace_once(
    recovery,
    '''def _historical_validate_artifacts(\n    artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n) -> dict[str, str]:\n    observed: dict[str, str] = {}\n    for name, expected in dict(contract.expected_artifact_sha256).items():\n        path = artifact_root / name\n        if not path.is_file():\n            raise OperationalCampaignRecoveryError(\n                f"historical artifact missing: {name}"\n            )\n        digest = _sha256(path)\n        if digest != str(expected):\n            raise OperationalCampaignRecoveryError(\n                f"historical artifact SHA mismatch: {name}"\n            )\n        observed[name] = digest\n    try:\n        child = json.loads(\n            (artifact_root / "child-stderr.txt").read_text(encoding="utf-8")\n        )\n        summary = json.loads(\n            (artifact_root / "terminal-summary.json").read_text(encoding="utf-8")\n        )\n    except (OSError, json.JSONDecodeError) as exc:\n        raise OperationalCampaignRecoveryError(\n            "historical terminal artifacts are unreadable"\n        ) from exc\n''',
    '''def _historical_validate_artifacts(\n    artifact_root: Path,\n    application_artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n) -> dict[str, str]:\n    expected = dict(contract.expected_artifact_sha256)\n    required_names = set(_HISTORICAL_APPLICATION_ARTIFACT_NAMES).union(\n        _HISTORICAL_EXECUTION_ARTIFACT_NAMES\n    )\n    if set(expected) != required_names:\n        raise OperationalCampaignRecoveryError(\n            "historical artifact contract ownership set mismatch"\n        )\n    if not artifact_root.is_dir():\n        raise OperationalCampaignRecoveryError(\n            "historical execution artifact root missing"\n        )\n    if not application_artifact_root.is_dir():\n        raise OperationalCampaignRecoveryError(\n            "historical application artifact root missing"\n        )\n\n    observed: dict[str, str] = {}\n    for name in _HISTORICAL_EXECUTION_ARTIFACT_NAMES:\n        path = artifact_root / name\n        if not path.is_file():\n            raise OperationalCampaignRecoveryError(\n                f"historical execution artifact missing: {name}"\n            )\n        digest = _sha256(path)\n        if digest != str(expected[name]):\n            raise OperationalCampaignRecoveryError(\n                f"historical artifact SHA mismatch: {name}"\n            )\n        observed[name] = digest\n    for name in _HISTORICAL_APPLICATION_ARTIFACT_NAMES:\n        path = application_artifact_root / name\n        if not path.is_file():\n            raise OperationalCampaignRecoveryError(\n                f"historical application artifact missing: {name}"\n            )\n        digest = _sha256(path)\n        if digest != str(expected[name]):\n            raise OperationalCampaignRecoveryError(\n                f"historical artifact SHA mismatch: {name}"\n            )\n        observed[name] = digest\n    try:\n        child = json.loads(\n            (application_artifact_root / "child-stderr.txt").read_text(encoding="utf-8")\n        )\n        summary = json.loads(\n            (artifact_root / "terminal-summary.json").read_text(encoding="utf-8")\n        )\n    except (OSError, json.JSONDecodeError) as exc:\n        raise OperationalCampaignRecoveryError(\n            "historical terminal artifacts are unreadable"\n        ) from exc\n''',
    "two-root artifact validator",
)

replace_once(
    recovery,
    '''def _historical_already_reconciled(\n    *,\n    db_path: Path,\n    artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n    physical_lease_path: Path,\n    lease_path_override_enabled: bool,\n) -> bool:\n''',
    '''def _historical_already_reconciled(\n    *,\n    db_path: Path,\n    artifact_root: Path,\n    application_artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n    physical_lease_path: Path,\n    lease_path_override_enabled: bool,\n) -> bool:\n''',
    "already reconciled signature",
)
replace_once(
    recovery,
    '''    if exact:\n        _historical_validate_artifacts(artifact_root, contract)\n    return exact\n''',
    '''    if exact:\n        _historical_validate_artifacts(\n            artifact_root, application_artifact_root, contract\n        )\n    return exact\n''',
    "already reconciled artifact validation",
)

replace_once(
    recovery,
    '''def _historical_preflight(\n    *,\n    db_path: Path,\n    pre_campaign_backup: Path,\n    artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n''',
    '''def _historical_preflight(\n    *,\n    db_path: Path,\n    pre_campaign_backup: Path,\n    artifact_root: Path,\n    application_artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n''',
    "preflight signature",
)
replace_once(
    recovery,
    '''    artifacts = _historical_validate_artifacts(artifact_root, contract)\n''',
    '''    artifacts = _historical_validate_artifacts(\n        artifact_root, application_artifact_root, contract\n    )\n''',
    "preflight artifact validation",
)

replace_once(
    recovery,
    '''def reconcile_exact_historical_four_token_execution(\n    *,\n    operator_approved: bool,\n    current_db: str | Path,\n    pre_campaign_backup: str | Path,\n    artifact_root: str | Path,\n    recovery_root: str | Path,\n''',
    '''def reconcile_exact_historical_four_token_execution(\n    *,\n    operator_approved: bool,\n    current_db: str | Path,\n    pre_campaign_backup: str | Path,\n    artifact_root: str | Path,\n    application_artifact_root: str | Path,\n    recovery_root: str | Path,\n''',
    "reconciliation signature",
)
replace_once(
    recovery,
    '''    baseline = Path(pre_campaign_backup).resolve()\n    artifacts = Path(artifact_root).resolve()\n    instant = now or datetime.now(timezone.utc)\n''',
    '''    baseline = Path(pre_campaign_backup).resolve()\n    artifacts = Path(artifact_root).resolve()\n    application_artifacts = Path(application_artifact_root).resolve()\n    instant = now or datetime.now(timezone.utc)\n''',
    "application root resolution",
)

# There are three exact historical already-reconciled/preflight call sites.
text = recovery.read_text(encoding="utf-8")
old = '''        artifact_root=artifacts,\n        contract=active,\n        physical_lease_path=physical_lease_path,\n'''
new = '''        artifact_root=artifacts,\n        application_artifact_root=application_artifacts,\n        contract=active,\n        physical_lease_path=physical_lease_path,\n'''
count = text.count(old)
if count != 2:
    raise SystemExit(f"already-reconciled call sites: expected two matches, found {count}")
text = text.replace(old, new)
old_preflight = '''        pre_campaign_backup=baseline,\n        artifact_root=artifacts,\n        contract=active,\n        live_process_probe=live_process_probe,\n'''
new_preflight = '''        pre_campaign_backup=baseline,\n        artifact_root=artifacts,\n        application_artifact_root=application_artifacts,\n        contract=active,\n        live_process_probe=live_process_probe,\n'''
if text.count(old_preflight) != 1:
    raise SystemExit("preflight call site mismatch")
text = text.replace(old_preflight, new_preflight, 1)
recovery.write_text(text, encoding="utf-8")

replace_once(
    fixture,
    '''        "artifact_root": root,\n        "recovery_root": tmp_path / "recovery",\n''',
    '''        "artifact_root": root,\n        "application_artifact_root": root,\n        "recovery_root": tmp_path / "recovery",\n''',
    "legacy fixture explicit application root",
)

for path in (recovery, fixture):
    path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
