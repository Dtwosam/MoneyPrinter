# Printer V1 V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Implementation

Date: 2026-08-01

Lane: `V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Implementation (C1-C15)`

Branch: `agent/v2-9-8b-c1-c15-full-run-implementation`

Starting HEAD: `6aab4aa22f81b6e52b7376ad767a47fed121de6f`

Ending HEAD: reported from `git rev-parse HEAD` in the final handoff after the
lane commit. A Git commit cannot embed its own object ID because changing that
text changes the object ID; the final response is the exact ending-HEAD record.

Type: implementation and focused disposable-database verification only.

Verdict:
`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`

This PASS authorizes only independent read-only conformance review. It does not
authorize migration application, bounded proof, campaign execution, or any later
capability.

## Implementation result

The ordinary coordinator now creates one `CampaignSixUnitOwner` and one
`CampaignActionLocalLedger` before accountable work, carries a complete immutable
campaign/run/cycle/configuration/factory identity through the real factory, and
finalizes those same objects into one canonical report. The finalizer uses the
accepted stage-scoped Scheduler ownership API and the obsolete shadowed
pre-migration projection implementation was removed. No second accounting owner,
Scheduler, source path, campaign runner, replay owner, or report owner was added.

Governed attempts are observed at the actual success/failure boundary, including
primary, fallback, backup, context, snapshot, and close attempts. Response bytes
and normalized rows come from canonical transport metadata, never `LENGTH(...)`
or a hardcoded row count. Reservations and named validations are emitted at their
real capacity and validation boundaries. Scheduler enqueue/claim/terminal events
are observed at central Scheduler boundaries, while authoritative cleanup
cancellations are observed in unified cleanup.

Campaign window ownership is registered immediately after a lawful close and
before Scheduler/slot terminalization. Slot disposition is read back from the
persisted tracking queue and slot; there is no default `COOLDOWN`. Report-only
reconstruction opens the exact disposable database read-only, verifies durable
V2 evidence and hashes, independently reconstructs ownership and Scheduler state,
and performs zero source calls, Scheduler actions, or writes. Historical V1
evidence cannot satisfy repaired V2 replay or acceptance.

## Files changed

| File | Implementation |
| --- | --- |
| `src/printer_v1/operator_cli/campaign_full_run_accounting.py` | Exact context, lifecycle observation adapter, accepted scope-aware lifecycle projection, all-stage owner/action equality, durable-attempt reconstruction, cadence/ownership/terminal report, strict gate, report hashes, actual cleanup/retry truth. |
| `src/printer_v1/operator_cli/campaign_ownership.py` | Removed obsolete duplicate pre-migration projection; retained the sole stage-scoped authority and WINDOW_LIFECYCLE compatibility wrapper. |
| `src/printer_v1/operator_cli/campaign_supervision.py` | Emits action-local terminal evidence for jobs cancelled at the authoritative unified-cleanup boundary. |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | Preallocated factory identity, actual attempt/reservation/validation/Scheduler observation, close-boundary campaign registration, shared reservation policy. |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Creates and preserves the single owner/ledger, propagates complete context and observers, seals real discovery/terminal stages, consumes actual cleanup truth, persists the canonical report, exposes read-only exact replay. |
| `src/printer_v1/operator_cli/origin_lifecycle_campaign.py` | Projects exact discovery/selection and first-15m handoff Scheduler jobs through the stage-scoped authority at the real handoff boundary. |
| `src/printer_v1/operator_cli/unified_terminal_closure.py` | Uses registered campaign-window ownership to persist the lawful queue/slot terminal disposition without defaulting to `COOLDOWN`. |
| `src/printer_v1/scheduler/scheduler.py` | Context-local enqueue/claim/terminal observer at the central Scheduler mutation boundaries. |
| `src/printer_v1/sources/campaign_six_unit_accounting.py` | Deterministic owner/ledger identities, transition coverage, idempotent close, full-manifest non-vacuous bidirectional equality. |
| `src/printer_v1/sources/governed_execution.py` | Context-local observer for every actual governed success/failure attempt. |
| `src/printer_v1/sources/measured_transport.py` | Canonical result/reservation linkage and the single immutable WINDOW_15M reservation policy. |
| `tests/test_v2_9_8b_full_run_accounting_semantics_correction.py` | Focused positive and fail-closed C1-C15 semantic proofs. |
| `tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py` | Ownership, projection, report/gate, quality, terminal, and replay proofs. |
| `tests/test_v2_9_8b_full_run_wiring_integration.py` | Real disposable factory/coordinator boundary, 16 snapshots/two closes, 28 governed attempts/reservations, complete Scheduler families, exact public replay. |
| `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` | Historical V1 replay blocks; disposable migration-head assertions use accepted 050. |
| `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` | Accepted disposable migration-050 head assertions. |
| `tests/test_v2_9_8b_operational_factory_active_path_restoration.py` | Accepted migration-050 schema-head contract. |
| `tests/test_v2_9_8b_post_handoff_terminal_compensation.py` | Accepted disposable migration-050 head assertions. |
| `docs/printer-v1-v2-9-8b-post-repair-window-15m-full-run-accounting-and-terminal-evidence-implementation.md` | This factual closeout. |

