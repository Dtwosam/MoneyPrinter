# Printer V1 V2-9.8B Post-Scope-Propagation-Repair Fresh Readiness

Date: 2026-09-01

Verdict:

`V2_9_8B_POST_SCOPE_PROPAGATION_REPAIR_FRESH_READINESS_PASS`

## 1. Purpose

This is the currently permitted lane:

`POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE ONLY`

It is read-only readiness/governance after the consumed Sep-1 Standard-4H
scope-propagation repair. It does not prepare or apply an authorization, run
Printer, start a campaign, contact providers/RPC/WebSocket, run Central
Scheduler operationally, mutate the authoritative DB, or unlock any capability.

The authorization-boundary design remains already complete:

`docs/printer-v1-v2-9-8b-next-standard-4h-authorization-preparation-boundary-design.md`

Classification of that design remains `EXISTING_OWNER_ALREADY_SUFFICIENT`.
Do not redo it.

## 2. Authority

Active source stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

Current-lane files at audit start:

- `CURRENT_HANDOFF.md`
- `docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-closeout.md`

Those sources all named this readiness/governance lane as the exact next
permitted action. Older historical pointers were not used.

## 3. Git readiness

| Item | Value |
| --- | --- |
| Branch | `assistant/v2-9-8b-campaign-source-request-scope-propagation-repair` |
| Repair-closeout HEAD audited | `952960452999379abaaf99fb579f58ae00b3ab9a` |
| Parent / authorized consumed-run HEAD | `eefd909fe40b14a6459154c71ba56ace8be08b4f` |
| Tracked working tree | clean |
| Staged | empty |
| Untracked | previously known `operator-runs/...` evidence directories only |

Independent production-diff review of `95296045` versus `eefd909f` shows only
the proven forwarding seam:

- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/_graduated_supply_front_door_base.py`

plus tests and the repair/closeout documents. No unexplained tracked drift.

The production change does not:

- weaken `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`
- reconstruct a scope from request-key strings
- create a second source owner
- bypass Source Governor or Central Scheduler
- change budgets, 4/2/2, or freeze-ready depth 4
- activate `WINDOW_12H` / `WINDOW_24H`
- unlock retrieval or financial capability

## 4. Authoritative DB identity

Canonical `inspect_authoritative_database` over
`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`:

- exists / readable: true
- SHA-256: `ca4c678b6164ad2aad36ed6140a06d96dc409d1cd3b64c40b17bce78a42b01dc`
- size: `146505728`
- inode: `1230526`
- mtime_ns: `1788290102639046545`
- migration count/head: `62` / `062_pre_admission_attempt_evidence.sql`
- `PRAGMA integrity_check`: `ok`
- foreign-key violations: `0`
- journal mode: `delete`
- sidecars (`-wal` / `-shm` / `-journal`): none
- opened mode: `read_only_immutable`

The pre-campaign SHA `f5ea648a...` is not reused as current truth.

Canonical `evaluate_schema_admission_coherence`:
`admission_schema_ready=True`, empty blocker codes.

## 5. Durable zero-state

Canonical `project_four_token_proof_zero_state` is zero across every required
domain:

- active campaigns / runs / cycles
- active campaign scheduler work
- campaign supervision (`ACTIVE`/`STOPPING`)
- proof supervision
- active discovery work
- active factory runs / steps
- non-terminal pre-admission attempts
- active pre-lifecycle discovery refresh work
- active scheduler jobs

Additional lease checks:

- campaign supervision unreleased leases: `0`
- candidate-acquisition leases: all historical `TERMINAL`; unreleased `0`

Historical terminal rows, including the consumed Sep-1 campaign
`20260901T191450Z-520d6a348621-campaign` (`TERMINAL_FAILED`), were preserved
and not mutated. Raw historical slot state is not execution authority.

## 6. Runtime quiescence

- canonical `active_printer_runtime_processes(...)`: empty
- no matching Printer / Memory Factory / four-token operational process
- no `lsof` holders on the authoritative DB
- no competing operational writer

## 7. Consumed authorization trust

Authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`

- exactly one canonical application marker
- wrapper terminal: `CHILD_EXITED_NONZERO`; one child start; retries/reruns/
  restarts/resumes/successors all `0`; `marker_consumed=true`
- permanent disposition remains
  `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

Canonical `validate_prior_authorizations_non_reusable` accepts that package's
declared prior root (56 IDs). Required permanently non-reusable IDs remain
inside it, including stale `...b6d7ab46` and consumed `...804f9a32`,
`...a89ed6bc`, `...5fcb1bf5`, `...7e03d673`.

Any future Standard-4H package must include this consumed Sep-1 ID in addition
to that complete prior root. Markers and authorization files were not modified.

Stale frozen `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46` remains
`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`.

## 8. Repair-specific readiness

Inspected current production seam, no further code change:

`CampaignSourceRequestScope`
→ `build_graduated_supply` (`scope_obj`)
→ `run_persistent_eligible_token_supply(campaign_source_request_scope=scope_obj)`
→ `_refresh_freeze_ready_depth`
→ `assemble_and_reconcile_campaign_source_requests(campaign_source_request_scope=...)`

Canonical root derivation, identity checks, and fail-closed missing / invalid /
foreign / legacy / historical-substitution guards remain in
`permanent_discovery_availability`. Focused regressions re-proved that contract
on this HEAD (`25 passed`).

No new code defect was found.

## 9. Standard-4H envelope / permanent locks

Canonical `exact_operational_policy()` remains:

- policy `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- 2 cycles; 2 tokens/cycle; 4 through-4h identities
- `automatic_retries=0`; `endpoint_rotation=false`
- `long_windows_activated=false`; locked `WINDOW_12H`, `WINDOW_24H`
- root main window `WINDOW_15M`
- freeze-ready depth `MINIMUM_FREEZE_DEPTH == 4`
- concurrent selected capacity remains 2

Window law unchanged: `WINDOW_15M -> WINDOW_1H -> WINDOW_4H -> stop`;
`WINDOW_5M_MICRO_EVENT` support-only. Cycle-2 fresh/disjoint remains owned by
`validate_later_cycle_atomic_activation`. Source Governor and Central Scheduler
remain authoritative.

Permanent V1 locks unchanged: Solana-only; Solana memecoin-only; paper-only; no
live wallet/private keys/signing/real funds/live execution; no paid API
dependency; no scoring/ranking/confidence/weighted logic; no embeddings/vectors
unless explicitly approved; no dirty-memory retrieval/decisions; retrieval and
all financial capability locked.

## 10. Verification

- independent repair production/test diff review
- focused repair/contract regressions: `25 passed`
- `python -m py_compile` of the repaired production/test files
- `git diff --check`
- canonical DB inspect, schema coherence, zero-state, runtime-process probe,
  and prior-non-reuse validation

No broad suite. No provider/source calls.

## 11. Next permitted action

This documentation-only synchronization commit becomes the exact live HEAD that
a later separately approved preparation lane must bind. Do not reuse
`95296045...` after this commit exists.

Exact next permitted lane after this commit:

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION
```

Prepare exactly one fresh exact-HEAD / exact-DB one-shot Standard-4H
authorization package using the existing canonical authorization owners, binding
the actual HEAD of this readiness commit and the freshly re-read authoritative
DB identity, including the complete prior non-reuse trust root plus
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`, and stop unconsumed
for independent package review.

Do not redo the completed authorization-boundary design. Do not create an
application marker. Do not call `apply_authorization_once`. Do not run Printer.
