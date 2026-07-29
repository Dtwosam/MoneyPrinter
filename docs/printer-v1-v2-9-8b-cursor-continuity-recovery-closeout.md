# Printer V1 V2-9.8B Cursor Continuity Recovery Closeout

Date: 2026-07-29

Starting HEAD: `01e2315430ce401ae8d0658da988d1875672ada6`

Live checkpoint HEAD: `5af4b456676acc5eb07fa7844561cc0336962833`

Lane: `V2-9.8B Cursor Continuity Recovery Architecture and Final Live N2`

## Verdict

`V2_9_8B_CURSOR_CONTINUITY_RECOVERY_AND_LIVE_N2_BLOCKED`

The full audit classified the blocker as a `DESIGN_GAP`: the normal N2 path
correctly failed closed, but it had no durable multi-execution continuation.
The lane designed and implemented that missing recovery contract without a
schema change or a normal N2/N7 ceiling change. All offline gates passed and
the implementation was frozen in checkpoint commit
`5af4b456676acc5eb07fa7844561cc0336962833` before any live source call.

The finite live recovery then consumed all 12 pre-authorized explicit
executions. Pump create reached its exact prior boundary after 2,724 signatures
and 11 pages. The much denser Pump program/migration namespace did not reach its
prior boundary after 11,000 signatures and 44 pages. Execution 12 therefore
terminalized `CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED`. The frozen bound was not
raised. Foundation, authoritative head advancement, certificates, manifests,
and projection stayed disabled, and the final live N2 was correctly `NOT_RUN`.

No implementation was patched after live work began. This is an honest bounded
recovery result, not permission to continue the scan or run N2.

## Confirmed and rejected findings

Confirmed:

1. The blocked admission run's exact stored-to-tip slot distances were 7,907
   for create and 7,912 for migration. Its one two-signature page per namespace
   could not encounter either boundary.
2. Slot distance is not signature distance. The recovery run measured the real
   asymmetry: 2,724 create signatures closed 13,431 slots, while 11,000
   migration-program signatures moved only from the frozen tip at 435,999,023
   to a continuation at 435,998,983.
3. The normal N2 page limit is candidate-oriented and incompatible with manual
   or irregular execution cadence as a continuity-recovery mechanism.
4. Normal N2 request headroom cannot safely cover catch-up and enrichment.
   Recovery requires a separately frozen request budget with enrichment off.
5. Before this lane, partial `CURSOR_CONTINUITY_GAPPED` scans were auditable but
   operationally discarded; the next run restarted at the newest tip.
6. Existing immutable integration/work/report rows safely represent recovery
   continuation when recovery identity, namespace, authoritative snapshot,
   frozen tip, input/output continuation, ordered page evidence, and hashes are
   validated on every process restart.
7. `FORWARD` recovery and `BACKWARD` historical backfill remain distinct. No
   historical head or range was read as recovery authority or mutated.
8. Candidate nomination, enrichment, foundation, certificates, manifests, and
   head advancement must remain disabled until both namespaces complete.
9. Offline proofs establish fail-closed crash, rollback, duplicate, overlap,
   no-new-data, malformed evidence, wrong continuation, provider failure, and
   unreachable-boundary behavior.
10. The minimum restart-safe architecture is three separate values: exact
    authoritative processed head, exact durable recovery continuation, and
    immutable frozen live tip.

Rejected:

- increasing the normal N2 ceiling;
- silently increasing the frozen live recovery bound;
- moving the authoritative head after a partial page;
- treating an empty page or slot arithmetic as complete evidence;
- mixing create and migration state or FORWARD and BACKWARD direction;
- admitting candidates while recovery is incomplete; and
- automatic retry, restart, successor, cursor reset, or unbounded looping.

## Final recovery architecture

