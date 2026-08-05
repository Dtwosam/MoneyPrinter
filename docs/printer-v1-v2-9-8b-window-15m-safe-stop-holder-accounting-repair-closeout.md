# V2-9.8B WINDOW_15M Safe-Stop and Holder-Accounting Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_SAFE_STOP_HOLDER_ACCOUNTING_REPAIR_PASS`

This implementation lane is closed PASS. It does not authorize the continuous
wrapper-to-memory proof or any runtime, provider, Scheduler, memory-generation,
retrieval, decision, position, trade, audit, PnL, wallet, signing, funding, or
execution action.

## Git identity

- Required baseline branch: `agent/v2-9-8b-window-15m-safe-stop-holder-accounting-audit-design`
- Exact baseline commit: `4339e2b49e1d682b948c79969db0c2d7b437b9aa`
- Repair branch: `agent/v2-9-8b-window-15m-safe-stop-holder-accounting-repair`
- Final commit: the commit containing this closeout, with subject
  `Repair WINDOW_15M safe-stop and holder accounting`; its full object ID is
  recorded in the operator handoff because a Git commit cannot embed its own
  object ID in its tree.

The baseline branch, exact HEAD, ancestry, and clean tracked worktree were
verified before editing.

## Files changed

- `src/printer_v1/operator_cli/operational_database_target_binding.py`
- `src/printer_v1/operator_cli/continuous_proof_evidence_retention.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- `src/printer_v1/operator_cli/safety_context_source_redundancy.py`
- `src/printer_v1/sources/goplus.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/sources/helius_holder.py`
- `tests/test_v2_9_8b_window_15m_safe_stop_holder_accounting_repair.py`
- `tests/test_v2_9_8b_window_15m_final_integrated_continuous_proof.py`
- this closeout

## Repair A — operational database target binding

PASS.

One frozen `OperationalDatabaseTargetBinding` now carries the exact target
kind, resolved path, authorized pre-mutation SHA-256, Migration 052 identity,
durable database-target identity, authorization/application marker hashes, and
execution/campaign/run/cycle/configuration ownership. The public coordinator is
the production constructor. The same object is passed through the authoritative
campaign owner and origin/lifecycle driver to `run_one_command_15m_factory`.

Operational-persistent execution now fails closed on a missing binding, a raw
path-only call, invalid target kind, path/canonical-path mismatch, baseline or
migration mismatch, marker mismatch, ownership mismatch, and reuse/history
mismatch. The baseline authorization SHA is not compared with the mutable
post-campaign database SHA. The exact categorical reason is retained in the
factory terminal `blocked_reasons` surface.

Production remains canonical-database-only. An authorized disposable
operational proof remains non-production, exact-path/exact-baseline-bound,
single-use, no-retry, no-restart, no-resume, and no-successor, while preserving
`proof_mode = false` and `operational_persistent_mode = true`.

## Repair B — exact holder-stage six-unit integration

PASS.

GoPlus emits one `TransportOperationIdentity` for its attempted holder/safety
HTTP request. Solana RPC emits one identity per actually attempted method, in
order: `getTokenLargestAccounts`, then `getTokenSupply` only if attempted. The
primary and Helius Free backup source/endpoint owners remain distinct. No retry,
rotation, paid provider, or independent counter owner was added.

The holder stage owns one `MeasuredTransportLedger`. Identity fan-out occurs at
measurement time to the existing action-local observer. The identical serialized
identities survive normalization and holder persistence. Strict operational
acceptance validates exact count equality, unique identity/ordinal keys,
non-negative byte/row measures, and request/source/kind/target/endpoint
correspondence. Numeric counts without identities block the authorized public
operational path. Accounted source failure remains holder context and does not
erase an otherwise valid memory-observation candidate; missing accounting blocks
handoff and cannot create `FULLY_ELIGIBLE`.

The public coordinator seals one conditional `HOLDER_SAFETY` stage through the
existing campaign stage evidence sink. Clean zero-operation exhaustion uses the
existing `PRE_OPERATION_NO_WORK` evidence contract.

## Repair C — continuous-proof evidence retention

PASS for implementation; proof NOT RUN.

The future proof harness now captures the real stdout/stderr emitted by
`public_command.main()`, keeps launcher metadata separate, parses the final
child terminal JSON, preserves blocker/orchestration/identity/verdict/report
truth, projects already-produced holder/freeze diagnostics, and fail-closes on
unparseable terminal output or absent mandatory evidence.

Retention copies every present mandatory artifact before disposable cleanup,
records categorical absence for missing artifacts, hashes copied bytes, writes
`artifact-hashes.json`, and rereads/verifies the retained bytes. It never writes
an empty success artifact for absent evidence.

## Authoritative database identity

The authoritative database was inactive before and after implementation.

| Property | Before | After |
|---|---:|---:|
| Resolved path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` | same |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` | same |
| Size | `68067328` bytes | same |
| Migration count | `52` | `52` |
| Migration head | `052_memory_observation_eligibility_layers.sql` | same |
| Integrity | `ok` | `ok` |
| Foreign-key violations | `0` | `0` |
| Journal mode | `delete` | `delete` |
| WAL/SHM/journal sidecars | none | none |

No authoritative-database mutation occurred.

## Tests and checks

- New focused repair tests: `31 passed`.
- Directly affected database-target, holder, six-unit, action-local, wrapper,
  readiness, and public-composition regressions: `198 passed, 6 subtests passed`.
- Changed GoPlus/Solana holder adapter tests: `39 passed`.
- Python compilation for every changed Python module and test: PASS.
- `git diff --check`: PASS.
- Continuous wrapper-to-memory proof: NOT RUN, as required.
- Provider calls, discovery runtime, Central Scheduler runtime, and memory
  generation: NOT RUN.

An intentionally broader diagnostic selection also reported `225 passed` and
8 unrelated baseline failures: one legacy holder-budget test expects a
`base_operations` detail absent at the required baseline, and seven historical
tests assert Migration 050 although the active repository migration head is
052. No production file changed by this lane causes those assertions, and they
were not weakened or edited.

## Money-usefulness contribution

This repair prevents a campaign from attributing memory-growth writes to an
unbound database, prevents numeric holder-cost claims from masquerading as
measured transport truth, and preserves the terminal evidence needed to decide
whether a future bounded proof created trustworthy clean memory. That improves
capital-protection realism without adding a trade signal or financial action.

## What improved

- Exact authorization-bound database ownership across the public call chain.
- Exact holder HTTP/RPC measurement at the transport boundary.
- Campaign/action-local holder identity reconciliation and categorical blocking.
- Honest source-failure context without false holder eligibility.
- Complete, hash-verified future-proof evidence retention.

## What remains locked

All existing V1 and V2 locks remain in force, including Solana memecoin-only,
paper-only, no live funds/execution/wallet/private key/signing, no paid API,
no scoring/ranking/confidence/weighting, no embeddings/vectors, no Source
Governor or Central Scheduler bypass, 5m support-only, no production
1h/4h/12h/24h activation, no retrieval, no paper decisions, no BUY/SELL/HOLD,
no positions/trades/audits/PnL, no real authorization, and no automatic retry,
restart, recovery, resume, or successor.

## Functionality Risks / Setbacks / Efficiency Blockers

- The continuous proof has not run, so end-to-end evidence availability and
  diagnostic field placement still require the separately authorized proof.
- Historical fixture-only callers may still use legacy numeric holder counts;
  the authorized public operational path is the strict identity-bearing path.
- Response-byte length is exact for received HTTP bodies; transport failures
  before a body exists truthfully record zero response bytes.
- The unrelated stale Migration 050 assertions and legacy `base_operations`
  assertion remain repository test-maintenance debt outside this lane.

## Exact next permitted step

Independent read-only implementation review. If and only if that review passes,
the operator may separately approve a bounded continuous wrapper-to-memory proof
lane. This PASS does not authorize that proof.
