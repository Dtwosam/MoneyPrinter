# Direct Pump.fun On-Chain Creation Discovery Contract

**Status:** ADOPTED for contract and fixture use only on 2026-07-19
**Lane:** V2-9.7D.7B.3A
**Authority:** official Pump public repository/IDL and official Solana RPC
documentation, constrained by the Printer V1 source stack

This contract defines how a future read-only adapter may recognize a direct
Pump Program coin creation. It does not implement or activate an adapter,
subscription, RPC request, cursor, campaign, database write, or runtime.

## Todo / Checklist

- [x] Pin official Pump Program, repository commit, and IDL bytes.
- [x] Freeze supported instruction, event, transaction, and extraction rules.
- [x] Freeze finality, failure, cursor, continuity, and backfill rules.
- [x] Bind all future source work to Source Governor and Central Scheduler.
- [x] Preserve unknowns, limits, creator-evidence boundaries, and V1 locks.

## Adopted Authority

Official Pump source, retrieved 2026-07-19:

- repository: `https://github.com/pump-fun/pump-public-docs`
- commit: `9c82f61cb711b044a17f770ab8ce9f9bdf78f333`
- IDL path: `idl/pump.json`
- IDL SHA-256:
  `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49`
- Pump Program ID:
  `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`

The hash is over the exact raw `idl/pump.json` bytes at the pinned commit.
Moving `main`, an SDK, an explorer label, third-party decoder output, a log
string, or a provider's Pump.fun category is not authority for this contract.
A later IDL/repository change requires a new explicit adoption.

Official Solana authority:

- `getSlot`
- `getSignaturesForAddress`
- `getTransaction`
- `logsSubscribe` / `logsUnsubscribe`
- confirmed-transaction JSON structures and versioned-message address loading

All requests must state `finalized` where the method supports commitment.
Printer's local source-of-truth documents remain binding where they are
stricter than upstream documentation.

## Supported Creation Instruction

Only the pinned instruction named `create` is supported:

- discriminator bytes: `[24, 30, 200, 40, 5, 28, 7, 119]`
- discriminator hex: `181ec828051c0777`
- arguments, Borsh order:
  1. `name: string`
  2. `symbol: string`
  3. `uri: string`
  4. `creator: pubkey`

The exact account order is:

| Index | IDL name | Required contract use |
|---:|---|---|
| 0 | `mint` | extracted mint; writable signer |
| 1 | `mint_authority` | exact account position retained |
| 2 | `bonding_curve` | extracted bonding-curve PDA |
| 3 | `associated_bonding_curve` | extracted associated bonding-curve token account |
| 4 | `global` | exact account position retained |
| 5 | `mpl_token_metadata` | exact account position retained |
| 6 | `metadata` | exact account position retained |
| 7 | `user` | transaction user evidence only; not creator |
| 8 | `system_program` | exact official System Program |
| 9 | `token_program` | exact official SPL Token Program |
| 10 | `associated_token_program` | exact official Associated Token Program |
| 11 | `rent` | exact Rent sysvar |
| 12 | `event_authority` | exact IDL-constrained event-authority PDA |
| 13 | `program` | exact Pump Program ID |

Extra or missing instruction accounts are malformed for this adopted layout.
The compiled instruction's resolved program ID must equal the pinned Pump
Program ID. Account indices are resolved against static message account keys
followed by `meta.loadedAddresses.writable` and then
`meta.loadedAddresses.readonly`.

The future decoder must additionally prove:

- account 2 equals the Pump PDA derived from
  `["bonding-curve", account_0_mint]`;
- account 3 equals the associated token address for owner account 2, mint
  account 0, the SPL Token Program, and the Associated Token Program;
- fixed-address accounts equal their pinned IDL addresses/PDA constraints.

Instruction data that does not decode to exactly four arguments with no
trailing bytes is malformed. The `creator` comes from argument 4. It must not be
substituted with `user`, a fee payer, a signer, metadata authority, or an event
source.

The pinned IDL also contains `create_v2` with discriminator
`[214, 144, 76, 236, 95, 139, 49, 180]`. `create_v2`, any future creation
instruction, and any older/different `create` layout are
`UNSUPPORTED_INSTRUCTION_VERSION` in this lane. They create visible incomplete
coverage and no origin claim. This contract must be re-adopted before support.

## Supported `CreateEvent` Layout

The pinned event is `CreateEvent`:

- event discriminator bytes: `[27, 114, 169, 77, 222, 235, 99, 118]`
- event discriminator hex: `1b72a94ddeeb6376`
- supported Anchor CPI event wrapper, when present:
  `[228, 69, 165, 46, 81, 203, 154, 29]`
  (`e445a52e51cb9a1d`)

