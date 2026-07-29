# Printer V1 V2-9.8B Durable Cursor-to-Live-Range Repair Design

Date: 2026-07-29

Depends on:
`printer-v1-v2-9-8b-durable-cursor-live-range-audit.md`

Classification: `COMMITTED_CODE_DEFECT`

## Design verdict

The repair is implementable without a schema, migration, new RPC method,
provider contract, retry path, or new orchestration owner.

## Canonical ownership

```text
public operational command
-> existing candidate-acquisition integration
-> acquire exclusive acquisition lease
-> exact short-transaction cursor hydration
-> canonical live transport owner constructs finite operations
-> Central Scheduler and Source Governor execute every operation
-> foundation BEGIN IMMEDIATE exact-head recheck
-> atomic observations/certificates/manifest/ranges/head commit
-> terminal report, replay, cleanup
```

The acquisition lease is the logical cross-request cursor lock. Cursor
hydration uses a short `BEGIN IMMEDIATE` transaction and releases the SQLite
lock before network I/O. The foundation re-reads the same namespace under its
own `BEGIN IMMEDIATE` transaction immediately before atomic commit. No write
transaction spans transport work.

## Namespace and hydration contract

Exact key:

```text
network | indexed_address | official_contract_pin | decoder_version | direction
```

Exact head:

```text
boundary_slot | boundary_signature | cursor_version | last_range_id
```

The live owner declares both Pump namespaces before operations. The integration
owner loads them only after acquiring the exclusive lease and passes immutable
head values into operation construction.

- No exact row and no prior exact-direction range: explicit bootstrap.
- Exact row: slot and signature must both be present and valid.
- Prior exact-direction range but missing head: `CURSOR_DURABLE_HEAD_MISSING`.
- Same address/direction with a different network, pin, or decoder:
  `CURSOR_NAMESPACE_MISMATCH`.
- A supplied/mutated head whose identity differs from the declared namespace:
  `CURSOR_NAMESPACE_MISMATCH`.
- `FORWARD` and `BACKWARD` rows are isolated namespaces and never substitute for
  one another.

Fresh bootstrap is allowed only when the exact namespace has never established
a range. It is explicit in cursor evidence and terminal reporting.

## Query and range semantics

### `LIVE_TAIL`

- durable direction: `FORWARD`;
- provider response order: newest to oldest;
- established boundary verification: exact `getTransaction(prior_signature)`;
- first page: `until=prior_signature`, no `before`;
- continuation page: same `until`, plus
  `before=last_signature_from_previous_page`;
- `until` and `before` are exclusive;
- normalized range start: exact prior slot/signature, inclusive as Printer's
  already-processed boundary;
- normalized range end: newest newly returned row, inclusive;
- no new rows: start equals end, `cursor_advanced=false`;
- full final declared page before the lower boundary is demonstrably exhausted:
  `GAPPED`, `LIVE_TAIL_PAGE_CEILING_BEFORE_BOUNDARY`;
- unavailable prior transaction: `CURSOR_PRIOR_BOUNDARY_UNREACHABLE`.

On first bootstrap there is no `until`. The first valid returned row (the newest
tip) becomes the head. Older rows are not claimed as forward-live coverage and
remain eligible only for separate backfill. Empty bootstrap produces no head,
no synthetic slot/signature, and no advancement.

### `BACKFILL`

- durable direction: `BACKWARD`;
- an exact prior head is mandatory;
- first page: `before=prior_signature`, no `until`;
- continuation page: `before=last_signature_from_previous_page`;
- normalized start: exact prior head;
- normalized end: oldest returned row;
- full page ceilings remain incomplete/gapped;
- bootstrap is prohibited.

Backfill request construction remains internal and offline-proven. This lane
does not run or activate a backfill.

## Page validation

Every page must be a list of mappings with a non-empty signature, integer
non-negative slot, and non-increasing slot order. Duplicate signatures within
or across pages fail `CURSOR_DUPLICATE_SIGNATURE`. A live-tail row below the
prior slot fails continuity. Transaction decoding still considers only
successful finalized rows, but cursor coverage accounts for every valid
returned signature, including failed transactions.

## Atomic head contract

Foundation retains sole write ownership and:

1. rechecks exact namespace start against the currently locked durable head;
2. persists immutable range evidence;
3. advances only `CONTIGUOUS` ranges with a real end;
4. deduplicates by exact namespace, not observation ordinal;
5. increments each advanced namespace version exactly once per execution; and
6. rolls observations, certificates, manifest, ranges, and head updates back
   together on any failure.

Integration reporting counts unique proposed namespaces and exact heads whose
`last_execution_id` equals the execution. Proposed and committed counts must be
equal on terminal success and committed must be zero on pre-foundation or
foundation rollback.

## Public-path proof

The proof uses `main([mode, "--operator-approved"])`, disposable databases
migrated through 049, the concrete live owner, and frozen low-level transport
responses. It covers:

1. explicit fresh bootstrap for both namespaces;
2. a second separately constructed execution on the same DB;
3. exact prior slot/signature hydration;
4. `until` live-tail and `before` continuation/backfill construction;
5. one head advance per namespace with no duplicates/gaps;
6. no-new-signature stability;
7. multi-page exact boundary preservation;
8. terminal replay/idempotence;
9. namespace/pin/decoder/direction/slot/signature negatives;
10. missing and unreachable prior heads;
11. success/rollback report reconciliation;
12. qualifying public N2 two-item manifest;
13. runtime-neutral N7 and strict legacy rejection;
14. zero-source deterministic replay;
15. zero lease/Scheduler residue and protected deltas.

## Scope and locks

Changed owners may be only:

- candidate-acquisition integration cursor hydration/reporting;
- canonical live transport cursor request/normalization;
- foundation exact head advancement deduplication;
- directly affected tests and the three lane documents.

No schema, migration, quote, holder, liquidity, tradeability, admission, cohort,
budget, Scheduler, Governor, campaign, tracking, lifecycle, snapshot, window,
memory, retrieval, decision, position, trade, audit, PnL, wallet, signing, paid
source, score, rank, confidence, weighting, embedding, or vector change is
authorized.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Exact boundary verification consumes two additional RPC operations on a
   normal established run; ceilings remain fixed.
2. Forward bootstrap intentionally does not claim old history. Backfill remains
   separate and inactive.
3. An unavailable prior boundary blocks rather than silently bootstrapping,
   resetting, or rotating endpoints.
4. Same-slot ordering is provider-defined newest-first; slot alone is not used
   as a total ordering key, so exact signature identity remains mandatory.
5. The proof is deterministic mechanics only and makes no live reliability
   claim.
