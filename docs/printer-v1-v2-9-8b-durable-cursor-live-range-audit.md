# Printer V1 V2-9.8B Durable Cursor-to-Live-Range Continuity Audit

Date: 2026-07-29

Baseline: `f1def8f6154cd718b30fff469d602bafa900e926`

Lane: `V2-9.8B Durable Cursor-to-Live-Range Continuity Audit and Repair`

Gate: independent audit before design or code change

## Audit verdict

`COMMITTED_CODE_DEFECT`

Code change is justified. The canonical live transport owner did not accept or
load durable cursor state, constructed both Pump namespaces with null starts on
every invocation, and used newest-first RPC pages as though their oldest row
were the live-tail head. The foundation correctly detected the first durable
start mismatch, but that check occurred after every source operation and could
not construct the RPC range.

No schema change or new provider method contract is required. Migration 049
already supports exact namespace identity, both directions, immutable range
evidence, and atomic head advancement. The adopted Solana contract already
includes `getSignaturesForAddress` and `getTransaction`.

## Hard-gate evidence

| Check | Result |
| --- | --- |
| exact starting HEAD | `f1def8f6154cd718b30fff469d602bafa900e926` |
| tracked/untracked state | clean |
| authoritative DB SHA-256 | `d062a108fa178527e64c5ceb061c30a6889832dab8d072ff486b6a70797008f2` |
| authoritative migration | 049 |
| journal / integrity / foreign keys | `delete` / `ok` / zero violations |
| Python / SQLite / pytest | 3.12.13 / 3.53.4 / 9.1.1 |
| baseline focused cursor/foundation tests | 76 passed |
| live/provider work consumed by audit | zero |

The authoritative DB contains two non-null durable heads. Both use network
`solana-mainnet`, contract pin
`9c82f61cb711b044a17f770ab8ce9f9bdf78f333`, decoder
`canonical-live-acquisition-v1`, and direction `BACKWARD`. The Pump-create head
is slot `435969990`, cursor version 1; the Pump-migration head is slot
`435970004`, cursor version 4. Signatures are non-null and were inspected
read-only. The version asymmetry is additional evidence that one namespace was
advanced repeatedly by multiple observations in one execution.

## Complete owner chain

```text
printer_candidate_acquisition_cursors
-> no pre-transport cursor reader
-> public operational command builds live owner without DB/cursor state
-> integration acquires the exclusive acquisition lease
-> live owner initializes two null-start dictionaries
-> getSignaturesForAddress starts at newest and uses before only for later pages
-> oldest returned row becomes proposed end
-> foundation begins its atomic transaction and reads the durable heads
-> exact start comparison raises CURSOR_START_MISMATCH
-> observations/certificates/manifest/head writes roll back together
```

The foundation remains the correct atomic commit owner. The missing boundary is
between lease acquisition and live operation construction.

## Preliminary findings

1. **CONFIRMED.** `LiveCandidateAcquisitionTransportOwner.operations()` has no
   durable-head input and no DB reader. The public CLI constructs it from RPC
   configuration only.
2. **CONFIRMED.** `create_cursor` and `migration_cursor` set `start_slot` and
   `start_signature` to null for every process invocation.
3. **CONFIRMED.** `_validate_current_cursor_heads()` in the foundation is the
   first durable-head read. It runs inside the final foundation transaction,
   after the RPC range already exists.
4. **CONFIRMED.** Existing offline tests cover fresh disposable DBs and
   proposed-versus-committed rollback, but not a second process execution using
   heads committed by the first.
5. **CONFIRMED.** The live owner never derives an initial `until` or `before`
   parameter from a durable head. It only adds `before` from the last row of an
   earlier page.
6. **CONFIRMED.** Provider order, chronological direction, start/end meaning,
   and exclusive RPC bounds are conflated. Results are newest-first, yet the
   oldest accumulated row becomes `end`; empty results create slot zero and the
   synthetic signature `EMPTY_BOUNDED_RANGE`.
7. **CONFIRMED.** A terminal page can label a null-start range `CONTIGUOUS` and
   request advancement. The blocked live artifact contains seven such proposed
   advances against two non-null durable heads.
8. **CONFIRMED, REFINED.** One canonical owner is correct, but live-tail and
   backfill need separate query construction and direction namespaces. Live
   tail uses a `FORWARD` durable namespace with `until=prior_signature`; older
   backfill retains `BACKWARD` and uses `before=prior_signature`. Provider
   responses remain newest-first in both cases.
