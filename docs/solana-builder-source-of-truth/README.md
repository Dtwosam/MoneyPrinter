# Solana Builder Source-of-Truth Stack

**Status:** SB-2 CORE MODULE INDEX — AUTHORED, NOT ADOPTED.
SB-2.1 INDEPENDENTLY VERIFIED — STACK REMAINS NOT ADOPTED.

This directory is the Printer V1 Solana Builder source-stack workspace. It is a
**subordinate reference library**, not a competing build order. It sits beneath
the active Printer source-of-truth stack and may never override it.

**SB-2.1 non-adoption statement:** SB-2.1 verified and corrected these modules
against primary upstream sources. Verification does not adopt the stack.
Adoption requires the explicit adoption gate described in §9 below. No module
in this directory changes production code, tests, migrations, or DB. No module
unlocks A3, execution, retrieval, paper decisions, BUY/SELL/HOLD, paper
positions, or PnL.

---

## 1. Subordination to the Active Printer Stack

This stack is subordinate to (in authority order):

1. `AGENTS.md` — build-discipline and V1 restriction law
2. `docs/printer-v1-clean-master-spec.md` — product and system law
3. `docs/printer-v1-post-rc-build-order.md` — active post-RC roadmap
4. `docs/printer-v1-memory-factory-guide.md` — memory-growth policy
5. `docs/printer-v1-memory-growth-build-order-v2.md` — active V2 build order
6. `docs/printer-v1-sb-1-solana-builder-source-stack-architecture.md` — stack architecture

If this stack and the active Printer stack ever conflict, the active Printer
stack wins and the conflicting module is corrected.

---

## 2. Authority Hierarchy (A1–A7)

Every claim in every module must be traced to one of the tiers below.
Upstream authority (A1–A5) defines external protocol/API contracts. Printer
implementation (A6) defines current local behavior. A7 may only corroborate;
it may never originate an adopted rule.

| Tier | Authority class | Examples for this stack |
|---|---|---|
| A1 | Official deployed-program source / official protocol repository | `github.com/solana-program/token` (SPL Token); `github.com/solana-program/token-2022` (Token-2022); `github.com/pump-fun/pump-public-docs` (Pump program README) |
| A2 | Official IDL or protocol-owned SDK | Anchor IDLs where published (Pump, PumpSwap); not yet inventoried in Printer |
| A3 | Official protocol developer documentation | `solana.com/docs`, `developers.jup.ag` docs |
| A4 | Official provider API documentation | `docs.dexscreener.com`, `docs.coingecko.com`, `apiguide.geckoterminal.com`, `docs.gopluslabs.io`, `api-docs.defillama.com`, `alternative.me/crypto/api`, `helius.dev/docs`, `pumpportal.fun/data-api` |
| A5 | Official changelog / release notes | Jupiter portal rate-limit pages; PumpSwap launch announcements corroborated by A1/A3 |
| A6 | Governed Printer payloads + local implementation evidence | `src/printer_v1/sources/*.py`, V2-2* design/proof docs, live/proof DB counts |
| A7 | Third-party material (corroboration only) | Explorers/indexers for cross-checking a program ID already asserted by A1 |

**Rule:** Do not rely on model memory, search-result summaries, blogs, cached
snippets, or social posts when an A1–A5 source exists. A7 may only corroborate
a fact already asserted by a higher tier; it may never originate an adopted rule.

---

## 3. External-Contract vs Printer-Implementation Distinction

- **External contract** (A1–A5): the upstream protocol/API defines what a
  program instruction does, what an endpoint returns, what a field means. This
  is authoritative over Printer code.
- **Printer implementation** (A6): current source files, tests, migrations, and
  adopted docs define what Printer currently does. Implementation gaps relative
  to upstream are recorded as `LEGACY_OR_DEPRECATED`, `PARTIAL_WITH_BLOCKER`,
  or `UNKNOWN_REQUIRES_RESEARCH`.
- Neither side silently rewrites the other. A disagreement is a documented gap.

---

## 4. Five Status Dimensions

Every module records all five dimensions. No single-label shorthand is
authoritative. Vocabulary (from SB-1 §6):

| Dimension | Allowed values |
|---|---|
| `upstream_lifecycle` | `ACTIVE`, `SUPERSEDED`, `DEPRECATED`, `UNKNOWN_REQUIRES_RESEARCH` |
| `printer_readiness` | `ACTIVE_READY`, `PARTIAL_WITH_BLOCKER`, `REGISTERED_NOT_READY`, `REFERENCE_ONLY`, `DEFERRED` |
| `printer_role` | `DISCOVERY`, `TOKEN_AGE`, `SAFETY`, `PAPER_REALISM_ONLY`, `CONTEXT_ONLY`, `LABEL_CONTEXT`, `EVIDENCE_RULES` |
| `access_policy` | `KEYLESS_PUBLIC`, `FREE_KEY_REQUIRED`, `UNKNOWN_REQUIRES_RESEARCH`, `PROHIBITED_PAID` |
| `v1_permission` | `ALLOWED_GOVERNED`, `ALLOWED_FIXTURE_ONLY`, `OPERATOR_APPROVAL_REQUIRED`, `PROHIBITED_V1` |

