# Printer V1 V2-9.7D.7B.3A Direct Pump Contract Adoption Closeout

## Verdict

`V2_9_7D_7B_3A_DIRECT_PUMP_CONTRACT_ADOPTION_PASS`

PASS means the official direct Pump Program creation-discovery contract is
pinned, bounded, fail-closed, and fixture-proven for later implementation. It
does not mean a decoder, adapter, subscription, RPC path, cursor, campaign,
database write, or runtime is implemented or activated.

## Todo / Checklist

- [x] Verify exact starting commit and preserve unrelated worktree artifacts.
- [x] Audit the active source stack and 7B.2 design.
- [x] Pin official Pump repository, IDL bytes, program, instruction, and event.
- [x] Adopt extraction, finality, failure, continuity, governance, and ceilings.
- [x] Add focused contract fixtures and parser checks.
- [x] Run the bounded verification and preserve every downstream lock.

## Scope and Baseline

- Starting HEAD:
  `a31f1d3eec66f528bbb9794a96438e57b3574977`
- Starting tracked tree: clean
- Existing unrelated untracked data, operator runs, and lane output artifacts:
  observed and untouched
- Lane work: documentation, one synthetic contract fixture, and one
  fixture-only parser test
- Network use: official documentation/repository research only
- Solana RPC calls, endpoint probes, subscriptions, source fetching, runtime,
  and database commands: none

## Adopted Authority

Official Pump authority accessed 2026-07-19:

- `https://github.com/pump-fun/pump-public-docs`
- exact commit:
  `9c82f61cb711b044a17f770ab8ce9f9bdf78f333`
- exact `idl/pump.json` SHA-256:
  `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49`
- official Pump Program:
  `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`
- official Pump Program README and coin-creation documentation at the same
  repository

Official Solana authority accessed 2026-07-19:

- `https://solana.com/docs/rpc/http/getslot`
- `https://solana.com/docs/rpc/http/getsignaturesforaddress`
- `https://solana.com/docs/rpc/http/gettransaction`
- `https://solana.com/docs/rpc/websocket/logssubscribe`
- official confirmed-transaction and versioned-message JSON structures

Repository authority:

- active Printer V1 source stack and assistant anchor
- `printer-v1-v2-9-7d-7b-2-combined-pumpfun-discovery-selection-design.md`
- Solana builder source-of-truth RPC, transaction parsing, Pump protocol, and
  Source Governor evidence documents

Official Pump/Solana facts control upstream shapes. Printer sources control
stricter permission, ownership, evidence, budget, stop, and capability locks.

## Adoption Result

The adopted contract pins:

- the official Pump Program, repository commit, and exact IDL hash;
- the supported `create` discriminator, four Borsh arguments, and 14-account
  order;
- the exact 17-field pinned `CreateEvent` layout and optional Anchor CPI event
  wrapper;
- legacy and version-0 transaction envelopes only;
- exact mint, bonding curve, associated bonding curve, creator, signature,
  slot, block-time, and program extraction;
- explicit finalized successful transaction requirements;
- failed, null, unavailable, malformed, wrong-program, ambiguous,
  unsupported-version/instruction, signature/slot mismatch, event mismatch,
  mint mismatch, and conflicting-duplicate outcomes;
- five design-frozen `solana_rpc` Source Governor request kinds and the
  `DISCOVERY_PUMPFUN_LATEST` Central Scheduler owner;
- immutable finalized cutoff, tuple cursor, deterministic same-slot ordering,
  duplicate behavior, zero-reconnect disconnect behavior, and next-cycle
  ownership;
- two pages of at most 16 signatures each, at most 16 direct transaction reads,
  and no unbounded/archival/provider fallback;
- exact `CONTIGUOUS`, `GAPPED`, and `UNKNOWN` meanings;
- fork/conflict, pruned/unavailable history, maximum-backfill, and cursor
  non-advancement rules;
- separate governed-request and underlying-operation accounting under the
  existing 35 direct-request, 45 combined-call, and 45 underlying direct-RPC
  ceilings; and
- authority limits and explicit unknowns.

The official pinned IDL also defines `create_v2`. It is deliberately
unsupported here because the requested lane adopts the exact `create` contract
and no implementation/live evidence can safely establish equivalence.
`create_v2` therefore creates a visible gap and no Pump-origin claim until a
later explicit adoption.

Creator is preserved only as the fourth observed `create` argument. The
contract explicitly forbids inferences about wallet control, coordination,
insider status, authenticity, beneficial ownership, identity, or intent.

## Blockers

No blocker prevents this documentation/fixture adoption.

The following block implementation or completeness claims, as intended:

- `create_v2` and any later instruction are not adopted.
- Official deployed-program equivalence to every pinned IDL layout was not
  live-proven in this lane.
