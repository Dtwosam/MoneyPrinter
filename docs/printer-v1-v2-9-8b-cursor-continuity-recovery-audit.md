# Printer V1 V2-9.8B Cursor Continuity Recovery Audit

Date: 2026-07-29

Starting HEAD: `01e2315430ce401ae8d0658da988d1875672ada6`

Authoritative starting DB SHA-256:
`c8787da63b1f37a21366399444420e392d273d574e0904a06b2395bd83da3bc3`

Lane: `V2-9.8B Cursor Continuity Recovery Architecture and Final Live N2`

## Classification

`DESIGN_GAP`

The blocked N2 behaved correctly under its committed bounded live-tail policy:
it failed closed before foundation when neither exact prior boundary was found.
The missing capability is an explicitly approved, finite, durable recovery
continuation that can span separate manual executions without moving the
authoritative head. This lane supplies that approved boundary. It is not a
provider workaround, cursor reset, automatic retry, or N2 ceiling increase.

## Source-grounded blocker investigation

```text
BLOCKER CLASSIFICATION: DESIGN_GAP
EVIDENCE: both established FORWARD heads were exact and reachable for the
  preliminary getTransaction check, but the one-page-per-namespace N2 plan
  examined only two newest signatures per namespace and did not encounter
  either prior boundary.
OFFICIAL-SOURCE COMPARISON: getSignaturesForAddress is newest-first; before
  continues toward older rows; public history is not archival and empty/null
  results cannot prove absence. The pinned contract does not authorize an
  unbounded scan or infer continuity from slot distance.
PRINTER-CONTRACT COMPARISON: Source Governor and Central Scheduler must own every
  request/job; forward live recovery and backward historical backfill must stay
  distinct; incomplete recovery cannot admit candidates or move cursor heads.
ROOT CAUSE: the normal N2 transport has a deliberately tiny candidate-oriented
  signature budget and no durable multi-execution recovery continuation.
CODE CHANGE JUSTIFIED: YES, by this explicit operator-approved recovery lane.
MINIMUM SAFE RESPONSE: add a separate finite recovery command that chains exact
  immutable work evidence, resumes with before=the exact prior continuation,
  and invokes foundation only after both exact boundaries are encountered.
FOCUSED PROOF: process restart between every pass, exact-boundary and negative
  continuation tests, atomic final head advancement, then existing N2/N7 gates.
UNTOUCHED SCOPE: normal N2/N7 ceilings, campaign, tracking, lifecycle, memory,
  retrieval, financial capabilities, wallets, paid sources, scores, or vectors.
```

## Blocked-run facts

Execution: `20260729T175446Z-acq-222214011e4b`

| Namespace | Authoritative slot | Observed tip slot | Exact slot distance | N2 signature pages | Derived page size | Boundary encountered |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Pump create index | 435985590 | 435993497 | 7,907 | 1 | 2 | no |
| Pump migration program | 435985595 | 435993507 | 7,912 | 1 | 2 | no |

The exact signature distance is not derivable from slot distance and was not
measured by the bounded run. Reporting a signature count from these slot values
would be fabricated. The categorical exact fact is that each full two-row page
ended before its stored signature was encountered.

N2 used 20 Scheduler jobs, 20 governed requests, and 23 underlying transport
operations. Its fixed Solana plan reserved candidate mint, pool, holder, and
transaction enrichment. The signature budget was one governed page request for
each namespace. The transport derived page size from N=2 transaction capacity,
not from real elapsed cadence. That is appropriate for a normal bounded N2 but
not compatible with manual or irregular execution when Pump activity creates a
gap larger than two signatures.

## Complete current cursor model

```text
printer_candidate_acquisition_cursors exact FORWARD head
-> integration lease
-> exact head hydration
-> live owner verifies prior transaction
-> newest-first getSignaturesForAddress(until=prior)
-> one N2 page of two signatures per namespace
-> full page without exhaustion => GAPPED
-> immutable work/report evidence
-> foundation disabled
-> authoritative head byte-identical
```

