# Printer V1 V2-9.8B WINDOW_15M Checkpoint 4 — Holder Budget, Evidence, and Two-Token Admission Audit

## Audit status

`V2_9_8B_WINDOW_15M_CHECKPOINT_4_HOLDER_ADMISSION_AUDIT_NO_REACHABLE_DEFECT_FOUND_PENDING_FOCUSED_PROOF`

This is an audit/readiness finding, not the final checkpoint verdict.

- Baseline: `af4503b8f175b556129516a7770fb1c3f9df6906`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-4-holder-budget-evidence-two-token-admission`
- Linear: `DTW-30`
- Mode: static inspection and existing-artifact review only
- Provider contact: none
- Printer/runtime: none
- Authorization: none created, reused, modified, or consumed
- Authoritative database: not accessed or mutated

Checkpoint 5 is not started.

## Controlling source stack

This audit used the active Printer V1 source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

It also used the rolling blocker-readiness design/plan and the reached V2-9.8B holder, source-accounting, memory-activation, and clean-object repair closeouts.

## Binding policy clarification

The rolling plan's older phrase “two holder-eligible admitted tokens” is superseded by the adopted memory-observation architecture.

The current binding contract is:

- market/protocol/tracking-qualified candidates may be `MEMORY_OBSERVATION_ELIGIBLE` with holder pass, holder fail, source unavailable, or budget-bound unknown context;
- only an actual clean holder pass may create `FULLY_ELIGIBLE`;
- future-action eligibility remains blocked or unknown unless its explicit later policy passes;
- the holder workload must never truncate the market/protocol observation universe.

Checkpoint 4 therefore produces two memory-admitted tokens with truthful holder context, not necessarily two holder-pass tokens.

## Exact production path inspected

```text
reconciled discovery request manifest
→ campaign-owner measured transport identities
→ independent action-local measured transport identities
→ exact pre-holder M = C = A reconciliation
→ immutable holder budget ledger
→ tracking feasibility before holder I/O
→ deadline and per-attempt budget decision
→ maturation/reuse decision
→ sequential pacing
→ Source-Governed GoPlus / Solana holder transport
→ measured holder transport ledger
→ durable request/response/failure and attempt persistence
→ holder-stage six-unit sealing
→ holder-context conversion
→ MEMORY_OBSERVATION_ELIGIBLE / FULLY_ELIGIBLE separation
→ four-candidate freeze
→ exact two-token memory readiness
```

Primary owners inspected:

- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/operator_cli/pilot_input_readiness.py`
- `src/printer_v1/sources/goplus.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/sources/helius_holder.py`
- `src/printer_v1/sources/measured_transport.py`
- `src/printer_v1/sources/campaign_six_unit_accounting.py`

## Boundary findings

### 1. Exact pre-holder `M = C = A`

Classification: `NO_REACHABLE_DEFECT_FOUND`.

`build_pre_holder_budget_snapshot()` compares canonical transport identity sets from:

- request manifest (`M`);
- campaign six-unit owner (`C`);
- independent action-local observer (`A`).

Equal numeric counts are insufficient. Missing keys, malformed keys, count/key mismatch, duplicate ownership, request mismatch, and any of the six bounded set differences fail closed before holder collection.

No holder transport occurs after this pre-holder fault because reconciliation and snapshot construction precede `_evaluate_holder_eligibility()`.

### 2. Holder budget and reservations

Classification: `NO_REACHABLE_DEFECT_FOUND`.

The permanent path preserves:

- operation ceiling: `45`;
- zero-transport validation charge: `9`;
- snapshot reservations: `2 + 4`;
- pre-attempt worst-case requirement: `5`;
- permanent holder-stage transport ceiling: `8`.

Governed request count remains reporting truth. Operation charging uses measured transports plus the fixed zero-transport charge. `holder_attempt_admission()` is non-mutating and checks campaign budget, stage budget, and deadline before a request begins.

Permanent observation admission does not consult the holder-derived candidate cap. The holder workload cannot delete otherwise valid observation candidates.

### 3. Pacing and source execution

Classification: `NO_REACHABLE_DEFECT_FOUND`.

`SequentialRequestPacer` derives spacing from the committed source registry, performs one synchronous wait when required, and adds no retry, recursion, endpoint rotation, reconnect, or automatic successor.

The write transaction is released before pacing and provider I/O. The source path remains the adopted GoPlus request followed by the governed Solana holder path only when required, with at most the existing fixed backup.

### 4. Transport measurement and holder-stage accounting

Classification: `NO_REACHABLE_DEFECT_FOUND`.

The strict operational path owns one holder `MeasuredTransportLedger`:

- GoPlus emits one exact identity for its attempted HTTP request;
- Solana RPC emits one identity for every actually attempted method;
- identity fan-out reaches the independent action-local observer at measurement time;
- identical serialized identities survive normalization and persistence;
- numeric counts without exact identities block;
- source, request kind, target mint, method/endpoint, ordinal, and endpoint ownership correspondence are validated;
- the campaign seals one conditional `HOLDER_SAFETY` stage;
- lawful zero-operation exhaustion uses the existing pre-operation no-work contract.

The historical missing holder-stage integration was already repaired and closed PASS. It is not a current defect.

### 5. Persistence, maturation, and reuse

Classification: `NO_REACHABLE_DEFECT_FOUND`.

Maturation is durable and replayable. Waiting, cancellation, deadline refusal, and replay create zero source calls. The production maturity threshold remains truthfully `UNPROVEN_DISABLED`; no provider-index delay is invented.

