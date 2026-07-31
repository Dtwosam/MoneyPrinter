# Printer V1 V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit

Date: 2026-07-31

Lane:
`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit`

Branch:
`codex/v2-9-8b-post-repair-15m-readiness-audit`

Inspected baseline HEAD:
`35258c4a3f4a4b8d3099d06345ce1afd1bf436c2`

Verdict:
`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_READINESS_AUDIT_PASS`

## 1. Boundary

This was an audit/readiness lane only.

Allowed work performed:

- static source and documentation inspection of the ordinary repaired
  `WINDOW_15M` route;
- read-only SQLite open of `data/printer_v1.sqlite3` via `mode=ro`;
- SHA-256 before/after equality;
- read-only inspection of the permanent external no-rerun marker and July 31
  terminal-summary artifact;
- readiness documentation.

Not performed:

- operational command execution (`preflight-only`, `run`, `report-only`, or any
  other mode);
- providers, RPC, WebSockets, or source fetching;
- authoritative DB mutation or copy-back;
- recovery, N2, N7, cursor reset, campaign, tracking, lifecycle, snapshot,
  window, or memory generation;
- July 31 report repair or reclassification;
- tests or broad regression suites;
- runtime, test, migration, build-order anchor, or policy changes;
- 1h/4h/12h/24h, V2-10, retrieval, paper decisions, BUY/SELL/HOLD, positions,
  trades, audits, or PnL unlock.

## 2. Baseline and Inspected Commit

| Item | Value |
| --- | --- |
| Branch | `codex/v2-9-8b-post-repair-15m-readiness-audit` |
| Inspected HEAD | `35258c4a3f4a4b8d3099d06345ce1afd1bf436c2` |
| HEAD subject | `Correct historical operational campaign status` |
| Repair closeout | `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-closeout.md` |
| Repair implementation commits | `b168c57`, `fd35b41`, `0118a37` |
| Design baseline | `e71e543d197154eba427b41e2e01574a59f527f5` |
| Worktree at audit start | clean (no runtime/doc edits before this audit file) |

## 3. Ordinary Public Route Trace (Static)

Ordinary public entry:

```text
pyproject entry: printer-run-v2-9-8-memory-factory
  -> printer_v1.operator_cli.operational_memory_factory_command:main
```

Mode dispatch (`main`):

| Mode | Owner | Ordinary authority |
| --- | --- | --- |
| `preflight-only` | `build_activation_preflight` | readiness only |
| `run` | `run_operational_campaign` | ordinary two-token `WINDOW_15M` |
| `report-only` | `report_only` | exact-identity zero-source replay |
| `status` / `cooperative-stop` / `recover-orphan` | restricted helpers | not ordinary campaign start |
| `discovery-only` | qualification only | not campaign authority |
| `selective-1h-*` | separate proof policy | locked for ordinary run |
| candidate-acquisition / cursor-recovery | deferred helpers | not ordinary prerequisite |

Ordinary `run` path (static):

```text
main(run --operator-approved)
-> run_operational_campaign / _run_operational_campaign
-> build_activation_preflight + verified backup / restore rehearsal
-> CampaignSixUnitOwner created before first accounted stage
-> independent action_local_transport_identities observer installed
-> acquire_campaign_supervision + heartbeat
-> AuthoritativeLiveOperationalCampaignOwner.run_operational(
     fifteen_minute_only=True,
     accounting_stage_evidence_sink=owner.ingest only,
     transport_identity_observer=pre-seal measurement observer
   )
-> graduated/eligible supply:
     optional locator
     direct migration discovery
     multi-round exact-liquidity front door
     selection / tracking handoff when capacity ready
-> Source Governor + Central Scheduler for lifecycle (if started)
-> cleanup_campaign_supervision
-> reconcile_campaign_terminal
-> assemble_campaign_terminal_reporting
-> _finalize_operational_six_unit_accounting
     + reconcile_owner_to_action_local (pre-lifecycle exact identity gate)
-> build/write terminal report only when accounting complete
-> report-only exact campaign/run replay
-> safe stop (automatic_retries=0; restart/successor false)
```

Policy constants on the ordinary path:

