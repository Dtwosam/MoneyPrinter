# Printer V1 V2-9.8B Campaign Accounting and Terminal Enforcement Audit

Date: 2026-07-30

Lane: `V2-9.8B Campaign Accounting and Terminal Enforcement Completion`

Status: `AUDIT_COMPLETE`

## Baseline

- Branch: `master`
- HEAD: `e864463472ad8c1db6f171847caac885940445fd`
- Prior verdict re-audited:
  `V2_9_8B_DISCOVERY_SELECTION_VERIFIABLE_REAL_PATH_OPERATOR_REVIEW_BLOCKED`
- Authoritative DB SHA-256 (unchanged):
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head: `049`

## Method

Re-read the active ordinary path end to end: direct Pump/PumpSwap live-tail
discovery (`discovery/direct_migration_discovery.py`,
`sources/direct_pump_migration.py`, `sources/pump_migration.py`), exact-pair
DexScreener liquidity (`sources/dexscreener.py`), eligible supply, holder/safety
evidence, canonical selection, the initial atomic two-slot handoff
(`discovery/combined_executor.py`), lifecycle materialization
(`operator_cli/origin_lifecycle_campaign.py`,
`operator_cli/one_command_15m_factory.py`), Scheduler work, and the terminal
report / replay (`operator_cli/unified_terminal_closure.py`, coordinator
`operator_cli/operational_memory_factory_command.py`). Six-unit accounting
primitives live in `sources/measured_transport.py` and
`sources/campaign_six_unit_accounting.py`.

## Confirmed operator-review blockers

| # | Requirement | Confirmed defect at baseline |
|---|---|---|
| B1 | Every **exact-pair** DexScreener HTTP attempt emits exactly one measured identity on every outcome | `build_dexscreener_smoke_transport` (the exact-pair snapshot path) emits an identity **only on success**. Byte-ceiling, row-ceiling, non-object malformed, HTTP 429, HTTP 5xx, HTTP 4xx, decode failure, and timeout/transport branches all return **without a `TransportOperationIdentity`**. The prior lane fixed only the fresh-profiles transport. |
| B2 | Preserve earlier identities on later-hop failure | Fresh-profiles preserves step-1 identity; the single-call exact-pair path never emitted a failure identity at all (subsumed by B1). |
| B3 | `ACCOUNTING_BLOCKED` is an immediate campaign safe stop; existing registry candidates must not continue toward selection | On `accounting_block_reason`, `run_direct_migration_discovery` still called `export_graduated_candidates` and returned a populated `candidate_mix` of **all** persisted registry rows, which the coordinator would carry toward selection. |
| B4/B5 | `CampaignSixUnitOwner` is the top-level coordinator, threaded through every active stage | The owner was **constructed inside** `run_direct_migration_discovery` only. The coordinator `_run_operational_campaign` never owns one; the terminal report drew six-unit values from `reporting.get(...) or lifecycle.get(...)`. |
| B6 | Remove optional-dictionary accounting as an authority; the top-level owner aggregates | `assemble_campaign_terminal_reporting` and `build_campaign_terminal_report` treat an optional lifecycle/reporting dict as the six-unit authority, with `empty_six_unit_totals()` / `empty_six_unit_evidence()` fallbacks. |
| B7 | Missing/malformed/duplicate/partial/mismatched evidence fails closed before report persistence | `build_campaign_terminal_report` **synthesized `empty_six_unit_evidence()`** for missing evidence and never raised; `write_campaign_terminal_report` performed **no** evidence validation before persisting. |
| B8 | No synthetic empty evidence for an attempted campaign | Same synthesis path as B7: real work with omitted evidence was silently covered by an all-zero evidence block. |
| B9 | Require `six_unit_evidence_match=True`; else terminalize with an explicit accounting failure | `six_unit_evidence_match` was computed and stored but **never enforced**; a mismatched report was still written and reported as completion. |
| B10 | Replay reconstructs from durable evidence with zero source calls / Scheduler work / writes | Present, but only proven by report-equality; needed an explicit zero-operation assertion at the coordinator replay boundary. |
| B11/B12 | Real disposable-DB failure injections **after** successful initial handoff (batch creation, executor-job cancellation, job replanning, object materialization, post-activation transition), proving zero orphan state | The prior proof reused the **atomic two-slot handoff** harness, which injects faults **during** the handoff (pre-commit rollback). No injection exercised a fault **after** a successful initial handoff during the five post-handoff lifecycle stages, and there was no compensating teardown for that window. |
| B13 | Correct anchor / supersede prior PASS | Anchor still points to the verifiable-real-path PASS as the completed surface. |

## Classification

```text
BLOCKER CLASSIFICATION:
INCOMPLETE_WIRING (B1,B4,B5) + ACCOUNTING_AUTHORITY (B6) +
TERMINAL_ENFORCEMENT_GAP (B7,B8,B9) + SAFE_STOP_LEAK (B3) +
POST_HANDOFF_PROOF_GAP (B11,B12)

CODE CHANGE JUSTIFIED: YES
```

## Exact next task after audit

Final design → cohesive repair → frozen offline proof → corrected closeout.
