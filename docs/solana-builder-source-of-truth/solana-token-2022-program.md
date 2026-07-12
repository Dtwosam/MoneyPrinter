# Solana Token-2022 Program

Status: SB-2 CORE MODULE, DOCUMENTATION ONLY

## 1. Module Identity

- Module: Solana Token-2022 Program
- Scope: Token-2022 mint-account validation and extension layout for read-only evidence.
- Source-stack lane: SB-2.

## 2. Five-Dimension Status

- `upstream_lifecycle`: CURRENT_UPSTREAM_FOR_TOKEN_2022.
- `printer_readiness`: PARTIAL_IMPLEMENTED_NOT_ADOPTED.
- `printer_role`: TOKEN_2022_MINT_STATE_REFERENCE.
- `access_policy`: READ_ONLY_STATE_AND_TRANSACTION_REFERENCE.
- `v1_permission`: ALLOWED_FOR_GOVERNED_EVIDENCE_ONLY.

## 3. Authority Boundary

The Token-2022 program defines external mint-account and extension behavior. Printer implementation defines the current validation. Gaps require later repair or verification.

## 4. Upstream Sources

- Official Token-2022 repository: `https://github.com/solana-program/token-2022`
- Official Token-2022 docs: `https://www.solana-program.com/docs/token-2022`
- Repository paths to pin in later verification: extension layout definitions, account type definitions, mint state definitions, and instruction definitions.

Pinned upstream commit: not pinned in SB-2. Later verification should pin exact commit and file paths.

## 5. Program Identity

Current Printer implementation recognizes the Token-2022 program id:

`TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`

## 6. Authoritative Layout Requirement

The verified Token-2022 extended-mint layout used by Printer is:

- Mint base: bytes `0-81`.
- Zero padding: bytes `82-164`.
- AccountType: byte `165`.
- TLV extension data: byte `166+`.

The AccountType must identify a mint account.

## 7. Current Printer Decoder Behavior

Current Printer tests and docs require:

- Initialized mint base.
- Valid padding.
- AccountType equals Mint.
- Valid TLV walk.
- Partial headers fail closed.
- Length overflow fails closed.
- Malformed or unsupported layouts fail closed.

## 8. Token-2022 Initialize-Mint Evidence

Token-2022 T3 evidence still requires matching successful initialization evidence for the exact requested mint and a valid non-future block time. Layout validation alone is not token creation time.

## 9. Exact Mint Attribution

Evidence must target the exact requested mint. Token-2022 extension data cannot relax target-mint matching.

## 10. Failure Behavior

Malformed Token-2022 state leaves token age unknown:

- `token_created_at = None`
- `token_age_seconds = None`
- no T3 tier

Failure provenance may be recorded without creating age evidence.

## 11. Current Printer T3 Fit

V2-2AL.2 verified that byte 82 being zero should not alone reject a Token-2022 mint. The current layout expectation is the extended mint layout above.

## 12. Extension Handling

Unsupported extensions are acceptable only if the TLV walk remains structurally valid and the base mint/account type checks pass. Malformed extension lengths or partial headers fail closed.

## 13. Source Governor Boundary

Any live Token-2022 evidence read must go through governed Solana RPC paths. This module does not authorize a direct RPC loop.

## 14. A3 Boundary

Token-2022 can support A3 only after approved T3 evidence populates real `token_age_seconds` and finality requirements pass. SB-2 does not unlock A3.

## 15. Safety Boundary

Token-2022 extensions may affect safety analysis in future lanes, but this core module does not implement or approve new safety interpretation.

## 16. Forbidden Uses

This module does not allow minting, transfers, approvals, signing, wallet access, transaction construction, live execution, BUY/SELL/HOLD, paper positions, or PnL.

## 17. Known Gaps

- Exact upstream commit/file paths remain to be pinned.
- Full extension semantics are not adopted as Printer safety logic.
- Finality remains an SB-6 design decision.

## 18. Tests and Verification Expectations

Verification should cover:

- Legacy SPL Token exact 82-byte path unchanged.
- Token-2022 extended layout accepted.
- Bad padding rejected.
- Wrong AccountType rejected.
- TLV overflow rejected.
- Partial header rejected.
- T3 failure remains fail-closed.

## 19. Adoption Requirements

This module is authored only. Adoption requires independent verification and an explicit source-stack adoption step.

## 20. SB-2 Conclusion

Token-2022 is a core source-stack module for read-only mint-state evidence, but it does not broaden Printer live behavior or unlock A3.
