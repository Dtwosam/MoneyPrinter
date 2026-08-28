# Printer V1 V2-9.8B Cycle-2 Cooperative Acquisition Design Amendment

Date: 2026-08-28

Status: approved implementation amendment

Governing design:
`docs/printer-v1-v2-9-8b-4-2-2-orchestration-correctness-design.md`

## 1. Amendment verdict

`V2_9_8B_CYCLE_2_COOPERATIVE_ACQUISITION_DESIGN_AMENDMENT_PASS`

This amendment replaces the governing design's Defect-2 child-job/per-physical-
transport model. It also supersedes corresponding generic acquisition-quantum
language in sections 3.2, 4, 5, 6, and 7. The other three defect designs remain
authoritative.

The minimum safe repair refines Printer's existing cooperative acquisition
owners. It does not add a scheduler, discovery engine, generic Scheduler child-
job hierarchy, or generic acquisition-quantum table.

## 2. Existing owners remain authoritative

The implementation reuses:

- the existing pre-admission attempt owner and acquisition horizon;
- the existing Central Scheduler job/claim and cooperative yield/reclaim path;
- the existing temporal refresh wait/work owner;
- existing durable source-request/response/failure rows and deterministic
  request keys;
- the existing `StageBudget` and total operation ceiling; and
- the existing Source Governor request boundary.

Migration 062, if required, is limited to the Defect-3 append-only attempt-
evidence ledger. It must not create a generic acquisition-quantum table.

## 3. Correct schedulable unit

One cooperative Scheduler claim may perform at most the next missing **Source-
Governed request**. A governed request may lawfully contain multiple physical
transports. PumpSwap verification remains one governed request even though its
verifier can perform several RPC transports; it must not be split into multiple
Source Governor requests.

The deadline-fit bound is:

```text
governed request worst-case duration + enforced bounded checkpoint reserve
```

The PumpSwap verifier's existing approximately 80-second bound remains valid.
Provider timeouts are not lowered to make work fit. A request may start only
when its full bound fits strictly before both the next protected lifecycle
deadline and the immutable acquisition horizon.

## 4. Cooperative direct-migration sequence

For each claim, the existing attempt or refresh-work owner must:

1. reconstruct completed request state from exact durable source truth;
2. validate the current attempt, opportunity, cursor, budget, Scheduler claim,
   and deterministic request identities;
3. replay terminal requests locally without issuing or double-counting them;
4. select at most the next missing governed request;
5. yield without provider work when its full bound does not fit;
6. otherwise commit the deterministic request intent, execute exactly that one
   request through Source Governor, persist and seal its terminal result, then
   yield the same Scheduler owner; and
7. resume on a later lawful reclaim from durable source truth.

Candidate promotion and cursor advancement remain blocked until the existing
contiguous, complete exact-migration/PumpSwap/pair/liquidity/safety evidence is
present. An incomplete or ambiguous request is not reissued and fails closed.

## 5. Delayed refresh ownership and timing

The same request-at-a-time refinement applies to `DISCOVERY_REFRESH` work. A
refresh work row may remain incomplete across cooperative yield/reclaim without
creating child jobs. Its absolute opportunity times are anchored to the original
attempt evaluation time:

```text
initial, +600 seconds, +1200 seconds, +1800 seconds
```

Later opportunities do not drift from earlier completion times. The existing
wait/work contract remains the owner of scheduling, claim, cancellation, and
terminal state. Lifecycle work retains priority on every re-entry.

## 6. Idempotency, crash, and accounting contract

- Existing deterministic request keys and exact terminal source rows are replay
  authority; a completed request is never reissued.
- StageBudget usage is reconstructed from attempt-linked durable requests before
  another request may run, preventing budget reset or double charge.
- Source transport accounting is observed once at actual execution. Durable
  replay adds no action-local transport observation.
- Cooperative yield persists no hidden process-local authority.
- After a crash, a terminal exact request may be adopted once; absent,
  incomplete, duplicated, or ambiguous request lineage blocks rather than
  triggering a provider retry.
- No authorization restart/resume/reuse is implied by cooperative in-process
  yield/reclaim.

## 7. Failure behavior

No fit means yield to lifecycle work. Scheduler ownership mismatch, Source
Governor denial, provider failure, incomplete source lineage, budget mismatch,
cursor mismatch, or evidence ambiguity remains a typed fail-closed outcome.
Exact pair, Pump migration/PumpSwap, liquidity, freshness, holder, safety,
historical disjointness, and duplicate gates are unchanged.

## 8. Focused proof contract

Implementation proof must demonstrate:

- the historical 115-second aggregate conflicts with TRACK_FAST while its next
  lawful governed request can progress when its own bound fits;
- one claim issues at most one new governed request;
- terminal request replay issues no provider call and no duplicate transport
  observation;
- PumpSwap verification stays one governed request with its full bound;
- lifecycle deadlines and the acquisition horizon both preempt acquisition;
- delayed refresh work yields/reclaims under the same owner at fixed
  +600/+1200/+1800 timestamps; and
- no new Scheduler, Source Governor, discovery owner, or generic quantum table
  is introduced.

All proof is disposable/offline. This amendment authorizes no campaign,
authorization, provider contact, authoritative DB migration, retrieval,
financial capability, or longer window.
