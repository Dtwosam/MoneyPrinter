# Printer V1 V2-9.8B Campaign Source-Request Scope Propagation Repair Design

Date: 2026-09-01

Verdict:

`V2_9_8B_CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_REPAIR_DESIGN_COMPLETE`

Design-only until implementation on the repair branch. No authorization, campaign,
provider, Scheduler, or authoritative DB work is authorized by this document.

## Baseline

| Item | Value |
| --- | --- |
| Forensic audit | `docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-forensic-audit.md` |
| Consumed authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe` |
| Authorized HEAD (do not rewrite) | `eefd909fe40b14a6459154c71ba56ace8be08b4f` |
| Repair branch parent | that same HEAD |
| Failed execution | `20260901T191450Z-520d6a348621` |
| Classification | `COMMITTED_CODE_DEFECT` / `CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_LOSS` |

## Objective

Keep the authentic owner-produced `CampaignSourceRequestScope` alive through the
permanent eligible-supply freeze-ready measurement path.

The fail-closed assemble guard remains intact. Missing, invalid, foreign, and
legacy scopes must still fail closed. Historical durable rows must not substitute
for the current typed scope.

## Canonical owners

Unchanged:

- typed scope construction: `build_campaign_source_request_scope` in
  `AuthoritativeLiveOperationalCampaignOwner.run_operational` and the later-cycle
  owner
- typed scope validation / scoped reconciliation:
  `validate_campaign_source_request_scope` and
  `assemble_and_reconcile_campaign_source_requests`
- Source Governor remains the only source-request owner
- Central Scheduler remains the only scheduled-work owner

New forwarding duty, not a new owner:

- `build_graduated_supply` already holds the validated `scope_obj`
- `run_persistent_eligible_token_supply` already issues current-run-rooted
  requests and later measures freeze-ready depth
- that service must receive the same authentic scope object and pass it to
  assemble

## Production change

1. Add `campaign_source_request_scope=None` to
   `run_persistent_eligible_token_supply`.
2. Forward `scope_obj` from `build_graduated_supply` into that parameter.
3. In `_refresh_freeze_ready_depth`, pass the same object as
   `campaign_source_request_scope=` to
   `assemble_and_reconcile_campaign_source_requests`.
4. Optionally retain the authentic scope in persistent diagnostics so later
   consumers still see the owner object. Do not rebuild it from request keys.

Do not change:

- assemble fail-closed codes
- prefix/root validation
- budgets, capacity 4/2/2, freeze-ready depth 4
- Source Governor, Central Scheduler, providers, windows, retrieval, or
  financial capability

## Explicit non-repairs

- Do not reconstruct a `CampaignSourceRequestScope` from request-key strings
  inside eligible supply or freeze-ready measurement.
- Do not treat durable historical rows as current-run scope.
- Do not catch `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED` and continue.
- Do not pass only `request_key_root` and hope assemble infers a scope.

## Focused proof

Disposable migrated databases and fixture transports only.

RED, on current code:

- authentic scope created upstream
- front door forces prefixes to that root
- governed fixture request(s) use the exact current-run root
- freeze-ready measurement later calls assemble with the root and no typed scope
- current code raises `ValueError: CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`

GREEN, after the forwarding repair:

1. the same owner-produced scope survives into freeze-ready assemble
2. exact request root survives
3. downstream consumer receives that same valid scope
4. missing scope still fails closed
5. invalid scope still fails closed
6. foreign/cross-campaign scope still fails closed
7. legacy static root remains rejected
8. historical evidence cannot substitute for current scope
9. Source Governor remains authoritative
10. Central Scheduler remains authoritative
11. budgets unchanged
12. 4/2/2 unchanged
13. freeze-ready depth remains 4
14. `WINDOW_5M_MICRO_EVENT` remains support-only
15. 12H/24H remain locked
16. no retrieval/financial capability unlock

## Stop condition

Repair is complete only after focused GREEN proof, `py_compile` of changed
Python, `git diff --check`, and closeout. Do not run Printer. Do not prepare or
apply another authorization in this lane.
