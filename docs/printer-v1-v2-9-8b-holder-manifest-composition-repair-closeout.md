# V2-9.8B Holder Manifest Composition Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Holder Manifest Composition Repair`

## Verdict

`V2_9_8B_HOLDER_MANIFEST_COMPOSITION_REPAIR_PASS`

The real holder-evidence path now returns durable Source Governor request IDs, stage-owned coverage, and accounting-blocker status into campaign-wide reconciliation. Offline fixture-only. No providers, discovery runtime, Scheduler runtime, authorization, `WINDOW_15M`, memory generation, retrieval, decisions, positions, trades, audits, or PnL were run.

## Exact production-composition defect

1. `persist_bundle_attempts()` read real `execution.request_record.id` but returned only request/transport **counts**.
2. `_evaluate_holder_eligibility()` returned only `(holder_facts, ledger)`.
3. The authoritative campaign then tried to recover holder IDs from diagnostics or a nonexistent `ledger.request_ids` attribute.
4. Real holder requests were therefore missing from `stage_reported_request_ids`, `holder_source_request_coverage`, the campaign manifest, and all-stage accounting-blocker propagation.

## Owners changed

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/holder_reliability_budget_control.py` | `HolderContextResult`, `HolderBundlePersistResult`; `persist_bundle_attempts` emits real IDs + coverage + accounting status; no RPC/non-RPC transport fallbacks |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | `_evaluate_holder_eligibility` returns `HolderContextResult`; campaign wires `holder_context` / IDs / coverage before reconcile; removes `ledger.request_ids` fallback |
| `src/printer_v1/sources/goplus.py` | Surfaces authoritative single-HTTP `underlying_operation_count` on success and rate-limit normalize paths |
| `tests/test_v2_9_8b_holder_manifest_composition_repair.py` | New focused proofs (15) |
| Affected holder/campaign test fakes and goplus fixtures | Return `HolderContextResult`; include measured counts on fixture payloads |
| Closeout | this document |

## Holder result contract

```text
HolderContextResult
  holder_facts
  ledger
  source_request_ids
  source_request_coverage
  accounting_blocker
  accounting_blocker_reason
  governed_request_count
  measured_transport_count
```

`HolderBundlePersistResult` is the per-candidate persist owner consumed while building the stage result.

Coverage entry (one per distinct governed execution object):

```text
source_request_id
source_name
request_kind
logical_stage_id   # campaign|run|cycle|HOLDER|{mint}|{role}
terminal_status
transport_identity_count
normalized_member_count
```

Request IDs come only from `execution.request_record.id`. Alias keys that share the same execution object are not double-counted.

## Real request-ID and coverage wiring

Before `assemble_and_reconcile_campaign_source_requests(...)`:

```text
supply.diagnostics["holder_context"]
supply.diagnostics["holder_source_request_ids"]
supply.diagnostics["holder_source_request_coverage"]
```

`holder_context` carries accounting blocker/reason, IDs, coverage, governed request count, and measured transport count.

Existing collectors already read `holder_source_request_ids`, `holder_source_request_coverage`, and `holder_context.accounting_blocker`.

Invariant proven on the authoritative path:

```text
database-proven durable IDs
== stage-reported IDs
== coverage manifest IDs
```

## Accounting-failure versus source-failure distinction

| Case | Coverage terminal | `accounting_blocker` | Memory observation |
|---|---|---|---|
| Holder evidence unavailable / rate-limited / extreme with complete measured accounting | may be `BLOCKED` | `False` | remains context; not blocked solely by holder failure |
| Missing or contradictory measured transport evidence | `BLOCKED` | `True` | readiness/handoff blocked via campaign reconciliation |

Request count and transport count remain separate. Transport counts require proven metadata (`transport_operation_identities` / matching used count, or explicit `underlying_operation_count`). No invent of “RPC response ⇒ 2” / “non-RPC ⇒ 1”.

## Exact tests and counts

| Suite | Result |
|---|---|
| `tests/test_v2_9_8b_holder_manifest_composition_repair.py` | **15 passed** |
| + holder reliability, readiness, reconciliation, authoritative campaign suites | **80 passed** (+ 5 subtests) |
| `compileall` (changed modules) | OK |
| `git diff --check` | OK |

Focused proofs cover: durable ID return; one/multiple coverage entries; alias de-dupe; stage-reported insertion; campaign manifest; three-way DB reconcile; ID-without-coverage block; coverage-without-DB block; missing transport accounting blocker; readiness/handoff block; rate-limit complete accounting remains context; extreme remains memory-observation eligible; future action `BLOCKED_OR_UNKNOWN`; authoritative path real `_evaluate_holder_eligibility` + campaign owner (no prebuilt `holder_context` injection).

## Schema result

No migration. Existing `printer_source_requests`, holder attempt tables, and diagnostics JSON fields.

## Money-usefulness contribution

Pre-lifecycle admission cannot claim PASS while governed holder requests are invisible to campaign reconciliation. Operators get honest three-way ID/coverage equality and typed holder accounting blockers before memory readiness, without treating ordinary holder evidence failure as a campaign accounting fault.

## What remains locked

Freeze depth 4, surplus 8, $3k floor, ceiling 30, reservations `3/2/6/7/8/4`, holder evidence as MEMORY_OBSERVATION context, FUTURE_ACTION holder gate, Source Governor / Scheduler ownership, retrieval, trading, PnL, authorization, live providers, `WINDOW_15M`.

## Remaining risks

- Fixture adapters that bypass source normalizers must still attach measured transport metadata when they participate in the holder path; missing counts correctly fail closed as accounting blockers.
- Stages that still omit coverage/accounting surfaces outside this lane remain subject to earlier generic collector rules.
- Full multi-stage fixture-transport campaign walk (locator → direct pump → gecko → backup → market → protocol → **holder**) is the next offline proof.

## Next offline proof

Integrated fixture-transport campaign:

```text
locator → direct pump → gecko → backup → market → protocol → holder
→ durable/stage/coverage ID equality including holder
→ accounting-complete source failure vs incomplete measurement
→ MEMORY_OBSERVATION readiness or durable mismatch / accounting terminal
→ stop before lifecycle
```

## Commit subject

`Repair holder manifest composition`

Do not push. Do not authorize or run a live campaign.
