# Solana Transaction Instruction Parsing

Status: SB-2 CORE MODULE, DOCUMENTATION ONLY

## 1. Module Identity

- Module: Solana Transaction Instruction Parsing
- Scope: How Printer should reason about Solana transaction, instruction, and inner-instruction evidence.
- Source-stack lane: SB-2.

## 2. Five-Dimension Status

- `upstream_lifecycle`: CURRENT_UPSTREAM, versioned transaction behavior may evolve.
- `printer_readiness`: PARTIAL_IMPLEMENTED_NOT_ADOPTED.
- `printer_role`: EVIDENCE_PARSING_REFERENCE.
- `access_policy`: READ_ONLY_TRANSACTION_DECODING_ONLY.
- `v1_permission`: ALLOWED_FOR_GOVERNED_EVIDENCE_PARSING, NOT_ALLOWED_FOR_EXECUTION.

## 3. Authority Boundary

Solana transaction JSON structures define external response shapes. Printer parsing code defines what is currently recognized. A missing parser branch is an implementation gap, not permission to infer evidence.

## 4. Upstream Sources

- Solana transaction JSON structures: `https://solana.com/docs/rpc/json-structures`
- Solana `getTransaction`: `https://solana.com/docs/rpc/http/gettransaction`
- Solana transaction and versioned transaction concepts: `https://solana.com/docs/core/transactions`
- Address lookup table context: Solana official docs and runtime references, exact pinned file pending verification.

Pinned upstream commit: not pinned in SB-2. Later verification should pin official Solana docs or runtime files if direct parser expansion is implemented.

## 5. Current Printer Implementation

Relevant current implementation:

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`

Current T3 parsing is intentionally narrow and fixture-proven. It focuses on successful transaction evidence containing parsed `initializeMint` or `initializeMint2` instructions for the exact requested mint.

## 6. Transaction Response Shapes

Evidence parsing must account for:

- Parsed instructions.
- Compiled instructions.
- Inner instructions.
- Versioned transactions.
- Address lookup table references.
- Failed transaction status.
- Missing or pruned transaction history.

Unsupported shapes must fail closed.

## 7. Top-Level Instructions

Top-level instructions can provide mint-initialization evidence only when the instruction type, target mint, program, transaction status, and block time all pass the approved contract.

## 8. Inner Instructions

Inner instructions may contain relevant program calls. Printer must not treat inner instructions as covered unless tests prove exact requested-mint attribution and program identity.

## 9. Parsed Instructions

Parsed instructions are easier to inspect, but still require:

- Exact instruction type.
- Exact requested mint target.
- Successful transaction.
- Valid non-future block time.
- Correct program attribution.

## 10. Compiled Instructions

Compiled instructions require account-index resolution, program-id resolution, and instruction-data decoding. They are not adopted as live T3 evidence by SB-2.

## 11. Versioned Transactions

Versioned transactions and address lookup tables can change how account keys are represented. Printer must not assume legacy key layout for versioned transactions until explicit parser tests cover it.

## 12. Direct-Signature T3 Requirement

Future direct-signature T3 work must cover current and historical Pump creation instructions found in pinned official IDL/docs. It must not hardcode only one Pump `create` spelling.

The requirement is exact requested-mint attribution, including top-level/inner, parsed/compiled, versioned-transaction, and ALT cases where applicable.

## 13. PumpPortal Locator Boundary

PumpPortal signature data may be used only as a locator for a later governed Solana RPC verification path. PumpPortal signature presence alone is not token creation time.

## 14. Failure Conditions

Parsing must fail closed on:

- Failed transaction.
- Missing block time.
- Future block time.
- Mint mismatch.
- Missing exact target mint.
- Unsupported compiled instruction.
- Unresolved account lookup.
- Pruned history.
- Page-cap exhaustion.

## 15. Evidence Output Rules

Successful token-age evidence may populate T3 provenance only after all approved checks pass. Failure provenance may record bounded attempts but must not populate success fields.

## 16. A3 Safety Boundary

A3 remains locked unless `token_age_seconds` is populated by approved T1, T2, or T3 evidence. Pair age, observed-live launch status, captured time, migration time, and first trade time cannot unlock A3.

## 17. Forbidden Uses

This module does not allow transaction building, signing, swaps, live execution, BUY/SELL/HOLD decisions, retrieval activation, paper positions, or PnL.

## 18. Tests and Verification Expectations

Future parser expansion needs tests for:

- Parsed top-level instructions.
- Parsed inner instructions.
- Compiled instruction decode.
- Versioned transactions.
- ALT account resolution.
- Mint mismatch rejection.
- Failure provenance.

## 19. Adoption Requirements

This module is authored only. Direct parser expansion requires explicit future implementation and verification lanes.

## 20. SB-2 Conclusion

Transaction instruction parsing is a core source-stack dependency for honest T3 evidence, but SB-2 does not broaden the current parser or unlock A3.