After the event discriminator, the exact Borsh field order is:

1. `name: string`
2. `symbol: string`
3. `uri: string`
4. `mint: pubkey`
5. `bonding_curve: pubkey`
6. `user: pubkey`
7. `creator: pubkey`
8. `timestamp: i64`
9. `virtual_token_reserves: u64`
10. `virtual_sol_reserves: u64`
11. `real_token_reserves: u64`
12. `token_total_supply: u64`
13. `token_program: pubkey`
14. `is_mayhem_mode: bool`
15. `is_cashback_enabled: bool`
16. `quote_mint: pubkey`
17. `virtual_quote_reserves: u64`

The event is optional corroboration, not the creation authority by itself.
Where a supported event is consumed, its enclosing inner instruction must
resolve to the Pump Program, its bytes must consume the exact supported layout,
and its `mint`, `bonding_curve`, `creator`, and `token_program` must exactly
match the supported `create` instruction and fixed program identities. A
supported event mismatch rejects the transaction. An absent event does not
override an otherwise exact supported `create`. A truncated, appended,
different-discriminator, log-text-only, or independently supplied event is not
decoded and cannot fill an instruction field.

The event `timestamp` is observed program event data only. Canonical discovery
time is the finalized transaction `blockTime`.

## Supported Transaction Envelope and Exact Extraction

Supported transaction versions are:

- `"legacy"`; and
- version `0`, requested with `maxSupportedTransactionVersion: 0`.

Any numeric version above `0`, missing/unrecognized version, unresolved address
lookup, parsed instruction without recoverable raw bytes, or non-JSON
transaction encoding is `UNSUPPORTED_TRANSACTION_VERSION` or malformed and
produces no origin claim.

A transaction is accepted only when exactly one supported Pump `create`
instruction exists across top-level and inner compiled instructions. Zero is
not a creation. More than one is `AMBIGUOUS_CREATE`.

Exact normalized fields are:

| Field | Sole extraction |
|---|---|
| `mint` | resolved `create` account index 0 |
| `bonding_curve` | resolved `create` account index 2, plus exact Pump PDA check |
| `associated_bonding_curve` | resolved `create` account index 3, plus exact ATA derivation check |
| `creator_address` | fourth Borsh `create` argument |
| `signature` | `transaction.signatures[0]`, exactly equal to the requested/listed/notified signature |
| `slot` | top-level `getTransaction.result.slot`, exactly equal to signature-list/notified slot where both exist |
| `block_time` | non-null top-level `getTransaction.result.blockTime` |
| `program_id` | resolved compiled-instruction program ID |

`getSignaturesForAddress.blockTime` and event `timestamp` may be retained as
corroborating observations, but neither replaces the canonical transaction
`blockTime`. A null block time remains unknown and blocks an adopted complete
creation record; this lane adopts no `getBlockTime` fallback.

Creator address is observed evidence only. It does not prove wallet control,
coordination, insider status, authenticity, beneficial ownership, identity, or
intent. It cannot be scored, ranked, weighted, or promoted into a safety or
financial claim.

## Finalized Success and Failure Matrix

An origin claim requires all of the following:

1. the signature row or live notification is reconciled to explicit finalized
   history;
2. `getTransaction` was requested at `finalized`;
3. the result is non-null with supported version and JSON shape;
4. `meta` is non-null and `meta.err` is null;
5. signature, slot, program, instruction, accounts, arguments, PDA/ATA
   derivations, and any consumed event all match;
6. block time is non-null; and
7. when verifying a requested mint, it exactly equals decoded account 0.

| Condition | Required result |
|---|---|
| failed signature row, notification, or `meta.err != null` | `FAILED_TRANSACTION`; no claim |
| null/pruned/unavailable transaction or block time | `UNAVAILABLE_HISTORY`; continuity not claimed |
| short/bad data, bad Borsh, bad account index/count, unresolved ALT, bad PDA/ATA | `MALFORMED_TRANSACTION`; no claim |
| resolved instruction program is not exact Pump Program | `WRONG_PROGRAM`; no claim |
| zero supported `create` | `NOT_SUPPORTED_CREATE`; no claim |
| more than one supported `create` | `AMBIGUOUS_CREATE`; no claim |
| transaction version above 0 or `create_v2`/other layout | `UNSUPPORTED_VERSION`; no claim |
| requested/listed/notified signature or slot differs | `SIGNATURE_OR_SLOT_MISMATCH`; no claim |
| requested mint differs from decoded mint | `MINT_MISMATCH`; no claim |
| supported event conflicts with instruction | `EVENT_MISMATCH`; no claim |
| repeated signature with byte-identical normalized evidence | idempotent duplicate; one observation |
| repeated signature with conflicting evidence | `CONFLICTING_DUPLICATE`; no claim and visible gap |