| Constant | Value |
| --- | --- |
| `TOKEN_CAPACITY` | `2` |
| `MAIN_WINDOW` | `WINDOW_15M` |
| `TOTAL_DURATION_SECONDS` | `1200` |
| `AUTOMATIC_RETRIES` | `0` |
| `LOCKED_WINDOWS` | `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` |
| `AUTHORITATIVE_DB` | `data/printer_v1.sqlite3` (via `CANONICAL_PERSISTENT_DB`) |
| ordinary `fifteen_minute_only` | hard-coded `True` |
| ordinary selective-1h continuation | `False` |
| candidate acquisition | `DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY` |

## 4. Evidence Table

| Claim | Evidence |
| --- | --- |
| Public command entry is non-placeholder | `pyproject.toml` console script `printer-run-v2-9-8-memory-factory`; module `operational_memory_factory_command.main` |
| Authoritative DB target | `AUTHORITATIVE_DB = Path(CANONICAL_PERSISTENT_DB).resolve()`; `CANONICAL_PERSISTENT_DB = .../data/printer_v1.sqlite3` |
| Required env names | `PRINTER_SOLANA_RPC_URL`, optional `PRINTER_HELIUS_API_KEY` in `operational_source_contracts.py` / readiness preflight |
| Two-token / 15m-only ordinary policy | `TOKEN_CAPACITY = 2`, `MAIN_WINDOW = "WINDOW_15M"`, `fifteen_minute_only=True`, `LOCKED_WINDOWS` |
| No proof-launcher ordinary dependency | Ordinary `run` uses `_NORMAL_CAMPAIGN_POLICY` and operational owner; no proof DB launcher |
| No N2/N7/cursor operational dependency | Deferred modes listed; ordinary run does not require them; `CANDIDATE_ACQUISITION_STATE` deferred |
| Pre-seal observer installed by coordinator | `_observe_transport_identity` + `transport_identity_observer=` in `_run_operational_campaign` |
| Owner sink is seal-ingest only | `_campaign_stage_evidence_sink` only calls `campaign_units.ingest_stage_evidence` |
| Observer reaches locator | `run_fresh_profile_locator` sets `MeasuredTransportLedger(on_transport_recorded=transport_identity_observer)` |
| Observer reaches direct migration | `direct_migration_discovery` assigns `measured_ledger.on_transport_recorded = transport_identity_observer` |
| Observer reaches each exact-liquidity round | `eligible_token_supply` passes observer into `run_graduated_liquidity_front_door`; front door ledger uses `on_transport_recorded` |
| Exception-safe sealing active | locator, direct-migration, and exact-liquidity stages seal/ingest in `finally` before unexpected exceptions escape |
| Exact identity reconciliation active | `reconcile_owner_to_action_local` requires both-direction identity-set equality; count-only -> `ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED` |
| Exact report-only selection active | `_resolve_report_only_identity` + report query by exact campaign/configuration; no global newest-report fallback |
| Missing report/summary fail-closed | `EXACT_TERMINAL_REPORT_MISSING` vs `EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED` |
| Migration head | 49 migrations; latest `049_candidate_acquisition_integration.sql` |
| Integrity | `PRAGMA integrity_check = ok`; foreign-key check rows `0` |
| DB SHA-256 before | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |
| DB SHA-256 after | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` (equal) |
| No WAL/SHM/journal sidecars | only `data/printer_v1.sqlite3` present under `data/` |
| Active campaigns/runs/supervision | all campaign/run rows terminal (`TERMINAL_COMPLETED` or `TERMINAL_FAILED`); all supervision `TERMINAL` |
| Active Scheduler jobs/locks | status only `SUCCEEDED`/`FAILED`/`CANCELLED`; zero locked/runnable jobs |
| Discovery work / factory steps | only terminal `SUCCEEDED`/`FAILED`/`CANCELLED` |
| Candidate-acquisition leases active | zero active/stopping held leases; 19 terminal leases historical |
| July 31 campaign residual | campaign/run/cycle terminal with `SOURCE_VISIBILITY_SHORTAGE`; supervision terminal COMPLETED; lease released; cleanup completed |
| July 31 report row | `0` rows for that campaign |
| July 31 exhaustion certificate | present; classification `SOURCE_VISIBILITY_SHORTAGE`; 30 source ops used |
| July 31 terminal summary | present externally; `report_written=false`; `SIX_UNIT_ACCOUNTING_BLOCKED` / `SIX_UNIT_EVIDENCE_MISSING`; `restart_created=false`; `successor_created=false` |
| Permanent no-rerun marker | `$HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json`; `attempt_number=1`; `rerun_authorized=false`; pins launch commit `b5761b65...` |
| Retrieval / financial baselines | retrieval matches `0`; retrieval queries `10`; paper decisions `2`; paper audit reports `1`; positions/trade events/trade audits `0` |

## 5. Independent Pre-Seal Observer Coverage

The public coordinator creates one action-local list and one observer. That
observer is passed through:

1. `AuthoritativeLiveOperationalCampaignOwner.run_operational`
2. `build_graduated_supply` / `run_persistent_eligible_token_supply`
3. optional locator stage
4. direct migration discovery stage
5. each exact-liquidity front-door round

At measurement time, `MeasuredTransportLedger.record_transport` invokes
`on_transport_recorded` **before** stage sealing. The campaign sink remains a
separate owner-ingest path and does not copy sealed transports into
action-local. This preserves independent verification rather than sealed-stage
self-comparison.

Pre-lifecycle completion requires exact owner/action-local identity equality.
Holder/lifecycle stages after lifecycle start are intentionally not forced into
that pre-lifecycle gate (documented residual risk from the repair closeout; not
a readiness blocker for ordinary pre-lifecycle accounting).

## 6. Exact Report-Only and Historical July 31 Behavior

Repaired `report-only`:

- requires both `--campaign-id` and `--run-id`, or neither;
- with neither, resolves newest **supervision** first, then that exact
  campaign/run/configuration;
- never selects the globally newest report first;
- returns deterministic `REPLAY_BLOCKED` when the exact report is missing.

Historical July 31 facts remain:

- campaign verdict `V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`;
- no terminal report row;
- terminal summary exists but lacks top-level `run_id` and `configuration_id`;
- under the repaired summary loader, incomplete summary identity fails closed
  rather than replaying the unrelated July 28 report;
- permanent marker forbids rerun of execution `20260731T002406Z-7612696c7295`.

This audit does not repair or reclassify that attempt.

## 7. Authoritative Residual State Summary

```text
DB: data/printer_v1.sqlite3
SHA-256: f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
integrity: ok
foreign_key_violations: 0
migration_rows: 49
migration_head: 049_candidate_acquisition_integration.sql
sidecars: none
```

Operational residual:

| Surface | Residual |
| --- | --- |
| Campaigns | 18 terminal historical rows (11 completed / 7 failed) |
| Runs | 18 terminal historical rows |
| Supervision | 18 terminal rows; zero non-terminal |
| Scheduler jobs | only SUCCEEDED/FAILED/CANCELLED; zero active/locked |
| Discovery work | only SUCCEEDED/FAILED |
| Factory steps | only SUCCEEDED/CANCELLED |
| Proof supervision | 0 rows |
| Active CA leases | 0 |
| July 31 lifecycle windows/slots/factory runs/discovery work/jobs | 0 |
| July 31 reports | 0 |
| Restart/successor/resume for July 31 | false / not present |

Residual history is present and expected after prior operator campaigns. No
active campaign, supervision, Scheduler lock, discovery work, factory step, or
proof supervision remains runnable.

## 8. Exact Command and Environment Contract

Readiness command shape (not executed by this audit):

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  preflight-only
```

