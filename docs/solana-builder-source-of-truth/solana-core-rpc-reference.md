# Solana Core RPC Reference

Status: SB-2 CORE MODULE, DOCUMENTATION ONLY

## 1. Module Identity

- Module: Solana Core RPC Reference
- Scope: Read-only Solana JSON-RPC methods used or planned by Printer V1.
- Source-stack lane: SB-2.

## 2. Five-Dimension Status

- `upstream_lifecycle`: CURRENT_UPSTREAM, subject to Solana RPC documentation changes.
- `printer_readiness`: PARTIAL_IMPLEMENTED_NOT_ADOPTED.
- `printer_role`: READ_ONLY_EVIDENCE_REFERENCE.
- `access_policy`: FREE_PUBLIC_OR_OPERATOR_APPROVED_READ_ONLY_RPC_ONLY.
- `v1_permission`: ALLOWED_FOR_GOVERNED_READ_ONLY_EVIDENCE, NOT_ALLOWED_FOR_EXECUTION.

## 3. Authority Boundary

Solana RPC documentation defines request and response contracts. Printer implementation defines the current bounded behavior. If Solana RPC docs and Printer behavior disagree, the result is an implementation gap, not an automatic override.

## 4. Upstream Sources

- Solana RPC HTTP method documentation: `https://solana.com/docs/rpc/http`
- Solana `getAccountInfo`: `https://solana.com/docs/rpc/http/getaccountinfo`
- Solana `getSignaturesForAddress`: `https://solana.com/docs/rpc/http/getsignaturesforaddress`
- Solana `getTransaction`: `https://solana.com/docs/rpc/http/gettransaction`
- Solana `getBlockTime`: `https://solana.com/docs/rpc/http/getblocktime`
- Solana `getTokenLargestAccounts`: `https://solana.com/docs/rpc/http/gettokenlargestaccounts`
- Solana `getTokenSupply`: `https://solana.com/docs/rpc/http/gettokensupply`
- Solana clusters/reference endpoint documentation: `https://solana.com/docs/references/clusters`

Pinned upstream commit: not applicable for hosted RPC documentation in SB-2. A later verification lane should record doc retrieval dates or pinned archive references if needed.

## 5. Current Printer Implementation

Relevant current implementation files:

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`
- `tests/test_post_rc_real_evidence_collection.py`

Printer currently has bounded Solana RPC paths for token-age reference evidence and holder concentration reference evidence. These paths are not transaction execution paths.

## 6. RPC Methods In Scope

Printer core reference methods are:

- `getAccountInfo`
- `getSignaturesForAddress`
- `getTransaction`
- `getBlockTime`
- `getTokenLargestAccounts`
- `getTokenSupply`

No method in this module may build, sign, simulate, send, or execute transactions.

## 7. Endpoint Policy

Printer may use a free public Solana RPC endpoint or an explicit operator-approved free/read-only endpoint. The default implementation references `https://api.mainnet-beta.solana.com`.

Endpoint output must redact secrets. Reports should show host-only information and must not expose query strings, API keys, credentials, or tokens.

## 8. Source Governor Boundary

Any live RPC use must go through the Source Governor or an explicitly approved governed proof path. Engines must not open direct independent RPC loops.

## 9. Central Scheduler Boundary

This module does not start scheduler work. Any future scheduled RPC collection must go through Central Scheduler policy and source budgets.

## 10. Commitment and Finality

Commitment level is not pre-approved in this module. `confirmed` versus `finalized`, and any minimum-finality contract for token-age evidence, remains an explicit SB-6 design decision.

No token-age evidence may satisfy A3 until the approved finality contract passes.

## 11. Current T3 Request Limits

Current Printer T3 implementation records these bounded limits:

- Maximum 8 RPC operations per token.
- Maximum 3 signature pages.
- Maximum 3 transaction calls.
- Maximum 1 `getBlockTime` fallback.
- 10-second timeout.
- Zero retries.
- No endpoint rotation.

These are implementation facts, not permission to expand live coverage.

## 12. Failure Provenance

Safe failure provenance may include:

- Requested mint.
- Redacted RPC host.
- RPC methods attempted.
- Request IDs.
- Signature pages fetched.
- Transaction calls attempted.
- Block-time calls attempted.
- Failure stage.

Failure provenance must not populate `token_created_at`, `token_age_seconds`, or `token_age_evidence_tier`.

## 13. Safety Evidence Use

Solana RPC can support safety or holder-context evidence only when source status, data quality, target matching, and freshness gates pass. Failed, stale, missing-critical, or rate-limited responses remain audit-only or fail-closed.

## 14. Token-Age Evidence Use

Solana RPC T3 token-age evidence requires a valid mint account, matching successful mint initialization, exact requested-mint attribution, and valid non-future block time. Pair age, capture time, migration time, first trade time, and observed-live status are prohibited substitutes.

## 15. Known Implementation Gaps

- SB-6 must decide commitment/finality for T3.
- Public RPC history can be pruned or rate-limited.
- Direct-signature parsing coverage is not adopted from this module.
- Helius/free-tier fallback remains optional and not a paid dependency.

## 16. Forbidden Uses

This module does not allow:

- Wallets.
- Private keys.
- Signing.
- Transaction construction.
- `sendTransaction`.
- Swaps.
- BUY, SELL, or HOLD decisions.
- Retrieval activation.
- Paper positions or PnL.

## 17. Evidence Labels

RPC output may contribute to categorical evidence labels only. It must not create scores, ranks, confidence percentages, weighted logic, or token-selection probability.

## 18. Tests and Verification Expectations

Verification should confirm:

- RPC calls remain bounded.
- Failure paths are fail-closed.
- Redaction is safe.
- Source Governor traces exist where required.
- Persistent DB is not mutated during isolated proofs.

## 19. Adoption Requirements

This module is not adopted by SB-2. Adoption requires later explicit review, passing tests, bounded proof where approved, and update to the active source-stack status.

## 20. SB-2 Conclusion

Solana Core RPC is a valid core source-stack module for governed read-only evidence. It remains bounded, paper-only, and not an execution or trading path.