Failures are evidence, not retry permission. They must retain the exact
request, scheduler work, provider/endpoint, signature, slot where known,
contract identity, failure kind, and capture time.

## Source Governor and Central Scheduler Ownership

The adopted Source Governor source is `solana_rpc`. The adopted request kinds
from 7B.2 are:

| Request kind | Governed meaning | Maximum per cycle |
|---|---|---:|
| `pumpfun_create_event_subscription` | one bounded session envelope, including one finalized cutoff read and the subscribe/unsubscribe operations | 1 |
| `pumpfun_create_signature_backfill` | one finalized `getSignaturesForAddress` page for the Pump Program | 2 |
| `pumpfun_create_transaction_reference` | one finalized `getTransaction` for a directly observed signature | 16 |
| `pumpfun_origin_signature_reference` | one bounded finalized signature lookup for one admitted secondary mint | 8 |
| `pumpfun_origin_transaction_reference` | one finalized `getTransaction` for one admitted secondary-mint origin candidate | 8 |

No network operation may occur before Governor admission, outside the admitted
request, after cancellation, or on an adapter-owned retry/endpoint loop.
Fan-out is never hidden: each underlying JSON-RPC operation, WebSocket
subscribe/unsubscribe operation, connection identity, byte count, timeout, and
outcome must be counted and linked even when one governed session envelope
owns several operations.

Central Scheduler owns one cycle-rooted
`job_kind=DISCOVERY_REFRESH`,
`work_type=DISCOVERY_PUMPFUN_LATEST` item. The Scheduler owns start, lease,
deadline, cancellation, terminal state, and next-cycle eligibility. The future
adapter may not create work, reconnect, resume, rotate endpoints, start a
successor, advance a cursor, or schedule backfill independently.

## Cursor, Cutoff, Backfill, and Continuity

The persisted logical cursor contract (not implemented here) contains:

- cluster and redacted endpoint identity;
- Pump Program ID, official commit, and IDL SHA-256;
- last contiguous finalized slot and last processed signature within that
  slot;
- one immutable cycle cutoff slot resolved by the governed session at
  `finalized`;
- first/last covered signatures, page count, inspected transaction count, and
  duplicate count;
- exact request/response/failure and scheduler-work links; and
- `CONTIGUOUS`, `GAPPED`, or `UNKNOWN`.

The cutoff is resolved once before live capture. A signature above the cutoff
is provisional for a later cycle and cannot mutate the current cycle. Within
one slot, deterministic signature ordering is bytewise ascending for storage
and replay; the persisted boundary is the exact `(slot, signature)` tuple.

Backfill rules:

- query the Pump Program with explicit `finalized`, newest first;
- use the prior contiguous signature as the exclusive `until` boundary;
- use `before` for the second page;
- maximum two pages, maximum 16 signature rows per page;
- maximum 32 enumerated signature rows and maximum 16 transaction decodes;
- discard and report post-cutoff rows;
- stop when the prior boundary is reached, all in-range rows are inspected, or
  any page/decode/operation/deadline ceiling is reached;
- no ordinary retry, third page, page-size expansion, archival fallback, or
  endpoint rotation.

Continuity meanings:

- `CONTIGUOUS`: a known prior contiguous boundary was reached; every
  in-range Pump Program signature through the cutoff was enumerated; every row
  was reconciled; all possible supported-create rows were inspected within the
  16-transaction ceiling; and no missing, conflicting, failed, unsupported, or
  unavailable item remains.
- `GAPPED`: both sides of a missing/conflicting interval are known, or a page,
  decode, disconnect, failure, unsupported-version/instruction, ambiguity,
  fork/conflict, or maximum-backfill ceiling prevents complete inspection.
- `UNKNOWN`: no trusted prior boundary exists, history is pruned/unavailable,
  provider behavior cannot distinguish absence from unavailability, or the
  exact interval cannot be bounded.

`GAPPED` and `UNKNOWN` allow exact individually finalized observations to
remain factual rows, but they forbid a completeness claim and cursor advance
past the last proven contiguous boundary.

## Disconnect, Duplicate, Fork, and History Rules

- One live session is allowed for at most 10 seconds to connect and 30 seconds
  to capture.
- Disconnect marks the work item failed. There is no same-cycle reconnect.
- Planned backfill still runs from the unchanged contiguous cursor to the
  immutable cutoff, subject to all ceilings.
- The next scheduled cycle may start new work only after its own planned
  backfill. It is not a retry or resume.
