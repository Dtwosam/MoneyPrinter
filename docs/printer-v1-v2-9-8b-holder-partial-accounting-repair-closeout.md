# V2-9.8B Holder Partial Accounting and Snapshot Readiness Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Holder Partial Accounting and Snapshot Readiness Repair`

## Verdict

`V2_9_8B_HOLDER_PARTIAL_ACCOUNTING_REPAIR_PASS`

Both shared-path defects are repaired and proven offline with fixture transports only. No providers, discovery runtime, Scheduler runtime, authorization, `WINDOW_15M`, memory generation, retrieval, decisions, positions, trades, audits, or PnL were run.

## The two defects

### Defect 1 — `SNAPSHOT_READINESS` ignored `HolderContextResult.accounting_blocker`

`run_snapshot_readiness()` consumed only `holder_result.holder_facts` and `holder_result.ledger`. A holder stage whose governed request/transport accounting was incomplete still produced holder-eligible candidates, still attempted readiness snapshot bundles, and could still return `READY`. Untrustworthy holder accounting was invisible to the readiness gates and to the terminal status.

### Defect 2 — A partial holder attempt could disappear

`_evaluate_holder_eligibility()` called `_collect_preclose_context()` and then `persist_bundle_attempts()` inside one `try`. Any exception was swallowed into a candidate-local `HOLDER_EVIDENCE_COLLECTION_FAILED` fact. Consequences:

* a GoPlus governed request that really succeeded, followed by an RPC factory/collection failure, left a durable `printer_source_requests` row that never reached holder IDs, coverage, the campaign manifest, or reconciliation;
* a `persist_bundle_attempts()` failure after processing some executions lost every ID and coverage entry already derivable from real execution records;
* no holder accounting blocker was raised, so campaign reconciliation, `PILOT_INPUT_READINESS`, and `SNAPSHOT_READINESS` all passed over a real, unaccounted governed request.

## Production owners changed

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/holder_reliability_budget_control.py` | New `HolderBundlePersistPartialError`; `persist_bundle_attempts()` restructured per-execution around `_persist_one_holder_attempt()` / `_blocked_coverage_entry()` so a durable identity is captured before any operation that can raise, and a typed partial result is raised instead of losing evidence |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | New `PrecloseContextPartialError`; `_collect_preclose_context()` gains opt-in `preserve_partial_executions` holder mode carrying the governed executions that already happened. Default caller behaviour unchanged |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | `_evaluate_holder_eligibility()` opts into the partial mode and recovers/persists partial attempts as `BLOCKED` coverage with a typed accounting blocker; `run_snapshot_readiness()` inspects the complete `HolderContextResult`, adds the `holder_accounting_complete` gate, `BLOCKED_HOLDER_ACCOUNTING` status, and holder evidence surfaces; `SnapshotReadinessResult.holder_context` added |
| `tests/test_v2_9_8b_holder_partial_accounting_repair.py` | New focused proofs (19) |
| `tests/test_v2_9_7e_33_canonical_readiness_boundary.py` | `_eligible_safety_factories()` fixture now attaches the same authoritative single-HTTP `GOPLUS_TRANSPORT_OPERATION_COST` the production normalizer emits (the raw fixture adapter bypasses that normalizer) |
| Closeout | this document |

No migration. No provider, fallback, Source Governor, or Central Scheduler policy changed.

## Partial-result contract

Two typed contracts, both fail-closed, both carrying only real evidence.

```text
PrecloseContextPartialError            # one_command_15m_factory
  code           = PRECLOSE_CONTEXT_COLLECTION_FAILED
  executions     # every governed execution that really happened
  failed_stage   # market_chain | safety | entry_quote | exit_quote
                 # | holder_primary | holder_backup
  cause
```

```text
HolderBundlePersistPartialError        # holder_reliability_budget_control
  code           = HOLDER_BUNDLE_PERSIST_INCOMPLETE
  partial        -> HolderBundlePersistResult
                      governed_request_count      # = preserved durable IDs
                      measured_transport_count    # 0 on an incomplete attempt
                      source_request_ids          # every real request row
                      source_request_coverage     # all entries terminal BLOCKED
                      accounting_blocker = True
                      accounting_blocker_reason
  failed_stage   # execution key that failed
  cause
