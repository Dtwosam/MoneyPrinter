from __future__ import annotations

from pathlib import Path

COMMAND = "src/printer_v1/operator_cli/operational_memory_factory_command.py"
LIVE = "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"missing final-wiring anchor in {path}: {old[:160]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def mutate_region(path: str, start: str, end: str, fn) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    left = text.find(start)
    right = text.find(end, left + len(start))
    if left < 0 or right < 0:
        raise RuntimeError(f"missing region in {path}: {start!r} -> {end!r}")
    region = text[left:right]
    updated = fn(region)
    if updated == region:
        raise RuntimeError(f"final-wiring region was unchanged in {path}: {start!r}")
    target.write_text(text[:left] + updated + text[right:], encoding="utf-8")


# Immutable policy identity.
replace_once(
    COMMAND,
    '''class _OperationalCampaignPolicy:\n    mode: str\n    duration_seconds: int\n''',
    '''class _OperationalCampaignPolicy:\n    mode: str\n    policy_version: str\n    duration_seconds: int\n''',
)
replace_once(
    COMMAND,
    '''_NORMAL_CAMPAIGN_POLICY = _OperationalCampaignPolicy(\n    mode="run",\n    duration_seconds=TOTAL_DURATION_SECONDS,\n''',
    '''_NORMAL_CAMPAIGN_POLICY = _OperationalCampaignPolicy(\n    mode="run",\n    policy_version=POLICY_VERSION,\n    duration_seconds=TOTAL_DURATION_SECONDS,\n''',
)
replace_once(
    COMMAND,
    '''_SELECTIVE_1H_PROOF_POLICY = _OperationalCampaignPolicy(\n    mode=SELECTIVE_1H_MODE,\n    duration_seconds=SELECTIVE_1H_TOTAL_DURATION_SECONDS,\n''',
    '''_SELECTIVE_1H_PROOF_POLICY = _OperationalCampaignPolicy(\n    mode=SELECTIVE_1H_MODE,\n    policy_version=POLICY_VERSION,\n    duration_seconds=SELECTIVE_1H_TOTAL_DURATION_SECONDS,\n''',
)
replace_once(
    COMMAND,
    '''STANDARD_FOUR_HOUR_POLICY = _OperationalCampaignPolicy(\n    mode=STANDARD_FOUR_HOUR_MODE,\n    duration_seconds=STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS,\n''',
    '''STANDARD_FOUR_HOUR_POLICY = _OperationalCampaignPolicy(\n    mode=STANDARD_FOUR_HOUR_MODE,\n    policy_version=STANDARD_FOUR_HOUR_POLICY_VERSION,\n    duration_seconds=STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS,\n''',
)

# Distinct, read-only standard 4h preflight overlay. It reuses the full ordinary
# source/dependency/DB/Git preflight, then projects only the already-approved
# standard policy and outer lifecycle ceilings.
replace_once(
    COMMAND,
    '''\n\ndef _artifact_paths(\n''',
    '''\n\ndef build_standard_four_hour_preflight(\n    *,\n    db_path: str | Path | None = None,\n    repository_root: str | Path | None = None,\n    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None = None,\n) -> dict[str, Any]:\n    """Read-only preflight projection for one standard 15m -> 1h -> 4h campaign."""\n    base = build_activation_preflight(\n        db_path=db_path,\n        repository_root=repository_root,\n        git_provenance_authorization=git_provenance_authorization,\n    )\n    policy = STANDARD_FOUR_HOUR_POLICY\n    if AUTOMATIC_RETRIES != 0:\n        _preflight_fail("retry_policy", "automatic retries must remain zero")\n    if set(policy.locked_windows) != {"WINDOW_12H", "WINDOW_24H"}:\n        _preflight_fail(\n            "later_window_locks",\n            "standard four-hour operation must keep WINDOW_12H and WINDOW_24H locked",\n        )\n    return {\n        **base,\n        "mode": STANDARD_FOUR_HOUR_PREFLIGHT_MODE,\n        "status": "V2_9_8B_STANDARD_FOUR_HOUR_PREFLIGHT_READY",\n        "standard_four_hour_policy": {\n            "policy_version": policy.policy_version,\n            "campaigns": 1,\n            "cycles": 1,\n            "starting_token_maximum": TOKEN_CAPACITY,\n            "main_window": MAIN_WINDOW,\n            "main_window_seconds": MAIN_WINDOW_SECONDS,\n            "continuous_first_hour": True,\n            "continuous_four_hour": True,\n            "standard_four_hour_campaign": True,\n            "locked_windows": policy.locked_windows,\n            "automatic_retries": 0,\n            "restart_created": False,\n            "successor_created": False,\n        },\n        "standard_four_hour_ceilings": {\n            "duration_seconds": policy.duration_seconds,\n            "pre_lifecycle_acquisition_duration_seconds": (\n                policy.pre_lifecycle_acquisition_duration_seconds\n            ),\n            "governed_requests": policy.governed_request_ceiling,\n            "governed_requests_per_token": policy.governed_requests_per_token,\n            "scheduler_rows": policy.scheduler_row_ceiling,\n        },\n        "source_calls": 0,\n        "scheduler_runtime_calls": 0,\n        "database_writes": 0,\n    }\n\n\ndef _artifact_paths(\n''',
)

# Durable campaign configuration must say what the selected public policy says.
def update_create(region: str) -> str:
    region = region.replace('"policy_version": POLICY_VERSION,', '"policy_version": policy.policy_version,', 1)
    region = region.replace(
        '"continuous_four_hour": False,\n        "selective_1h_continuation":',
        '"continuous_four_hour": bool(policy.continuous_four_hour),\n        "standard_four_hour_campaign": bool(policy.standard_four_hour_campaign),\n        "selective_1h_continuation":',
        1,
    )
    count = region.count("policy_version=POLICY_VERSION")
    if count < 3:
        raise RuntimeError(f"expected at least 3 policy-version owners, found {count}")
    region = region.replace("policy_version=POLICY_VERSION", "policy_version=policy.policy_version")
    return region

mutate_region(COMMAND, "def _create_campaign_command(\n", "\n\ndef _build_pre_lifecycle_temporal_refresh_owner(", update_create)

# Standard policy gets its own preflight and retains external one-use DB binding.
replace_once(
    COMMAND,
    '''    if policy.selective_1h_continuation:\n        preflight = build_selective_1h_preflight()\n    elif disposable_proof is not None:\n''',
    '''    if policy.standard_four_hour_campaign:\n        preflight = build_standard_four_hour_preflight(\n            git_provenance_authorization=git_provenance_authorization\n        )\n    elif policy.selective_1h_continuation:\n        preflight = build_selective_1h_preflight()\n    elif disposable_proof is not None:\n''',
)
replace_once(
    COMMAND,
    '''    authorization_runtime_facts = (\n        None\n        if policy.selective_1h_continuation or disposable_proof is not None\n        else validated_authorization_runtime_facts(\n            git_provenance_authorization\n        )\n    )\n''',
    '''    authorization_runtime_facts = (\n        None\n        if (\n            disposable_proof is not None\n            or (\n                policy.selective_1h_continuation\n                and not policy.standard_four_hour_campaign\n            )\n        )\n        else validated_authorization_runtime_facts(\n            git_provenance_authorization\n        )\n    )\n''',
)

# Thread standard authority to factory and persistent live owner.
replace_once(
    COMMAND,
    '''                    "selective_1h_continuation": (\n                        policy.selective_1h_continuation\n                    ),\n                    "configuration_id": command.configuration_id,\n''',
    '''                    "selective_1h_continuation": (\n                        policy.selective_1h_continuation\n                    ),\n                    "standard_four_hour_campaign": (\n                        policy.standard_four_hour_campaign\n                    ),\n                    "configuration_id": command.configuration_id,\n''',
)
replace_once(
    COMMAND,
    '''                fifteen_minute_only=True,\n                accounting_stage_evidence_sink=_campaign_stage_evidence_sink,\n''',
    '''                fifteen_minute_only=True,\n                standard_four_hour_campaign=policy.standard_four_hour_campaign,\n                accounting_stage_evidence_sink=_campaign_stage_evidence_sink,\n''',
)

# Final public terminal projection follows immutable selected policy.
replace_once(
    COMMAND,
    '''            "selective_1h_continuation": policy.selective_1h_continuation,\n            "continuous_four_hour": False,\n            "locked_windows": policy.locked_windows,\n''',
    '''            "policy_version": policy.policy_version,\n            "selective_1h_continuation": policy.selective_1h_continuation,\n            "continuous_four_hour": policy.continuous_four_hour,\n            "standard_four_hour_campaign": policy.standard_four_hour_campaign,\n            "locked_windows": policy.locked_windows,\n''',
)

# Add the one public standard wrapper beside existing ordinary/selective wrappers.
wrapper_anchor = '''def run_selective_1h_proof(\n'''
standard_wrapper = '''def run_standard_four_hour_campaign(\n    *,\n    operator_approved: bool,\n    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None,\n    owner: Any | None = None,\n    pump_transport: Any | None = None,\n    secondary_transport: Any | None = None,\n    migration_transport: Any | None = None,\n) -> dict[str, Any]:\n    """Run one externally authorized production-persistent standard 4h campaign."""\n    return _run_operational_campaign(\n        policy=STANDARD_FOUR_HOUR_POLICY,\n        operator_approved=operator_approved,\n        owner=owner,\n        pump_transport=pump_transport,\n        secondary_transport=secondary_transport,\n        migration_transport=migration_transport,\n        git_provenance_authorization=git_provenance_authorization,\n    )\n\n\n'''
replace_once(COMMAND, wrapper_anchor, standard_wrapper + wrapper_anchor)

# Public dispatch: standard preflight uses standard projection; standard run is
# no longer blocked once it reaches the exact wrapper-bound authorization path.
replace_once(
    COMMAND,
    '''        if args.mode == STANDARD_FOUR_HOUR_MODE:\n            raise OperationalMemoryFactoryError(\n                "standard four-hour run is not active until one-shot/factory authority integration passes"\n            )\n        if args.mode == STANDARD_FOUR_HOUR_PREFLIGHT_MODE:\n            result = build_activation_preflight(\n                git_provenance_authorization=git_provenance_authorization\n            )\n''',
    '''        if args.mode == STANDARD_FOUR_HOUR_PREFLIGHT_MODE:\n            result = build_standard_four_hour_preflight(\n                git_provenance_authorization=git_provenance_authorization\n            )\n''',
)
replace_once(
    COMMAND,
    '''        elif args.mode == "run":\n            result = run_operational_campaign(\n                operator_approved=args.operator_approved,\n                git_provenance_authorization=git_provenance_authorization,\n            )\n        elif args.mode == SELECTIVE_1H_MODE:\n''',
    '''        elif args.mode == "run":\n            result = run_operational_campaign(\n                operator_approved=args.operator_approved,\n                git_provenance_authorization=git_provenance_authorization,\n            )\n        elif args.mode == STANDARD_FOUR_HOUR_MODE:\n            result = run_standard_four_hour_campaign(\n                operator_approved=args.operator_approved,\n                git_provenance_authorization=git_provenance_authorization,\n            )\n        elif args.mode == SELECTIVE_1H_MODE:\n''',
)

# Live owner keeps production-persistent mode while explicitly enabling the
# standard first-hour/four-hour path. The old proof mode stays separate.
replace_once(
    LIVE,
    '''        stop_before_lifecycle: bool = False,\n        fifteen_minute_only: bool = False,\n        accounting_stage_evidence_sink: (\n''',
    '''        stop_before_lifecycle: bool = False,\n        fifteen_minute_only: bool = False,\n        standard_four_hour_campaign: bool = False,\n        accounting_stage_evidence_sink: (\n''',
)
replace_once(
    LIVE,
    '''        lk = dict(lifecycle_kwargs or {})\n        if fifteen_minute_only:\n''',
    '''        lk = dict(lifecycle_kwargs or {})\n        if standard_four_hour_campaign and not fifteen_minute_only:\n            raise LiveOperationalError(\n                "STANDARD_FOUR_HOUR_REQUIRES_OPERATIONAL_PERSISTENT_MODE",\n                "standard four-hour campaign requires fifteen_minute_only persistent authority",\n            )\n        if standard_four_hour_campaign:\n            lk["standard_four_hour_campaign"] = True\n        if fifteen_minute_only:\n''',
)
replace_once(
    LIVE,
    '''            proof_mode=not fifteen_minute_only,\n            continuous_first_hour=not fifteen_minute_only,\n            continuous_four_hour=not fifteen_minute_only,\n            four_hour_proof_mode=not fifteen_minute_only,\n            operational_persistent_mode=fifteen_minute_only,\n''',
    '''            proof_mode=not fifteen_minute_only,\n            continuous_first_hour=(\n                not fifteen_minute_only or standard_four_hour_campaign\n            ),\n            continuous_four_hour=(\n                not fifteen_minute_only or standard_four_hour_campaign\n            ),\n            four_hour_proof_mode=(\n                not fifteen_minute_only and not standard_four_hour_campaign\n            ),\n            operational_persistent_mode=fifteen_minute_only,\n''',
)
