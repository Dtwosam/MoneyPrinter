# Printer V1 V2-9.8B 4/2/2 Orchestration Correctness Design Amendment

Date: 2026-08-28

Lane: design amendment / implementation gate synchronization

Baseline design HEAD: `8b902554889ba4422b9815705a4cb076d6e9788a`

Governing design:

`docs/printer-v1-v2-9-8b-4-2-2-orchestration-correctness-design.md`

## 1. Amendment verdict

`V2_9_8B_4_2_2_ORCHESTRATION_CORRECTNESS_DESIGN_AMENDMENT_PASS`

The original design remains governing for the four proven defects, invariants,
fail-closed behavior, evidence requirements, and bounded verification. This
amendment narrows only the Cycle-2 implementation mechanics after deeper source
tracing proved that a new child-quantum Scheduler hierarchy is unnecessary and
would change the existing Source Governor request/accounting boundary.

The narrower design reuses existing owners and preserves more of the proven
runtime contract.

## 2. Why the original Cycle-2 implementation detail is amended

The original design proposed one physical HTTP/RPC transport per Scheduler
micro-quantum and new child `DISCOVERY_REFRESH` jobs. Source inspection showed
that the exact PumpSwap graduation verifier intentionally owns multiple measured
Solana RPC transports inside one existing Source-Governed request. Splitting
those physical transports into separate governed requests would change source
request counts, request keys, rate/budget accounting, failure attribution, and
stage evidence semantics without a product requirement to do so.

The existing later-cycle pre-admission attempt already has a durable Scheduler
job, and delayed refreshes already have durable wait/work rows plus an existing
`DISCOVERY_REFRESH` Scheduler job. Adding a parallel child-job hierarchy would
duplicate ownership rather than repair the proven cadence-fit defect.

Therefore the schedulable unit is one existing **Source-Governed request** (or a
bounded local-only transition), not one physical transport.

## 3. Amended Cycle-2 execution model

### 3.1 Existing owners remain authoritative

Initial Cycle-2 acquisition continues to be owned by the existing durable
pre-admission attempt and its `PRE_ADMISSION_DISCOVERY_SELECTION` Scheduler job.

Delayed +600/+1200/+1800 refresh opportunities continue to be owned by the
existing pre-lifecycle refresh wait/work rows and their existing
`DISCOVERY_REFRESH` Scheduler job.

No new Scheduler job kind, child-job hierarchy, worker, polling loop, retry
loop, or second scheduler is introduced.

### 3.2 One claim executes at most one new governed request

Within cooperative Cycle-2 direct migration, one Scheduler claim may:

1. reconstruct prior progress from durable terminal source rows under the exact
   deterministic request-key root;
2. perform bounded local validation/reduction needed to identify the next
   missing operation;
3. execute at most one **new** Source-Governed request;
4. persist/link the resulting terminal source evidence and cumulative progress;
5. yield the same Scheduler-owned attempt/work item if more direct work remains.

A local-only terminal transition may complete in a claim when no outbound source
request is required.

### 3.3 Deterministic replay, not duplicate provider work

Direct migration request keys are already deterministic for page, transaction,
and exact PumpSwap verification operations. On re-entry, the owner must load an
exact prior request by request key and require exactly one terminal response or
failure bound to it.

A prior terminal request is replayed locally into the direct-stage reducer. It
must not call the provider again, create a second source request, or emit a
second action-local transport observation.

Absent terminal evidence means the operation is still the next executable
request. Ambiguous request identity, multiple terminal results, mismatched
source/request kind, malformed retained normalized payload, or foreign
request-key root fails closed as an internal/evidence defect.

### 3.4 Deadline bound

The cadence conflict check uses the bound of the **next Source-Governed
request**, plus a small bounded local checkpoint reserve, rather than the sum of
an entire direct-migration page/transaction/verifier sequence.

Ordinary direct Pump page/transaction requests retain their existing transport
timeout. The exact PumpSwap verifier remains one governed request and retains its
existing internal bounded RPC behavior. No provider timeout is reduced merely to
make scheduling fit.

A request starts only if its complete bound fits strictly before the earliest
protected lifecycle deadline and before the bounded acquisition horizon.
Otherwise the coordinator yields to lifecycle work.

### 3.5 Fixed delayed refresh opportunities

The canonical delayed opportunities remain anchored to the initial attempt
instant at +600, +1200, and +1800 seconds. Their due times do not drift from the
completion time of earlier source work.

Existing refresh wait/work ownership is reused. When a delayed Pump refresh
needs multiple governed requests, the same existing refresh job/work owner may
yield and later reclaim while the refresh remains nonterminal. It terminalizes
only when that refresh opportunity completes, blocks, is cancelled, or its
bounded horizon is exhausted.

No source request remains open across a yield, and no provider I/O occurs while
holding an SQLite write transaction.

## 4. Attempt evidence amendment

The original design's need for durable full-attempt evidence remains. The
implementation is narrowed to one additive attempt-evidence ledger; there is no
new acquisition-quantum table.

Migration `062` may add append-only rows bound to the existing
`printer_pre_admission_discovery_attempts` owner. Rows may record only
categorical/provenance facts required to reduce the complete attempt, including:

