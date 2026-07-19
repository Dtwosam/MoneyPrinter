# V2-9.7D.7B.4A Direct Pump Adapter and Continuity Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.4A
**Boundary:** implementation and synthetic fixture proof only
**Date:** 2026-07-19

PASS means the adopted direct Pump.fun creation contract now has a pure,
fixture-fed decoder and bounded continuity owner. It does not mean that a
network adapter, live subscription, RPC client, persistent cursor, combined
execution owner, campaign, tracking handoff, or financial capability exists.

## Todo / Checklist

- [x] Reconfirm the adopted Pump and Solana contract identities.
- [x] Implement exact finalized `create` decoding and fail-closed mutations.
- [x] Implement fixture-only governed operation and continuity ownership.
- [x] Prove cutoff, duplicate, gap, continuation, replay, and ceilings.
- [x] Run focused tests, static bypass scans, and both diff checks.
- [x] Preserve every Printer V1 capability lock.

## Adopted Authority

The implementation pins and tests:

- Pump Program:
  `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`;
- official `pump-fun/pump-public-docs` commit:
  `9c82f61cb711b044a17f770ab8ce9f9bdf78f333`;
- official `idl/pump.json` SHA-256:
  `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49`;
- `create` discriminator `181ec828051c0777`;
- `create_v2` discriminator `d6904cec5f8b31b4`, retained only to reject;
- supported transaction versions `"legacy"` and `0`;
- the official account order, fixed program/sysvar identities, Pump
  bonding-curve PDA, associated bonding-curve ATA, metadata PDA, and
  event-authority PDA;
- optional exact `CreateEvent`/Anchor CPI-event layout as corroboration only;
  and
- the adopted Source Governor and Central Scheduler ownership identities.

Official Pump Program/IDL and official Solana transaction/RPC structure remain
upstream authority. The adopted repository source stack remains authoritative
where it is stricter. No provider label, log text, score, rank, response order,
or inferred creator property is authority.

## Implemented Ownership and Data Flow

`src/printer_v1/sources/pumpfun_direct.py` contains only pure parsing and a
sequential fixture-operation port:

1. one governed `pumpfun_create_event_subscription` envelope supplies one
   finalized `getSlot` cutoff, one synthetic `logsSubscribe` response, and at
   most one synthetic `logsUnsubscribe` result;
2. up to two separately governed
   `pumpfun_create_signature_backfill` fixture pages enumerate finalized Pump
   signatures through the immutable cutoff;
3. signatures are normalized by exact signature, reconciled with finalized
   history, and ordered by `(slot, signature)`;
4. at most sixteen separately governed
   `pumpfun_create_transaction_reference` fixture results are decoded;
5. exact finalized observations are returned with mint, bonding curve,
   associated bonding curve, creator address, primary signature, slot, block
   time, and Pump Program ID; and
6. a fixture-only result returns observations, first-fault rejections,
   continuity, cursor, duplicate count, page count, and separate governed and
   underlying-operation accounting.

Every fixture operation must identify:

- `source_name=solana_rpc`;
- an adopted Source Governor request kind;
- `scheduler_job_kind=DISCOVERY_REFRESH`; and
- `scheduler_work_type=DISCOVERY_PUMPFUN_LATEST`.

Validation occurs before fixture consumption. An incorrect source/request kind
is `SOURCE_GOVERNOR_BYPASS`; incorrect Scheduler identity is
`CENTRAL_SCHEDULER_BYPASS`. The production Governor registry now admits the
five previously adopted direct/origin request kinds, but this lane invokes
only the three direct kinds.

There is no network library, socket, RPC method call, WebSocket connection,
database access, persistence function, command, or runtime entry point.

## Supported and Rejected Cases

Accepted evidence requires one and only one exact Pump `create` across
top-level and inner compiled instructions, a supported transaction version,
explicit finalized reference, exact primary signature and slot, successful
`meta.err=null`, non-null transaction block time, exact account identities and
derivations, no post-cutoff admission, and optional event agreement.

| Case | Implemented result |
|---|---|
| valid finalized legacy or v0 `create` | exact observation |
| v0 loaded addresses | static + writable-loaded + readonly-loaded resolution |
| identical duplicate signature | idempotent; one observation |
| failed signature or `meta.err` | `FAILED_TRANSACTION`; no claim |
| wrong instruction program | `WRONG_PROGRAM`; no claim |
| bad data/account count/index/PDA/ATA/metadata/fixed identity | `MALFORMED_TRANSACTION`; no claim |
| more than one supported `create` | `AMBIGUOUS_CREATE`; no claim |
| version above 0 or `create_v2` | `UNSUPPORTED_VERSION`; no claim |
| missing finality | `MISSING_FINALITY`; no claim |
| signature or slot mismatch | `SIGNATURE_OR_SLOT_MISMATCH`; no claim |
| exact-mint mismatch | `MINT_MISMATCH`; no claim |
| null block time or transaction unavailable | `UNAVAILABLE_HISTORY`; no claim |
| supported event conflict | `EVENT_MISMATCH`; no claim |
| post-cutoff signature/transaction | `POST_CUTOFF`; no current-cycle admission |
| conflicting duplicate | `CONFLICTING_DUPLICATE`; no claim and visible gap |
| finalized non-`create` Pump transaction | `NOT_SUPPORTED_CREATE`; reconciled non-creation |

Creator address is decoded only from the fourth Borsh `create` argument and is
labeled `OBSERVED_EVIDENCE_ONLY`. It does not establish control, coordination,
insider status, identity, authenticity, beneficial ownership, or intent and is
not an eligibility, ranking, weighting, safety, or financial input.

## Cursor, Gap, and Disconnect Behavior

The fixture owner resolves the cutoff exactly once. Its operation ceiling
rejects a second `getSlot`; post-cutoff evidence is reported and cannot mutate
the current cycle.