## C1-C15 completion-law conformance

| ID | Design requirement | Real execution boundary | Single-owner evidence | Independent action-local evidence | Canonical report field | Acceptance gate | Positive proof | Negative proof | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | One continuous owner and ledger | Coordinator allocation before owner execution; same objects passed to finalizer | Deterministic `owner_id`, stage ingestion, V2 durable evidence | Deterministic `ledger_id`, live observer callbacks | `full_run_accounting.accounting_owner_id`, `action_local_ledger_id` | Continuity mismatch compensation block plus non-vacuous equality | Real factory/coordinator helper reaches PASS with the same objects | Replacing owner or ledger blocks | PASS |
| C2 | Complete immutable identity before planning/source work | Preallocated factory run and validated `OperationalLifecycleOwnershipContext` before driver/factory work | Owner campaign/run/cycle plus factory-bound sealed stages | Observer closes over the same immutable context | `identity.*`, selection batch and factory config hash | Canonical identity completeness and one authoritative bind | Two-token factory runs under the preallocated exact identity | Factory-run drift produces no succeeded closes | PASS |
| C3 | Observe every governed attempt exactly once | `execute_governed_source_attempt` success/failure return boundary | Durable request/response/failure-linked transport identities in slot stages | `GOVERNED_SOURCE_ATTEMPT` callback for primary/fallback/backup/context/close | `source_operation_outcomes`, owner/action transport identities | Exact bidirectional reconciliation and attempted=succeeded+failed | 28 attempts: 18 pair observations plus 10 close-context attempts | Removing one context attempt blocks | PASS |
| C4 | Canonical bytes and normalized rows | Governed adapter canonical metadata merge | Exact response/failure identity with bytes, rows, result, reservation link | Same measured identity observed before sealing | Six-unit totals and full transport identity lists | Exact identity equality; positive nonzero operations | Canonical response-byte/row totals match | Same request identity with byte or row drift blocks | PASS |
| C5 | Reservations at authoritative boundary | Factory capacity check immediately before a step executes | Step result persists exact reservation identities from shared policy | `LIFECYCLE_RESERVATION` emitted after capacity succeeds | Reserved/attempted/succeeded/failed outcomes and reservation identities | Nonzero reservation/attempt outcome completeness | Exactly 28 reservations for 16 snapshots and two closes | Missing/ordinal-drift reservation evidence blocks | PASS |
| C6 | Named validations when executed | Immutable identity, cadence, capacity, pair, close, coverage, quality, handoff and terminal checks | Named validation identities sealed in their actual stages | `LOCAL_VALIDATION` and boundary validation observations | `named_validation_families` | Required-family set must be complete | All required families present in real fixture | Removing a validation identity blocks equality | PASS |
| C7 | Complete Scheduler ownership and transitions | Central enqueue/claim/terminal, origin projection, factory jobs, unified cleanup cancellation | One V2 stage-scoped ownership row per job; discovery, selection, handoff, lifecycle scopes | Transition events with enqueue/claim/terminal coverage; cleanup cancellation callback | Scheduler rows, family attribution, transition coverage, cleanup observation counts | Exact lifecycle correspondence, discovery/selection/handoff/18 lifecycle attribution, terminal/lock/cleanup checks | Positive fixture has discovery, selection, two handoffs and 18 lifecycle jobs | Missing discovery row, removed identity, failed/nonterminal/locked/retried/cross-scope conflict block | PASS |
| C8 | Full repaired-manifest equality | Final reconciliation after all four stages seal | Complete owner manifest and diagnostics | Complete ledger identities across every stage | `owner_action_local_reconciliation.equality_scoped_stage_ids=null` | Equality must be non-vacuous and unscoped | Four-stage equality passes | Scoped equality or an omitted mandatory stage blocks | PASS |
| C9 | Window ownership before terminalization; no default cooldown | Immediately after succeeded close, before Scheduler completion and unified slot reconciliation | Exact campaign/run/cycle/slot/window ownership row | Close/window validation and persisted-state observation | Ownership rows and `slot_dispositions` with queue/slot read-back | Both windows owned and persisted dispositions exact | Two campaign-owned terminal windows preserve lawful `COOLDOWN` | Missing ownership or mismatched persisted state blocks; no close defaults | PASS |
| C10 | Exact cadence/coverage/two closes | Real snapshot and close steps | Authoritative cadence policy, exact step/snapshot/job IDs | Step-local cadence/close validations | Per-token cadence evidence and close IDs | Two normal tokens, total 16 snapshots, one succeeded close each, zero missing | Exactly 16 snapshot steps and two succeeded closes | Missing snapshot/close or cadence mismatch blocks | PASS |
| C11 | Prevent unlawful clean episode insertion | Pre-insert quality/do-not-train gate in clean-memory creation | Durable window quality and actual episode rows | Quality validation at close | `quality_consistency`, episode ID/kind/outcome | Quality must be explicitly consistent | Clean windows retain lawful outcome | Dirty window call returns blocked and inserts zero clean episodes | PASS |
| C12 | One complete canonical report | Coordinator finalization after cleanup/reconciliation | Owner evidence, stages, Scheduler rows, identity, cadence, safety and hashes | Full ledger evidence and transition coverage embedded | `V2_9_8B_FULL_RUN_WINDOW_15M_TERMINAL_EVIDENCE` | No omitted family and no default-true Scheduler/quality inputs | Complete report and gate/top-level verdict agree | Omitted Scheduler family or lease failure blocks every PASS surface | PASS |
| C13 | Actual authorization, marker/hash and terminal safety truth | Durable bind/read-back and unified cleanup result | Config/invocation marker plus owner evidence hash | Ledger hash and observed work/lease/forbidden-delta facts | `hashes`, `authorized_invocation_count`, `terminal_safety` | Exact invocation, 64-char hashes, zero active/locked/retry/restart/resume/successor and forbidden deltas | One invocation, hashes present, zero residue/deltas | Count 0/2, lock, retry, lease, forbidden delta, successor truth omission block | PASS |
| C14 | Public exact report-only replay with zero effects | SQLite URI `mode=ro` exact campaign/run lookup | Durable V2 report, owner evidence and database ownership rows | Recomputed owner/action/body hashes and independent row reconstruction | Exact replay payload and side-effect counters | V2 evidence, unscoped equality, hashes and durable rows must match | Public replay reproduces exact hashes with unchanged DB mtime and zero calls/actions/writes | Wrong identity, missing V2 evidence and historical V1 report block | PASS |
| C15 | Real stage terminal status and immutable first cause | Slot step/Scheduler boundary, origin handoff boundary, terminal cleanup boundary | Per-stage `stage_terminal_status` and `first_terminal_cause` | Terminal transition events carry actual state/cause/time | `sealed_stage_diagnostics`, runtime first cause, Scheduler terminal fields | All mandatory stages must explicitly be `COMPLETED`; failed/blocked stages remain visible | Four real mandatory stages report completed | Failed/nonterminal Scheduler or missing/altered stage blocks | PASS |