- exact source request/response/failure linkage by durable IDs;
- observed mint and exact mint/pair identity facts;
- candidate disposition/rejection events;
- provider failure facts;
- reserve-depth/checkpoint facts;
- refresh/opportunity identity and terminal state where not already derivable
  without ambiguity from existing durable owner rows.

The reducer must prefer existing normalized source rows and existing owner rows
where they already provide exact truth. It must not duplicate raw provider
bodies or create a second source/accounting authority.

Evidence insertion is append-only and idempotent on exact identity. A conflicting
same-key fact fails closed.

Yielded source evidence must be linked/persisted before the Scheduler job is
yielded, not deferred until the terminal invocation.

Terminal shortage/certificate reporting is reduced from the durable full
attempt, never only the final process-local invocation.

## 5. Accounting amendment

Defect 4 keeps the original repair direction, with the narrowest existing-owner
implementation:

- pass the already-existing independent `transport_identity_observer` into every
  accounting-active initial/later discovery and holder composition;
- do not reconstruct action-local transport observations from sealed owner
  evidence;
- preserve cumulative pre-close `lifecycle_reservations` across source-unit
  yields by merging the exact new reservation into the previously persisted
  manifest before the provider attempt;
- same identity is idempotent; conflicting ordinal/owner/unit identity fails
  closed;
- final owner/action-local equality remains strict.

No accounting ceiling or tolerance is increased.

## 6. Revised implementation boundary

The expected implementation scope is now:

1. `migrations/062_pre_admission_attempt_evidence.sql` — additive attempt-owned
   evidence only; no quantum-owner table.
2. `src/printer_v1/operator_cli/operational_selective_1h.py` — identity-only
   precreated `WINDOW_1H` bind helper.
3. `src/printer_v1/operator_cli/one_command_15m_factory.py` — pre-E2Z 1h bind
   sequencing and cumulative pre-close reservation persistence.
4. `src/printer_v1/discovery/direct_migration_discovery.py` — cooperative
   deterministic terminal-row replay and at-most-one-new-governed-request yield
   boundary while preserving ordinary one-shot behavior.
5. `src/printer_v1/discovery/eligible_token_supply.py` — next-request quantum
   bound/progress diagnostics and full-attempt terminal reduction inputs.
6. `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py` and, if a
   focused owner keeps responsibilities clearer, one small
   `pre_admission_attempt_evidence.py` module — append/link/reduce attempt facts.
7. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` —
   reuse the existing attempt Scheduler job across yields, persist yielded
   evidence, retain durable progress, and restore observer wiring to later-cycle
   holder work.
8. `src/printer_v1/discovery/pre_lifecycle_refresh_composition.py` and
   `src/printer_v1/operator_cli/pre_lifecycle_persistent_refresh_owner.py` —
   reuse the existing refresh job/work owner across cooperative Pump request
   yields; keep fixed opportunity times.
9. `src/printer_v1/operator_cli/operational_memory_factory_command.py` only if
   focused tests prove an initial-path observer edge is still missing there.
10. `src/printer_v1/operator_cli/campaign_full_run_accounting.py` only if the
    final reconstruction needs a narrow cumulative-reservation read change after
    the producer manifest is repaired.

No change is authorized for Lane Q, Lane K, eligibility/liquidity thresholds,
exact-pair rules, Source Governor admission policy, standard 4h transfer-first
ownership, retrieval, decisions, positions, trades, audits, PnL, wallet/signing,
or live execution.

## 7. Bounded verification additions

In addition to the original design's focused verification list, implementation
must prove:

1. a cooperative direct stage executes no more than one new governed request per
   Scheduler claim;
2. re-entry reuses the exact terminal request by request key without provider
   recall or duplicate action-local observation;
3. the exact PumpSwap verifier remains one governed request even when it records
   multiple physical RPC transport identities;
4. the declared next-request deadline bound fits a real TRACK_FAST gap where the
   old aggregate direct bound did not;
5. +600/+1200/+1800 due times are anchored to the original attempt instant;
6. a delayed refresh may yield/reclaim through the same existing job/work owner
   without duplicate provider calls;
7. yielded source evidence is durably linked before yield;
8. terminal reporting reduces nonzero prior observations/failures/rounds from
   durable attempt evidence even when the final invocation itself observes none;
9. observer wiring covers initial and later holder/discovery paths exactly once;
10. cumulative pre-close reservations survive multiple yields and reconcile
    strictly at final accounting.

## 8. Stop conditions

Stop implementation and return to audit/design if source inspection or RED tests
show that any amended premise is false, including:

- deterministic request keys cannot uniquely identify resumable work;
- terminal normalized source rows are insufficient to reconstruct the exact
  direct-stage reducer state;
- the existing Scheduler owner cannot lawfully yield/reclaim without changing
  retry/restart semantics;
- a single existing governed request still cannot fit the protected TRACK_FAST
  deadline gap without weakening its supported timeout contract;
- attempt evidence cannot be made append-only and provenance-bound without
  becoming a second source/accounting authority.

No test may be made green by weakening a safety, memory-quality, cadence,
Source Governor, Central Scheduler, exact-identity, or accounting gate.
