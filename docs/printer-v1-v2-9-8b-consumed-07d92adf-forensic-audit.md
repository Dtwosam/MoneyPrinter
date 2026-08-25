# Printer V1 / V2-9.8B — Consumed `...07d92adf` Forensic Audit

Verdict:

`V2_9_8B_CONSUMED_07D92ADF_FORENSIC_AUDIT_PASS_NARROW_REPAIR_DESIGN_REQUIRED`

## Scope

Exact consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf`

Bound tracked HEAD:

`b8ace09a414d4056dc849e419fd9f4d8d1ee0cb8`

Execution:

`20260825T111829Z-234284139d8e`

The authorization is permanently consumed. No retry, rerun, resume, restart, or
successor is authorized by this audit.

## Terminal facts

The one-shot wrapper returned:

- `terminal_classification=CHILD_EXITED_NONZERO`
- child exit code `1`
- marker consumed `true`
- child terminal valid `true`
- cleanup complete `true`
- lease released `true`
- active locked Scheduler work `0`
- Scheduler runtime calls `0`
- source calls `54`
- database writes `6`
- reconstructed child terminal truth valid
- primary child failure:
  `NameError:name 'TerminalClosureError' is not defined`

The authoritative DB after the run is:

`2d372c6658819bce6e8e69c83eab1d0baeb799a7b9acddf18cb04b0528e99e95`

No retry/successor inference is permitted from the nonzero child exit.

## Durable admission truth

The authoritative DB contains exactly one durable campaign cycle for the
execution:

- cycle ordinal `1`
- state `TERMINAL_BLOCKED`
- first terminal cause `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`

The proposed Cycle-2 pre-admission attempt is durable separately:

- proposed ordinal `2`
- attempt state `FAILED`
- `consumed_cycle_id=NULL`
- first terminal cause `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`

Therefore proposed Cycle 2 was never a durable admitted campaign cycle.

## Exact persistence diagnostic

The production read-only decoder returned:

```json
{
  "diagnostic_schema": "PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1",
  "exception_type": "PreAdmissionAttemptError",
  "failure_category": "APPLICATION_VALIDATION",
  "failure_code": "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED",
  "operation_phase": "FROZEN_CARRIER",
  "producer_code": "FROZEN_LANE_CLASSIFICATION",
  "reason_code": "FROZEN_TRACKING_LANE_UNAVAILABLE"
}
```

Scheduler job `2590` is terminal `FAILED`, unlocked, and carries the same
diagnostic in `last_error`.

Classification of this upstream condition:

`HONEST_APPLICATION_VALIDATION_BLOCK`

`FROZEN_TRACKING_LANE_UNAVAILABLE` is not proven to be a provider defect, source
scarcity defect, Scheduler defect, or code defect. This repair lane MUST NOT
weaken or bypass that block.

## Accounting producer-path finding

`authoritative_live_operational_campaign._bind_later_cycle_accounting_owner()`
registers the proposed later-cycle accounting sink before durable later-cycle
admission. This is necessary to capture real pre-admission transport/evidence
for the proposed cycle.

That means `CampaignCycleAccountingRegistry.registered_cycle_ids` can lawfully
contain a proposed cycle that never becomes an admitted
`printer_memory_factory_campaign_cycles` row.

The outer operational command currently interprets:

`len(cycle_accounting_registry.registered_cycle_ids) > 1`

as sufficient reason to build a `CampaignSixUnitProjection`.

That is not equivalent to durable multi-cycle admission.

## Lane-4 failure chain

The resulting projection contained Cycle 1 plus proposed Cycle 2.

`finalize_full_run_ownership_and_report()` correctly reads durable admitted
cycles from `printer_memory_factory_campaign_cycles`. It therefore observed
only ordinal `(1,)`.

Because the caller supplied a `CampaignSixUnitProjection`,
`multi_cycle_accounting` became true and Lane-4 correctly rejected the state:

`full-run accounting requires exact admitted ordinals 1 and 2`

`_apply_full_run_campaign_acceptance()` caught that accounting fault and returned
`FULL_RUN_FINALIZATION_FAULT...`, with no canonical `terminal_accounting`
mapping.

The outer four-token path then unconditionally required canonical Lane-4
terminal accounting whenever the four-token controller existed and attempted:

`raise TerminalClosureError("LANE4_CANONICAL_TERMINAL_ACCOUNTING_MISSING")`

but `TerminalClosureError` is not imported by
`operational_memory_factory_command.py`.

The resulting `NameError` therefore masked the intended fail-closed accounting
condition.

## Proven classifications

Primary repair classification:

`CROSS_PATH_DURABLE_ADMISSION_ACCOUNTING_PROJECTION_DEFECT`

Masking defect:

`MASKING_TERMINAL_CLOSURE_IMPORT_DEFECT`

Upstream condition to preserve:

`HONEST_APPLICATION_VALIDATION_BLOCK:FROZEN_TRACKING_LANE_UNAVAILABLE`

## Production-path completeness

The relevant states are all real production states:

- proposed later-cycle accounting owner: produced by the real later-cycle supply
  path before admission;
- failed pre-admission attempt: durable DB row;
- frozen-lane diagnostic: durable Scheduler `last_error`;
- one admitted campaign cycle: durable DB row;
- two-owner in-memory accounting projection: real runtime state;
- Lane-4 ordinal rejection: real finalizer;
- missing import: real production module defect.

No test-only injected final classification is required to reproduce the defect.

## Not authorized

This audit does not authorize:

- fixing or bypassing `FROZEN_TRACKING_LANE_UNAVAILABLE`;
- retry/rerun/resume/restart/successor;
- a new authorization;
- provider/source changes;
- schema or migration changes;
- new accounting ledger;
- scoring/ranking/confidence logic;
- retrieval or financial capabilities;
- Cycle 3 or longer-window activation.

Exact next action:

`NARROW DURABLE-ADMISSION TERMINAL-ACCOUNTING SCOPE REPAIR DESIGN ONLY`
