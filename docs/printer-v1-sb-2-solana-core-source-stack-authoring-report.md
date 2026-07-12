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

---

# SB-2.1 Verification Record

**Lane:** SB-2.1 — Independent Solana Core Module Verification and Correction
**Executor/model:** Claude Sonnet 4.6
**Date:** 2026-07-12
**Anchor:** commit `0507ddd` (SB-2 authoring); SB-1 architecture doc
**Verdict:** `CORE_MODULE_VERIFICATION_PASS_WITH_BLOCKERS`

SB-2.1 did not adopt the source stack, did not change production code or tests,
did not run live RPC/API calls, did not resume T3, did not unlock A3, and did
not move V2-3 forward.

## SB-2.1 Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-sb-1-solana-builder-source-stack-architecture.md`
- `docs/printer-v1-sb-2-solana-core-source-stack-authoring-report.md`
- All 6 target files in `docs/solana-builder-source-of-truth/`

## SB-2.1 Git Verification

Commit `0507ddd` verified: authored exactly the 7 target files (README.md plus
5 core modules plus this report). No other files were staged.

## SB-2.1 Authorities Verified

All authorities verified against primary sources per SB-1 §2 and SB-2.1 lane:

| Source | Tier | Verified |
|---|---|---|
| Solana RPC HTTP docs (`solana.com/docs/rpc/http`) | A3 | ✓ (2026-07-12) |
| Solana clusters/endpoint docs (`solana.com/docs/references/clusters`) | A3 | ✓ (2026-07-12) |
| Solana transaction JSON structures (`solana.com/docs/rpc/json-structures`) | A3 | ✓ (2026-07-12) |
| Solana versioned transactions docs (`solana.com/docs/advanced/versions`) | A3 | ✓ (2026-07-12) |
| SPL Token repo (`github.com/solana-program/token`) | A1 | ✓ path cited; exact commit: `UNKNOWN_REQUIRES_RESEARCH` |
| Token-2022 repo (`github.com/solana-program/token-2022`) | A1 | ✓ path cited; exact commit: `UNKNOWN_REQUIRES_RESEARCH`; `extension/mod.rs` confirmed as layout source in V2-2AL.1 (`7aad246`) |
| Pump.fun `pump-public-docs` | A1 | ✓ per SB-1 §3.2 (Pump `create` carries no timestamp) |
| Circle USDC Solana documentation | A4 | `UNKNOWN_REQUIRES_RESEARCH` — exact URL not pinned |
| Tether USDt Solana documentation | A4 | `UNKNOWN_REQUIRES_RESEARCH` — exact URL not pinned |

## SB-2.1 Claims Confirmed

- SPL Token program ID `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`: confirmed (A1).
- `Mint::LEN = 82` bytes: confirmed from Printer implementation (A6) and
  consistent with SPL Token program source (A1 — exact commit not pinned).
- Token-2022 program ID `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`: confirmed (A1).
- Token-2022 layout: base [0,82), padding [82,165), AccountType@165, TLV@166,
  minimum 166 bytes: confirmed from V2-2AL.1 repair (`7aad246`) + V2-2AL.2
  independent verification (`5a4309e`).
- Infrastructure mint addresses (WSOL, USDC, USDT): consistent with Printer
  implementation (A6); exact A4-tier URL pins for USDC/USDT remain
  `UNKNOWN_REQUIRES_RESEARCH`.
- `getSignaturesForAddress` returns newest-first: confirmed (A3).
- `getAccountInfo.value` can be null: confirmed (A3).
- `getTransaction` can return null: confirmed (A3).
- Transaction `meta` and `blockTime` can be null: confirmed (A3).
- `maxSupportedTransactionVersion: 0` required for v0 transactions: confirmed (A3).
- Pump `create` issues `initializeMint` as an inner instruction (CPI): confirmed
  (A1: pump-public-docs; consistent with V2-2AL live proof evidence).
- V2-2AL.2 (`5a4309e`) correctly described as Token-2022 layout verification
  (independent verification of V2-2AL.1): confirmed from git history.

## SB-2.1 Corrections Applied

