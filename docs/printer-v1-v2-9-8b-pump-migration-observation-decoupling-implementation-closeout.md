# Printer V1 V2-9.8B Pump Migration Observation Decoupling Implementation Closeout

Date: 2026-07-29

Starting HEAD: `a7e3ea29bf4163786f6bc2856b27bea31b119c65`

Required authoritative DB SHA-256:
`36cf157b74a28fe93695f7c29ffee143a3d7ed6453bdcec5ad74ea666284fa09`

Lane:
`V2-9.8B Pump Migration Observation Decoupling Implementation and Offline Proof`

## Verdict

`V2_9_8B_PUMP_MIGRATION_OBSERVATION_DECOUPLING_IMPLEMENTATION_PASS`

The approved minimum implementation is complete and proved entirely offline.
No live provider, RPC, WebSocket, recovery, N2, N7, campaign, tracking,
lifecycle, snapshot, window, or memory execution ran.

This PASS authorizes only a separately explicit future bounded live N2 proof.
It does not run or automatically authorize that proof, a retry, N7, a
successor, or the operational campaign.

## Source-grounded classification

The Python Builder investigation classified the blocker as
`MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`.

The existing global Pump migration work was required and its cursor evidence
leaked into unrelated pool work. The committed audit and design established
that the global channel is valid optional coverage but is not universal
candidate-admission authority. The implementation follows that approved
boundary without inventing a new source, contract, recovery rule, or financial
capability.

## Schema decision

Migrations 048 and 049 safely represent:

- compact page summaries and hashes in existing observation facts;
- exact governed request, response, failure, work, and transport-operation
  links;
- exact positive Pump migration and PumpSwap Pool evidence;
- immutable locator identity and cutoff;
- terminal integration reports; and
- deterministic zero-source replay.

A disposable database migrated through 049 reported:

```text
latest migration: 049_candidate_acquisition_integration.sql
SQLite: 3.53.4
threadsafety: 3
integrity_check: ok
foreign_key_check rows: 0
```

No migration 050, schema change, or authoritative-database change was needed.

## Confirmed implementation scope

1. Program-wide Pump migration signature pages and transactions are optional
   `GLOBAL_OPTIONAL` work with `required=false`.
2. Optional global failure and cursor continuity never enter universal required
   failures.
3. Global cursor evidence is detached from candidate mint, current-pool,
   holder, and other unrelated observations.
4. Existing cursor/recovery rows and their rules are unchanged. No reset,
   rewind, checkpoint adoption, recovery-bound increase, or fabricated
   continuity was added.
5. Pure cohort-level branch classification now yields:
   `PUMP_GRADUATION_CLAIMED`, `PUMP_ACTIVE_BONDING_CURVE`,
   `NO_PUMP_GRADUATION_CLAIM`, or the precise
   `PUMP_LINEAGE_CONFLICT`.
6. Candidate migration planning chooses exactly one most-specific predeclared
   locator in this order: migration signature, PumpSwap Pool, verified bonding
   curve, candidate mint. It does not fall back after failure.
7. Pump graduation requires one successful finalized pinned Pump `migrate`
   transaction and one exact pinned PumpSwap Pool verification joined to the
   same mint, curve, Pool, and creator.
8. Active Pump curves perform no migration work.
9. Generic, independently non-Pump, and unknown-origin exact-present-pool
   branches do not depend on global Pump migration continuity.
10. A failed explicit Pump claim remains unsupported/conflicting Pump lineage;
    it cannot downgrade to generic or unknown origin.
11. PumpSwap presence without the exact joined `migrate` transaction never
    produces graduation.
12. Three exact Source Governor request kinds and corresponding Central
    Scheduler-owned work were added under the canonical acquisition owner. No
    runner, adapter-owned loop, or bypass was added.

## Final branch-specific evidence contracts

### `PUMP_GRADUATION_CLAIMED`

The candidate must pass all of:

- exact Pump origin;
- an exact predeclared candidate locator;
- finalized successful `getTransaction` evidence;
- supported legacy/version-0 transaction parsing;
- exactly one pinned Pump `migrate` discriminator;
- exact 25-account layout;
- exact candidate mint at account 2;
- exact bonding curve at account 3;
- exact PumpSwap Pool at account 9;
- exact creator at account 10;
- every pinned fixed program/account identity; and
- strict PumpSwap owner, layout, base mint, WSOL quote, creator, index, PDA, LP
  mint, and vault verification.