---

## 5. Conflict-Resolution Rules

(From SB-1 §9)

1. **Authority roles stay separate.** A1-A5 defines the external contract. A6
   defines current Printer implementation. Disagreement = documented gap.
2. **Silence is not permission.** If the highest available tier does not
   formally define a field, the conclusion is `UNKNOWN_REQUIRES_RESEARCH`.
3. **Preserve roles on conflict.** When two primary sources disagree, keep
   both, mark A7 as corroboration-only, and adopt the A1 value.
4. **Deprecation flags, never silent swaps.** If upstream supersedes a Printer
   endpoint, mark Printer `LEGACY_OR_DEPRECATED` and record the replacement;
   do not fix it in this reference lane.
5. **Locator vs proof.** A third-party-provided identifier (e.g., a PumpPortal
   signature or pool address) is locator evidence only. It becomes proof only
   when an A1–A3 on-chain read independently confirms the exact transaction/
   account.
6. **No fabrication.** Missing data is recorded as missing/failed. No source
   may invent a program ID, endpoint, or field.

---

## 6. Risk-Based Freshness Policy

(From SB-1 §10)

- **Provider endpoints, auth policy, quotas, response schema:** stale after
  **30 days** and before any live proof.
- **Program layouts, IDLs, instruction semantics, account layouts:** stale
  after **90 days**, and sooner if a protocol migration or failing proof
  suggests drift.
- **`UNKNOWN_REQUIRES_RESEARCH` items:** recheck before every live proof
  that depends on them.
- **Program IDs:** pin to official repo/tag/commit; recheck on any migration
  notice.
- **Immediate re-verify** regardless of age when: an adapter starts failing
  with auth/HTTP errors; upstream changelog announces an endpoint/version
  change; a live proof contradicts the module; a program migration is observed.
- Fixture-only status does not exempt a module from freshness. Reference
  correctness is still required.
- Re-verification updates §3 (last-verified) and §20 (change history); it
  never silently rewrites a rule without a dated entry.

---

## 7. Protocol/Provider Separation

- **Protocol modules** cite A1/A2 (deployed program source, IDL) for program
  IDs and on-chain semantics.
- **Provider modules** cite A4 (provider API docs) for off-chain endpoints.
- Pump.fun (bonding curve) and PumpSwap are separate protocols and must never
  share a module.
- Raydium is a label-context module only — it has no Printer adapter.

Core modules in this directory are chain-level primitives (Solana core, SPL
Token, Token-2022, transaction parsing, infrastructure mints). Protocol and
provider modules are planned for SB-3+ lanes.

---

## 8. Module Inclusion and Exclusion Criteria

**Inclusion triggers (any one):**
- Printer currently registers, calls, or normalizes it (A6 evidence).
- Printer stores a field that requires it to interpret (e.g., `dex` label).
- It is a Solana core primitive Printer's evidence path depends on (RPC, SPL
  Token, Token-2022, transaction parsing).
- It is an explicitly planned V1 source in `AGENTS.md` §Source Rules.

**Exclusion filter (all must hold):**
- Free/public or keyless-capable, or explicitly registered as free_tier_optional.
  Paid-only components are `PROHIBITED_V1`.
- Solana-relevant to Printer's memecoin memory/paper path. Popular but unused
  protocols (Meteora, Orca, Serum/OpenBook) are excluded. SB-0 confirmed they
  appear only in historical fixtures.
- Including it does not imply execution, signing, or wallet capability.

---

## 9. Task-to-Module Routing

When an agent picks up a Solana task, it MUST read the routed modules first.