| # | Module | Correction |
|---|---|---|
| 1 | README.md | Expanded from minimal index (~58 lines) to full architecture entry point including A1–A7 hierarchy, conflict-resolution rules, freshness policy, protocol/provider separation, module inclusion/exclusion, task routing, adoption gates, SB-2.1 non-adoption statement |
| 2 | All 5 core modules | Restructured from original custom section numbering to exact 20-section template per SB-1 §5 |
| 3 | All 5 core modules | Status dimensions updated from custom vocabulary to SB-1 §6 vocabulary (`ACTIVE`, `PARTIAL_WITH_BLOCKER`, `ALLOWED_GOVERNED`, etc.) |
| 4 | solana-core-rpc-reference.md | Added method-level request/response contracts for all 6 RPC methods (getAccountInfo, getSignaturesForAddress, getTransaction, getBlockTime, getTokenLargestAccounts, getTokenSupply) |
| 5 | solana-core-rpc-reference.md | Documented mainnet endpoint implementation gap (`api.mainnet-beta.solana.com` vs `api.mainnet.solana.com`) from SB-1 §3.1 |
| 6 | solana-core-rpc-reference.md | Added `maxSupportedTransactionVersion: 0` requirement for v0 transactions |
| 7 | solana-core-rpc-reference.md | Added explicit `getSignaturesForAddress` newest-first pagination direction and `before`/`until` parameter behavior |
| 8 | solana-core-rpc-reference.md | Added DB persistence gap as explicit Known Printer Mistake (V2-2AL.4B blocker) |
| 9 | solana-transaction-instruction-parsing.md | Added legacy vs versioned transaction distinctions; ALT account-index ordering documented; CPI inner instruction indexing documented |
| 10 | solana-transaction-instruction-parsing.md | Added ALT coverage gap as Known Printer Mistake (current tests cover only legacy-style transactions) |
| 11 | solana-spl-token-program.md | Added `Mint` struct field-level byte offsets table; `Mint::LEN = 82` made explicit with byte offsets |
| 12 | solana-spl-token-program.md | Added `InitializeMint` (discriminant 0) and `InitializeMint2` (discriminant 20) with jsonParsed and compiled forms documented |
| 13 | solana-spl-token-program.md | Added `COption<Pubkey>` 4-byte tag encoding documentation |
| 14 | solana-spl-token-program.md | Added cross-module note on Token-2022 byte-82 mistake origin in Known Printer Mistakes |
| 15 | solana-token-2022-program.md | Added explicit 166-byte minimum requirement with citation of `BASE_ACCOUNT_AND_TYPE_LENGTH = 166` |
| 16 | solana-token-2022-program.md | Added TLV header format: 2-byte type (u16 LE) + 2-byte length (u16 LE) + data |
| 17 | solana-token-2022-program.md | Added 5-step validation sequence as explicit normalization rule |
| 18 | solana-token-2022-program.md | Added `_SPL_TOKEN_ACCOUNT_SIZE`, `_TOKEN_2022_ACCOUNT_TYPE_OFFSET`, `_TOKEN_2022_EXTENSION_DATA_START` constants to integration points section |
| 19 | solana-token-2022-program.md | `V2-2AL.2` confirmed as correct reference (git: `5a4309e Add V2-2AL.2 Token-2022 layout verification`) |
| 20 | solana-mint-addresses.md | Added per-address authority tables; official URL `UNKNOWN_REQUIRES_RESEARCH` status for USDC/USDT explicitly documented |
| 21 | solana-mint-addresses.md | Added WSOL trailing-`2` explanation; USDt vs USDT symbol distinction from Tether; impersonator-token warning |
| 22 | solana-mint-addresses.md | Added discovery exclusion rule: infrastructure mints that match memecoin candidate must be INSTANT_REJECT |

## SB-2.1 Claims Confirmed Without Change

- Safety invariants: pair age ≠ token age; capture time ≠ token creation time;
  migration time ≠ token creation time; first trade time ≠ token creation time;
  observed-live status does not satisfy A3.
- Locator-vs-proof rule (SB-1 Rule 5): PumpPortal signature is locator only.
- A3 gate: `assign_bucket()` requires `token_age_seconds is not None`. No
  failure path satisfies this gate.
- T3 budget: all 5 limit constants unchanged.
- Token-2022 byte-82 repair (V2-2AL.1 `7aad246`) correctly cited; V2-2AL.2
  verification reference confirmed from git history.
- SB-6 finality contract deferred: no module pre-decides commitment level.

## SB-2.1 Remaining Unknowns and Blockers