- Public RPC retention, archival availability, SLA, and stable limits are not
  guaranteed.
- A two-page/16-transaction ceiling can leave busy Pump history gapped.
- Durable cursor, first-fault, underlying-operation, and byte accounting do not
  yet exist for this path.
- No decoder or address-derivation validation exists in production code.

These are honest later-lane dependencies, not reasons to invent behavior or
block a fail-closed contract adoption.

## Money-Usefulness

The contract makes Pump origin depend on one exact successful finalized
on-chain creation for the exact mint. It prevents provider category labels,
failed transactions, creator/user confusion, wrong programs, incomplete
history, duplicate conflicts, and unsupported creation variants from becoming
clean launch facts. Lower candidate yield is acceptable because it protects
future memory from false age/provenance and therefore reduces fake paper-profit
risk.

This contribution is factual intake quality only. It does not predict profit,
rank tokens, authorize selection, or unlock any action.

## Proof

| Check | Result |
|---|---|
| Exact starting commit and clean tracked baseline | PASS |
| Official repository commit resolved and recorded | PASS |
| Raw pinned IDL SHA-256 recomputed | PASS |
| Program ID matched official IDL | PASS |
| `create` discriminator/account/argument order matched official IDL | PASS |
| `CreateEvent` discriminator/field order matched official IDL | PASS |
| Synthetic raw Borsh instruction extracted all adopted fields | PASS |
| Synthetic current event consumed exact 17-field layout | PASS |
| Failed/wrong-program/unsupported-version/malformed-account mutations rejected | PASS |
| Source Governor/Central Scheduler ownership and bypass scan | PASS |
| `git diff --check` | PASS |
| `git diff --stat` / lane-file scope review | PASS |

Focused fixture result:

`3 passed`

The pytest cache warning was environmental: the runner could not write its
cache path. It did not change the test result or lane files.

## Files Changed

- `docs/solana-builder-source-of-truth/pump-fun-direct-creation-discovery-contract.md`
- `tests/fixtures/pumpfun_direct_create_contract.json`
- `tests/test_pumpfun_direct_create_contract_fixture.py`
- `docs/printer-v1-v2-9-7d-7b-3a-direct-pump-contract-adoption-closeout.md`

## What Was Built

- Adopted official direct Pump `create` discovery contract.
- Synthetic immutable instruction/event contract fixture.
- Fixture-only reference parsing and fail-closed checks.
- Lane-specific adoption closeout.

## What Was Not Touched

- Production source adapters or parsers
- WebSocket subscriptions or RPC calls
- Source Governor and Scheduler production code/registries
- schemas, migrations, databases, cursors, campaigns, or persistent targets
- secondary-provider contracts
- runtime, operational commands, memory creation, retrieval, or financial
  capabilities
- unrelated tracked or untracked files

## Tests / Checks Run

- Static pinned-IDL/fixture consistency script
- `python -m pytest tests/test_pumpfun_direct_create_contract_fixture.py -q`
- focused Source Governor/Scheduler bypass scan
- `git diff --check`
- `git diff --stat`

No broader test suite was run because the lane is documentation/fixture-only
and the minimum verification policy requires static and focused checks.

## Remaining Locks

Decoder implementation, production adapter, subscription, RPC proof,
secondary-provider adoption, schema/database mutation, cursor persistence,
campaign wiring, combined execution, operational runtime, persistent
migration, V2-9.7D closeout, pilot, memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets,
private keys, signing, real funds, paid APIs, scoring, ranking, confidence,
weighted logic, embeddings, vectors, and live execution remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Current official `create_v2` is outside this adopted `create` contract and
  can reduce launch coverage.
- An open official-repository report alleges IDL/deployment freshness drift;
  later implementation/live proof must revalidate without expanding authority.
- Busy program history can exceed two pages or 16 decodes quickly.
- Public nodes may prune history or return null block time; neither proves
  absence.
- Version-0 loaded addresses, inner instructions, PDA/ATA verification, and
  Anchor event parsing make the future decoder non-trivial.
- The subscription request is one governed envelope but multiple underlying
  operations; both budgets must be enforced and reported.
- Zero reconnect/retry and strict maximum backfill preserve safety but can
  create `GAPPED`/`UNKNOWN` cycles.
- Creator evidence is useful provenance but cannot safely answer control,
  authenticity, identity, coordination, or intent.

## Next Recommended Phase

`V2-9.7D.7B.3B — Secondary contract adoption`, only when explicitly requested.
Do not begin it from this lane.

## Final Lane Result

`V2_9_7D_7B_3A_DIRECT_PUMP_CONTRACT_ADOPTION_PASS`

Stop after the PASS-only lane commit. Do not tag and do not begin decoder
implementation, subscriptions, live RPC proof, secondary-provider adoption,
V2-9.7D closeout, or the pilot.