```

`_collect_preclose_context(..., preserve_partial_executions=True)` is a holder-specific mode. It reuses the existing governed holder collection logic, duplicates no provider or fallback policy, and leaves the default (`False`) path used by unrelated memory-close callers byte-for-byte in behaviour — the original exception propagates untouched.

`_evaluate_holder_eligibility()` recovery, per failing candidate:

1. classify the typed partial (`HolderBundlePersistPartialError` → evidence already built; `PrecloseContextPartialError` → re-run `persist_bundle_attempts()` over the preserved executions, itself tolerant of a second typed partial);
2. add every preserved durable request ID to holder IDs;
3. add every preserved coverage entry with `terminal_status=BLOCKED`;
4. set `accounting_blocker=True` with reason `HOLDER_PARTIAL_ATTEMPT_<ExcType>:stage=<stage>` joined with the persist-owner reason;
5. add the real governed request and measured transport counts to the ledger (never fabricated);
6. terminalize maturation work and keep the candidate-local `HOLDER_EVIDENCE_COLLECTION_FAILED` fact.

A failure before any governed request exists reports zero IDs and zero coverage but still sets the holder-stage accounting blocker.

## Snapshot-readiness fail-closed behaviour

After `_evaluate_holder_eligibility()` returns, `run_snapshot_readiness()` reads the complete result:

```text
holder_result.accounting_blocker == True
  -> snapshot_candidates = []          # zero readiness snapshot bundles attempted
  -> gate holder_accounting_complete = False
  -> READY unreachable
  -> status = BLOCKED_HOLDER_ACCOUNTING     (dominates other blockers)
