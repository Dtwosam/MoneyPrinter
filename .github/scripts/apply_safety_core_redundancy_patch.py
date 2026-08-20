from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"PATCH_ANCHOR_MISSING:{path}:{old[:80]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"PATCH_ANCHOR_AMBIGUOUS:{path}:{text.count(old)}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# 15m policy: metadata is useful source coverage, but its absence is not a hard
# gate. Explicit mutable metadata remains an observed danger and still blocks.
goplus = "src/printer_v1/safety/goplus_normalizer.py"
replace_once(
    goplus,
    '''HARD_SAFETY_FIELD_EXPECTATIONS: dict[str, str] = {
    "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
    "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
    "metadata_mutability_status": "METADATA_IMMUTABLE",
    "supply_sanity_label": "SUPPLY_SANITY_OK",
    "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
}
''',
    '''HARD_SAFETY_FIELD_EXPECTATIONS: dict[str, str] = {
    "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
    "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
    "supply_sanity_label": "SUPPLY_SANITY_OK",
    "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
}
''',
)
replace_once(
    goplus,
    '''SOURCE_COVERAGE_PENDING_VALUES: dict[str, str] = {
    "holder_concentration_label": "HOLDER_CONCENTRATION_UNKNOWN",
    "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_UNKNOWN",
    "known_risk_flag_label": "KNOWN_RISK_FLAGS_UNKNOWN",
}
''',
    '''SOURCE_COVERAGE_PENDING_VALUES: dict[str, str] = {
    "metadata_mutability_status": "METADATA_UNKNOWN",
    "holder_concentration_label": "HOLDER_CONCENTRATION_UNKNOWN",
    "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_UNKNOWN",
    "known_risk_flag_label": "KNOWN_RISK_FLAGS_UNKNOWN",
}
''',
)
replace_once(
    goplus,
    '''    for field in ("liquidity_lock_or_burn_label", "known_risk_flag_label"):
''',
    '''    for field in (
        "metadata_mutability_status",
        "liquidity_lock_or_burn_label",
        "known_risk_flag_label",
    ):
''',
)

