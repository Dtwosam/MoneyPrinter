# Printer V1 V2-9.8B Restored Factory Source Compatibility Correctness Repair Closeout

Date: 2026-07-30

Lane: `V2-9.8B Restored Factory Source Compatibility Correctness Repair`

Verdict:
`V2_9_8B_RESTORED_FACTORY_SOURCE_COMPATIBILITY_CORRECTNESS_REPAIR_BLOCKED`

## Outcome

The lane stopped at its mandatory preimplementation operation-budget gate.
Exact measured-operation planning proves that the current active source breadth
cannot fit the unchanged 45-operation ceiling.

No partial correctness repair was applied. No runtime, test, active-authority
document, migration or database file was changed. No provider, RPC, WebSocket,
live source probe, Memory Factory, N2, N7, recovery, tracking, snapshot, window
or memory operation ran.

## Baseline

- Branch: `master`
- HEAD:
  `da9ad61a0be696e1ddae7e19c83649360d49f832`
- Direct parent:
  `e54ce92aef59d0c9edd2266f69e3572d4b084c97`
- Initial tracked worktree: clean
- Authoritative database SHA-256:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`

## Exact blocker

Solana permits as many as 256 accounts per transaction, while
`getMultipleAccounts` accepts at most 100 addresses. The active PumpSwap
verifier therefore has a legitimate worst case of one transaction lookup plus
three account batches per candidate.

The current active direct plan permits:

```text
1 signature page
+ 12 finalized transaction lookups
+ 5 * (1 PumpSwap transaction + 3 account batches)
= 33 real transport operations
```

Adding Printer's unchanged nine zero-transport validations and six snapshot
reservations produces 48 operations against the ceiling of 45, an overage of
three before DexScreener, holder evidence or lifecycle work.

The complete current legitimate worst case is 71:

```text
33 direct Pump/PumpSwap
+ 2 DexScreener fresh-profile HTTP calls
+ 11 exact-pair HTTP calls permitted by current request-count supply budgeting
+ 9 zero-transport validations
+ 6 snapshot reservations
+ 10 holder operations for two candidates
= 71
```

The unchanged ceiling is 45, so the full overage is 26.

The lane explicitly required BLOCKED when the legitimate worst-case active path
could not fit and prohibited raising a ceiling. That condition fired before
implementation.

## Five discrepancy dispositions

All five operator-review findings remain confirmed and unresolved because the
lane prohibited splitting or partially applying the cohesive repair:

1. **Measured accounting:** request totals and hardcoded PumpSwap/DexScreener
   operation totals do not represent exact real transport identities.
2. **Pump account roles:** the 25-account count plus selected position checks do
   not validate the complete pinned ordered role contract.
3. **Solana endpoint owner:** ordinary holder evidence can independently use the
   module fallback rather than the single resolved runtime/preflight endpoint.
4. **Typed capability enforcement:** the profile schema and partial text scan do
   not cover every prohibited capability and every serialized active field.
5. **Active documentation:** current-authority sections still describe
   PumpPortal as active and direct Pump/PumpSwap as deferred.

The legacy Solana-host test also remains correctly classified as intersecting
this reset. It was not modified because partial implementation was prohibited.
The unrelated holder-report wording and GoPlus forbidden-term debts remain
untouched.

## Measured operation-accounting model

The required future model remains:

```text
predeclared worst-case operation identities
-> actual attempted identities
-> durable operation evidence
-> campaign ledger
-> terminal report
-> zero-source replay
```

Each identity must include source, governed request, method/endpoint kind,
ordinal and target category. Failed calls must retain bytes, rows and
categorical cause. Parsing and validation contribute zero transport operations.
Duplicate, undeclared or over-ceiling operations must stop universally before
lifecycle continuation.

That model was designed but not implemented because its truthful predeclared
plan fails the unchanged-ceiling gate.

## Complete migration-account role contract

The pinned IDL's 25 roles were enumerated in the lane design, including Global
and withdraw-authority relations, candidate mint/bonding-curve and associated
accounts, user signer, fixed programs, canonical PumpSwap pool/authority/config,
LP mint and user LP account, base/quote vaults, both event authorities, Pump
program and Rent sysvar.

The code remains unchanged. A later approved design must prove every fixed
identity, PDA/ATA relationship, relation, signer/writable contract and permitted
alias without inventing constraints.

## Endpoint ownership path

The intended future path is one shared resolution of
`PRINTER_SOLANA_RPC_URL`, followed by injection of the exact immutable resolved
contract into every active Solana consumer and the preflight. The existing
fallback, HTTPS validation and redaction contract remains unchanged; the holder
runtime parity defect remains open.

## Prohibited-capability schema

The required explicit future fields remain wallet, private key, signing,
funding, paid dependency, metered account/trade stream, transaction submission,
execution endpoint, credential requirement and allowed credential category.
Recursive serialized-profile inspection remains required. No schema change was
made in this BLOCKED lane.

## Documentation corrections

No active-authority section was partially rewritten. The assistant anchor and
Clean Master Spec conflict remains visible and must be corrected only with a
complete later implementation. Historical PumpPortal and candidate-acquisition
material remains preserved.

## Proof and checks

Performed:

- exact branch, HEAD and clean-tree preflight;
- authoritative database SHA-256 verification;
- active source-stack and Python Builder Guide review;
- reset design/closeout and prior BLOCKED readiness review;
- pinned Pump/PumpSwap, Solana RPC, DexScreener, Jupiter and Source Governor
  contract review;
- direct call-path and canonical-owner inspection;
- exact operation-plan arithmetic;
- immutable authoritative inventory count supporting the legitimate multi-round
  path;
- documentation-only diff and whitespace checks.

Not run because the preimplementation gate blocked implementation:

- focused Python tests;
- disposable migration-049 proof;
- broad affected operational suite;
- live or provider checks.

Running implementation tests after the design gate failed would not make the
active plan fit and would misrepresent the required cohesive proof.

## Files changed

- `docs/printer-v1-v2-9-8b-restored-factory-source-compatibility-correctness-repair-design.md`
- `docs/printer-v1-v2-9-8b-restored-factory-source-compatibility-correctness-repair-closeout.md`

No runtime, test, active source-of-truth, schema, migration or database file
changed.

## Money-usefulness contribution

The BLOCKED result prevents a false readiness claim. Accurate operation
planning protects bounded free-source capacity and avoids starting a two-token
paper-memory lifecycle whose mandatory evidence budget cannot be completed.
It creates no profit, decision, position, trade or PnL capability.

## What remains locked

- bounded live source-contract probe;
- Memory Factory campaign;
- provider/RPC/WebSocket execution;
- N2, N7, cursor, recovery, backfill and candidate-acquisition authority;
- tracking, snapshots, windows and memory creation;
- retrieval;
- BUY, SELL, HOLD and paper decisions;
- positions, trade events, audits and PnL;
- wallets, private keys, signing, funds and live execution;
- paid APIs, scoring, ranking, confidence, weighting, embeddings and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- The complete source plan exceeds the unchanged ceiling before lifecycle.
- Variable Solana account batching cannot be honestly collapsed to one assumed
  operation.
- Reducing source depth or evidence breadth would be a separate behavioral
  design decision and may increase safe-stops or reduce candidate coverage.
- Raising the ceiling is expressly prohibited by this lane.
- Partial repairs would leave runtime, preflight, active documentation and
  baseline-test disposition inconsistent.

## Commit and next task

No commit was created because only PASS authorized the requested commit.

The exact next permitted task is operator review of this blocker and its
arithmetic only. No blocker repair, revised ceiling/source-breadth design,
bounded live source-contract probe or Memory Factory campaign is authorized by
this closeout.

