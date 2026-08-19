# Printer V1 V2-9.8B Multi-Cycle CampaignSixUnitProjection Terminal-Finalization Repair Design

Date: 2026-08-19

Lane: `V2-9.8B Multi-Cycle CampaignSixUnitProjection Terminal-Finalization Repair Design`

Status: `DESIGN_APPROVED_FOR_IMPLEMENTATION_BY_OPERATOR`

## 1. Governing blocker

Post-corrective 4/2/2 authoritative readiness closed BLOCKED on the already-observed multi-cycle campaign-acceptance fault:

`FULL_RUN_FINALIZATION_FAULT:AttributeError:'CampaignSixUnitProjection' object has no attribute 'ingest_stage_evidence'`

The executable baseline is:

`e8979e9c7e44e3165aa471827cecc407604895c0`

The corrective-program adoption does not repair this surface.

## 2. Root cause

`CampaignCycleAccountingRegistry` owns one mutable `CampaignSixUnitOwner` per cycle. `CampaignSixUnitProjection` is intentionally a read-only aggregate of those already-owned cycle ledgers.

For a multi-cycle campaign, `operational_memory_factory_command.py` currently creates the campaign projection before calling full-run acceptance. `finalize_full_run_ownership_and_report()` still contains the older single-owner preparation behavior: while reconstructing exact durable `WINDOW_15M_SLOT_1/2` terminal evidence it calls `owner.ingest_stage_evidence(...)` for any missing stage.

That is lawful for a mutable `CampaignSixUnitOwner`, but unlawful for a `CampaignSixUnitProjection`. The projection intentionally exposes no ingestion authority.

Simply skipping the ingestion is not an acceptable repair because the finalizer is also the fail-closed owner of reconstructing missing mandatory 15m terminal-stage evidence from durable runtime rows.

## 3. Required ownership law

The repaired terminal boundary SHALL separate mutable stage preparation from read-only campaign aggregation:

1. Every sealed stage is ingested exactly once by the exact mutable cycle owner that owns that stage.
2. A multi-cycle `CampaignSixUnitProjection` is created or rebuilt only after any required mutable-cycle stage preparation is complete.
3. `CampaignSixUnitProjection` remains read-only. It SHALL NOT gain `ingest_stage_evidence`, cycle-registration, or mutation authority.
4. Full-run reconciliation/reporting consumes the resulting owner/projection only after preparation.
5. Missing, malformed, duplicate, cross-cycle, or otherwise invalid stage evidence continues to fail closed.
6. Single-cycle behavior remains byte-semantically equivalent: the existing `CampaignSixUnitOwner` remains both the stage-preparation owner and final accounting owner.

## 4. Minimum production change

### A. `campaign_full_run_accounting.py`

Add a narrow helper that finalizes a set of already-sealed slot-stage evidence against a mutable stage owner and then returns the accounting object to use for reconciliation:

- input: current accounting owner/projection;
- input: exact mutable `CampaignSixUnitOwner` permitted to ingest these stages (defaults to the ordinary owner for single-cycle);
- input: sealed stage evidence sequence;
- optional input: zero-argument campaign projection factory;
- ingest only into the mutable stage owner, idempotently by `stage_id`;
- close that mutable owner;
- if a projection factory is supplied, rebuild and return the projection after ingestion;
- otherwise return the ordinary owner;
- if a read-only projection is supplied without a lawful mutable stage owner and missing evidence would require ingestion, fail closed with a categorical accounting error rather than an `AttributeError`.

`finalize_full_run_ownership_and_report()` SHALL collect its exact durable slot-stage evidence first, invoke this helper, and use the returned refreshed accounting object for owner/action-local reconciliation and terminal reporting.

No campaign DB evidence is invented or rewritten by this refactor.

### B. `operational_memory_factory_command.py`

At the existing multi-cycle acceptance seam:

- retain the exact mutable initial/current acceptance-cycle owner as the stage-evidence owner;
- build the initial read-only campaign projection exactly as today when multiple cycle owners exist;
- pass the mutable stage owner plus `cycle_accounting_registry.campaign_projection` as the rebuild factory into the full-run finalizer;
- after any missing stage is lawfully materialized, the finalizer rebuilds the projection so reconciliation sees the new evidence.

The coordinator SHALL NOT mutate the projection itself.

## 5. Explicit non-goals

This repair does NOT:

- change discovery, candidate supply, freeze, selection, or Cycle-2 freshness;
- change Source Governor or Central Scheduler ownership;
- change E2Q/E2Z clean-memory authority;
- change wallet/trading-flow completeness;
- create a migration or schema change;
- change 4/2/2 capacity, timing, liquidity floor, freeze depth, or continuation law;
- contact a provider;
- create/reuse authorization;
- run Printer;
- unlock retrieval or financial capability.

## 6. Required behavioral proof

Minimum proof must demonstrate:

1. **Multi-cycle missing stage:** a missing sealed stage is ingested into the supplied mutable cycle owner, then a newly rebuilt projection contains it; no projection mutation method is required.
2. **Prior-cycle isolation:** preparing the acceptance-cycle owner does not mutate another cycle owner.
3. **Idempotence:** an already-ingested stage is not duplicated.
4. **Projection stays read-only:** `CampaignSixUnitProjection` still has no `ingest_stage_evidence` authority.
5. **Fail closed without mutable owner:** a read-only projection that needs a missing stage but is not supplied a lawful mutable stage owner returns a categorical accounting error, not an `AttributeError` or silent skip.
6. **Single-cycle preservation:** ordinary `CampaignSixUnitOwner` preparation still ingests and finalizes exactly once.
7. Existing nearby terminal-safety/accounting and four-token composition regressions remain green.

## 7. Verification boundary

Use disposable/in-memory fixtures only. No live provider, authoritative runtime DB write, authorization, or Printer execution.

Minimum checks:

- new focused repair tests;
- existing terminal-safety/accounting tests directly affected by the finalizer;
- existing campaign/four-token accounting/composition tests that cover the multi-cycle acceptance seam;
- touched-module compile/import checks;
- `git diff --check`.

Do not request the full repository suite unless a causal failure requires broader evidence.

## 8. Implementation verdict contract

PASS only if the real multi-cycle ownership split is behaviorally proven and no causal regression remains:

`V2_9_8B_MULTICYCLE_CAMPAIGN_PROJECTION_TERMINAL_FINALIZATION_REPAIR_IMPLEMENTATION_PASS`

Otherwise:

`V2_9_8B_MULTICYCLE_CAMPAIGN_PROJECTION_TERMINAL_FINALIZATION_REPAIR_IMPLEMENTATION_BLOCKED`

A PASS permits independent closeout/review only. It does not authorize a 4/2/2 run.