## Verification commands and exact results

All databases were created under disposable temporary directories by the tests.
Injected/frozen adapters were used; no provider, RPC, WebSocket, discovery
network, operational campaign, or public runtime command was executed.

```text
.venv/bin/python -m py_compile src/printer_v1/operator_cli/campaign_full_run_accounting.py src/printer_v1/operator_cli/campaign_ownership.py src/printer_v1/operator_cli/campaign_supervision.py src/printer_v1/operator_cli/one_command_15m_factory.py src/printer_v1/operator_cli/operational_memory_factory_command.py src/printer_v1/operator_cli/origin_lifecycle_campaign.py src/printer_v1/operator_cli/unified_terminal_closure.py src/printer_v1/scheduler/scheduler.py src/printer_v1/sources/campaign_six_unit_accounting.py src/printer_v1/sources/governed_execution.py src/printer_v1/sources/measured_transport.py
Result: exit 0, no output.

.venv/bin/python -m pytest -q tests/test_v2_9_8b_full_run_accounting_semantics_correction.py tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py tests/test_v2_9_8b_full_run_wiring_integration.py
Result: 47 passed, 6 subtests passed in 13.14s.

.venv/bin/python -m pytest -q tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py
Result: 51 passed, 1 skipped in 10.77s. The skip is the suite's intentional platform/fixture skip.

.venv/bin/python -m pytest -q tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py tests/test_v2_9_8b_terminal_safety_accounting_finalization.py tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py tests/test_v2_4_one_command_15m_factory.py tests/test_v2_9_8b_operational_factory_active_path_restoration.py tests/test_v2_9_8b_post_handoff_terminal_compensation.py tests/test_v2_9_8b_restored_factory_source_compatibility_reset.py
Result: 130 passed in 37.99s.

.venv/bin/python -m pytest -q tests/test_v2_9_7e_46b_2_source_accounting.py
Result: 10 passed in 2.51s.

git diff --check
Result: exit 0, no output.
```

