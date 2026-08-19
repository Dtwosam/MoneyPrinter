from __future__ import annotations

from pathlib import Path


path = Path("src/printer_v1/operator_cli/campaign_full_run_accounting.py")
text = path.read_text(encoding="utf-8")

old = '''    ingested_new_stage = False
    for evidence in sealed_stage_evidences:
        stage_id = str(evidence.get("stage_id") or "").strip()
        if not stage_id:
            raise FullRunAccountingError("FULL_RUN_STAGE_EVIDENCE_ID_MISSING")
        if stage_id not in mutable_owner.ingested_stage_ids:
            mutable_owner.ingest_stage_evidence(evidence)
            ingested_new_stage = True
    mutable_owner.close()

    if is_projection:
        if accounting_projection_factory is None:
            if ingested_new_stage:
                raise FullRunAccountingError(
                    "MULTI_CYCLE_PROJECTION_REBUILD_REQUIRED"
                )
            return accounting_owner
        refreshed = accounting_projection_factory()
'''

new = '''    sealed_stage_ids: list[str] = []
    for evidence in sealed_stage_evidences:
        stage_id = str(evidence.get("stage_id") or "").strip()
        if not stage_id:
            raise FullRunAccountingError("FULL_RUN_STAGE_EVIDENCE_ID_MISSING")
        sealed_stage_ids.append(stage_id)

    if is_projection and accounting_projection_factory is None:
        if any(
            stage_id not in mutable_owner.ingested_stage_ids
            for stage_id in sealed_stage_ids
        ):
            raise FullRunAccountingError(
                "MULTI_CYCLE_PROJECTION_REBUILD_REQUIRED"
            )

    for evidence, stage_id in zip(sealed_stage_evidences, sealed_stage_ids):
        if stage_id not in mutable_owner.ingested_stage_ids:
            mutable_owner.ingest_stage_evidence(evidence)
    mutable_owner.close()

    if is_projection:
        if accounting_projection_factory is None:
            return accounting_owner
        refreshed = accounting_projection_factory()
'''

if new in text:
    print("pre-mutation projection rebuild guard already applied")
elif text.count(old) == 1:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("pre-mutation projection rebuild guard applied")
else:
    raise SystemExit(
        "guard failed: expected exactly one unsafe projection rebuild block"
    )
