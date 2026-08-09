# Printer V1 — V2-9.8B Post-DTW99 Consumed Pre-Lifecycle Interface Failure Audit Plan

## Status

`V2_9_8B_POST_DTW99_CONSUMED_PRE_LIFECYCLE_INTERFACE_FAILURE_AUDIT_PLANNED`

This lane is read-only. The authorization is permanently consumed and must not be retried, rerun, restarted, resumed, or reused.

## Consumed attempt

- authorization: `V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z`
- authorization SHA-256: `52a036cec8d104cc0bd22ff52a66be33b040515fe518ce06f97d3fb2bd8aed15`
- bound preparation HEAD: `f72020dd2704d9b5691d39d21a2898ccf9743cce`
- execution: `20260809T165814Z-e16ee84dc4c7`
- campaign: `20260809T165814Z-e16ee84dc4c7-campaign`
- run: `20260809T165814Z-e16ee84dc4c7-campaign-run`
- cycle: `20260809T165814Z-e16ee84dc4c7-cycle`
- supervision: `20260809T165814Z-e16ee84dc4c7-supervision`
- child exit: `1`
- failure phase: `CAMPAIGN_PRE_LIFECYCLE`
- first terminal cause: `TypeError:build_graduated_supply() got an unexpected keyword argument 'temporal_refresh_owner'`
- lifecycle started: not proven / did not reach lifecycle
- source calls reported by child: `0`
- Scheduler runtime calls reported by child: `0`
- DB writes reported by child: `6`
- marker consumed: `true`
- cleanup complete: `true`
- lease released: `true`

## Static interface finding

At the bound source tree:

- `run_persistent_eligible_token_supply(...)` accepts `temporal_refresh_owner`;
- `build_graduated_supply(...)` does not accept or forward `temporal_refresh_owner`;
- the implementation-completion lane changed the ordinary caller/wiring but did not modify `graduated_supply_front_door.py`.

This is a production composition-interface gap. It is not permission to edit yet; the consumed-attempt audit must first establish durable terminal/cleanup/DB truth.

## Audit requirements

Read-only audit must verify:

1. exact consumed marker identity and no reuse;
2. child terminal artifact identity and failure cause;
3. exact attempt IDs and pre-lifecycle terminal state;
4. no active process, lease, campaign, Scheduler, discovery, factory, proof, or temporal-wait residue;
5. no source requests attributable to the attempt;
6. no Scheduler runtime work attributable to the attempt;
7. DB integrity `ok`, FK violations `0`, no sidecars;
8. authoritative DB identity before/after audit identical;
9. migration remains 54/54;
10. locked capability counts unchanged and no forbidden retrieval/decision/position/trade/audit/PnL deltas;
11. exact rows written by the failed pre-lifecycle attempt are terminal and attributable;
12. no authorization/package/marker created by the audit and no runtime started.

## Next step if audit passes

Design a narrow interface-completion repair: make `build_graduated_supply(...)` accept the existing optional temporal owner and forward it unchanged to `run_persistent_eligible_token_supply(...)`, with an unmocked production call-chain proof that would have caught this TypeError before runtime.

No source-budget, Scheduler, selection, eligibility, tracking, memory, or financial rule may change.