| Task | Required modules |
|---|---|
| Any T3 / token-age work | solana-core-rpc-reference, solana-transaction-instruction-parsing, solana-spl-token-program, solana-token-2022-program, pump-fun-bonding-curve-protocol\*, pumpportal-api-contract\*, token-age-evidence-tier-registry\*, source-governor-evidence-rules\* |
| Direct-signature T3 design | all of the above (per SB-1 §13) |
| Discovery/selection intake | dexscreener-api-contract\*, geckoterminal-api-contract\*, pumpportal-api-contract\*, solana-mint-addresses |
| Migration/graduation handling | pump-fun-bonding-curve-protocol\*, pumpswap-amm-protocol\*, raydium-amm-label-context\*, pumpportal-api-contract\* |
| Safety / rug evidence | goplus-api-contract\*, solana-core-rpc-reference, solana-spl-token-program, solana-token-2022-program |
| Paper quote realism | jupiter-quote-api-contract\*, jupiter-routing-protocol\* |
| Market/chain-heat context | coingecko-api-contract\*, defillama-api-contract\*, alternative-me-api-contract\*, geckoterminal-api-contract\* |
| Any new source adapter | source-governor-evidence-rules\* + target provider module + solana-core-rpc-reference if on-chain |

\* Planned for SB-3+ lanes; not yet authored.

---

## 10. Adoption and Verification Gates

The stack does not become authoritative merely by existing. From SB-1 §11:

**Adoption gate:**
(a) `README.md` states the authority order and that the stack is subordinate
    to the active Printer source stack.
(b) An independent verifier (SB-1.1 architecture; SB-2.1 core modules) confirms
    this architecture.
(c) Each first-batch module is authored to the §5 template with cited authorities.
(d) No module unlocks execution, paid tiers, A3, V2-3, memory, or retrieval.

**Verification gate:**
Every module must pass an independent read (SB-1.1/SB-2.1): authority citations
resolve to A1-A5 hosts; all five status dimensions match upstream contract and
Printer implementation reality; no prohibited capability is implied; no live
endpoint testing was used to author it.

**SB-2.1 outcome:** all five core modules verified and corrected. Stack
structure and content confirmed. Stack remains NOT ADOPTED pending SB-3+
protocol/provider modules and explicit adoption lane.

---

## 11. Module Index

| Module | Scope | SB-2 authored | SB-2.1 verified |
|---|---|---|---|
| [solana-core-rpc-reference.md](solana-core-rpc-reference.md) | JSON-RPC 6 methods, commitment, endpoint, T3 budgets | ✓ | ✓ (corrected to 20-section template; method contracts added) |
| [solana-transaction-instruction-parsing.md](solana-transaction-instruction-parsing.md) | Transaction shapes, parsed/compiled, inner instructions, versioned tx, ALT, blockTime | ✓ | ✓ (corrected to 20-section template; parsing paths expanded) |
| [solana-spl-token-program.md](solana-spl-token-program.md) | Legacy SPL Token mint account, Mint::LEN, initializeMint/initializeMint2 | ✓ | ✓ (corrected to 20-section template; layout pinned) |
| [solana-token-2022-program.md](solana-token-2022-program.md) | Token-2022 mint account, AccountType@165, TLV@166, min 166 bytes | ✓ | ✓ (corrected to 20-section template; V2-2AL.1 repair verified) |
| [solana-mint-addresses.md](solana-mint-addresses.md) | Infrastructure mint addresses: WSOL, USDC, USDT | ✓ | ✓ (corrected to 20-section template; addresses pinned with authority) |

The following provider/protocol and cross-cutting modules were authored
pragmatically during the source-productivity / readiness mini-sprint (A6
implementation + A4 provider docs; uncertain items marked
`UNKNOWN_REQUIRES_RESEARCH`). They are practical adapter contracts, not yet
put through the formal SB independent-verification gate:

- [dexscreener-api-contract.md](dexscreener-api-contract.md)
- [pumpportal-api-contract.md](pumpportal-api-contract.md)
- [pump-fun-bonding-curve-protocol.md](pump-fun-bonding-curve-protocol.md)
- [pumpswap-pool-confirmation-contract.md](pumpswap-pool-confirmation-contract.md)
- [token-age-evidence-tier-registry.md](token-age-evidence-tier-registry.md)
- [source-governor-evidence-rules.md](source-governor-evidence-rules.md)

Remaining protocol/provider modules (pumpswap-amm-protocol,
raydium-amm-label-context, jupiter-routing-protocol, geckoterminal-api-contract,
etc.) are still planned for SB-3+ lanes.

---

## 12. Core Locks Preserved

- Solana-only. Solana memecoin-only. Paper-trading only.
- No wallet, private keys, signing, real funds, or live execution.
- No paid API dependency. No scoring, ranking, confidence, weighted, embedding,
  or vector logic.
- No retrieval activation. No paper decisions.
- No BUY, SELL, or HOLD unlock.
- No paper positions, trade events, paper audits, or PnL.
- No T3 resume, A3 unlock, staged/native 15m blocker resolution, or V2-3 work.
- Source Governor and Central Scheduler bypass is prohibited.

---

*SB-2 authored: 2026-07-12. SB-2.1 verified and corrected: 2026-07-12.*
