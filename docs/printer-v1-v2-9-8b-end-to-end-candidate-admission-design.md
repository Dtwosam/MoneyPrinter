# Printer V1 V2-9.8B End-to-End Candidate Admission Design

Date: 2026-07-29

Lane: `V2-9.8B End-to-End Candidate Admission Audit, Repair, and Final Live N2 Proof`

Design status: complete

## Objective

Repair every confirmed admission defect as one bounded, runtime-neutral change
so one evidence chain preserves:

```text
candidate mint
↔ canonical current pool or exact active Pump bonding curve
↔ pool program and distinct account role
↔ exact base mint
↔ exact quote mint
↔ provider market pair
↔ holder/liquidity/tradeability facts
↔ foundation candidate identity and certificate
```

No value in that chain may be guessed from a symbol, venue label, default quote,
candidate key, or adjacent batch response.

## Invariants

- Solana-only and Solana-memecoin-only.
- Paper-only; no wallet, signing, transaction, funds, or execution capability.
- No score, rank, confidence, weight, source preference, or quota.
- Source Governor owns each source operation; Central Scheduler owns each job.
- The foundation remains the only certificate, reserve, selection, and manifest
  owner.
- Active runtime capacity remains exactly two.
- `M=2N` and all N2/N7 policy ceilings remain unchanged.
- Cursor namespace, direction, head, cohort, mint, tracking/cooldown, safety,
  and protected-table rules remain unchanged.
- Missing, conflicting, malformed, unsupported, or stale evidence fails closed.
- No schema or migration is introduced.

## Provider identity preservation

DexScreener normalization stores exact provider base mint, quote mint, DEX ID,
and pair address. The live owner binds each batch pair back to the explicitly
requested profile mint. If the requested candidate is on the quote side, the
candidate identity is retained and the exact orientation is marked failed; the
infrastructure base is not silently nominated as the candidate.

GeckoTerminal normalization stores exact base and quote relationships and the
DEX relationship requested by the pinned endpoint. Missing relationships remain
missing; no native quote is inserted.

Integration observations carry candidate mint, pair, base, quote, venue, market
freshness/age, liquidity, and tradeability exactly as normalized. Provider venue
is diagnostic only and never proves an on-chain program.

## Exact pool target association

The pool source operation constructs target contexts from the bounded cohort:

1. aggregator current pair;
2. Pump bonding curve only for an originated mint without an observed
   migration; and
3. exact Pump migration pool.

For a migrated mint, the historical bonding curve remains lineage evidence and
does not compete with the current PumpSwap Pool identity.

The account batch is associated by the Solana RPC positional contract in live
responses. Address-bearing fixtures are associated by exact response address.
Every observation records target, response slot, response address when present,
and association mode. Missing, duplicate, reordered, or mismatched evidence is
categorical and cannot slide to an adjacent target.

## Distinct pool-role branches

### Pump bonding curve

The branch requires:

- exact pinned Pump creation evidence;
- exact PDA derived from `["bonding-curve", candidate_mint]`;
- exact Pump program owner;
- complete pinned BondingCurve prefix and discriminator;
- exact quote mint decoded from the account; and
- `complete == false`.

It emits role `PUMP_BONDING_CURVE`, never `AMM_POOL`. A completed curve cannot
pass this branch and requires exact graduation evidence.

### Graduated PumpSwap Pool

The branch requires the existing pinned Pump migration transaction, canonical
PumpSwap Pool PDA/index, exact PumpSwap account owner/layout, exact base mint,
exact allowed quote mint, exact vault relationships, and exact origin/migration
contract pins. It emits `PUMPSWAP_AMM_POOL` and
`PUMP_GRADUATION_CONFIRMED`.

### Generic non-Pump current pool

The branch requires:

- an exact aggregator pair and provider base/quote orientation;
- candidate mint on the base side;
- an allowed exact quote mint;
- exact current pool account presence;
- exact on-chain pool account owner; and
- exact RPC evidence that the owner account is executable.

The provider DEX label is retained only as a label. It is not converted into a
program ID. The branch emits `GENERIC_AMM_POOL` and
`NON_PUMP_POOL_CONFIRMED`. This supports approved non-Pump and unknown-origin
candidates without asserting unsupported Pump lineage.

An exact owner with a missing/non-executable program account, an unsupported
Pump/PumpSwap role, reversed orientation, missing quote, or account-target
mismatch fails categorically.

The executable-owner lookup is a second low-level RPC call inside the existing
single Source-Governed pool operation. Both low-level calls are measured in
transport accounting. No governed-request or policy ceiling is raised.

## Identity merge and failure precedence

Pool, base, quote, and pool-program merge uses only observations linked to an
exact pool address. Mint, holder, and safety observations cannot invent or
conflict pool orientation through convenience fields.

`IDENTITY_AVAILABLE` means a non-conflicting candidate/pool/base relationship
and supported token program exist. `POOL_QUOTE_VALID` separately proves role,
program, base orientation, and allowed quote. This separation lets missing
quote, wrong role/program, reversal, and target mismatch survive as their first
precise causes.

Failure precedence is:

1. source contract/provider/budget/coverage failure;
2. exact mint target/layout/program failure;
3. true identity conflict;
4. earliest candidate funnel rejection; and
5. honest complete-coverage shortage.

Only genuine cross-observation identity conflicts use
`IDENTITY_MERGE_FAILURE`. Missing mandatory evidence uses
`STALE_OR_INCOMPLETE_EVIDENCE`; precise categorical market outcomes remain
`ADMISSION_FAILURE` with the first exact reason where uniform.

## Sequential identity persistence

Observation content hashes remain evidence-content hashes. Observation primary
keys additionally bind the execution ID, preventing distinct sequential
executions from colliding while preserving deterministic replay within the same
execution. This is compatible with migration 049 and needs no schema change.

## Offline proof design

All proofs use public CLI paths, frozen low-level HTTP/RPC transports, and fresh
disposable databases migrated through 049.

Positive proof:

- N2 from a four-candidate cohort: at least two admitted certificates, exact
  two-item manifest, projection two, handoff zero;
- N7 from seven candidates: seven admitted certificates, exact seven-item
  runtime-neutral manifest, projection zero, legacy projection rejection;
- Pump bonding curve, graduated PumpSwap, generic non-Pump, and allowed
  unknown-origin roles;
- classic SPL Token and Token-2022 mints;
- DexScreener/GeckoTerminal/direct-Pump overlap;
- first `FORWARD` bootstrap and sequential established-head execution;
- deterministic report replay without transport calls;
- exact Scheduler, Governor, transport, lease, residue, integrity, foreign-key,
  and protected-table reconciliation.

Negative proof mutates one low-level fact at a time and asserts the first
persisted failure for missing quote, wrong role/program, base/quote reversal,
pool-target mismatch, holder concentration, liquidity, tradeability,
unsupported lineage, stale evidence, active tracking/cooldown, and
malformed/incomplete source or account evidence.

## Live gate

Only after focused, regression, compilation, migration-compatibility, diff, and
broad affected tests pass may the authoritative DB and fresh backup be verified.
The authorized N2 command may then run exactly once. It is terminal evidence:
no code patch, retry, N7, successor, cursor reset, or campaign follows it.
