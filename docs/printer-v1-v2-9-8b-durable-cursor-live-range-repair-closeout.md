# Printer V1 V2-9.8B Durable Cursor-to-Live-Range Repair Closeout

Date: 2026-07-29

Starting HEAD: `f1def8f6154cd718b30fff469d602bafa900e926`

Lane: `V2-9.8B Durable Cursor-to-Live-Range Continuity Audit and Repair`

## Verdict

`V2_9_8B_DURABLE_CURSOR_LIVE_RANGE_REPAIR_PASS`

The independent audit, source-grounded classification, design, narrow repair,
sequential persistent-state proofs, public N2/N7 offline proofs, migration
compatibility, directly affected regressions, broad affected suite, and
authoritative-database hash gate all pass.

This PASS authorizes only a separately explicit future N2 live proof. No live
provider, RPC, N2, N7, campaign, tracking, lifecycle, snapshot, window, memory,
retrieval, decision, position, trade, audit, or PnL operation ran in this lane.

## Confirmed and rejected findings

All nine preliminary findings were confirmed; findings 8 and 9 were refined.
None was rejected.

1. Durable heads were not loaded into the live owner — confirmed.
2. Both cursor dictionaries restarted with null starts — confirmed.
3. Foundation was the first durable-head reader — confirmed.
4. Tests covered fresh DBs but not separate restart/resume — confirmed.
5. Live-tail RPC parameters were not derived from the durable head — confirmed.
6. Exclusive bounds, newest-first order, range start/end, and chronology were
   conflated — confirmed.
7. `CONTIGUOUS` proposed evidence could remain unanchored — confirmed.
8. Live tail and backfill require different construction under one canonical
   owner — confirmed/refined: `FORWARD` live tail uses `until`; `BACKWARD`
   backfill uses `before`.
9. All exact namespace dimensions and both head values must participate —
   confirmed/refined: five fields key the namespace; slot/signature are the
   exact hydrated and rechecked head.

Two additional defects were confirmed and repaired:

- intermediate multi-page cursor snapshots could reach foundation as competing
  ranges; and
- one namespace could be advanced/versioned once per observation ordinal
  instead of once per execution.

## Exact root cause

The canonical live transport owner was a stateless operation factory even
though signature-range construction is stateful. The integration acquired the
exclusive lease but did not read cursor heads before asking the owner to build
operations. The owner therefore created null starts, fetched from the newest
tip, paged only with `before`, and chose the oldest accumulated row as its end.
Foundation's correct exact-start recheck occurred only after all transport work.

The repair places an exact short-transaction cursor read after lease acquisition
and before operation construction. The logical lease spans transport; no SQLite
write transaction does. Foundation remains the sole atomic write owner and
rechecks the same exact start under `BEGIN IMMEDIATE` before commit.

## Final cursor semantics

### Live tail

```text
namespace direction = FORWARD
prior boundary verification = getTransaction(prior_signature)
first signature page = until=prior_signature
continuation page = until=prior_signature + before=previous_page_last_signature
RPC bounds = exclusive
RPC order = newest to oldest
Printer range start = prior durable head, inclusive
Printer range end = newest returned new signature, inclusive
```

No-new results keep start=end and do not advance. First bootstrap is explicit,
has no `until`, anchors only the current newest tip, and makes no older-history
claim. Empty bootstrap writes no head and no synthetic slot/signature; a later
execution may bootstrap again safely.

### Backfill

```text
namespace direction = BACKWARD
first page = before=prior_signature
continuation page = before=previous_page_last_signature
bootstrap = prohibited
normalized end = oldest returned signature
```

Backfill construction is offline-proven only. No backfill ran or was activated.
The two historical authoritative `BACKWARD` heads remain byte-preserved and are
never reused as `FORWARD` live-tail heads.

### Failure behavior

- Missing exact head after an advancing exact range:
  `CURSOR_DURABLE_HEAD_MISSING`.
- Wrong network, pin, decoder, or supplied direction:
  `CURSOR_NAMESPACE_MISMATCH`.
- Wrong durable start slot or signature: `CURSOR_START_MISMATCH` in foundation.
- Prior signature unavailable at the adopted exact transaction boundary:
  `CURSOR_PRIOR_BOUNDARY_UNREACHABLE`.
- Full declared live pages before bounded exhaustion:
  `CURSOR_CONTINUITY_GAPPED` with
  `LIVE_TAIL_PAGE_CEILING_BEFORE_BOUNDARY` range evidence.
- Duplicate signature or invalid page order: categorical transport failure; no
  cursor advance.

There is no reset, overwrite, rewind, skip, synthetic boundary, silent
bootstrap, retry, reconnect, endpoint rotation, or successor.

## Sequential offline proof results

All public-path executions used disposable migration-049 databases and the
normal command dispatch with the concrete live owner and frozen low-level
transports.

