# Printer V1 V2-9.8B Campaign Source-Request Scope Propagation Repair Closeout

Date: 2026-09-01

Verdict:

`V2_9_8B_CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_REPAIR_PASS`

## 1. Scope

This closeout records the forensic investigation and narrow repair of the consumed
Sep-1 Standard-4H failure:

Authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`

Final authorization state:

`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

Execution:

`20260901T191450Z-520d6a348621`

First terminal cause:

`ValueError:CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`

This lane did not reuse that authorization. It did not retry, rerun, resume,
restart, or create a successor. It did not run Printer, contact providers as a
campaign, run Central Scheduler, mutate the authoritative DB, activate retrieval,
unlock BUY/SELL/HOLD, or unlock WINDOW_12H / WINDOW_24H.

## 2. Authority

Active source stack unchanged:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

Forensic audit:

`docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-forensic-audit.md`

Design:

`docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-design.md`

Authorized historical HEAD (not rewritten):

`eefd909fe40b14a6459154c71ba56ace8be08b4f`

Repair branch:

`assistant/v2-9-8b-campaign-source-request-scope-propagation-repair`

## 3. Classification

Primary:

`COMMITTED_CODE_DEFECT`

Subtype:

`CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_LOSS`

The fail-closed assemble guard is intact and correct. The defect is that a valid
owner-produced `CampaignSourceRequestScope` was created, used to root real
governed requests, then dropped before freeze-ready measurement required it.

GeckoTerminal rate-limit on request `4272` is not the root cause.

## 4. Exact repair seam

Producer remains `build_campaign_source_request_scope` in the operational campaign
owner / later-cycle owner.

`build_graduated_supply` already validated the typed scope and forced prefixes to
its root. It now also forwards that authentic `scope_obj` into
`run_persistent_eligible_token_supply`.

`_refresh_freeze_ready_depth` now passes that same object to
`assemble_and_reconcile_campaign_source_requests`.

The authentic object is retained in persistent diagnostics. No scope is
reconstructed from request-key strings.

`CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED` remains fail-closed.

## 5. RED evidence

Before the forwarding change, the production-shaped test:

`test_front_door_forwards_owner_scope_into_freeze_ready_assemble`

failed at:

```text
build_graduated_supply
  -> run_persistent_eligible_token_supply
    -> _refresh_freeze_ready_depth()          # eligible_token_supply.py:2246
      -> assemble_and_reconcile_campaign_source_requests  # :2138
        -> ValueError: CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED  # permanent_discovery_availability.py:5324
```

That is the same raise the consumed Sep-1 child hit after requests `4265..4274`.

## 6. GREEN proof

Focused tests passed (`34` in the primary repair/wiring/contract set, plus `4`
nearest composition/identity tests):

- authentic owner-produced scope survives into freeze-ready assemble
- exact current-run request root survives
- downstream consumer receives the same valid scope
- missing scope still fails closed
- invalid scope still fails closed
- foreign/cross-campaign scope still fails closed
- legacy static root remains rejected
- historical foreign-root rows cannot substitute for current scope
- freeze-ready wiring inspects the forwarded parameter
- front-door composition still constructs and forwards the canonical root

Also passed:

- `python -m py_compile` of changed Python/test files
- `git diff --check`

No broad suite. Source Governor and Central Scheduler owners were not replaced.
Budgets, 4/2/2, freeze-ready depth 4, support-only 5m, locked 12h/24h, and
retrieval/financial locks are unchanged.

## 7. Files changed

Production:

- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/_graduated_supply_front_door_base.py`

Tests:

- `tests/test_v2_9_8b_campaign_source_request_scope_propagation_repair.py`
- `tests/test_v2_9_8b_freeze_ready_wiring_completion.py`
- `tests/test_v2_9_8b_window_15m_source_request_scope_repair.py`

Docs:

- `docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-forensic-audit.md`
- `docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-design.md`
- `docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-closeout.md`
- `CURRENT_HANDOFF.md`
- `AGENTS.md` current-lane pointer only
- `docs/printer-v1-assistant-active-build-order-anchor.md` current-lane pointer only

No migration. No authorization files. No operator-run artifacts.

## 8. Consumed authorization disposition

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe` remains:

`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

It must stay in every future Standard-4H `prior_authorizations_non_reusable`
trust root, together with every already-required prior ID.

## 9. Exact next permitted action

```text
POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE ONLY
```

A future run requires a completely fresh exact-HEAD / exact-DB readiness and
authorization sequence after this closeout commit exists. This closeout does not
prepare or apply an authorization and does not run Printer.
