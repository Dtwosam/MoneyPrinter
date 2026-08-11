from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACTORY = ROOT / "src/printer_v1/operator_cli/one_command_15m_factory.py"
STANDARD_4H = ROOT / "src/printer_v1/operator_cli/operational_standard_4h.py"


def replace_once(text: str, before: str, after: str, label: str) -> str:
    count = text.count(before)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one occurrence, found {count}")
    return text.replace(before, after, 1)


def replace_in_region(
    text: str,
    *,
    start_marker: str,
    end_marker: str,
    replacements: list[tuple[str, str, str]],
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"missing region start: {start_marker}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f"missing region end: {end_marker}")
    region = text[start:end]
    for before, after, label in replacements:
        region = replace_once(region, before, after, label)
    return text[:start] + region + text[end:]


def patch_factory() -> None:
    text = FACTORY.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from printer_v1.sources.measured_transport import (\n"
        "    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND,\n"
        "    PRECLOSE_CONTEXT_REQUEST_COUNT,\n"
        ")",
        "from printer_v1.sources.measured_transport import (\n"
        "    FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,\n"
        "    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND,\n"
        "    PRECLOSE_CONTEXT_REQUEST_COUNT,\n"
        ")",
        "measured-transport import",
    )
    text = replace_once(
        text,
        "_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = (\n"
        "    _MAX_GOVERNED_REQUESTS_PER_TOKEN\n"
        "    + _continuation_expected_snapshots(\"TRACK_FAST\")\n"
        ")",
        "_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = (\n"
        "    _MAX_GOVERNED_REQUESTS_PER_TOKEN\n"
        "    + _continuation_expected_snapshots(\"TRACK_FAST\")\n"
        "    + FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT\n"
        ")",
        "continuous first-hour request ceiling",
    )

    text = replace_in_region(
        text,
        start_marker="def _lifecycle_reservation_records_for_step(",
        end_marker="\ndef _observe_scheduler_terminal(",
        replacements=[
            (
                "        elif step_kind == \"CONTINUATION_CLOSE\":\n"
                "            family = \"CONTINUATION_CLOSE_OBSERVATION\"",
                "        elif step_kind == \"CONTINUATION_CLOSE\":\n"
                "            family = (\n"
                "                \"CONTINUATION_CLOSE_OBSERVATION\"\n"
                "                if reservation_index == 0\n"
                "                else \"FIRST_HOUR_SAFETY_CONTEXT\"\n"
                "            )",
                "first-hour reservation families",
            )
        ],
    )

    text = replace_in_region(
        text,
        start_marker="def _execute_continuation_close(",
        end_marker="\ndef _derive_and_persist_four_hour_outcome(",
        replacements=[
            (
                "    timeout_seconds: float,\n"
                "    fallback_adapter_factory: Callable[..., Any] | None = None,",
                "    timeout_seconds: float,\n"
                "    context_adapter_factories: dict[str, Callable[..., Any]] | None = None,\n"
                "    fallback_adapter_factory: Callable[..., Any] | None = None,",
                "continuation-close context adapter dependency",
            ),
            (
                "    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline\n\n"
                "    _check_cancellation(cancellation_probe)\n"
                "    result = _execute_snapshot(",
                "    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline\n"
                "    from printer_v1.operator_cli.first_hour_safety_binding import (\n"
                "        attach_first_hour_safety_overlay,\n"
                "    )\n\n"
                "    context_bundle = _collect_preclose_context(\n"
                "        conn,\n"
                "        step,\n"
                "        timeout_seconds=timeout_seconds,\n"
                "        adapter_factories=context_adapter_factories,\n"
                "        include=frozenset({\"safety\"}),\n"
                "        cancellation_probe=cancellation_probe,\n"
                "    )\n"
                "    _check_cancellation(cancellation_probe)\n"
                "    result = _execute_snapshot(",
                "fresh first-hour safety collection",
            ),
            (
                "    if not result.get(\"ok\"):\n"
                "        return result\n"
                "    first = conn.execute(",
                "    if not result.get(\"ok\"):\n"
                "        return result\n"
                "    result[\"governed_context_collection\"] = context_bundle[\"report\"]\n"
                "    result[\"governed_context_persistence\"] = _persist_preclose_context(\n"
                "        conn,\n"
                "        step=step,\n"
                "        snapshot_id=int(result[\"snapshot_id\"]),\n"
                "        context_bundle=context_bundle,\n"
                "    )\n"
                "    first = conn.execute(",
                "first-hour safety persistence",
            ),
            (
                "    if window_id is None:\n"
                "        result.update(ok=False, blocked_reason=\"1h close produced no window\")\n"
                "        return result\n"
                "    result[\"full_first_hour_outcome\"] = _derive_and_persist_first_hour_outcome(",
                "    if window_id is None:\n"
                "        result.update(ok=False, blocked_reason=\"1h close produced no window\")\n"
                "        return result\n"
                "    result[\"first_hour_safety_binding\"] = attach_first_hour_safety_overlay(\n"
                "        conn,\n"
                "        step=step,\n"
                "        memory_window_id=int(window_id),\n"
                "        closing_snapshot_id=int(result[\"snapshot_id\"]),\n"
                "        persisted_context=result[\"governed_context_persistence\"],\n"
                "    )\n"
                "    result[\"full_first_hour_outcome\"] = _derive_and_persist_first_hour_outcome(",
                "exact first-hour safety binding",
            ),
        ],
    )

    text = replace_once(
        text,
        "                        adapter_factory=adapter_factory,\n"
        "                        timeout_seconds=timeout_seconds,\n"
        "                        fallback_adapter_factory=fallback_factory,\n"
        "                        cancellation_probe=cancellation_probe,\n"
        "                    )\n"
        "                elif str(pending[\"step_kind\"]).startswith(\"LONG_CONTINUATION_\"):",
        "                        adapter_factory=adapter_factory,\n"
        "                        timeout_seconds=timeout_seconds,\n"
        "                        context_adapter_factories=context_adapter_factories,\n"
        "                        fallback_adapter_factory=fallback_factory,\n"
        "                        cancellation_probe=cancellation_probe,\n"
        "                    )\n"
        "                elif str(pending[\"step_kind\"]).startswith(\"LONG_CONTINUATION_\"):",
        "continuation-close context adapter wiring",
    )

    FACTORY.write_text(text, encoding="utf-8")


def patch_standard_4h() -> None:
    text = STANDARD_4H.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "LIFECYCLE_REQUEST_OUTER_CEILING = 230",
        "LIFECYCLE_REQUEST_OUTER_CEILING = 236",
        "standard-four-hour outer request ceiling",
    )
    STANDARD_4H.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_factory()
    patch_standard_4h()
    print("Applied exact V2-9.8B first-hour safety/provenance repair patch.")