| Proof | Result |
| --- | --- |
| fresh N2 bootstrap | COMPLETED; two explicit namespaces; 0 loaded / 2 bootstrap; proposed/committed 2/2; one exact two-item manifest; projection 2 |
| separate N2 resume on same DB | COMPLETED; 2 loaded / 0 bootstrap; both exact prior slot/signature starts present in durable work; `until` equals each prior signature; proposed/committed 2/2 |
| one advance per namespace | PASS; both versions `1 -> 2` exactly once; heads equal newest new signatures |
| no-new execution | COMPLETED; proposed/committed 0/0; both versions remain 2 |
| empty bootstrap twice | COMPLETED twice; no synthetic range end, no durable head, no false advancement |
| multi-page N7 resume | COMPLETED; constant exact `until`, exclusive page-two `before`, newest end preserved; manifest 7, projection 0 |
| terminal idempotence | PASS; same execution replays identical report with zero new transport calls |
| wrong namespace/pin/decoder/direction | categorical fail/isolated bootstrap behavior proven; no cross-namespace reuse |
| wrong slot/signature | both block `CURSOR_START_MISMATCH`; committed advancement 0 |
| missing established head | blocks `CURSOR_DURABLE_HEAD_MISSING` before source work |
| unreachable prior boundary | blocks `CURSOR_PRIOR_BOUNDARY_UNREACHABLE`; foundation not run; heads unchanged |
| declared page ceiling before boundary | blocks `CURSOR_CONTINUITY_GAPPED`; no skip/rewind/advance |
| later required-source rollback | proposed/committed 2/0; heads and versions unchanged |
| N2 qualifying fixtures | foundation reached; exact two-item manifest and projection 2 |
| N7 qualifying fixtures | runtime-neutral seven-item manifest; projection 0; legacy adapter rejects |
| replay / cleanup / isolation | deterministic zero-source replay; leases 0; Scheduler residue 0; every protected delta 0 |

## Files changed

- `src/printer_v1/operator_cli/candidate_acquisition_integration.py` — exact
  post-lease head hydration, namespace/bootstrap reporting, terminal-range
  reconciliation, and unique proposed-head accounting.
- `src/printer_v1/operator_cli/live_candidate_acquisition_transport.py` — exact
  namespace declaration, live-head construction, exclusive `until`/`before`
  requests, boundary verification, page/order/duplicate checks, and safe empty
  behavior.
- `src/printer_v1/discovery/candidate_acquisition.py` — exact range conflict
  check and one atomic head update/version increment per namespace.
- `tests/test_v2_9_8b_candidate_acquisition_post_foundation_integration.py` —
  sequential public-path and negative cursor proofs.
- `docs/printer-v1-v2-9-8b-durable-cursor-live-range-audit.md`.
- `docs/printer-v1-v2-9-8b-durable-cursor-live-range-design.md`.
- this closeout.
- `AGENTS.md`, `docs/printer-v1-assistant-active-build-order-anchor.md`, and
  `docs/printer-v1-memory-growth-build-order-v2.md` — source-stack alignment:
  record this offline PASS and name only the separately explicit future N2
  live proof as next.

No migration, schema, authoritative DB, provider contract, source budget,
Scheduler owner, Source Governor owner, quote, holder, liquidity, tradeability,
cohort, or admission rule changed.

## Tests and checks

| Check | Result |
| --- | --- |
| pre-change focused baseline | 76 passed |
| final focused integration/cursor suite | 58 passed |
| directly affected foundation/lifecycle/readiness regressions | 52 passed |
| broad V2-9.8 affected suite | 267 passed and 24 subtests passed |
| Python compilation | PASS |
| fresh migration-049 DB | 49-ledger PASS; integrity `ok`; FK 0 |
| copied authoritative migration compatibility | 49-ledger PASS; integrity `ok`; FK 0; copy hash unchanged |
| `git diff --check` | PASS |
| authoritative active acquisition leases / Scheduler work | 0 / 0 |
| authoritative SQLite sidecars / open handle | 0 / 0 |

These suites overlap; counts are reported per verification boundary and are not
summed as unique tests.

## Authoritative database

Required starting SHA-256:

`d062a108fa178527e64c5ceb061c30a6889832dab8d072ff486b6a70797008f2`

Final SHA-256:

`d062a108fa178527e64c5ceb061c30a6889832dab8d072ff486b6a70797008f2`

Result: byte-identical PASS. Journal mode remains `delete`; integrity is `ok`;
foreign-key violations are zero.

## Capability locks

Active runtime capacity remains exactly two. The repair creates no campaign,
tracking, lifecycle, snapshot, window, memory, selective continuation,
retrieval, paper decision, BUY/SELL/HOLD, position, trade event, paper audit,
PnL, wallet, private key, signing, transaction submission, fund movement, paid
source, score, rank, confidence, weighting, embedding, or vector capability.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The authoritative DB has historical `BACKWARD` rows but no `FORWARD` live
   heads. A separately authorized future N2 will therefore perform explicit
   forward tip bootstrap; it will not rewrite or reuse the backward rows.
2. Busy Pump addresses can exceed the existing N2 page bound before an old
   forward head is reached. The correct result is a categorical coverage block,
   not a ceiling increase, skip, or cursor reset.
3. Exact transaction unavailability proves the prior boundary cannot be safely
   used; it does not distinguish provider pruning from every other provider-side
   unavailability cause. The report remains categorical and does not invent a
   pruning fact.
4. Boundary verification adds one underlying RPC operation per established
   namespace. Existing ceilings passed without change, but spare operation
   capacity is smaller.
5. Offline fixtures prove mechanics and persistence only. Live reliability and
   market yield remain unproven.

## Commit and worktree

One commit is required with message:

`Repair durable acquisition cursor continuity`

No tag is authorized. Commit identity and final worktree state are reported by
the operator-facing completion response after the commit is created.

## Exact next permitted task

A separately explicit, operator-authorized bounded live
`ACQUISITION_ONLY_N2` proof using the repaired public CLI path. That future task
must refresh the official Solana/Pump/PumpSwap contracts required by its live
preflight, preserve the authoritative cursor rows, and accept bootstrap,
coverage, provider, contract, or candidate outcomes honestly.

No N7 live run, retry, cursor reset, campaign, tracking, lifecycle, snapshot,
window, memory, retrieval, decision, position, trade, audit, PnL, or financial
task is authorized next.
