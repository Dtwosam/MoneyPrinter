# SB-2 Solana Core Source-Stack Authoring Report

Status: DOCUMENTATION ONLY

## 1. Lane

Lane: SB-2 - Author Solana Core Source-Stack Modules

This lane authored core source-stack documents only. It did not adopt the stack, change code, run live sources, mutate databases, resume T3, unlock A3, or move V2-3.

## 2. Source Stack Read

Read or inspected:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-sb-1-solana-builder-source-stack-architecture.md`
- `src/printer_v1/sources/solana_rpc_token_age.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/selection_batch.py`
- focused tests around T3, T2, observed-live launch, and pair-age safety

## 3. Files Authored

- `docs/solana-builder-source-of-truth/README.md`
- `docs/solana-builder-source-of-truth/solana-core-rpc-reference.md`
- `docs/solana-builder-source-of-truth/solana-transaction-instruction-parsing.md`
- `docs/solana-builder-source-of-truth/solana-spl-token-program.md`
- `docs/solana-builder-source-of-truth/solana-token-2022-program.md`
- `docs/solana-builder-source-of-truth/solana-mint-addresses.md`

## 4. Module Coverage

The authored modules cover:

- Solana RPC method boundaries and current bounded Printer use.
- Transaction and instruction parsing requirements.
- Legacy SPL Token mint-state and initialize-mint evidence.
- Token-2022 extended mint layout and fail-closed validation.
- Infrastructure mint addresses and reference-only Printer use.

## 5. Five-Dimension Model

Each module records:

- `upstream_lifecycle`
- `printer_readiness`
- `printer_role`
- `access_policy`
- `v1_permission`

No module uses a single primary status as the authoritative contract.

## 6. Authority Boundary

The modules consistently state:

- Upstream defines external protocol/API contracts.
- Printer code, tests, migrations, and adopted docs define current implementation.
- Disagreement creates an implementation gap.
- Neither upstream nor Printer silently rewrites the other.

## 7. T3 Safety Result

The modules preserve the current T3 boundaries:

- Exact requested-mint attribution required.
- Valid mint account required.
- Successful matching initialization transaction required.
- Valid non-future block time required.
- Pair age, `captured_at`, migration time, first trade, and `OBSERVED_LIVE_LAUNCH` remain prohibited substitutes.
- `confirmed` versus `finalized` remains an SB-6 design decision.
- A3 remains locked.

## 8. Token-2022 Result

The Token-2022 module records the verified extended-mint layout:

- Mint base bytes `0-81`.
- Padding bytes `82-164`.
- AccountType byte `165`.
- TLV data byte `166+`.

It also records fail-closed malformed-extension handling as a verification requirement.

## 9. Mint Address Result

The mint-address module records current Printer infrastructure constants for WSOL, USDC, and USDT as reference-only context. It does not turn infrastructure mints into target assets and does not unlock quote execution.

## 10. Locks Preserved

SB-2 preserved:

- Solana-only.
- Solana memecoin-only.
- Paper-only.
- No wallet/private-key/signing/live execution.
- No paid APIs.
- No scoring/ranking/confidence/weighted logic.
- No embeddings/vectors.
- No source fetching.
- No DB mutation.
- No memory generation.
- No retrieval.
- No paper decisions.
- No BUY/SELL/HOLD.
- No paper positions, trades, audits, or PnL.

## 11. Remaining Unknowns

- Exact upstream repository commit/file pins remain to be verified for SPL Token and Token-2022 modules.
- Exact official address reference pages for infrastructure mints should be pinned in a later verification lane.
- SB-6 must decide T3 finality and direct-signature parser coverage.
- Public RPC history, pruning, and rate-limit behavior remain operational blockers.
- The source stack is authored, not adopted.

## 12. Verdict

`CORE_MODULES_AUTHORED_WITH_BLOCKERS`

The core modules are authored and ready for independent verification, but adoption should wait for pinning and verification of the remaining upstream references and T3 finality/design decisions.

## 13. Next Recommended Lane

SB-2.1 - Independent Solana Core Source-Stack Module Verification.