# Composite: accept one independent Solana mint-account contribution and merge
# only the four chain-provable hard fields. Conflicts become UNKNOWN and block.
composite = "src/printer_v1/safety/composite.py"
replace_once(composite, "MAX_CONTRIBUTIONS = 2\n", "MAX_CONTRIBUTIONS = 3\n")
replace_once(
    composite,
    '''    goplus_execution: Any,
    holder_execution: Any | None = None,
    memory_window_id: int | None = None,
''',
    '''    goplus_execution: Any,
    holder_execution: Any | None = None,
    core_solana_execution: Any | None = None,
    memory_window_id: int | None = None,
''',
)
replace_once(
    composite,
    '''    holder_labels: list[tuple[str, str]] = []
''',
    '''    core_conflicts: list[str] = []
    core_bindings: dict[str, str | None] = {}
    if core_solana_execution is not None:
        core_payload = dict(
            core_solana_execution.normalized_result.normalized_payload or {}
        )
        core_fields = {
            field: core_payload.get(field)
            for field in (
                "mint_authority_status",
                "freeze_authority_status",
                "supply_sanity_label",
                "token_program_label",
            )
        }
        core_contribution = _execution_contribution(
            connection,
            core_solana_execution,
            category="TOKEN_CORE_SAFETY",
            token_mint=token_mint,
            pair_address=pair_address,
            fields=core_fields,
            evaluated_at=evaluated,
        )
        contributions.append(core_contribution)
        if core_contribution["usable"]:
            unknown_values = {
                "mint_authority_status": "MINT_AUTHORITY_UNKNOWN",
                "freeze_authority_status": "FREEZE_AUTHORITY_UNKNOWN",
                "supply_sanity_label": "SUPPLY_SANITY_UNKNOWN",
                "token_program_label": "TOKEN_PROGRAM_UNKNOWN",
            }
            conflict_labels = {
                "mint_authority_status": "MINT_AUTHORITY_SOURCE_CONFLICT",
                "freeze_authority_status": "FREEZE_AUTHORITY_SOURCE_CONFLICT",
                "supply_sanity_label": "SUPPLY_SANITY_SOURCE_CONFLICT",
                "token_program_label": "TOKEN_PROGRAM_SOURCE_CONFLICT",
            }
            goplus_usable = contributions[0]["usable"]
            for field, unknown_value in unknown_values.items():
                core_value = core_fields.get(field)
                if core_value in {None, "", unknown_value}:
                    continue
                existing = base.get(field)
                if not goplus_usable or existing in {None, "", unknown_value}:
                    base[field] = core_value
                    core_bindings[field] = "solana_rpc"
                elif existing != core_value:
                    core_conflicts.append(conflict_labels[field])
                    base[field] = unknown_value
                    core_bindings[field] = None
                else:
                    # Chain-native proof is the authoritative binding when both
                    # approved sources agree on the same chain fact.
                    core_bindings[field] = "solana_rpc"

    holder_labels: list[tuple[str, str]] = []
''',
)
replace_once(
    composite,
    '''    conflicts: list[str] = []
''',
    '''    conflicts: list[str] = list(core_conflicts)
''',
)
replace_once(
    composite,
    '''    field_bindings = {
        field: "goplus"
        for field in SAFETY_FIELDS
        if field != "holder_concentration_label"
    }
''',
    '''    field_bindings = {
        field: "goplus" if contributions[0]["usable"] else None
        for field in SAFETY_FIELDS
        if field != "holder_concentration_label"
    }
    field_bindings.update(core_bindings)
''',
)
replace_once(
    composite,
    '''    blockers = list(policy["hard_blocking_safety_fields"])
    if not contributions[0]["usable"]:
        blockers.append("GOPLUS_MANDATORY_SAFETY_SOURCE_NOT_USABLE")
    for contribution in contributions[1:]:
        if contribution["rejection_reason"] == "SOURCE_TRACE_MISMATCH":
            blockers.append("HOLDER_EVIDENCE_PROVENANCE_INVALID")
        elif contribution["rejection_reason"] == "TARGET_MINT_MISMATCH":
            blockers.append("HOLDER_EVIDENCE_TARGET_MISMATCH")
''',
    '''    blockers = list(policy["hard_blocking_safety_fields"])
    for contribution in contributions[1:]:
        category = contribution["evidence_category"]
        if category == "TOKEN_CORE_SAFETY":
            if contribution["rejection_reason"] == "SOURCE_TRACE_MISMATCH":
                blockers.append("CORE_SAFETY_EVIDENCE_PROVENANCE_INVALID")
            elif contribution["rejection_reason"] == "TARGET_MINT_MISMATCH":
                blockers.append("CORE_SAFETY_EVIDENCE_TARGET_MISMATCH")
        elif category == "HOLDER_CONCENTRATION":
            if contribution["rejection_reason"] == "SOURCE_TRACE_MISMATCH":
                blockers.append("HOLDER_EVIDENCE_PROVENANCE_INVALID")
            elif contribution["rejection_reason"] == "TARGET_MINT_MISMATCH":
                blockers.append("HOLDER_EVIDENCE_TARGET_MISMATCH")
''',
)
replace_once(
    composite,
    '''    for contribution in contributions[1:]:
        if contribution["rejection_reason"] == "SAFETY_EVIDENCE_STALE":
            optional_unknowns.append("HOLDER_CONDITION_STALE")
''',
    '''    for contribution in contributions[1:]:
        if (
            contribution["evidence_category"] == "HOLDER_CONCENTRATION"
            and contribution["rejection_reason"] == "SAFETY_EVIDENCE_STALE"
        ):
            optional_unknowns.append("HOLDER_CONDITION_STALE")
''',
)
replace_once(
    composite,
    '''        "safety_contract_label": contract_label,
        "holder_concentration_label": base["holder_concentration_label"],
''',
    '''        "safety_contract_label": contract_label,
        "mint_authority_status": base["mint_authority_status"],
        "freeze_authority_status": base["freeze_authority_status"],
        "metadata_mutability_status": base["metadata_mutability_status"],
        "supply_sanity_label": base["supply_sanity_label"],
        "token_program_label": base["token_program_label"],
        "holder_concentration_label": base["holder_concentration_label"],
''',
)
replace_once(
    composite,
    '''        "optional_unknowns": optional_unknowns,
        "inserted": True,
''',
    '''        "optional_unknowns": optional_unknowns,
        "field_bindings": field_bindings,
        "inserted": True,
''',
)

