# Printer V1 Real T3 Token-Age Evidence Closeout

Status: `REAL_T3_TOKEN_AGE_PASS`

Date: 2026-07-12

Scope: real T3 token-age evidence only. A3, A4, and GROUP_A were not started.

## Source Stack

This lane used `AGENTS.md`, the Clean Master Spec, Post-RC Build Order, Memory
Factory Guide, current-state memory-growth audit, active V2 memory-growth build
order, and the Solana Builder source-of-truth modules for core RPC, transaction
parsing, SPL Token, Token-2022, PumpPortal, Pump.fun, token-age tiers, and Source
Governor evidence.

## Audit Finding

The existing T3 path already provided bounded read-only RPC transport, mint-state
validation, corrected Token-2022 extension decoding, page/call budgets, failure
provenance, and fail-closed age behavior. The remaining production blockers were:

- RPC requests used `confirmed`, not `finalized`.
- Only top-level `jsonParsed` instructions were inspected.
- Compiled instructions, inner instructions, versioned transactions, and
  ALT-loaded account keys were not resolved.
- Parsed instructions from an unknown program could be mislabeled as SPL Token.
- Multiple matching initialization instructions/transactions were not rejected.
- T3 provenance was dropped by the generic candidate normalizer.
- Failure provenance reached normalization but was not durably stored in the
  governed source-failure row.

## Design Decision

Printer accepts T3 only when all of the following hold:

1. `getAccountInfo`, `getSignaturesForAddress`, and `getTransaction` use
   `finalized` commitment.
2. The mint account is an initialized legacy SPL Token or valid Token-2022 mint.
3. A successful transaction contains exactly one `initializeMint` or
   `initializeMint2` attributable to the exact requested mint.
4. Parsed or compiled, top-level or inner instructions may be used only when the
   token program and every account index resolve exactly. Versioned account
   resolution uses static keys followed by loaded writable and readonly keys.
5. The transaction or bounded `getBlockTime` fallback supplies a valid,
   non-future block time.
6. Ambiguous, malformed, non-finalized, missing, wrong-mint, or source-failed
   evidence fails closed.

Pair age, migration time, pool time, first-trade time, discovery time, receipt
time, and `OBSERVED_LIVE_LAUNCH` are never substituted for token creation time.

## Implementation

- Added strict finalized T3 RPC behavior.
- Added parsed and compiled mint-initialization decoding.
- Added top-level and inner-instruction traversal.
- Added legacy and v0/ALT account-key resolution.
- Added strict token-program and exact requested-mint checks.
- Added ambiguity rejection across instructions and candidate transactions.
- Added explicit `t3_commitment` and `t3_finality_status` provenance.
- Preserved all T3 fields through candidate and selection metadata.
- Added migration 027 so governed source failures can retain normalized failure
  provenance without rewriting historical rows.

The operation limits remain unchanged: eight total RPC operations, three
signature pages, three transaction calls, one block-time fallback, ten seconds
per call, zero retries, and no endpoint rotation.

## Deterministic Proof

Focused tests prove:

- finalized top-level and inner parsed instructions;
- compiled legacy/v0 instruction decoding;
- ALT-loaded requested-mint resolution;
- strict wrong-mint and unknown-program rejection;
- malformed index and ambiguous-match rejection;
- non-finalized signature rejection;
- real T3 provenance reaches selection metadata;
- failure provenance persists through Source Governor to an isolated database;
- existing T2, observed-live, A3-lock, and selection behavior remains intact.

## Bounded Live Proof

Proof database:
`data/printer_v1_real_t3_proof_20260712.sqlite3` (isolated, not committed)

Approved mint:
`6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`

Endpoint type: public, free, read-only Solana RPC. Stored host was redacted to
`api.mainnet-beta.solana.com`.

The one governed attempt succeeded:

- Source status: `COMPLETE`
- Data quality: `CLEAN_DATA`
- Operations: 5 (`getAccountInfo`, two signature pages, two transactions)
- Accepted signature:
  `4tYV8tu2iUgZWFFauSmwXLGxDbV4tN41Dbnx5yCWPKTyfjE77ZwgfoTWwZpcmxeAMGUs7hVdYoHSyFYT7zTPh98x`
- Accepted slot: `431974965`
- Instruction: `initializeMint2`
- Program: `token_2022`
- Finality: `finalized`
- Block time source: `getTransaction`
- `token_created_at`: `2026-07-10T08:21:12+00:00`
- `token_age_seconds`: `219831.725498`
- `token_age_evidence_tier`: `T3`
- Source request ID in proof DB: `1119`
- Source response ID in proof DB: `1072`
- Source failure ID: none

## Lock Proof

Persistent database SHA-256 before and after:
`97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb`

Persistent counts were unchanged. Proof DB deltas were exactly one source
request and one source response. Deltas were zero for memory windows, retrieval
queries/matches, paper decisions, paper positions, trade events, paper trade
audits, and every inspected downstream table. No PnL table existed in the
inspected schema.

No wallet, private key, signing, transaction submission, paid API, execution,
token scoring, ranking, confidence, or weighted decision behavior was added.

## Source-Stack Updates

The Solana core RPC, transaction parsing, token-age tier registry, and Source
Governor evidence modules now record the finalized exact-init-transaction T3
contract and the bounded proof result. Upstream RPC contracts remain external
authority; Printer code, tests, migrations, and adopted docs define current
implementation.

## Closeout

Verdict: `REAL_T3_TOKEN_AGE_PASS`

The real T3 evidence lane is complete. This closes T3 evidence production and
provenance only. It does not activate A3, A4, GROUP_A, memory creation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

Staged/native 15m evidence remains a separate deferred blocker. The next lane
requires an explicit operator decision; this closeout does not begin A3.
