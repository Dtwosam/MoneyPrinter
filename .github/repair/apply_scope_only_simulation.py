from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ELIGIBLE = ROOT / "src/printer_v1/discovery/eligible_token_supply.py"
FRONT_DOOR = ROOT / "src/printer_v1/operator_cli/_graduated_supply_front_door_base.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one scope seam in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    ELIGIBLE,
    """    run_id: str | None = None,\n    cycle_id: str | None = None,\n    locator_runner: Callable[..., Mapping[str, Any]] | None = None,\n""",
    """    run_id: str | None = None,\n    cycle_id: str | None = None,\n    campaign_source_request_scope: Any | None = None,\n    locator_runner: Callable[..., Mapping[str, Any]] | None = None,\n""",
)

replace_once(
    ELIGIBLE,
    """    direct_acquisition_mode = str(cooperative_direct_mode or LIVE_TAIL_MODE)\n""",
    """    campaign_source_scope_obj = None\n    if campaign_source_request_scope is not None:\n        from printer_v1.discovery.permanent_discovery_availability import (\n            validate_campaign_source_request_scope,\n        )\n\n        campaign_source_scope_obj = validate_campaign_source_request_scope(\n            campaign_source_request_scope,\n            execution_id=execution_id,\n            campaign_id=campaign_id,\n            run_id=run_id,\n            cycle_id=cycle_id,\n        )\n\n    direct_acquisition_mode = str(cooperative_direct_mode or LIVE_TAIL_MODE)\n""",
)

replace_once(
    ELIGIBLE,
    """                request_key_root=str(discovery_request_key_prefix),\n            )\n""",
    """                request_key_root=str(discovery_request_key_prefix),\n                campaign_source_request_scope=campaign_source_scope_obj,\n            )\n""",
)

replace_once(
    ELIGIBLE,
    """        diagnostics = {\n            \"cooperative_phase\": cooperative_phase,\n""",
    """        diagnostics = {\n            \"cooperative_phase\": cooperative_phase,\n            \"campaign_source_request_scope\": (\n                None\n                if campaign_source_scope_obj is None\n                else campaign_source_scope_obj.as_dict()\n            ),\n""",
)

replace_once(
    FRONT_DOOR,
    """        run_id=run_id,\n        cycle_id=cycle_id,\n        locator_runner=run_fresh_profile_locator if run_locator else None,\n""",
    """        run_id=run_id,\n        cycle_id=cycle_id,\n        campaign_source_request_scope=scope_obj,\n        locator_runner=run_fresh_profile_locator if run_locator else None,\n""",
)

print("V2_9_8B_SCOPE_ONLY_SIMULATION_STAGED")
