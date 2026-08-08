# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-53 Final Acceptance Accounting Repair Design

Date: 2026-08-08

Linear: `DTW-53`

Design baseline: `e85a0dfc53e4a7a53ebd3f43bd2bd8c2e60ce582`

Audit: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-8-dtw53-final-acceptance-accounting-audit.md`

## Verdict

`DTW53_FINAL_ACCEPTANCE_ACCOUNTING_REPAIR_DESIGN_READY_FOR_DETERMINISTIC_RED`

This design fixes two neighboring acceptance defects without changing the truthful owner ledger, Source Governor, Central Scheduler, request/transport budgets, lifecycle reservations, memory law, or any downstream capability lock.

## Repair A — direct-migration local-validation action-local projection

### Canonical producer

`run_direct_migration_discovery()` remains the canonical producer of each `PUMPSWAP_GRADUATION_*` `LocalValidationIdentity`.

### New verification-only observer

Add one optional `local_validation_identity_observer` callable beside the existing `transport_identity_observer`.

For each real migration validation identity:

1. create the `LocalValidationIdentity` exactly where it is created today;
2. notify the optional action-local observer from that producer path before stage sealing;
3. preserve the same identity unchanged in `migration_validation_identities` for owner stage sealing;
4. never reconstruct or mirror the action-local identity from sealed evidence, DB rows, counts, or the final report.

The observer is verification-only and never becomes accounting authority.

### Propagation path

Thread the observer unchanged through the existing public composition path:

`operational_memory_factory_command`
→ `AuthoritativeLiveOperationalCampaignOwner`
→ `build_graduated_supply`
→ `run_persistent_eligible_token_supply`
→ `run_direct_migration_discovery`

The public command binds the observer to `CampaignActionLocalLedger.observe_local_validation`.

No other discovery validation family is changed unless an existing caller explicitly passes the observer. No new loop, source call, Scheduler work, DB write, retry, or stage is created.

## Repair B — lifecycle reservation-attempt outcome scope

`source_operation_outcomes` must preserve campaign-wide `SOURCE_TRANSPORT_OPERATION=46`; that total is truthful and must not be rewritten.

For the separate reservation-attempt acceptance fact, derive an exact lifecycle attempt set from the two owned `WINDOW_15M_SLOT_*` stage identities.

A transport qualifies as a lifecycle reservation attempt only when:

- its `stage` equals one of the exact owned lifecycle slot stage IDs; and
- its `reserved_from` is non-empty and refers to the same authoritative factory run / lifecycle step reservation namespace.

Fail closed when a transport belongs to an owned lifecycle stage but lacks valid reservation linkage. Do not silently filter such a transport out.

Pre-lifecycle transports (`LOCATOR`, `DIRECT_MIGRATION`, `FRESH_POOL_NOMINATION`, `MINT_MARKET_BATCH`, `HOLDER_SAFETY`, discovery-selection work) remain in campaign-wide transport accounting but do not enter lifecycle reservation-attempt outcome arithmetic.

The acceptance arithmetic remains unchanged:

`reserved >= attempted > 0`

and

`attempted == succeeded + failed`

For the frozen C8 shape the expected truthful projection is:

- reserved 28
- lifecycle attempted 26
- succeeded 26
- failed 0
- complete true

Unused reservation capacity remains lawful; an attempted lifecycle transport without a terminal `SUCCEEDED` or `FAILED` outcome remains blocking.

## Exact expected implementation surfaces

Production:

1. `src/printer_v1/discovery/direct_migration_discovery.py`
2. `src/printer_v1/discovery/eligible_token_supply.py`
3. `src/printer_v1/operator_cli/graduated_supply_front_door.py`
4. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
5. `src/printer_v1/operator_cli/operational_memory_factory_command.py`
6. `src/printer_v1/operator_cli/campaign_full_run_accounting.py`

Tests: one narrow DTW-53 regression file is preferred unless existing nearest contract tests provide a cleaner home.

No migration, schema, provider adapter, Source Governor, Scheduler, holder, memory, replay owner, or capability table change is expected.

## Deterministic RED requirements

Before production code changes, materialize focused tests that fail at this design baseline for exactly these reasons:

### RED-A

A direct-migration fixture produces four `PUMPSWAP_GRADUATION_VERIFIED` identities. Owner stage evidence contains all four, while an independently supplied local-validation observer receives none at the current baseline. The regression must assert the intended exact observer identity set and fail before repair.

### RED-B

A full-run accounting fixture contains:

- 20 valid pre-lifecycle campaign transports with non-lifecycle result vocabulary;
- 26 valid lifecycle transports with exact reservation linkage and `SUCCEEDED` outcomes;
- 28 lifecycle reservations.

The current baseline must fail reservation outcome completeness because it treats all 46 transports as lifecycle attempts. The intended projection must be 28/26/26/0 and complete.

### Negative safety case

A transport in an owned lifecycle stage with missing or malformed reservation linkage must remain blocking. The repair must not obtain PASS by filtering malformed lifecycle work away.

## Focused GREEN requirements

After implementation:

- direct-migration observer receives the exact four identities unchanged;
- owner/action-local `LOCAL_VALIDATION_STEP` sets reconcile exactly and non-vacuously for the C8 composition shape;
- campaign-wide `SOURCE_TRANSPORT_OPERATION` remains unchanged;
- lifecycle reservation outcomes report 28 reserved / 26 attempted / 26 succeeded / 0 failed / complete true;
- malformed/unlinked lifecycle attempt fails closed;
- nearest affected Checkpoint 8 accounting/replay compatibility tests pass;
- Python compilation and diff checks pass.

Use the minimum sufficient focused suite. Broad/full C8 regression belongs at DTW-53 major closeout / pre-proof readiness if implementation remains within these surfaces.

## Money-usefulness contribution

This repair lets a genuinely completed clean 15m campaign clear truthful accounting instead of being rejected by projection/scope artifacts, while preserving the safeguards that prevent fake or incomplete work from becoming trusted memory.

## What improves

- direct-migration local validations become independently observable at execution time;
- reservation completeness measures the lifecycle reservation domain it claims to measure;
- final acceptance and report-only replay can evaluate the same truthful frozen evidence without weakening any identity law.

## What remains locked

No C8 rerun, operational activation, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper trade audits, PnL, wallet, signing, live execution, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors are unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Observer fan-out must happen at the real producer boundary; post-seal mirroring would invalidate independence.
- New observer plumbing must remain optional for non-C8 consumers and must not alter source execution behavior.
- Lifecycle attempt filtering must use exact owned stage/reservation identity, not a permissive string heuristic.
- The 46 campaign-wide transport count must remain intact; only the reservation-outcome subprojection is scoped.
- Any implementation that expands into Scheduler, Source Governor, holder or memory policy exceeds this design and must stop.

## Stop condition

Commit this design, then materialize deterministic RED only. Do not modify production code until RED is demonstrated from this exact design baseline. Do not run a C8 controlling proof in DTW-53.