9. **CONFIRMED, REFINED.** The foundation lookup already keys on network,
   indexed address, contract pin, decoder version, and direction, then compares
   slot and signature. The defect is that the upstream owner never performs
   that exact lookup/hydration. Slot and signature are the exact head values,
   not additional namespace-key columns.

Additional confirmed defect: `_advance_current_cursor_heads()` deduplicates by
round ordinal rather than namespace. Shared cursor evidence can therefore bump
one namespace several times in one execution. Integration reporting similarly
counts proposed operations rather than unique proposed namespaces.

## Official-source comparison

The current official Solana page states that
`getSignaturesForAddress` returns records newest first and exposes `before` and
`until`. The pinned Agave v3.1.8 RPC source passes both values to blockstore. Its
blockstore source and tests establish:

- both `before` and `until` are exclusive;
- `before` paginates toward older rows;
- results remain newest to oldest, including reverse occurrence order inside a
  slot; and
- when `until` is not found in that pinned implementation, lookup can fall back
  to the first retained block instead of proving the boundary existed.

Sources:

- `https://solana.com/docs/rpc/http/getsignaturesforaddress`
- `https://github.com/anza-xyz/agave/blob/v3.1.8/rpc/src/rpc.rs`
- `https://github.com/anza-xyz/agave/blob/v3.1.8/ledger/src/blockstore.rs`
- `docs/solana-builder-source-of-truth/solana-core-rpc-reference.md`

Therefore an established live tail must verify the prior signature is still
available through the already-adopted exact `getTransaction` method before it
trusts `until`. A null/unavailable verification is categorical boundary
unreachability, not an empty range or bootstrap.

## Root cause

The transport owner was designed as a stateless operation factory even though
its RPC request is stateful. Durable state existed only in the final atomic
foundation owner. This split allowed transport-local dictionaries to claim
continuity without knowing the persisted range start. Newest-first page order
and per-operation shared cursor mutation then selected the wrong end and could
advance one namespace more than once.

## Coding gate

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
EVIDENCE: null live starts against two exact non-null durable heads; no cursor
  reader before operations; newest-first rows mapped to oldest-row head; seven
  proposed operation advances against two namespaces; no restart fixture.
OFFICIAL-SOURCE COMPARISON: before/until are exclusive, results are newest-first,
  and pinned missing-until behavior cannot prove the prior boundary existed.
PRINTER-CONTRACT COMPARISON: one Scheduler-led, Source-Governed owner must provide
  restart-safe live-tail and backfill continuity; foundation must remain atomic.
ROOT CAUSE: durable state was read only after transport range construction.
CODE CHANGE JUSTIFIED: YES.
MINIMUM SAFE RESPONSE: hydrate exact heads after the acquisition lease, construct
  explicit live/backfill requests, verify established boundaries, normalize the
  correct chronological end, and advance each namespace once in foundation.
FOCUSED PROOF: sequential public CLI executions on one disposable migration-049
  DB with frozen low-level transports, plus identity/gap/rollback negatives.
UNTOUCHED SCOPE: schema, provider contracts, Source Governor, Scheduler,
  admission policy, runtime capacity, campaign, memory, retrieval, financial work.
AUTHORIZATION STATUS: offline audit/design/repair/proof only; no live call.
NEXT ROADMAP-COMPLIANT STEP: implement the approved narrow design.
```

## Functionality Risks / Setbacks / Efficiency Blockers

1. Existing `BACKWARD` authoritative heads are preserved as historical/backfill
   namespaces. They must never be reused as `FORWARD` live-tail heads.
2. A first `FORWARD` execution is an explicit tip bootstrap; it does not claim
   or erase older history. Missed older history remains a separate bounded
   backfill concern.
3. A busy Pump address can fill every declared live-tail page before the prior
   boundary is reached. That must block as bounded coverage incomplete rather
   than raise budgets or skip.
4. Exact boundary verification adds one transport operation per established
   namespace, within existing operation ceilings but with lower spare capacity.
5. Public-node pruning remains possible. Printer can classify the prior exact
   boundary as unreachable; it cannot prove the provider's private pruning
   cause without an additional contract, so it must not invent one.