```

Exposed on `summary` and on the new `SnapshotReadinessResult.holder_context`:

```text
holder_context.accounting_blocker
holder_context.accounting_blocker_reason
holder_context.source_request_ids
holder_context.source_request_coverage
holder_context.governed_request_count
holder_context.measured_transport_count
```

plus flattened `holder_accounting_blocker`, `holder_accounting_blocker_reason`, `holder_source_request_ids`, `holder_source_request_coverage`, `holder_governed_request_count`, `holder_measured_transport_count`.

Lifecycle, memory windows, run steps, retrieval, decisions, positions, trades, audits, and PnL remain at zero on every blocked path.

`PILOT_INPUT_READINESS` blocks through the already-committed campaign reconciliation owner: the holder stage result is published to `holder_context` / `holder_source_request_ids` / `holder_source_request_coverage`, and `collect_stage_accounting_blockers()` turns the holder blocker into `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` before readiness/handoff.

## Source failure versus accounting failure

| Case | Coverage terminal | `accounting_blocker` | Effect |
|---|---|---|---|
| Holder evidence rate-limited / unavailable / extreme, **measured accounting complete** | may be `BLOCKED` | `False` | evidence context only; `MEMORY_OBSERVATION` path stays open; readiness not blocked by holder |
| Missing or contradictory measured transport evidence | `BLOCKED` | `True` | typed holder accounting blocker |
| Governed request exists, later collection/persistence raises | `BLOCKED` | `True` | IDs + coverage preserved; typed holder accounting blocker |
| Failure before any governed request exists | none | `True` | zero IDs, holder-stage accounting blocker |

Request count and transport count remain independent and are never invented. The e33 fixture correction is the same rule applied to a test double: a raw fixture adapter that bypasses the GoPlus normalizer must attach the measured count the normalizer would have attached, otherwise the stage correctly fails closed.

## Exact tests and counts

| Suite | Result |
|---|---|
| `tests/test_v2_9_8b_holder_partial_accounting_repair.py` (new) | **19 passed** |
| Directly affected holder, snapshot-readiness, reconciliation, campaign, and pre-close-caller suites (20 files incl. the new one) | **249 passed, 38 subtests passed, 2 pre-existing failures** |
| `tests/test_v2_9_3_early_failure_accounting_repair.py` (pre-close caller, run separately) | **4 passed, 2 pre-existing failures** |
| `compileall` (3 changed production modules + 2 changed/new test modules) | OK |
| `git diff --check` | OK |

Focused proof coverage, in lane order:

1. holder accounting blocker attempts zero readiness snapshot bundles (base factory `assert_not_called`, zero `printer_token_snapshots`);
2. readiness cannot return `READY` — `holder_accounting_complete` gate `False`, status `BLOCKED_HOLDER_ACCOUNTING`;
3. report exposes holder IDs (each proven durable in `printer_source_requests`), coverage, reason, governed request count, measured transport count;
4. GoPlus request succeeds, later RPC factory raises → GoPlus durable ID still reported;
5. the partial GoPlus coverage remains in the campaign manifest and stage/coverage collectors;
6. the partial collection sets a typed `HOLDER_PARTIAL_ATTEMPT_*` accounting blocker with `BLOCKED` coverage;
7. persistence failure after a governed request exists preserves both request IDs;
8. persistence failure emits `BLOCKED` coverage for that request, each ID proven durable;
9. `PILOT_INPUT_READINESS` reconciliation blocks on the partial holder attempt (`pilot_input_readiness is None`, recon `BLOCKED`, holder stage blocker present);
10. `SNAPSHOT_READINESS` blocks on the same partial-attempt condition with zero bundles;
11. failure before any request exists → accounting blocker, zero IDs, zero coverage, zero counts;
12. rate-limit / source-unavailable evidence with complete measured accounting stays context-only (both at stage level and at readiness level);
13. holder-extreme evidence remains valid for `MEMORY_OBSERVATION` (recon `OK`, freeze depth enforced);
14. future action remains `BLOCKED_OR_UNKNOWN`;
15. no lifecycle, memory windows, run steps, retrieval, decisions, positions, trades, audits, or PnL occur (readiness and campaign variants);
    plus: `_evaluate_holder_eligibility` preserves IDs when persistence always fails, and `_collect_preclose_context` default mode keeps the raising behaviour (no `PrecloseContextPartialError`).

Tests 4, 5, 6, 9, 10, 11, 12, 13, 14, 15 drive the **real** holder collection path through `_evaluate_holder_eligibility()` / the authoritative campaign owner and create genuine durable `printer_source_requests` rows before the injected later failure. No test satisfies a proof with a prebuilt `HolderContextResult`.

Pre-existing baseline failures (confirmed unchanged against `8134cd5`, deferred per the risk-based verification policy):

* `test_v2_9_7e_33_canonical_readiness_boundary.py::CanonicalModeSurfaceTests::test_activation_only_dispatch_starts_no_lifecycle` (`NOT_READY` vs `READY`);
* `test_v2_9_6_safety_context_source_redundancy.py::SafetyContextSourceRedundancyTests::test_goplus_holder_disagreement_is_blocking`;
* `test_v2_9_3_early_failure_accounting_repair.py` (2 environment-dependent `GitProvenanceError` cases).

## Schema result

No migration. Existing `printer_source_requests`, `printer_holder_evidence_attempts`, `printer_holder_campaign_operation_ledgers`, and existing report/diagnostics JSON surfaces only. One additive default-valued dataclass field (`SnapshotReadinessResult.holder_context`).

## Money-usefulness contribution

Pre-lifecycle admission cannot honestly claim readiness while a governed holder request that really happened is invisible, or while holder accounting is untrustworthy. The repair closes the last two shared paths where an operator could have been shown `READY` or a passing reconciliation over an unaccounted real request. Operators now get: zero snapshot spend on an untrustworthy holder stage, a typed terminal naming the exact cause, and the exact durable IDs, coverage, request count, and transport count behind that decision — without treating ordinary holder evidence failure as a campaign accounting fault, which would have destroyed usable `MEMORY_OBSERVATION` supply.

## What remains locked

Freeze depth `4`, surplus target `8`, liquidity floor `$3,000`, ceiling `30`, reservations `3/2/6/7/8/4`, holder evidence as `MEMORY_OBSERVATION` context, the `FUTURE_ACTION` holder gate, Source Governor and Central Scheduler ownership, provider/fallback selection, retrieval and trading locks, clean-memory creation, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, live execution, wallets, paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors, authorization, and `WINDOW_15M`.

## Remaining risks

* Fixture adapters that bypass a source normalizer must still attach measured transport metadata when they participate in the holder path. Missing counts now fail closed loudly at readiness as well as at reconciliation; the e33 fixture is corrected, but other suites that add holder participation later must do the same.
* `BLOCKED_HOLDER_ACCOUNTING` deliberately dominates `CANCELLED` and pool/bundle blockers. An operator reading only the status sees the accounting fault first; the maturity, eligibility, and bundle detail remain in `summary` and must still be read.
* The ledger is credited with the real governed request/transport counts of a partial attempt. Under the permanent-availability path this consumes the holder safety reservation honestly, so a repeatedly-failing holder source will reach `PERMANENT_DISCOVERY_HOLDER_SAFETY_RESERVATION_EXCEEDED` sooner. That is intended fail-closed behaviour, not a regression.
* The recovery re-persists preserved executions inside the failure handler. If the database itself is the failing resource, the recovery is skipped and an `HOLDER_PARTIAL_PERSIST_UNRECOVERABLE` reason is recorded instead — evidence is degraded but the blocker still fires.
* Stages outside this lane that omit coverage or accounting surfaces remain subject to the earlier generic collector rules.

## Next offline proof

The full multi-stage integrated fixture-transport campaign walk remains the narrowest useful next lane:

```text
locator → direct pump → gecko → backup → market → protocol → holder
→ durable/stage/coverage ID equality including a partial holder attempt
→ accounting-complete source failure vs incomplete measurement vs partial attempt
→ MEMORY_OBSERVATION readiness or durable mismatch / accounting terminal
→ stop before lifecycle
```

## Commit subject

`Repair holder partial accounting paths`

Do not push. Do not authorize or run a live campaign.