The public recovery command is:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command cursor-recovery-n2 --operator-approved
```

Each invocation is terminal and uses four pages per namespace, 250 signatures
per page, eight governed requests, at most ten underlying RPC operations, and a
120-second duration ceiling. The lane froze a maximum of 12 manual executions.
Automatic retries, restarts, and successors are zero.

Recovery freezes the first exact newest row as the live tip, walks older rows
with `before=<exact committed continuation>`, and requires exact encounter of
the authoritative signature. Create and migration page opportunities alternate
fairly and remain isolated. Every request is owned by Source Governor and every
job by Central Scheduler. Each next process reconstructs and validates the
immutable chain; it accepts no caller-supplied continuation.

The authoritative cursor does not move during incomplete recovery. Only after
both namespaces complete may the existing foundation owner recheck both heads
under `BEGIN IMMEDIATE` and atomically commit normalized cursor observations,
ranges, and both new heads. Recovery itself produces no candidates,
certificates, manifests, projection, or handoff.

Terminal categories distinguish incomplete bounded budget, exact boundary,
no-new-signatures, prior boundary unreachable, provider unavailable, malformed
or duplicate page, namespace mismatch, skip, rewind, and lane-bound exhaustion.

## Schema decision

No migration was added. Migration 049's immutable integrations, work rows with
JSON cursor evidence, terminal reports, global lease, exact cursor namespace,
and foundation transaction are sufficient. Adding a mutable recovery table
would create a second cursor authority; chained immutable work evidence is the
safer minimum design.

## Offline sequential proof

The dedicated recovery contract suite passed 16 tests. It proved:

- fresh bootstrap, one-page boundary, and boundary exactly at the page limit;
- gaps at and beyond two pages and recovery requiring two and three explicit
  processes with state reconstructed between every pass;
- final exact encounter and one atomic head advancement;
- no admission during incomplete recovery and deterministic zero-source replay;
- no new signatures, duplicate/overlap, malformed order, skip, rewind, wrong
  continuation/namespace/direction/slot/signature, unreachable boundary, and
  provider failure;
- crash before page-state commit and crash after recovery-state commit before
  final head commit;
- create/migration fairness and isolation; and
- zero cursor duplicate advancement, lease residue, Scheduler residue,
  protected-table delta, integrity failure, or foreign-key violation.

Post-recovery live-shaped admission remained intact:

| Proof | Certificates admitted | Manifest | Projection | Legacy projection | Result |
| --- | ---: | ---: | ---: | --- | --- |
| N2 | 4 | exact 2 | 2 | accepted | `COMPLETED` |
| N7 | 7 | exact 7 | 0 | rejected | `COMPLETED` |

The proof matrix retained exact mint, pool, quote, holder, liquidity,
tradeability, lineage, tracking, cooldown, insufficient-N, Scheduler, Source
Governor, replay, cleanup, and protected-delta gates. Runtime handoff was zero.

## Tests and checks

- recovery contract suite: `16 passed`;
- focused foundation/integration/recovery suite: `109 passed`;
- provider-inclusive affected suite: `386 passed`;
- broad affected suite: `587 passed, 116 subtests passed`;
- changed Python compilation: PASS;
- `git diff --check`: PASS;
- disposable migration application and idempotent reapplication: 49 migrations
  through 049, integrity `ok`, zero foreign-key violations;
- Ruff: not available in the repository virtual environment, so no Ruff result
  is claimed.

## Live preflight and backup

The checkpoint tree was clean. The canonical preflight returned
`V2_9_8_OPERATIONAL_PREFLIGHT_READY`; migration 049 was current, integrity was
`ok`, foreign-key violations were zero, and active leases, integrations,
Scheduler work, sidecars, and database handles were zero.

Fresh backup:

`/private/tmp/printer-v1-cursor-recovery-live.gXWtmJ/printer_v1.pre-recovery.backup.sqlite3`

The source and backup were both 17,448,960 bytes and shared SHA-256
`c8787da63b1f37a21366399444420e392d273d574e0904a06b2395bd83da3bc3`.

## Authorized live recovery executions

| # | Execution ID | Terminal cause | Jobs / governed / transport | Rows | Namespace result after execution |
| ---: | --- | --- | --- | ---: | --- |
| 1 | `20260729T183023Z-recovery-236a688fd522` | `CURSOR_RECOVERY_PROVIDER_UNAVAILABLE` | 1 / 1 / 1 | 0 | no committed page |
| 2 | `20260729T183345Z-recovery-c2697725455e` | incomplete bounded budget | 8 / 8 / 10 | 2,000 | create 1,000; migration 1,000 |
| 3 | `20260729T183407Z-recovery-398464eef121` | incomplete bounded budget | 8 / 8 / 10 | 2,000 | create 2,000; migration 2,000 |
| 4 | `20260729T183424Z-recovery-ef992f37c455` | incomplete bounded budget | 8 / 8 / 9 | 1,948 | create exact at 2,724; migration 3,000 |
| 5 | `20260729T183450Z-recovery-a8ff68ea9f87` | incomplete bounded budget | 8 / 8 / 5 | 1,000 | migration 4,000 |
| 6 | `20260729T183524Z-recovery-b9c830d8300e` | incomplete bounded budget | 8 / 8 / 5 | 1,000 | migration 5,000 |
| 7 | `20260729T183535Z-recovery-c50ee6ca2755` | incomplete bounded budget | 8 / 8 / 5 | 1,000 | migration 6,000 |
| 8 | `20260729T183611Z-recovery-6cc2c253937d` | incomplete bounded budget | 8 / 8 / 5 | 1,000 | migration 7,000 |
| 9 | `20260729T183636Z-recovery-4426261e1d9e` | incomplete bounded budget | 8 / 8 / 5 | 1,000 | migration 8,000 |
| 10 | `20260729T183647Z-recovery-0a043d63d94f` | incomplete bounded budget | 8 / 8 / 5 | 1,000 | migration 9,000 |
| 11 | `20260729T183726Z-recovery-4d25701d96db` | incomplete bounded budget | 8 / 8 / 5 | 1,000 | migration 10,000 |
| 12 | `20260729T183801Z-recovery-39858cca3127` | `CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED` | 8 / 8 / 5 | 1,000 | migration 11,000; boundary absent |

Execution 1 was an explicit sandboxed invocation that terminalized on provider
unavailability. Execution 2 was a separately explicit approved invocation with
network access. The failed first invocation counted against the frozen 12; the
bound was not extended.

Aggregate recovery accounting was 89 Scheduler jobs, 89 governed requests, 70
underlying operations, 13,948 rows, and 3,546,198 response bytes. The terminal
ledgers contain 88 succeeded and one failed Scheduler/work row, 89 source
requests, 88 responses, and one failure. All leases and jobs terminalized.

Final exact recovery state:

| Namespace | Authoritative slot | Frozen tip | Slot distance | Signatures | Pages | Exact boundary |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| create | 435985590 | 435999021 | 13,431 | 2,724 | 11 | reached |
| migration | 435985595 | 435999023 | 13,428 | 11,000 | 44 | not reached |

The migration continuation is exactly slot 435,998,983. Many signatures share
slots, so the small 40-slot movement after 11,000 signatures is valid evidence
of program-address density, not a continuity anomaly.

## Final live N2

`NOT_RUN`

The required gate—exact recovery and authoritative reconciliation for both
namespaces—did not pass. The canonical `acquisition-only-n2` command therefore
had invocation count zero in this lane. There was no retry and no live N7.

## Post-live reconciliation

- authoritative cursor rows: byte-identical to backup (`EXCEPT` both ways = 0);
- cursor advances, ranges, and foundation executions: zero;
- certificates, manifests, manifest items, projection, and handoff: zero;
- active leases, integrations, and Scheduler work: zero;
- protected tracking, snapshot, window, memory, retrieval, decision, position,
  trade, audit, and PnL table delta sum: zero;
- integrity: `ok`; foreign-key violations: zero; sidecars: none;
- post-live DB size: 64,618,496 bytes;
- post-live DB SHA-256:
  `36cf157b74a28fe93695f7c29ffee143a3d7ed6453bdcec5ad74ea666284fa09`.

The size growth is immutable governed recovery evidence. The internal report
ledger retains raw page rows and is consequently large. The committed redacted
artifact excludes raw signatures, payloads, endpoint URLs, candidates, and RPC
secret material.

## Files changed

- `docs/printer-v1-v2-9-8b-cursor-continuity-recovery-audit.md`
- `docs/printer-v1-v2-9-8b-cursor-continuity-recovery-design.md`
- `docs/printer-v1-v2-9-8b-cursor-continuity-recovery-closeout.md`
- `docs/printer-v1-v2-9-8b-cursor-continuity-recovery-live-redacted.json`
- `src/printer_v1/operator_cli/cursor_continuity_recovery.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_8b_cursor_continuity_recovery.py`

## What was not touched

No normal N2/N7 page, request, or time ceiling; schema/migration; active
capacity; `M=2N`; candidate admission rule; Scheduler/Source Governor ownership;
BACKWARD backfill; campaign; tracking; lifecycle; snapshot; window; memory;
retrieval; paper decision; BUY/SELL/HOLD; position; trade; audit; PnL; wallet;
signing; transaction; real funds; paid source; score; rank; confidence; weight;
embedding; or vector capability was added or loosened.

There was no cursor reset, automatic retry, restart, successor, live N7, final
live N2, campaign, or post-live code patch.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The exact migration boundary remains unreconciled after 11,000 signatures;
   no live candidate admission can rely on this incomplete range.
2. The live Pump program address is far denser than slot distance suggests. A
   future recovery bound must be source-grounded; this lane does not authorize
   one.
3. Public RPC retention or availability may still prevent exact boundary
   encounter in any separately authorized continuation.
4. Raw immutable page evidence increased the authoritative DB by about 47 MB.
   The reporting footprint is a bounded operational concern, not authorization
   to mutate or compact this evidence.
5. The recovery architecture and admission path are fully proved offline, but
   final N2 admission was not reached live in this lane.

## Exact next permitted task

Operator review of this BLOCKED closeout and redacted evidence only.

No further recovery execution, changed recovery bound, final N2, retry,
successor, cursor reset, N7, campaign, tracking, lifecycle, snapshot, window,
memory, retrieval, or financial lane is authorized. Any future source-grounded
recovery-bound investigation or continuation requires separate explicit
operator authorization under the active source stack.