Exact reuse requires matching mint, purpose, source, endpoint role, response lineage, capture/receipt times, parser/policy versions, clean quality, exact target, known holder label, and source TTL. Reuse charges zero fresh transport and does not fabricate a new provider response.

Attempt persistence links durable request, response or failure identities and retains method, endpoint role, commitment/context, operation count, failure subtype, and Retry-After where available. Partial collection/persistence failures retain already-created request evidence and become accounting blockers rather than disappearing.

### 6. Provider failure versus accounting failure

Classification: `NO_REACHABLE_DEFECT_FOUND`.

Failure precedence identifies missing execution, provider/transport/rate-limit/no-response/parser/quality failure before target mismatch. A parseable wrong-target response remains a target mismatch.

An accounted holder-source failure remains truthful context and may still allow memory observation. Missing or contradictory holder accounting blocks handoff and can never create `FULLY_ELIGIBLE`.

Expected live conditions remain distinct from code defects:

- provider rate limiting or transport failure;
- incomplete or unknown holder evidence;
- extreme holder concentration;
- insufficient market/protocol candidate supply;
- lawful budget exhaustion before every candidate is evaluated.

### 7. Two-token memory admission

Classification: `NO_REACHABLE_DEFECT_FOUND`.

The current path converts the full valid observation universe independently of holder pass. Budget-bound unattempted candidates receive exact `UNKNOWN` / `SOURCE_NOT_EVALUATED_BUDGET_BOUND` context and create zero requests.

Only actual holder passes become `FULLY_ELIGIBLE`. Holder fail, unavailable, and budget-bound unknown candidates remain future-action blocked/unknown while staying memory-activatable when all non-holder gates pass.

The four-candidate freeze remains the sole neutral observation selector and produces exactly two selected plus two alternates. Exact selected order and retained evidence flow into memory readiness without creating false source rows.

## Rejected suspicions

The following were investigated and rejected as current defects:

1. **Holder budget still truncates permanent observation supply.** Rejected: permanent admission uses the operational candidate maximum, not `ledger.candidate_cap()`.
2. **Holder transports are counted but absent from campaign ownership.** Rejected: later safe-stop/holder-accounting repair added exact holder measurement, fan-out, persistence, and stage sealing.
3. **Equal counts can pass unequal identities.** Rejected: current pre-holder owner requires exact canonical set equality and preserves all set differences.
4. **Provider failure is mislabeled as target mismatch.** Rejected: current failure precedence checks provider/source failure first.
5. **Unattempted candidates silently become eligible.** Rejected: they receive categorical budget-bound unknown context, zero source IDs, `fully_eligible=false`, and blocked/unknown future action.
6. **Memory admission still requires a holder pass.** Rejected: current activation tests explicitly accept pass, fail, unavailable, and budget-bound unknown context while preserving future-action locks.

## Focused proof required before closeout

The minimum sufficient current-branch proof is the directly affected existing regression set:

- exact pre-holder identity parity;
- holder budget, pacing, maturation, reuse, and failure precedence;
- permanent observation/holder-budget decoupling;
- exact holder-stage measured accounting;
- holder partial-attempt persistence;
- holder manifest composition;
- memory-admission truth for holder pass/fail/unavailable/budget-bound unknown;
- legacy holder evidence classification.

The proof must also include Python syntax/import checks, `git diff --check`, and a clean disposable worktree. No provider, Printer, authorization, authoritative DB, Scheduler runtime, lifecycle runtime, or memory generation is permitted.

If a current regression fails for the intended contract reason, classify it as RED and stop for a separate design decision before production code changes. If the focused proof passes, Checkpoint 4 may close with no production modification.

## Money-usefulness contribution

This audit protects future clean-memory creation from three expensive errors: charging source work without exact transport identity, discarding useful market observations merely because holder context is unavailable, and overstating an unknown or failed holder result as action-safe. It improves evidence reliability without producing a trade signal or financial action.

## What this checkpoint improves

- consolidated current-path confidence at the holder/admission boundary;
- exact separation of observation eligibility from future-action eligibility;
- explicit rejection of historical defects already closed by later repairs;
- a focused proof gate before moving to Scheduler/lifecycle activation.

## What this checkpoint does not unlock

This checkpoint does not unlock or run:

- providers, Printer, or the one-shot wrapper;
- authorization creation or consumption;
- authoritative database mutation;
- Scheduler or lifecycle runtime;
- memory generation or retrieval;
- paper BUY/SELL/HOLD decisions;
- positions, trade events, trade audits, or PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- Checkpoint 5.

All Solana-only, Solana-memecoin-only, paper-only, Source Governor, Central Scheduler, no-paid-API, no-score/rank/confidence/weighting, no-wallet, no-key, and no-real-funds locks remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Static inspection cannot guarantee live provider availability, holder evidence completeness, or candidate sufficiency.
- Provider-index maturation remains intentionally unproven/disabled rather than guessed.
- Historical fixture-only compatibility paths cannot prove strict public operational readiness.
- The directly affected suite spans several prior repair eras; proof must remain focused and may expose unrelated stale expectations that require classification rather than scope expansion.
- The connected GitHub environment cannot execute the local Python suite, so the focused proof must run in a detached disposable worktree on the operator machine.

## Next boundary

Do not begin Checkpoint 5 until the focused Checkpoint 4 proof passes and this checkpoint receives a closeout verdict.