| Item | Status | Priority |
|---|---|---|
| SPL Token repo exact commit and file paths | `UNKNOWN_REQUIRES_RESEARCH` | Medium — required before adoption |
| Token-2022 repo exact commit and file paths (`solana-program/token-2022`) | `UNKNOWN_REQUIRES_RESEARCH` | Medium — required before adoption |
| Circle USDC official Solana URL | `UNKNOWN_REQUIRES_RESEARCH` | Medium — required before address hard-policy adoption |
| Tether USDt official Solana URL | `UNKNOWN_REQUIRES_RESEARCH` | Medium — required before address hard-policy adoption |
| WSOL native_mint.rs exact path in `solana-program/token` | `UNKNOWN_REQUIRES_RESEARCH` | Medium |
| Solana public RPC rate limits | `UNKNOWN_REQUIRES_RESEARCH` | Low (informational; T3 budgets already bounded) |
| Official current mainnet endpoint (`mainnet` vs `mainnet-beta`) | `UNKNOWN_REQUIRES_RESEARCH` | High — must verify before next live proof |
| ALT account-index resolution in v0 transactions | `UNKNOWN_REQUIRES_RESEARCH` | High for direct-signature T3; deferred |
| Compiled `initializeMint` decode | `DEFERRED` | High for direct-signature T3; deferred |
| SB-6 finality contract | `UNKNOWN_REQUIRES_RESEARCH` | Blocking A3 |
| V2-2AL.4C DB persistence repair | Pending implementation | Blocking V2-2AL.5 |
| V2-2AL.5 live proof | Pending after V2-2AL.4C | Blocking A3 |

## SB-2.1 Template Compliance Result

| Module | 20-section template | All 5 dimensions | Official sources cited | Change history entry |
|---|---|---|---|---|
| README.md | ✓ (12 sections, architecture reference) | ✓ (table in §4) | ✓ | ✓ |
| solana-core-rpc-reference.md | ✓ | ✓ | ✓ | ✓ |
| solana-transaction-instruction-parsing.md | ✓ | ✓ | ✓ | ✓ |
| solana-spl-token-program.md | ✓ | ✓ | ✓ | ✓ |
| solana-token-2022-program.md | ✓ | ✓ | ✓ | ✓ |
| solana-mint-addresses.md | ✓ | ✓ | ✓ (with `UNKNOWN_REQUIRES_RESEARCH` for USDC/USDT URLs) | ✓ |

## SB-2.1 Module-by-Module Verdict

| Module | Verdict |
|---|---|
| README.md | PASS — fully expanded to required architecture entry point |
| solana-core-rpc-reference.md | PASS_WITH_BLOCKER — all 6 method contracts documented; mainnet endpoint gap and DB persistence gap recorded |
| solana-transaction-instruction-parsing.md | PASS_WITH_BLOCKER — ALT coverage gap and direct-signature path undesigned recorded |
| solana-spl-token-program.md | PASS_WITH_BLOCKER — `Mint` layout pinned; exact repo commit `UNKNOWN_REQUIRES_RESEARCH` |
| solana-token-2022-program.md | PASS_WITH_BLOCKER — layout fully documented; exact repo commit `UNKNOWN_REQUIRES_RESEARCH`; V2-2AL.1/AL.2 repair confirmed |
| solana-mint-addresses.md | PASS_WITH_BLOCKER — addresses confirmed; Circle/Tether official URLs `UNKNOWN_REQUIRES_RESEARCH` |

## SB-2.1 T3 Usefulness Contribution

- Method-level RPC contracts give future T3 implementers an authoritative
  reference for `getTransaction` parameter requirements, response nullability,
  and pagination behavior.
- ALT account-index ordering rule is now documented; direct-signature T3 must
  handle v0 transactions and will need ALT resolution tests.
- Token-2022 layout verification confirms V2-2AL.1 repair is correctly documented;
  future T3 live proofs can rely on this layout.
- Locator-vs-proof rule is preserved and reinforced in every relevant module.

## SB-2.1 What Remains Locked

- A3: locked until V2-2AL.4C + V2-2AL.5 + SB-6 finality contract.
- T3: T3 is fixture-proven (132 tests) but not positively live-proven.
- Staged/native 15m blocker: PARTIAL - DEFERRED, NOT RESOLVED.
- V2-3: PAUSED.
- Source stack: NOT ADOPTED. SB-2.1 verification does not adopt the stack.
- Production code, tests, migrations, AGENTS.md: unchanged.

