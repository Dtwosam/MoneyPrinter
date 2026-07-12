# Solana SPL Token Program

Status: SB-2 CORE MODULE, DOCUMENTATION ONLY

## 1. Module Identity

- Module: Solana SPL Token Program
- Scope: Legacy SPL Token mint account and initialize-mint evidence.
- Source-stack lane: SB-2.

## 2. Five-Dimension Status

- `upstream_lifecycle`: CURRENT_UPSTREAM_FOR_LEGACY_TOKEN_PROGRAM.
- `printer_readiness`: PARTIAL_IMPLEMENTED_NOT_ADOPTED.
- `printer_role`: TOKEN_MINT_STATE_AND_INITIALIZATION_REFERENCE.
- `access_policy`: READ_ONLY_STATE_AND_TRANSACTION_REFERENCE.
- `v1_permission`: ALLOWED_FOR_GOVERNED_EVIDENCE_ONLY.

## 3. Authority Boundary

The official SPL Token program defines legacy token account and instruction contracts. Printer implementation defines the current read-only validation. Disagreement is an implementation gap.

## 4. Upstream Sources

- Official token program repository: `https://github.com/solana-program/token`
- Official token program docs: `https://www.solana-program.com/docs/token`
- Repository paths to pin in later verification: token program instruction definitions, mint state definitions, and processor behavior for mint initialization.

Pinned upstream commit: not pinned in SB-2 because this lane does not fetch or vendor upstream code. Later verification should pin exact commit and file paths.

## 5. Program Identity

Current Printer implementation recognizes the legacy SPL Token program id:

`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`

## 6. Mint Account Layout

Printer current implementation treats legacy SPL Token mint accounts as exact 82-byte accounts. The initialized flag check is part of the current implementation contract.

## 7. Initialize-Mint Instructions

Current Printer T3 recognizes:

- `initializeMint`
- `initializeMint2`

Only matching successful initialization instructions for the exact requested mint may support token-age evidence.

## 8. Exact Mint Attribution

Exact requested-mint attribution is mandatory. Evidence for any other mint must fail closed.

## 9. Transaction Success Requirement

The transaction containing the initialization instruction must have succeeded. Failed transactions cannot produce token creation time.

## 10. Block-Time Requirement

A valid non-future block time is required. Null, missing, future, or unresolved block time fails closed.

## 11. Current Printer T3 Fit

The current T3 path validates the mint account owner and account size before looking for initialization evidence. It does not use pair age, capture time, migration time, first trade, or observed-live launch status as substitutes.

## 12. Failure Behavior

Failure leaves:

- `token_created_at = None`
- `token_age_seconds = None`
- no T3 tier

Safe failure provenance may be preserved separately.

## 13. Safety and Holder Context

The SPL Token program can also support read-only safety and holder context when combined with governed RPC methods such as `getTokenLargestAccounts` and `getTokenSupply`. This module does not approve live collection by itself.

## 14. Source Governor Boundary

Any live use must be source-governed and bounded. No engine may independently call RPC for SPL Token data.

## 15. A3 Boundary

Legacy SPL Token evidence may support A3 only after approved T3 evidence populates real `token_age_seconds` and the finality contract passes. SB-2 does not unlock A3.

## 16. Forbidden Uses

This module does not allow token creation, minting, transfers, approvals, burns, signing, wallet access, live execution, or transaction submission.

## 17. Known Gaps

- Exact upstream commit/file paths remain to be pinned.
- Compiled-instruction initialize-mint coverage is not adopted here.
- Finality requirements remain SB-6.

## 18. Tests and Verification Expectations

Verification should cover:

- Exact 82-byte mint layout.
- Owner match.
- Initialized mint requirement.
- Successful initialize-mint target match.
- Failed and mismatched transaction rejection.

## 19. Adoption Requirements

This module requires later independent verification before it can be cited as adopted source-stack implementation guidance.

## 20. SB-2 Conclusion

Legacy SPL Token is a valid core source for mint-state and initialization evidence. Printer remains read-only and paper-only.
