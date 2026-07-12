# Solana Builder Source-of-Truth Core Modules

Status: SB-2 CORE MODULE INDEX, DOCUMENTATION ONLY

This directory is the Printer V1 Solana Builder source-stack workspace for core Solana modules. It is subordinate to `AGENTS.md`, `docs/printer-v1-clean-master-spec.md`, `docs/printer-v1-post-rc-build-order.md`, `docs/printer-v1-memory-factory-guide.md`, `docs/printer-v1-memory-growth-build-order-v2.md`, and `docs/printer-v1-sb-1-solana-builder-source-stack-architecture.md`.

SB-2 authors the core reference modules only. It does not adopt the source stack, does not change Printer implementation, does not run live Solana RPC, does not resume T3, does not unlock A3, does not resolve staged/native 15m blockers, and does not move V2-3 forward.

## Authority Model

- Upstream Solana and SPL documentation defines the external protocol and API contracts.
- Printer code, tests, migrations, and adopted docs define the current implementation.
- Disagreement between upstream and Printer is an implementation gap to be verified in a later lane.
- Neither upstream text nor Printer implementation silently rewrites the other.

## Module Dimensions

Every module records five dimensions:

- `upstream_lifecycle`
- `printer_readiness`
- `printer_role`
- `access_policy`
- `v1_permission`

These dimensions replace any single primary status. Historical shorthand may appear only as explanatory vocabulary and is not authoritative.

## Authored Core Modules

| Module | Scope | Current SB-2 status |
|---|---|---|
| [solana-core-rpc-reference.md](solana-core-rpc-reference.md) | JSON-RPC methods, commitment, endpoint, bounded read-only use | Authored for verification |
| [solana-transaction-instruction-parsing.md](solana-transaction-instruction-parsing.md) | Transaction shapes, parsed/compiled instructions, inner instructions, versioned transactions, ALT context | Authored for verification |
| [solana-spl-token-program.md](solana-spl-token-program.md) | Legacy SPL Token mint-account and initialize-mint reference | Authored for verification |
| [solana-token-2022-program.md](solana-token-2022-program.md) | Token-2022 mint account, AccountType, TLV extension layout | Authored for verification |
| [solana-mint-addresses.md](solana-mint-addresses.md) | Infrastructure mint address authority and Printer usage boundaries | Authored for verification |

## Core Locks Preserved

- Solana-only.
- Solana memecoin-only.
- Paper-trading only.
- No wallet.
- No private keys.
- No signing.
- No real funds.
- No live execution.
- No paid API dependency.
- No scoring, ranking, confidence, weighted, embedding, or vector logic.
- No retrieval activation.
- No paper decisions.
- No BUY, SELL, or HOLD unlock.
- No paper positions, trade events, paper audits, or PnL.

## SB-2 Result

These files are source-stack authoring artifacts only. They are ready for independent verification, but they are not adopted as implementation authority until a later explicit adoption lane.