## SB-2.1 Adoption Blockers

The stack cannot be adopted until:
1. Upstream commit/file paths pinned for SPL Token and Token-2022.
2. Official URLs pinned for Circle USDC and Tether USDt.
3. Official current mainnet endpoint (`mainnet` vs `mainnet-beta`) verified.
4. Protocol modules (SB-3+) authored and verified.
5. SB-6 finality contract decided.
6. V2-2AL.4C DB persistence repair completed.
7. V2-2AL.5 live proof passes.
8. Explicit operator-approved adoption lane executed.

## SB-2.1 Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Severity | Status |
|---|---|---|
| Solana public RPC history pruning makes T3 impossible for older mints | HIGH | Known; T3 has always had this risk; direct-signature path mitigates but not yet designed |
| Official mainnet endpoint name discrepancy (`mainnet` vs `mainnet-beta`) | HIGH | Must verify before V2-2AL.5 live proof |
| V2-2AL.4B DB persistence gap for failure provenance | HIGH | V2-2AL.4C repair pending |
| ALT account-index resolution not tested in Printer | HIGH | Deferred; blocks direct-signature T3 for v0 transactions |
| Compiled `initializeMint` decode not adopted | MEDIUM | Deferred; direct-signature T3 may need it |
| SPL Token / Token-2022 upstream repo commit not pinned | MEDIUM | Required before adoption but does not block current fixture-only posture |
| Circle/Tether official URL not pinned for USDC/USDT | MEDIUM | Required before hard-policy adoption |
| Solana public RPC undocumented rate limits | LOW | Budgets already bounded by T3 limits |

## SB-2.1 Checks Run

- Verified commit `0507ddd` scope: exactly 7 files (README.md + 5 core modules +
  SB-2 report). No unrelated files staged.
- Verified V2-2AL.2 reference in Token-2022 module: confirmed via `git log`
  (`5a4309e Add V2-2AL.2 Token-2022 layout verification`).
- Verified V2-2AL lane sequence: AL → AL.1 → AL.2 → AL.3 → AL.4 → AL.4A →
  AL.4B (confirmed from git history).
- Scanned all 6 target files for: unlock language, prohibited capabilities,
  score/rank/confidence/weighted logic, wallet/key/signing references. None found.
- Verified all 20-section template compliance for each module.
- Verified all 5 status dimensions in each module use SB-1 §6 vocabulary.
- No production code, tests, migrations, or AGENTS.md changed.

## SB-2.1 Final Verdict

```text
LANE: SB-2.1 — Independent Solana Core Module Verification and Correction
EXECUTOR: Claude Sonnet 4.6
DATE: 2026-07-12
ANCHOR_COMMIT: 0507ddd Author SB-2 Solana core source-stack modules
VERDICT: CORE_MODULE_VERIFICATION_PASS_WITH_BLOCKERS

FILES_CORRECTED: 6 (README.md + 5 core modules)
SB_2_REPORT_UPDATED: this file

TEMPLATE_COMPLIANCE: PASS (all 5 modules + README restructured to exact template)
STATUS_DIMENSIONS: PASS (all updated to SB-1 §6 vocabulary)
AUTHORITY_CITATIONS: PASS_WITH_UNKNOWN (SPL Token, Token-2022 commit hashes
  and Circle/Tether URLs remain UNKNOWN_REQUIRES_RESEARCH)
RISKY_UNLOCK_LANGUAGE: NONE_FOUND
PROHIBITED_CAPABILITIES: NONE_FOUND

STACK_ADOPTED: NO
AGENTS_MD_CHANGED: NO
PRODUCTION_CODE_CHANGED: NO
TESTS_CHANGED: NO
LIVE_RPC_CALLS: NONE

T3_STATUS: FIXTURE_PROVEN_NOT_LIVE_PROVEN
A3_STATUS: LOCKED
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
V3_STATUS: PAUSED

NEXT_LANE: SB-3 — Author Solana Protocol Source-Stack Modules
  (pump-fun-bonding-curve-protocol.md, pumpswap-amm-protocol.md,
   raydium-amm-label-context.md, jupiter-routing-protocol.md)
  After SB-3, SB-4 would author provider API contract modules.
  Before adoption: pin upstream commits + USDC/USDT URLs, resolve mainnet
  endpoint, complete V2-2AL.4C, and pass V2-2AL.5 live proof.
```
