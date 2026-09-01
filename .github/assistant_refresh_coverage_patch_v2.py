from __future__ import annotations

import assistant_refresh_coverage_patch as base


def corrected_replace_count(path: str, old: str, new: str, expected: int) -> None:
    if (
        path == "src/printer_v1/operator_cli/pre_lifecycle_persistent_refresh_owner.py"
        and expected == 2
    ):
        base.replace_once(path, old, new)
        completed_old = (
            "channels_skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) "
            "if isinstance(x,Mapping)),newly_observed_exact_identities="
        )
        completed_new = (
            "channels_skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) "
            "if isinstance(x,Mapping)),source_request_coverage=coverage,"
            "newly_observed_exact_identities="
        )
        base.replace_once(path, completed_old, completed_new)
        return
    base.replace_count(path, old, new, expected)


base.replace_count = corrected_replace_count
base.apply_patch()
