# V2-9.7E.22 Holder Reliability and Campaign Budget Repair — Frozen Design

**Design gate:** PASS. This design was frozen before production edits.

## Scope and baseline

Baseline is `0b8d1e916262250b79a4ba7af5b9617fc8800343`, `Audit holder
reliability and campaign budget`. E.22 is offline design/repair only. It does
not authorize provider contact, E.20 reuse, a readiness cycle, or a pilot.

The prompt's `goplus-api-contract.md` does not exist. The canonical committed
contract read in its place is
`goplus-solana-token-security-api-contract.md`; this substitution does not
create a maturation threshold.

## Frozen minimum design

1. The live owner freezes finalized Pump proofs, deterministically orders them,
   and performs structural zero-source validation before holder work.
2. One pre-activation ledger owns the unchanged 45-operation ceiling. It
   separately records governed requests, underlying transports, zero-transport
   validation/reuse, the fixed deadline, and a non-spendable reservation of two
   DexScreener snapshot operations.
3. The candidate cap is derived, never configured independently:
   `floor((45 - Pump operations - 9 combined validation - 2 snapshots) / 3)`.
   Every candidate admission repeats the worst-case reservation check.
4. Exact evidence reuse is zero transport and requires exact lowercase mint and
   purpose, source and endpoint role, original response/lineage, capture and
   receipt times, unchanged parser and policy versions, complete clean quality,
   exact target, known label, and source TTL. Failure, stale, unknown,
   mismatched, malformed, conflicting, different-source/version evidence is
   rejected.
5. Pre-slot maturation work is durable Scheduler-owned work with
   `scheduled_for`, deadline and terminal cancellation. Waiting performs zero
   source calls. The production threshold is `UNPROVEN_DISABLED`: E.20 and the
   committed GoPlus contract do not support an exact age.
6. Evaluation is sequential. Pacing is deterministic from committed registry
   request limits and is represented as due-time work, never an adapter sleep
   or hidden retry. The request path remains GoPlus, primary RPC only if needed,
   and at most one fixed backup after an eligible transient failure.
7. Durable attempt evidence links request, response or failure and records
   endpoint role/redacted host, RPC method, commitment/context, underlying
   operation count, failure subtype and Retry-After. Source failures gain the
   missing request foreign key.
8. Failure reporting checks missing execution, failure/no response, stale or
   conflicting status, malformed/incomplete quality, and only then target
   mismatch. Exact parseable mismatch remains blocking.
9. Selection remains deterministic exactly-two-or-none, with no score, rank,
   confidence, weighting, new source, rotation, retry, or ceiling increase.

## Schema decision

Existing campaign ownership starts at selected token slots and therefore
cannot own pre-activation candidates. Migration 037 adds only a pre-slot
ledger, maturation work and holder-evidence provenance, plus a nullable
request foreign key on source failures. It does not add a provider, lifecycle,
memory, retrieval or financial capability.

## Proof gate

Focused fixture/fake-clock tests must cover budget reservation/cap/refusal,
reuse acceptance and rejection, maturation wait/due/deadline/cancellation and
replay, pacing/sequentiality, durable provenance, failure precedence,
two-or-none activation, cleanup, integrity/FKs and zero-source replay.