Future ordinary campaign command shape (not authorized by this audit):

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  run --operator-approved
```

Equivalent entrypoint name:

```text
printer-run-v2-9-8-memory-factory
```

Environment-variable names (values not inspected/printed here):

- required: `PRINTER_SOLANA_RPC_URL`
- optional free holder backup: `PRINTER_HELIUS_API_KEY`

DB target:

```text
data/printer_v1.sqlite3
```

## 9. Readiness Blockers

None found that require mutation, execution, source access, or repair.

Non-blocking residual awareness items:

1. Historical July 31 attempt remains `BLOCKED_UNSAFE` with incomplete canonical
   report and incomplete top-level terminal-summary identity fields. The repaired
   report-only path fail-closes rather than replaying a stale report.
2. Permanent first-authoritative no-rerun marker remains in place and correctly
   blocks any rerun of execution `20260731T002406Z-7612696c7295`. A later
   post-repair campaign, if ever authorized, must use a new execution identity
   and its own design/authorization sequence.
3. Post-lifecycle holder/scheduler stages are still outside the pre-lifecycle
   action-local identity gate (repair residual risk).
4. This audit did not re-run zero-source preflight or local tests; runtime proof
   of the repair remains grounded in the prior implementation closeout and the
   static/DB evidence above.

## 10. Money-Usefulness Contribution

This readiness gate confirms that the accounting/exact-identity repair is
present on the ordinary route and that the authoritative corpus is quiet enough
to consider a later design/authorization packet. That reduces the chance a next
bounded 15m learning attempt starts with:

- incomplete stage accounting;
- sealed-stage self-comparison disguised as independent verification;
- stale report-only fallback;
- active Scheduler/supervision residue;
- accidental July 31 rerun; or
- retrieval/financial unlock drift.

Honest shortage and fail-closed accounting remain valid terminal outcomes.

## 11. What This Audit Improves

- re-validates the repaired ordinary public route after the accounting repair;
- confirms independent pre-seal observation and exact owner reconciliation;
- confirms exact-identity report-only fail-closed behavior;
- records current authoritative residual state without mutating it;
- preserves the permanent July 31 no-rerun boundary;
- establishes the evidence needed for a post-repair campaign design/runbook.

## 12. What This Audit Still Does Not Unlock

It does not unlock:

- campaign execution;
- providers/RPC/WebSockets/source fetching;
- July 31 repair, backfill, or reclassification;
- recovery, N2, N7, cursor reset, or candidate-acquisition authority;
- memory generation or clean-memory promotion;
- `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H`;
- V2-10;
- retrieval;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

A readiness PASS may authorize only the next approved design/specification or
final-authorization step. It does not authorize campaign execution.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

- Provider availability and two-token eligible supply remain unproved until an
  authorized live attempt; readiness cannot guarantee market visibility.
- Environment values can drift between this audit and any future authorization;
  a fresh zero-source preflight must be part of any later design/authorization
  packet.
- Historical terminal corpus rows remain in the authoritative DB; future
  readiness/preflight must continue to distinguish terminal history from active
  residue.
- The first-authoritative permanent marker must not be deleted or reused as a
  shortcut for a second attempt.
- Focused repair suites previously passed, but this audit intentionally did not
  re-run tests; any later implementation lane must not weaken those proofs.
- Post-lifecycle identity equality remains a residual design surface if full-run
  transport equality is required beyond pre-lifecycle shortage terminals.

## 14. Acceptance Gate

PASS because all of the following hold:

- repaired ordinary route statically includes independent pre-seal observation,
  exception-safe sealing, exact owner/action-local reconciliation, and exact-
  identity report-only fail-closed behavior;
- authoritative residual state is terminal-only with zero active/runnable work;
- exact non-placeholder command, DB target, env names, two-token/`WINDOW_15M`
  policy, and deferred N2/N7/cursor status are consistent;
- July 31 remains permanently no-rerun and `BLOCKED_UNSAFE` without
  retry/restart/resume/successor/recovery/reclassification;
- retrieval/financial baselines remain locked;
- authoritative DB SHA-256 is unchanged by this audit.

## 15. Exact Next Permitted Lane

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Design and Operator Runbook
```

Type: design/specification only.

That lane must define the exact post-repair launch command packet, one-campaign
boundary, fresh preflight requirements, operator checkpoints, terminal evidence
bundle, stop conditions, interaction with the existing first-authoritative
no-rerun marker, and closeout requirements for a new execution identity.

It must not execute a campaign, contact providers/RPC, mutate the authoritative
database, repair the July 31 attempt, or unlock retrieval/financial capabilities.