The normal path correctly preserves the head. It does not expose a continuation
reader. `cursor_range_json` records only the terminal range view; the live owner
always initializes from the authoritative head and newest tip on the next run.
Therefore partial progress is operationally discarded even though the failed
work artifact remains auditable.

## Findings

1. **CONFIRMED.** Create and migration FORWARD heads are exact, separate, and
   byte-identical before/after the blocked N2.
2. **CONFIRMED.** Both stored boundaries were beyond the normal N2 page budget.
3. **CONFIRMED.** The normal N2 page limit is not cadence-compatible; it is a
   candidate-enrichment bound and must remain unchanged.
4. **CONFIRMED.** Normal N2 request headroom cannot safely be repurposed for
   arbitrary catch-up because candidate enrichment already has fixed governed
   and underlying-operation commitments.
5. **CONFIRMED.** Partial scan evidence is persisted but no exact continuation
   is reloaded; a later N2 starts again at the newest tip.
6. **CONFIRMED.** Existing immutable integration, work, and report rows can hold
   a safe recovery chain when the recovery ID, authoritative snapshot, frozen
   tip, continuation, page signatures, and page hash are exact and validated.
7. **CONFIRMED.** FORWARD recovery can bridge the live gap using `before` from a
   frozen live tip toward the exact authoritative signature. It must never read
   or mutate BACKWARD heads.
8. **CONFIRMED.** Nomination, enrichment, foundation, certificates, manifests,
   and head movement must stay disabled until both namespaces are complete.
9. **CONFIRMED.** A crash before immutable work commit repeats the same exclusive
   page safely; a crash after commit resumes from the exact committed last row.
   Duplicate, overlap, malformed order, wrong namespace/direction, rewind, skip,
   empty-before-boundary, and provider failure all fail closed.
10. **CONFIRMED.** The minimum safe architecture needs three distinct values:
    authoritative processed head, durable recovery continuation, and frozen live
    tip, plus exact chained page evidence and one final atomic foundation commit.

Rejected findings:

- raising the normal N2 page ceiling;
- reusing BACKWARD heads as forward recovery state;
- advancing a head after every recovery page;
- allowing candidate enrichment to compete with catch-up;
- treating slot distance as signature coverage;
- treating an empty page as proof of historical absence; and
- automatic retry, restart, successor, endpoint rotation, or unbounded looping.

## Schema decision

No migration is required.

Migration 049 already supplies:

- one global acquisition lease;
- immutable Scheduler/Source-Governed work rows;
- immutable per-work `cursor_range_json`;
- immutable terminal integration reports;
- exact FORWARD/BACKWARD cursor namespaces; and
- foundation-owned cursor ranges and atomic authoritative head advancement.

The recovery chain uses a deterministic recovery ID derived from both exact
authoritative head snapshots. Each committed page is one existing immutable
work row and carries its recovery ID, namespace, frozen tip, exact input
continuation, exact output continuation, ordered page signatures/slots, and
content hash. A next explicit recovery command accepts only the unique latest
valid chain. The global lease prevents concurrent chain writers. Foundation
rechecks the original heads under `BEGIN IMMEDIATE` before the final atomic
range/head commit.

A new mutable recovery table would add a second cursor authority and a second
partial-state write contract. The existing immutable ledger is safer and
sufficient once its recovery fields and validation are explicit.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Public RPC retention can make an exact old boundary unreachable even when
   its preliminary transaction check once succeeded.
2. A frozen finite lane bound can end before recovery completes. That must close
   BLOCKED without increasing the bound.
3. Recovery adds immutable work rows and page evidence; it does not create
   candidates and cannot claim missed Pump events were admitted.
4. New signatures arriving after the frozen recovery tip remain for the final
   N2 live tail; they do not alter the recovery chain.
5. Source Governor minute limits may prevent closely spaced manual executions.
   That is provider/governor unavailability, not authority to sleep, retry, or
   bypass accounting.