Any missing, mismatched, ambiguous, failed, unsupported, pruned, malformed, or
over-budget component rejects this branch without fallback.

### `PUMP_ACTIVE_BONDING_CURVE`

Exact Pump origin, derived curve identity, supported account layout, and
`complete=false` are sufficient for the existing
`PUMP_ORIGIN_CONFIRMED` branch. No migration lookup or global observer
continuity is required.

### `NO_PUMP_GRADUATION_CLAIM`

Exact current-pool/pair orientation, candidate mint, supported quote, account
owner, executable owner program, and the existing market/safety/liquidity/
tradeability gates apply.

An independently known non-Pump candidate may be
`NON_PUMP_POOL_CONFIRMED`; otherwise origin remains `UNKNOWN_ORIGIN`. Neither
classification asserts Pump absence or graduation.

## Optional global observer and historical gap

The global Pump-program observer remains optional coverage and diagnostic/audit
evidence. It has `admission_authority=NONE`, never substitutes for
candidate-specific proof, and never blocks unrelated candidate branches.

When enabled, it retains governed bounded cursor behavior and may nominate an
exact positive locator. That locator must enter the same candidate verifier
before a Pump graduation claim is possible. When disabled, its exact state is
`GLOBAL_PUMP_OBSERVER_NOT_RUN`.

The existing unresolved history remains represented as:

```text
observer status: OPTIONAL_OBSERVER_GAPPED
authoritative head slot: 435985595
frozen tip slot: 435999023
last recovery continuation slot: 435998983
signatures inspected: 11000
pages inspected: 44
prior boundary reached: false
recovery result: CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED
admission authority: NONE
```

This is report interpretation of preserved evidence. It is not a cursor
mutation, reset, fabricated checkpoint, or permission for more recovery.

## Failure categories

The implementation preserves precise categorical failures for:

- `CANDIDATE_MIGRATION_NOT_FOUND_WITHIN_BOUND`;
- `CANDIDATE_MIGRATION_HISTORY_UNAVAILABLE`;
- `CANDIDATE_MIGRATION_TRANSACTION_NULL_OR_PRUNED`;
- `CANDIDATE_MIGRATION_PROVIDER_UNAVAILABLE`;
- `CANDIDATE_MIGRATION_PAGE_MALFORMED`;
- `CANDIDATE_MIGRATION_AMBIGUOUS`;
- unsupported transaction, instruction, account, or Pool contracts;
- `CANDIDATE_MIGRATION_PREDECLARED_BUDGET_EXHAUSTED`;
- Pump/non-Pump identity conflict; and
- one-field migration/Pool identity mismatch.

Provider unavailability, pruning, malformed history, or restart never creates
absence evidence. There is no automatic retry, reconnect, fallback locator,
restart, recovery, or successor.

## Storage and replay evidence

Durable payloads retain:

- locator kind, target, pins, decoder identity, and immutable finalized cutoff;
- requested/returned counts, first/last slots, and canonical page hash;
- only the exact positive matching signature;
- exact decoded migration identity and slot/time;
- exact Pool account hash and pinned contract hashes; and
- governed request/response/failure/work/operation lineage.

They do not retain full unrelated program-wide signature arrays in normalized
payloads, work JSON, or report JSON. A terminal report replays exactly with zero
new source or transport calls.

The existing global cursor and recovery evidence remains byte-identical in the
offline preservation proofs.

## Scheduler, Source Governor, and accounting

Every retrieval is a Central Scheduler `DISCOVERY_REFRESH` job and a Source
Governor request. The new exact request kinds are:

- `candidate_pump_migration_signature_lookup`;
- `candidate_pump_migration_transaction`; and
- `candidate_pumpswap_pool_verification`.

Underlying successful and failed transport attempts, bytes, rows, governed
responses/failures, work terminal states, leases, and final report totals
reconcile. Failed local parsing after a returned response remains one completed
transport operation plus a categorical evidence failure.

All existing overall N2/N7 ceilings, the Solana RPC 30-request-per-minute
contract, `M=2N`, and active runtime capacity two remain unchanged. The exact
new per-kind limits are subordinate caps inside those unchanged ceilings, not a
capacity or provider-budget increase.

## Required offline proof results