# Lifecycle / holder arithmetic: one additional governed mint-account request,
# one additional actual RPC transport operation, no cadence or scheduler job.
measured = "src/printer_v1/sources/measured_transport.py"
replace_once(
    measured,
    '''# its exact-pair close observation plus the worst-case fresh first-hour safety
# bundle: GoPlus + holder primary + one approved holder backup.
PRECLOSE_CONTEXT_REQUEST_COUNT = 5
FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3
''',
    '''# its exact-pair close observation plus the worst-case fresh first-hour safety
# bundle: GoPlus + Solana core mint-account + holder primary + one approved
# holder backup.
PRECLOSE_CONTEXT_REQUEST_COUNT = 6
FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 4
''',
)
holder_budget = "src/printer_v1/operator_cli/holder_reliability_budget_control.py"
replace_once(
    holder_budget,
    '''HOLDER_WORST_CASE_GOVERNED_REQUESTS = 3
HOLDER_WORST_CASE_TRANSPORT_OPERATIONS = 5
''',
    '''HOLDER_WORST_CASE_GOVERNED_REQUESTS = 4
HOLDER_WORST_CASE_TRANSPORT_OPERATIONS = 6
''',
)

# Factory collection: add one core safety adapter/request inside the existing
# scheduled safety step. Explicit fixture callers that do not provide the new
# adapter remain offline and do not accidentally contact RPC.
factory = "src/printer_v1/operator_cli/one_command_15m_factory.py"
replace_once(
    factory,
    '''    from printer_v1.sources.solana_rpc_holder import (
        build_solana_rpc_holder_adapter,
        build_solana_rpc_holder_transport,
    )
''',
    '''    from printer_v1.sources.solana_rpc_holder import (
        build_solana_rpc_holder_adapter,
        build_solana_rpc_holder_transport,
    )
    from printer_v1.sources.solana_rpc_token_safety import (
        SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND,
        build_solana_rpc_token_safety_adapter,
        build_solana_rpc_token_safety_transport,
    )
''',
)
replace_once(
    factory,
    '''    quote_factory = factories.get("jupiter_quote")
''',
    '''    core_safety_factory = factories.get("solana_rpc_core_safety")
    core_safety_adapter = None
    if core_safety_factory is not None:
        core_safety_adapter = require_concrete_adapter(
            "preclose_solana_rpc_core_safety",
            holder_factory_call(
                core_safety_factory,
                token_mint=mint,
                timeout_seconds=timeout_seconds,
                measured_transport_ledger=holder_transport_ledger,
            ),
            expected_source_name="solana_rpc",
        )
    elif adapter_factories is None:
        core_safety_adapter = require_concrete_adapter(
            "preclose_solana_rpc_core_safety",
            build_solana_rpc_token_safety_adapter(
                enabled=True,
                fixture_transport=build_solana_rpc_token_safety_transport(
                    mint,
                    timeout_seconds=timeout_seconds,
                    measured_transport_ledger=holder_transport_ledger,
                ),
            ),
            expected_source_name="solana_rpc",
        )

    quote_factory = factories.get("jupiter_quote")
''',
)
replace_once(
    factory,
    '''        if "safety" in requested:
            stage[0] = "safety"
            executions["safety"] = execute(
                "goplus", GOPLUS_SAFETY_REQUEST_KIND, "safety", {}, safety_adapter
            )
        if "entry_quote" in requested:
''',
    '''        if "safety" in requested:
            stage[0] = "safety"
            executions["safety"] = execute(
                "goplus", GOPLUS_SAFETY_REQUEST_KIND, "safety", {}, safety_adapter
            )
            if core_safety_adapter is not None:
                stage[0] = "core_solana_safety"
                executions["core_solana_safety"] = execute(
                    "solana_rpc",
                    SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND,
                    "core-safety",
                    {},
                    core_safety_adapter,
                )
        if "entry_quote" in requested:
''',
)
replace_once(
    factory,
    '''            goplus_execution=safety,
            holder_execution=executions.get("holder"),
        )
''',
    '''            goplus_execution=safety,
            holder_execution=executions.get("holder"),
            core_solana_execution=executions.get("core_solana_safety"),
        )
''',
)
replace_once(
    factory,
    '''            "source_request_budget": len(requested) + (1 if "safety" in requested else 0),
''',
    '''            "source_request_budget": len(requested) + (2 if "safety" in requested else 0),
''',
)

print("SAFETY_CORE_REDUNDANCY_PATCH_APPLIED")