- Duplicate signatures are normalized once. Identical replay is idempotent;
  conflicting replay is a gap and first-fault evidence is preserved.
- Provisional observations that disappear, move slot, fail finalization, or
  conflict with finalized history are fork/conflict evidence. They never
  establish origin and never rewind or advance the finalized cursor.
- A finalized conflict is fail-closed even though finalized is expected to be
  stable. No local fork-choice inference is permitted.
- Empty pages, null transactions, pruned history, minimum-ledger boundaries,
  provider errors, or exhausted ceilings cannot prove no launch occurred.
- The maximum-backfill rule is absolute. Exceeding it yields `GAPPED` or
  `UNKNOWN`; it never authorizes more calls.

## Ceilings

The 7B.2 ceilings remain maximums, never targets:

- governed direct-lane requests: 35 per cycle
  (`1 + 2 + 16 + 8 + 8`);
- governed calls across all combined-intake providers: 45 per cycle;
- underlying direct-lane RPC/WebSocket operations: at most 45 per cycle;
- direct subscription envelope: at most one `getSlot`, one `logsSubscribe`,
  and one `logsUnsubscribe` operation;
- signature pages: 2 direct plus at most 8 secondary-mint lookups;
- transaction reads: 16 direct plus at most 8 secondary-origin reads;
- ordinary source retries: 0;
- ordinary scheduler retries: 0;
- per HTTP operation: 10 seconds;
- live capture: 30 seconds after the 10-second connection bound;
- raw payload: 1 MiB per response;
- intake wall clock and campaign-wide budgets remain those frozen by 7B.2 and
  7A.

If transport setup, cleanup, a provider requirement, or exact operation
accounting would exceed a ceiling, work stops before the excess operation.
Unused budget cannot become retries, more history, more candidates, or another
provider call.

## Authority Boundaries and Explicit Unknowns

This contract can establish only that a successful finalized supported Pump
`create` transaction for an exact mint was observed within bounded coverage.
It does not establish:

- complete Pump.fun creation coverage when continuity is not `CONTIGUOUS`;
- support for `create_v2`, future instructions, or transaction version > 0;
- that the pinned public IDL exactly matches every historical or future
  deployed program version;
- fixed public-RPC retention, archival availability, SLA, or stable limits;
- creator control, identity, authenticity, coordination, ownership, or intent;
- token legitimacy, safety, liquidity, tradeability, migration, market
  quality, selection eligibility, continuation value, or profitability;
- retrieval fitness or any paper/financial action.

The repository's open upstream report that `pump.json` may lag deployment is an
explicit freshness risk, not alternate authority. A later implementation/live
proof must revalidate the pinned bytes and deployed behavior without silently
expanding this contract. Until then, `create_v2` coverage and deployed-IDL
equivalence remain `UNKNOWN_REQUIRES_RESEARCH`.

## Money-Usefulness

Finalized, exact-mint Pump origin evidence prevents provider labels, failed
transactions, wrong programs, ambiguous decodes, and incomplete history from
becoming fake launch facts. Honest gaps reduce candidate yield but protect the
future memory corpus from false age, false provenance, and selection bias.
This improves later paper-learning inputs only; it does not predict or unlock
profit.

## Remaining Locks

Production decoder/adapter code, subscription, RPC calls, live proof, source
fetching, schema/database changes, cursor persistence, campaign wiring,
runtime, migration, combined execution, V2-9.7D closeout, pilot, memory
generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, PnL, wallets, private keys, signing, funds, paid APIs, scoring, ranking,
confidence, weighting, embeddings, vectors, and live execution remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- `create_v2` is present in the official pinned IDL but intentionally
  unsupported, so current launch coverage can be incomplete.
- An official repository issue reports potential deployed/IDL drift; no live
  program equivalence proof belongs to this adoption lane.
- The Pump Program is busy. Two 16-row pages and 16 transaction reads can gap
  quickly, but bounds must not expand silently.
- Public RPC history can be unavailable or pruned; empty/null is not absence.
- Version-0 address lookup resolution and Anchor CPI events add parser
  complexity to the later implementation.
- Requiring non-null transaction block time sacrifices yield rather than
  inventing creation time or adding an unadopted fallback call.
- A single governed subscription envelope contains multiple underlying
  operations, so later accounting must prove both ceilings independently.
- Honest fork, conflict, disconnect, and duplicate handling requires durable
  first-fault/cursor evidence that is not implemented here.

## Stop Boundary

V2-9.7D.7B.3A ends at this adopted document and its contract fixtures. No
adapter, decoder implementation, subscription, RPC proof, secondary-provider
adoption, persistent change, V2-9.7D closeout, or pilot begins.