- `CONTIGUOUS` requires a trusted prior contiguous boundary, non-empty
  backfill evidence marked complete to that boundary, reconciliation of every
  in-range row, and no disconnect, missing, failed, malformed, conflicting,
  unsupported, ambiguous, or ceiling fault. Only then does the boundary
  advance to the largest deterministic `(slot, signature)` tuple.
- `GAPPED` retains individually valid observations but keeps the prior
  contiguous boundary unchanged when a bounded interval has a disconnect,
  conflict, incomplete two-page backfill, decode fault, or exhausted ceiling.
- `UNKNOWN` retains individually valid observations but keeps the prior
  boundary unchanged when no trusted prior contiguous cursor exists or empty
  fixture history cannot distinguish absence from unavailability.

A disconnected live session is failed and never reconnects in-cycle. Its
already planned finalized backfill may still retain exact individual facts,
but the disconnect remains a visible gap. At most two pages of at most sixteen
rows each are consumed. A third page, page-size expansion, second subscription,
second cutoff, ordinary retry, endpoint rotation, or unplanned operation fails
closed.

A following synthetic cycle accepts only the prior result's last proven
contiguous cursor. Gapped and unknown results cannot advance past that
boundary. Identical fixture inputs produce identical canonical results.

## Operation Accounting

Governed requests and underlying operations are separate:

| Direct activity | Governed ceiling | Underlying operations |
|---|---:|---|
| live-session envelope | 1 | one `getSlot`, one `logsSubscribe`, at most one `logsUnsubscribe` |
| finalized signature pages | 2 | one `getSignaturesForAddress` per page |
| finalized transaction references | 16 | one `getTransaction` per decoded reference |

The owner checks the request-ID ceiling independently from operation counts.
It also applies the design-frozen 45 underlying direct-lane operation ceiling
before incrementing. The concrete 4A direct path is additionally constrained
by its smaller per-operation maxima; unused headroom is not converted into
retries, reconnects, pages, decodes, or other calls.

## Money-Usefulness Contribution

The adapter prevents failed transactions, wrong programs, malformed account
graphs, unsupported creation versions, ambiguous instructions, mismatched
mints, post-cutoff evidence, conflicting duplicates, and incomplete coverage
from becoming false Pump-origin facts. Exact origin/time/account evidence can
improve future discovery provenance and reduce dirty memory inputs. Honest
`GAPPED` and `UNKNOWN` outcomes reduce yield rather than invent completeness.
This is input-quality protection only; it predicts no return and unlocks no
paper or real financial action.

## Blockers

No blocker remains for this synthetic implementation lane.

Live deployed-program equivalence, public-RPC retention, real transport
behavior, persistent first-fault/cursor storage, and measured operation costs
remain intentionally unproved because they belong to later explicitly
authorized lanes.

## What Remains Locked

The following were not implemented or activated:

- real RPC calls, WebSocket connections, provider calls, endpoint rotation, or
  live-source proof;
- schemas, migrations, database writes, cursor persistence, or campaign
  mutation;
- secondary adapters, persistence reconciliation, combined execution owner,
  tracking handoff, campaign runtime, command publication, V2-9.7D closeout,
  or pilot;
- memory creation, retrieval, paper decisions, BUY/SELL/HOLD, positions,
  trades, paper audits, or PnL;
- wallet connection, private keys, signing, real funds, live execution, paid
  APIs, scoring, ranking, confidence, weighting, embeddings, or vectors.

## Proof Results

Focused synthetic proof:

- valid finalized `create`, including legacy, v0 loaded-address resolution,
  exact extracted fields, PDA/ATA/metadata identities, and supported event;
- failed transaction, wrong program, malformed accounts, unsupported version,
  unsupported `create_v2`, ambiguous create, mint mismatch, missing finality,
  post-cutoff admission, and event mismatch;
- idempotent duplicate, conflicting duplicate, contiguous advancement,
  interrupted session plus planned backfill, two-page bounded gap, unknown
  history, and next-cycle continuation;
- deterministic replay;
- request, per-operation, and 45-underlying-operation ceilings;
- immutable cutoff and zero same-cycle reconnect;
- Source Governor and Central Scheduler bypass prevention; and
- absence of network and persistence imports/surfaces.

The focused test module completed 12 tests successfully. Relevant static
compile, registry consistency, bypass scans, and both diff checks are recorded
in the final task report.

## Functionality Risks / Setbacks / Efficiency Blockers

- `create_v2` remains unsupported and deliberately creates incomplete
  coverage; current launch yield may therefore be lower than Pump activity.
- The official public IDL may lag deployed behavior. Synthetic fixtures do not
  prove deployed-program equivalence.
- The Pump Program is busy; two pages and sixteen decodes can become gapped
  quickly. The implementation does not expand those ceilings.
- Empty, pruned, null, or unavailable history remains `UNKNOWN`; it is never
  treated as proof that no creation occurred.
- Finalized block time has no fallback. Null block time sacrifices yield.
- Pure Python PDA validation is deterministic and dependency-free, but live
  compatibility remains unproved until an authorized live-proof lane.
- Fixture operation costs prove accounting logic, not measured provider or
  transport costs.
- Continuity is returned in memory only. Durable first-fault and cursor state
  remains a later persistence responsibility.
- Strict zero reconnect/retry behavior preserves budgets and auditability but
  can increase `GAPPED` and `UNKNOWN` cycles.

## Stop Boundary

V2-9.7D.7B.4A stops at the pure decoder, fixture continuity owner, adopted
Governor request kinds, synthetic fixtures/tests, and this closeout. Secondary
adapters, persistence repair, combined execution, live RPC proof, V2-9.7D
closeout, and the pilot have not begun.