| Proof boundary | Result |
| --- | --- |
| generic `UNKNOWN_ORIGIN` under global gapped/unknown/unavailable/blocked/not-run | PASS |
| independently known `NON_PUMP_POOL_CONFIRMED` under the same outcomes | PASS |
| exact active Pump curve without migration work | PASS |
| exact graduation from signature/pool/curve/mint locators | PASS, all four |
| one-field transaction and Pool join mutations | PASS, all rejected |
| PumpSwap-presence-only graduation | PASS, remained non-graduation |
| failed explicit Pump claim downgrade | PASS, prohibited |
| precise negative/failure categories | PASS |
| optional global positive locator re-verification | PASS |
| optional global failures excluded from required failures | PASS |
| crash/restart/duplicate/continuation/replay boundaries | PASS |
| compact storage and cursor/recovery preservation | PASS |
| Scheduler/Governor/transport/lease/report reconciliation | PASS |
| protected runtime/financial table deltas | PASS, all zero |

## Live-shaped offline N2 and N7

The frozen public-command proofs used disposable migration-049 databases.

| Mode | Result |
| --- | --- |
| offline N2 | branch-mixed cohort admitted at least two certificates; exact two-item manifest; legacy projection 2; runtime handoff 0 |
| offline N7 | seven admitted certificates; exact seven-item runtime-neutral manifest; projection 0; legacy two-item adapter rejection; runtime handoff 0 |

Active runtime capacity remains exactly two. N7 is proof of runtime-neutral
foundation mechanics only; it is not a live N7 authorization.

## Tests and checks

| Check | Result |
| --- | --- |
| complete decoupling/integration suite | 108 passed |
| broad adjacent provider, Pump, PumpSwap, foundation, cursor, and registry suite | 281 passed |
| Python compilation of every changed Python module | PASS |
| disposable migration-049 compatibility | PASS; integrity `ok`; FK 0 |
| exact branch, locator, join, negative, replay, N2/N7 proof matrix | PASS |
| `git diff --check` | PASS |

The test boundaries overlap and are not summed as unique tests. No unrelated
full-repository suite was run. An exploratory broader adapter-boundary check
encountered the pre-existing untouched
`test_phase23_source_adapter_execution_contract.py` import restriction in
`direct_migration_discovery.py`; that file has no lane diff and the failure is
outside this approved scope.

## Money-usefulness contribution

Printer can now admit truthful exact-present-pool candidates even when optional
program-wide Pump history is incomplete, while claimed Pump graduations remain
strictly tied to exact migration and Pool identity. This removes an unrelated
high-volume coverage bottleneck without manufacturing lineage, quote identity,
or profit. Compact evidence also prevents repeated raw program-history growth
from displacing useful candidate evidence.

No memory, retrieval, decision, position, trade, audit, PnL, or profit
capability was created.

## What remains locked

- live provider, RPC, WebSocket, recovery, N2, N7, and campaign execution;
- active runtime capacity above two;
- cursor reset, checkpoint adoption, recovery-bound increases, and source
  ceiling increases;
- tracking, lifecycle, snapshots, windows, memory creation, and continuation;
- retrieval and dirty/partial evidence use;
- paper decisions, BUY, SELL, HOLD, positions, trades, audits, and PnL;
- wallets, keys, signing, transaction submission, real funds, and live
  execution;
- paid sources;
- score, rank, confidence, weighting, quota, embedding, and vector logic; and
- Source Governor or Central Scheduler bypass.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Existing global Pump history is still gapped. Optional status prevents false
   universal blockage but does not improve coverage or prove absence.
2. Candidate histories may be pruned, unavailable, malformed, or longer than
   the fixed bound. Claimed Pump graduation then blocks honestly.
3. Under the unchanged Solana request ceiling, the canonical live-shaped plan
   predeclares one candidate migration verification slot. Additional claimed
   Pump graduations in the same cohort fail
   `CANDIDATE_MIGRATION_PREDECLARED_BUDGET_EXHAUSTED`; no quota, preference, or
   hidden fallback selects them.
4. An optional global locator may improve discovery but has no admission value
   until the exact candidate transaction and Pool join pass.
5. Frozen fixtures prove contracts, accounting, persistence, and branch
   independence only. Live provider availability and candidate yield remain
   unproven.
6. The untouched Phase 23 adapter import restriction remains an unrelated
   baseline issue and was not weakened or repaired.

## Exact next permitted task

Only this task is permitted next, and only under separate explicit operator
authorization:

```text
V2-9.8B bounded live N2 Pump migration observation decoupling proof
```

It must start from the clean committed implementation checkpoint, re-pin all
provider and program contracts required by that future lane, preserve the
authoritative DB preflight/hash rules, and remain N2 only. No automatic run,
retry, recovery, N7, campaign, or later runtime lane is authorized.