No full repository suite was run because the focused matrix did not expose a
shared architectural regression.

## Money-usefulness contribution

This is defensive money-usefulness. A WINDOW_15M run can no longer claim useful
learning evidence without proving the exact source attempts, Scheduler work,
reservations, validations, cadence, campaign ownership, window quality, cleanup,
and terminal state that produced it. That reduces the chance that incomplete,
duplicated, stale, or dirty operational evidence contaminates later analysis. It
adds no trading or money-moving capability and makes no profitability claim.

## What improved

- Repaired the obsolete finalizer call and removed duplicate ownership logic.
- Moved identity, attempt, reservation, validation, ownership, and terminal facts
  to their actual execution boundaries.
- Made equality cover the complete repaired stage manifest.
- Made report completeness, Scheduler families, cleanup, cadence, hashes and
  replay fail closed instead of relying on counts or omitted/default-true fields.
- Proved the required two-token, 16-snapshot, two-close disposable fixture and
  public exact zero-side-effect replay.

## What remains locked

Migration 050 application to `data/printer_v1.sqlite3`; authoritative database
access; bounded/live proof; providers, RPC, WebSockets and network discovery;
operational campaign/public runtime execution; authoritative memory generation or
promotion; 1h/4h/12h/24h; retrieval; paper decisions; BUY/SELL/HOLD; positions,
trades, audits and PnL; wallets, keys, signing, real funds and live execution;
paid APIs; scoring, ranking, confidence, weighting, embeddings and vectors.

## Proof still required

Only an independent read-only conformance review is authorized next. That review
must inspect this commit and the focused disposable evidence without applying
migration 050, opening the authoritative database, running a campaign, or
promoting any evidence. A later bounded-proof or operational lane requires a new
explicit authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Impact | Disposition |
| --- | --- | --- |
| Commit hash self-reference | The exact final commit ID cannot be embedded in the commit that defines it. | Starting HEAD is embedded; final `git rev-parse HEAD` is recorded in the handoff. |
| Cleanup cancellation observer is callback-based | A callback failure aborts cleanup rather than allowing unobserved terminal evidence. | Fail-closed by design; focused cleanup regressions pass. |
| Historical direct Scheduler writers still exist outside this lane | They cannot satisfy repaired V2 acceptance unless their exact work is projected and observed. | V2 gate blocks missing transition/ownership families; no expansion into unrelated lanes. |
| Full repository suite not run | Unrelated failures are not surveyed. | Focused architectural matrix is green, so the task explicitly says not to expand scope. |

## Final verdict

`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`

Next permitted lane: `V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Independent Read-Only Conformance Review`.

Stop after commit and push. Do not merge, tag, apply migration 050, run a
campaign, or open a successor implementation/proof lane.
