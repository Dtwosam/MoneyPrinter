# Printer V1 V2-9.8B Cursor Continuity Recovery Design

Date: 2026-07-29

Depends on:
`docs/printer-v1-v2-9-8b-cursor-continuity-recovery-audit.md`

Classification: `DESIGN_GAP`

## Design verdict

Add one public, operator-approved, recovery-only command mode that performs a
finite FORWARD scan under the existing acquisition lease, Central Scheduler,
Source Governor, transport, work, report, and foundation owners. It never
changes the normal N2/N7 plan or its ceilings.

## Frozen recovery command and limits

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command cursor-recovery-n2 --operator-approved
```

Each explicit command is one terminal execution:

| Limit | Frozen value |
| --- | ---: |
| pages per namespace per execution | 4 |
| signatures requested per page | 250 |
| governed requests per execution | 8 |
| underlying RPC operations per execution | 10 maximum |
| execution duration | 120 seconds |
| manually authorized executions in this lane | 12 maximum |
| automatic retries/restarts/successors | 0 |

The lane-wide theoretical scan bound is 12,000 signatures per namespace. It is
a recovery-only ceiling, not an increase to the one-page/two-signature normal
N2 plan. If either exact boundary is not encountered inside the twelfth explicit
execution, the lane closes BLOCKED.

## State architecture

```text
authoritative processed head
  = printer_candidate_acquisition_cursors exact FORWARD row

resumable recovery scan position
  = last exact committed recovery work page output continuation

current live tip
  = first exact row of the first recovery page, frozen for the recovery ID
```

Recovery identity binds both namespaces' network, address, pin, decoder,
direction, authoritative slot/signature/version, and the recovery contract
version. A process restart reconstructs the chain from immutable terminal
integration/work/report rows; it never trusts caller-supplied continuation.

Each page binds:

- recovery ID and execution ordinal;
- exact namespace and FORWARD direction;
- authoritative start slot/signature/version;
- frozen tip slot/signature;
- exact `before` input continuation or null for the first page;
- ordered returned signature/slot/error/finality rows;
- exact output continuation;
- whether the authoritative signature was encountered; and
- a canonical SHA-256 page hash.

## Request semantics

Recovery does not use `until`, because `until` is exclusive and cannot provide
the required exact boundary encounter. It pages newest-to-oldest:

1. first page: no `before`; freeze its newest row as the live tip;
2. later page: `before=last exact committed continuation signature`;
3. stop the page at the first exact authoritative signature;
4. reject any row after that boundary, duplicate/overlap, increasing slot,
   namespace mismatch, direction mismatch, skip, or rewind; and
5. treat empty results before encounter as prior-boundary unreachable.

The exact authoritative transaction is checked through the pinned existing
`getTransaction` contract before the first page for each namespace. No endpoint
rotation or alternate contract is introduced.

## Fairness and isolation

Page operations alternate create then migration by page ordinal. One namespace
may finish early; its later page slots become deterministic no-op work and do
not transfer budget to the other namespace. This preserves equal declared
opportunity, namespace isolation, and the frozen per-namespace ceiling.

Only exact FORWARD rows participate. BACKWARD historical heads and ranges are
read-only comparison evidence and are never accepted as a continuation.

## Terminal categories

- `CURSOR_RECOVERY_INCOMPLETE_BOUNDED_BUDGET`
- `CURSOR_RECOVERY_EXACT_BOUNDARY_REACHED`
- `CURSOR_RECOVERY_NO_NEW_SIGNATURES`
- `CURSOR_PRIOR_BOUNDARY_UNREACHABLE`
- `CURSOR_RECOVERY_PROVIDER_UNAVAILABLE`
- `CURSOR_RECOVERY_MALFORMED_PAGE`
- `CURSOR_RECOVERY_DUPLICATE_PAGE`
- `CURSOR_RECOVERY_NAMESPACE_MISMATCH`
- `CURSOR_RECOVERY_SKIP_ATTEMPT`
- `CURSOR_RECOVERY_REWIND_ATTEMPT`
- `CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED`

Failure precedence is contract/namespace/direction, skip/rewind, malformed or
duplicate evidence, provider unavailability, prior-boundary unreachability,
then bounded incompleteness.

## Persistence and crash behavior

- Before work commit: the authoritative head and durable continuation are
  unchanged; a later explicit command repeats the same exclusive page.
- After work commit: the next command resumes only from that row's exact output
  continuation and validates the full hash chain.
- Duplicate or overlapping page: no continuation update and terminal BLOCKED.
- Provider unavailable: retain the last committed continuation; no retry.
- No new signatures: exact boundary is the first row and recovery completes
  without a head change.
- Foundation exception/rollback: no authoritative head moves; the complete page
  chain remains available for explicit operator review, not automatic replay.

## Atomic completion

Candidate nomination/enrichment and foundation are disabled throughout every
incomplete execution. When both namespaces encounter their exact authoritative
signatures, the recovery owner builds two cursor-only normalized observations
covering each complete immutable chain. The existing foundation owner:

1. rechecks both exact authoritative heads under `BEGIN IMMEDIATE`;
2. persists source rounds, cursor observations, and complete cursor ranges;
3. advances each exact FORWARD namespace once to its frozen live tip; and
4. commits those records and heads atomically.

Recovery creates no certificate, reserve mutation, manifest, projection, or
runtime handoff. Its foundation result is expected to contain zero candidates;
recovery success is based only on atomic cursor reconciliation.

The final live N2 is a separate, exactly-once command after this reconciliation.
It loads the newly reconciled heads and performs normal current nomination and
admission under the unchanged N2 policy.

## Offline proof contract

The public command accepts only test-injected frozen one-shot transports and
disposable databases. Proof restarts the public command between every pass and
covers bootstrap, one-page, exact-limit, multi-pass, no-new, duplicates,
overlaps, both crash positions, wrong continuation/namespace/direction/slot/
signature, unreachable boundary, provider failure, fairness/isolation, replay,
atomic head advancement, residue, integrity, and protected deltas.

After recovery mechanics pass, the existing live-shaped N2/N7 proof must again
show exact 2 and 7 manifests, projections 2 and 0, legacy N7 rejection, and all
admission gates unchanged.

## Schema decision

No migration. See the audit's evidence-backed schema decision. The recovery
implementation may add only exact fields inside existing immutable JSON
artifacts and public-path code/tests.

## Scope locks

No campaign, tracking, lifecycle, snapshot, window, memory, retrieval, decision,
position, trade, audit, PnL, wallet, signing, transaction submission, funds,
paid source, score, rank, confidence, weighting, embedding, or vector capability
is added. Active runtime capacity remains exactly two.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A 12,000-signature bound may be insufficient; the correct outcome is
   BLOCKED, not a larger bound.
2. Work JSON is immutable but schema-level JSON field constraints are limited;
   every reconstruction therefore performs full canonical hash, identity,
   ordering, and chain validation before any request.
3. A public provider can prune or temporarily fail during the finite sequence.
4. Final N2 eligibility remains subject to all honest holder, liquidity,
   tradeability, freshness, identity, lineage, tracking, and cooldown gates.

