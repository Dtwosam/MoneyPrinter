from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"guard failed for {path}: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


full_run = Path("src/printer_v1/operator_cli/campaign_full_run_accounting.py")
command = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")

replace_once(
    full_run,
    """from printer_v1.sources.campaign_six_unit_accounting import (\n    CampaignActionLocalLedger,\n    CampaignSixUnitOwner,\n    build_campaign_stage_id,\n""",
    """from printer_v1.sources.campaign_six_unit_accounting import (\n    CampaignActionLocalLedger,\n    CampaignSixUnitOwner,\n    CampaignSixUnitProjection,\n    build_campaign_stage_id,\n""",
)

helper = '''\n\ndef prepare_full_run_accounting_owner(\n    accounting_owner: CampaignSixUnitOwner | CampaignSixUnitProjection,\n    *,\n    sealed_stage_evidences: Sequence[Mapping[str, Any]],\n    stage_evidence_owner: CampaignSixUnitOwner | None = None,\n    accounting_projection_factory: Callable[[], CampaignSixUnitProjection] | None = None,\n) -> CampaignSixUnitOwner | CampaignSixUnitProjection:\n    """Complete mutable stage ownership before read-only campaign projection.\n\n    Single-cycle callers keep the historical behavior: the accounting owner is\n    the mutable stage owner. Multi-cycle callers must supply the exact mutable\n    cycle owner for any missing stages and a projection factory so reconciliation\n    sees a fresh read-only aggregate after those stages are committed.\n    """\n    mutable_owner = stage_evidence_owner\n    is_projection = isinstance(accounting_owner, CampaignSixUnitProjection)\n    missing_stage_evidence = False\n\n    if mutable_owner is None:\n        if is_projection:\n            for evidence in sealed_stage_evidences:\n                stage_id = str(evidence.get("stage_id") or "").strip()\n                if not stage_id:\n                    raise FullRunAccountingError("FULL_RUN_STAGE_EVIDENCE_ID_MISSING")\n                if stage_id not in accounting_owner.ingested_stage_ids:\n                    missing_stage_evidence = True\n                    break\n            if missing_stage_evidence:\n                raise FullRunAccountingError(\n                    "MULTI_CYCLE_STAGE_EVIDENCE_OWNER_REQUIRED"\n                )\n            accounting_owner.close()\n            return accounting_owner\n        mutable_owner = accounting_owner\n\n    ingested_new_stage = False\n    for evidence in sealed_stage_evidences:\n        stage_id = str(evidence.get("stage_id") or "").strip()\n        if not stage_id:\n            raise FullRunAccountingError("FULL_RUN_STAGE_EVIDENCE_ID_MISSING")\n        if stage_id not in mutable_owner.ingested_stage_ids:\n            mutable_owner.ingest_stage_evidence(evidence)\n            ingested_new_stage = True\n    mutable_owner.close()\n\n    if is_projection:\n        if accounting_projection_factory is None:\n            if ingested_new_stage:\n                raise FullRunAccountingError(\n                    "MULTI_CYCLE_PROJECTION_REBUILD_REQUIRED"\n                )\n            return accounting_owner\n        refreshed = accounting_projection_factory()\n        if not isinstance(refreshed, CampaignSixUnitProjection):\n            raise FullRunAccountingError(\n                "MULTI_CYCLE_PROJECTION_REBUILD_INVALID"\n            )\n        return refreshed\n\n    return mutable_owner\n'''

replace_once(
    full_run,
    "\n\ndef finalize_full_run_ownership_and_report(\n",
    helper + "\n\ndef finalize_full_run_ownership_and_report(\n",
)

replace_once(
    full_run,
    """    owner: CampaignSixUnitOwner,\n    action_local: CampaignActionLocalLedger,\n""",
    """    owner: CampaignSixUnitOwner | CampaignSixUnitProjection,\n    action_local: CampaignActionLocalLedger,\n""",
)

replace_once(
    full_run,
    """    four_token_proof_owned: bool = False,\n    now: str | None = None,\n""",
    """    four_token_proof_owned: bool = False,\n    stage_evidence_owner: CampaignSixUnitOwner | None = None,\n    accounting_projection_factory: Callable[[], CampaignSixUnitProjection] | None = None,\n    now: str | None = None,\n""",
)

replace_once(
    full_run,
    """    sealed_transport_count = 0\n    lifecycle_source_request_count = 0\n    for ordinal in (1, 2):\n""",
    """    sealed_transport_count = 0\n    lifecycle_source_request_count = 0\n    sealed_slot_stage_evidences: list[Mapping[str, Any]] = []\n    for ordinal in (1, 2):\n""",
)

replace_once(
    full_run,
    """        if stage_id not in owner.ingested_stage_ids:\n            owner.ingest_stage_evidence(sealed)\n\n    owner.close()\n""",
    """        sealed_slot_stage_evidences.append(sealed)\n\n    owner = prepare_full_run_accounting_owner(\n        owner,\n        sealed_stage_evidences=sealed_slot_stage_evidences,\n        stage_evidence_owner=stage_evidence_owner,\n        accounting_projection_factory=accounting_projection_factory,\n    )\n""",
)

replace_once(
    full_run,
    '    "finalize_full_run_ownership_and_report",\n',
    '    "finalize_full_run_ownership_and_report",\n    "prepare_full_run_accounting_owner",\n',
)

replace_once(
    command,
    """    accounting_owner: Any | None = None,\n    action_local_ledger: Any | None = None,\n""",
    """    accounting_owner: Any | None = None,\n    accounting_stage_evidence_owner: Any | None = None,\n    accounting_projection_factory: Any | None = None,\n    action_local_ledger: Any | None = None,\n""",
)

replace_once(
    command,
    """                four_token_proof_owned=bool(four_token_proof_owned),\n            )\n""",
    """                four_token_proof_owned=bool(four_token_proof_owned),\n                stage_evidence_owner=accounting_stage_evidence_owner,\n                accounting_projection_factory=accounting_projection_factory,\n            )\n""",
)

replace_once(
    command,
    """        campaign_accounting_projection: Any = campaign_units\n        if len(cycle_accounting_registry.registered_cycle_ids) > 1:\n            campaign_accounting_projection = (\n                cycle_accounting_registry.campaign_projection()\n            )\n""",
    """        campaign_accounting_projection: Any = campaign_units\n        campaign_accounting_projection_factory: Any | None = None\n        if len(cycle_accounting_registry.registered_cycle_ids) > 1:\n            campaign_accounting_projection_factory = (\n                cycle_accounting_registry.campaign_projection\n            )\n            campaign_accounting_projection = (\n                campaign_accounting_projection_factory()\n            )\n""",
)

replace_once(
    command,
    """            accounting_owner=campaign_accounting_projection,\n            action_local_ledger=action_local_ledger,\n""",
    """            accounting_owner=campaign_accounting_projection,\n            accounting_stage_evidence_owner=campaign_units,\n            accounting_projection_factory=campaign_accounting_projection_factory,\n            action_local_ledger=action_local_ledger,\n""",
)

replace_once(
    command,
    """        aggregated_six_unit_totals = (\n            campaign_accounting_projection.six_unit_totals()\n        )\n""",
    """        if campaign_accounting_projection_factory is not None:\n            campaign_accounting_projection = (\n                campaign_accounting_projection_factory()\n            )\n        aggregated_six_unit_totals = (\n            campaign_accounting_projection.six_unit_totals()\n        )\n""",
)

print("guarded multi-cycle projection finalization repair applied")
