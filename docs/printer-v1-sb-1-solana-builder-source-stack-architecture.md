# Printer V1 SB-1 Solana Builder Source-Stack Architecture and Authority Design

**Lane:** SB-1 — Solana Builder Source-Stack Architecture and Authority Design
**Type:** Architecture and documentation design only. No production code, tests, migrations, or DB mutation. No live RPC/API calls. No live endpoint testing. No AGENTS.md modification.
**Executor:** Claude Opus 4.8
**Effort:** Highest
**Date:** 2026-07-12
**Anchor:** `docs/printer-v1-sb-0-solana-integration-upstream-documentation-inventory-audit.md` (as corrected in SB-0.1, commit `b5da5ae`)
**Verdict:** `ARCHITECTURE_COMPLETE_WITH_BLOCKERS`

---

## 0. What This Lane Is and Is Not

This lane designs the **canonical modular Solana Builder Source Stack** — a supporting reference layer that future agents (ChatGPT, Claude, Codex) use for Printer's Solana engineering work. It sits **beneath** the active Printer source-of-truth stack; it is a reference library, not a competing build order.

This lane does **not**:

- Change production code, tests, or migrations.
- Modify `AGENTS.md`.
- Adopt the source stack (no files under `docs/solana-builder-source-of-truth/` are created).
- Create every final module (the template + first-module set are specified; full authoring is SB-2+).
- Run live RPC/API calls or live endpoint testing.
- Mutate any DB.
- Run discovery or source fetching through Printer.
- Resume T3, unlock A3, or unlock V2-3.
- Generate memory, activate retrieval, or create paper decisions/BUY/SELL/HOLD/positions/trades/audits/PnL.
- Introduce a paid dependency or weaken Source Governor / Central Scheduler rules.

All research below used **primary upstream documentation and official repositories only** (WebFetch/WebSearch against official doc hosts). No Printer endpoint was called. Where a primary source does not formally define a field, the conclusion is marked `UNKNOWN_REQUIRES_RESEARCH`.

### Checklist executed

1. Read the 7 required anchor docs (`AGENTS.md`, clean-master-spec, post-rc-build-order, memory-factory-guide, current-state-memory-growth-audit, memory-growth-build-order-v2, SB-0 audit). — DONE
2. Verified current Solana code claims against the SB-0 corrected inventory. — DONE
3. Primary-source research on all high-risk items (Solana core, protocols, providers). — DONE
4. Authority hierarchy + conflict-resolution rules. — DONE (§2, §9)
5. Canonical module tree with protocol/provider separation. — DONE (§4)
6. Module template, status vocabulary, inclusion criteria, task-routing, freshness/versioning, adoption gates. — DONE (§5–§11)
7. Disposition of every high-risk SB-0 blocker with cited authority. — DONE (§12)
8. Minimum modules for direct-signature T3. — DONE (§13)
9. Write this artifact. — DONE
10. Static git checks + commit report only. — DONE (§18)

---

## 1. Executive Verdict

Printer's Solana integration is **small, raw, and mostly fixture-gated** — which is a safety asset, not a liability. All 11 registered sources go through the Source Governor; only PumpPortal (WebSocket) and `solana_rpc_token_age` (T3 HTTP RPC) have live transports; there is no Solana Python SDK. The gaps are not in safety architecture; they are in **upstream-authority discipline**: several adapters point at endpoints that upstream has since re-versioned, re-keyed, or relabeled, and the fixture-only posture has masked this drift.

The Solana Builder Source Stack fixes that by giving every protocol and provider a **single canonical module** with a cited upstream authority, a Printer readiness status, and explicit allowed/prohibited capabilities. This lane delivers the architecture (authority order, module tree, template, status vocabulary, conflict rules, freshness policy, task routing, adoption gates) and dispositions every SB-0 blocker against a **primary source**.

The verdict is `ARCHITECTURE_COMPLETE_WITH_BLOCKERS`. SB-1.1 independently verifies this architecture as `ARCHITECTURE_VERIFICATION_PASS_WITH_BLOCKERS` and corrects several over-specific SB-1 claims. The corrected high-severity facts are:

1. Jupiter has a documented `lite-api.jup.ag/swap/v1/quote` quote path in current developer docs, but official guidance around API-key requirements across Lite/API/Ultra/portal docs is not fully reconciled here. Printer's Jupiter adapter remains fixture-only and paper-realism-only. Live Jupiter wiring remains `UNKNOWN_REQUIRES_RESEARCH`.
2. The `dex: "raydium"` migration label is not reliable venue proof. PumpPortal's `newRaydiumPool` must be treated as a pool-address locator only; the actual venue remains unknown until on-chain owner/program verification proves it. SB-1.1 removes the unsupported PumpSwap graduation-percentage claim.

Neither blocker is resolved by writing code here; both are recorded with dispositions for SB-2+.

**T3 outcome:** the minimum module set to safely design direct-signature T3 is identified (§13). The PumpPortal signature is **locator evidence only**. Authoritative creation time must come from Solana RPC independently proving an exact requested-mint creation or mint-initialization transaction, covering current and historical Pump creation instructions from pinned official IDL/docs plus SPL Token / Token-2022 mint initialization where relevant, and reading its block time under an SB-6-approved finality contract.

---

## 2. Authority Hierarchy

Every major technical/architectural conclusion cites (a) the relevant Printer code/test/design/proof/audit, and (b) the exact upstream authority. Upstream authority defines external protocol/API contracts. Printer code, tests, migrations, and adopted docs define current Printer implementation. When the two disagree, the result is a documented implementation gap; neither side silently rewrites the other. When the higher tier is silent, the conclusion is `UNKNOWN_REQUIRES_RESEARCH` and the lower-tier reading is recorded but not adopted.

| Tier | Authority class | Examples used in this lane |
|---|---|---|
| A1 | Official deployed-program source / official protocol repository | `github.com/pump-fun/pump-public-docs` (Pump program README); `github.com/solana-program/token` (SPL Token); `github.com/solana-program/token-2022` (Token-2022) |
| A2 | Official IDL or protocol-owned SDK | Anchor IDLs where published (Pump, PumpSwap) — not yet inventoried in Printer |
| A3 | Official protocol developer documentation | `solana.com/docs`, `dev.jup.ag` / `developers.jup.ag` docs |
| A4 | Official provider API documentation | `docs.dexscreener.com`, `docs.coingecko.com`, `apiguide.geckoterminal.com`, `docs.gopluslabs.io`, `api-docs.defillama.com`, `alternative.me/crypto/api`, `helius.dev/docs`, `pumpportal.fun/data-api` |
| A5 | Official changelog / release notes | Jupiter portal rate-limit pages; PumpSwap launch announcements corroborated by A1/A3 |
| A6 | Governed Printer payloads + local implementation evidence | `src/printer_v1/sources/*.py`, V2-2* design/proof docs, live/proof DB counts |
| A7 | Third-party material (only when no primary authority exists) | Explorers/indexers for cross-checking a program ID already asserted by A1 |

**Rule:** Do not rely on model memory, search-result summaries, blogs, cached snippets, or social posts when an A1–A5 source exists. A7 may only *corroborate* a fact already asserted by a higher tier (e.g., confirming a program ID that A1 states); it may never *originate* an adopted rule.

**Application note:** A6 (Printer's own payloads and implementation evidence) defines what Printer currently does. A1-A5 authorities define the external protocol/API contract. When Printer code and upstream authorities disagree, record an implementation gap such as `LEGACY_OR_DEPRECATED`, `UNKNOWN_REQUIRES_RESEARCH`, or `PARTIAL_WITH_BLOCKER`; neither source silently rewrites the other.

---

## 3. Upstream Source Register

All URLs verified 2026-07-12 against the listed host. "Printer rule" is the exact rule the Solana Builder Source Stack should encode.

### 3.1 Solana core

| Component | Document / repo | Canonical URL | Version / tag | Status | Printer rule |
|---|---|---|---|---|---|
| JSON-RPC HTTP | Solana RPC HTTP Methods | `https://solana.com/docs/rpc/http` | Agave/current | ACTIVE | 6 methods only (§SB-0 §4); JSON-RPC 2.0 over HTTPS POST |
| Commitment levels | Solana RPC Overview — commitment | `https://solana.com/docs/rpc` | current | ACTIVE | `confirmed` versus `finalized` and any minimum-finality rule are SB-6 design decisions; no T3 age evidence satisfies A3 until the approved finality contract passes (§12.8) |
| Clusters | Solana Clusters & Endpoints | `https://solana.com/docs/references/clusters` | current | ACTIVE | Upstream currently documents public mainnet as `https://api.mainnet.solana.com`; Printer currently uses `https://api.mainnet-beta.solana.com`. Treat this as an implementation gap/reverify item before live proof; operator override remains allowed. |
| SPL Token | solana-program/token | `https://github.com/solana-program/token` | program `Tokenkeg…` | ACTIVE | `Mint::LEN = 82`; `initializeMint` / `initializeMint2` are creation instructions |
| Token-2022 | solana-program/token-2022 | `https://github.com/solana-program/token-2022` | program `Tokenz...` | ACTIVE | AccountType at byte 165; extensions from 166; min 166 bytes (V2-2AL.1). Avoid the archived `solana-labs/solana-program-library` path as the canonical module authority. |
| getTransaction | getTransaction | `https://solana.com/docs/rpc/http/gettransaction` | current | ACTIVE | `jsonParsed` encoding; parse inner + compiled instructions; handle versioned tx + ALT |

### 3.2 Protocol authorities

| Component | Document / repo | Canonical URL | Version / tag | Status | Printer rule |
|---|---|---|---|---|---|
| Pump.fun bonding curve | pump-public-docs PUMP_PROGRAM_README | `https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md` | program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` (mainnet + devnet) | ACTIVE (A1) | Bonding-curve PDA seeds `["bonding-curve", mint]`; `create` instruction mints a coin but **carries no timestamp**; `migrate` is permissionless |
| PumpSwap AMM | Official Pump.fun public repository PumpSwap docs / IDL / SDK | `https://github.com/pump-fun/pump-public-docs` | pin the exact repo commit and PumpSwap file paths in SB-3 | ACTIVE upstream / REFERENCE_ONLY in Printer | Official Pump.fun repo docs/IDL/SDK are A1/A2 for PumpSwap protocol facts. PumpPortal PumpSwap material is A4 provider documentation only. Program ID not in Printer source; adapter fixture-only; exact migration venue must be verified on-chain before use. |
| Raydium (label context) | no Printer adapter | n/a | n/a | LEGACY_OR_DEPRECATED label | Printer's `dex:"raydium"` migration label is a stale/unsafe venue assertion. Treat it as label context only, not venue proof. |
| Jupiter routing | Jupiter Meta-Aggregator / Router / API docs | `https://dev.jup.ag/docs/swap-api/get-quote` | Legacy Swap / Metis historical or superseded; newer Jupiter API generations are current upstream paths | ACTIVE upstream / PAPER_REALISM_ONLY in Printer | Aggregation routing is paper-realism context only. Exact live auth/endpoint contract remains `UNKNOWN_REQUIRES_RESEARCH`; transaction execution is not allowed in Printer V1. |

### 3.3 Provider API contracts

| Provider | Document | Canonical URL | Auth / cost | Status | Printer rule |
|---|---|---|---|---|---|
| PumpPortal | Real-time Data API | `https://pumpportal.fun/data-api/real-time/` | auth/keyless status UNKNOWN for production use | ACTIVE (A4) | WebSocket `wss://pumpportal.fun/api/data`; event schema undocumented; do not equate a subscription method with a guaranteed no-key policy; signature = locator only. |
| Jupiter Quote | Swap API / Get Quote | `https://dev.jup.ag/docs/swap-api/get-quote` | `lite-api.jup.ag` appears in current docs, but Lite/API/Ultra auth guidance needs recheck | PAPER_REALISM_ONLY / UNKNOWN_REQUIRES_RESEARCH for live wiring | Fixture-only; live endpoint/auth lifecycle not adopted (§12.1-§12.2). |
| DexScreener | API Reference | `https://docs.dexscreener.com/api/reference` | no key; per-endpoint rate limits, commonly 300 rpm for pair/token/search style endpoints and 60 rpm for profile/boost/order endpoints | ACTIVE / token endpoint LEGACY | Current token endpoint is `/tokens/v1/{chainId}/{tokenAddresses}`; Printer's `/latest/dex/tokens/` is legacy (§12.4). |
| GeckoTerminal | API Guide | `https://apiguide.geckoterminal.com/` | no key; version header `application/json;version=20230302` | ACTIVE | `new_pools` / `trending_pools` confirmed; low-frequency backup |
| GoPlus | Solana token security | `https://docs.gopluslabs.io/reference/solanatokensecurityusingget` | no key (basic); beta | ACTIVE (beta) | 429 → STALE; response `{code,message,result{<mint>}}` |
| CoinGecko | Keyless Public API | `https://docs.coingecko.com/docs/keyless-public-api` | keyless supported (low rate); demo key = 100/min | OPTIONAL_FREE_FALLBACK | Keyless `api.coingecko.com/api/v3` officially supported for low-frequency context (§12.5) |
| DefiLlama | API docs | `https://api-docs.defillama.com/` | free public; pro separate | ACTIVE | `api.llama.fi/v2/chains`; context only |
| Alternative.me | Fear & Greed API | `https://alternative.me/crypto/api/` | no key | ACTIVE | `fng/?limit=2&format=json`; broad sentiment context |
| Helius | Plans & Pricing / Endpoints | `https://www.helius.dev/docs/billing/plans` | free tier **requires** a free dashboard API key; 1M credits/mo, 10 RPC req/s | REGISTERED_NOT_READY / OPTIONAL_FREE_FALLBACK | No keyless path; no adapter exists; keep deferred (§12.9) |
| Solana public RPC | Clusters | `https://solana.com/docs/references/clusters` | keyless | ACTIVE_READY | Primary keyless on-chain path; strict Governor budgets |

---

## 4. Final Proposed Module Tree

The stack lives at `docs/solana-builder-source-of-truth/` (not created in this lane). It refines the SB-0/SB-0.1 proposal by (a) adding a dedicated **transaction/instruction parsing** core module and a **Source Governor evidence-rules** module, both required for direct-signature T3, and (b) keeping protocols and providers in separate sections.

```text
docs/solana-builder-source-of-truth/
├── README.md                                 # Index, authority order (A1–A7), status vocabulary, task routing
│
│ # ── Solana core (chain-level programs, accounts, RPC) ──
├── solana-core-rpc-reference.md              # 6 RPC methods, commitment (confirmed vs finalized), clusters, encodings
├── solana-transaction-instruction-parsing.md # jsonParsed vs compiled, inner instructions, versioned tx + ALT, blockTime
├── solana-spl-token-program.md               # SPL Token program ID, Mint::LEN=82, initializeMint/initializeMint2
├── solana-token-2022-program.md              # Token-2022 layout, AccountType@165, TLV extensions@166, min 166 bytes
├── solana-mint-addresses.md                  # 3 infrastructure mints: WSOL, USDC, USDT
│
│ # ── Protocol authorities (on-chain programs) ──
├── pump-fun-bonding-curve-protocol.md        # Program 6EF8…; create/migrate; bonding-curve PDA; no timestamp in event
├── pumpswap-amm-protocol.md                  # Official Pump.fun repo docs/IDL/SDK; PumpPortal docs are provider-level only
├── raydium-amm-label-context.md              # Raydium as stale dex label only; no Printer adapter; migration relabel
├── jupiter-routing-protocol.md               # Jupiter router/API generations; paper-realism context only; no execution
│
│ # ── Provider API contracts (off-chain data APIs) ──
├── pumpportal-api-contract.md                # WS URL, subscribe methods, undocumented event schema, signature=locator
├── jupiter-quote-api-contract.md             # Lite/API/Ultra auth unknown, fixture-only, no execution
├── dexscreener-api-contract.md               # pairs/tokens/v1 endpoints, legacy token URL, 60–300 rpm, no key
├── geckoterminal-api-contract.md             # new_pools/trending_pools, version header, low-frequency backup
├── goplus-api-contract.md                    # Solana token security, beta, 429→STALE, response shape
├── coingecko-api-contract.md                 # keyless public tier, demo-key option, context-only
├── defillama-api-contract.md                 # chains endpoint, free vs pro separation
├── alternative-me-api-contract.md            # fng endpoint, rate limits, 5-min update
├── helius-rpc-contract.md                    # free tier requires key, deferred, no adapter
├── solana-public-rpc-contract.md             # keyless mainnet-beta, Governor budgets, rate-limit behavior
│
│ # ── Cross-cutting evidence + governance ──
├── token-age-evidence-tier-registry.md       # T1>T2>T3>OBSERVED_LIVE_LAUNCH>T5; T4_PAIR_ONLY; A3 gate
└── source-governor-evidence-rules.md         # Governed execution path, failure provenance, budgets, redaction
```

**Count: 21 modules** (5 core, 4 protocol, 10 provider, 2 cross-cutting). Two are new relative to SB-0's 17: `solana-transaction-instruction-parsing.md` and `source-governor-evidence-rules.md`, plus `solana-public-rpc-contract.md` split from the provider list (SB-0 had folded public RPC into Helius/RPC discussion).

**Protocol vs provider separation (authority note):** protocol modules cite A1/A2 (deployed program source, IDL) for program IDs and on-chain semantics; provider modules cite A4 (provider API docs) for off-chain endpoints. Pump.fun and PumpSwap are **separate protocols** and never share a module. Raydium is a label-context module only — it has no Printer adapter and exists to document the stale `dex:"raydium"` relabel.

---

## 5. Standard Module Template

Every module MUST contain these 20 sections, in order:

1. **Purpose** — what this component is and why Printer touches it.
2. **Official upstream authorities** — A-tier, doc title, canonical URL, repo path.
3. **Last verified date and version** — ISO date + version/tag/API generation/commit.
4. **Authority/status dimensions** — record all five dimensions: `upstream_lifecycle`, `printer_readiness`, `printer_role`, `access_policy`, and `v1_permission`.
5. **Allowed capabilities** — exactly what Printer may do with it.
6. **Prohibited capabilities** — what Printer must never do (execution, paid tiers, etc.).
7. **Authentication and cost model** — key/no-key, free/paid, sign-up requirement.
8. **Programs, endpoints, methods, request contracts** — IDs, URLs, params, headers.
9. **Response and field semantics** — what each consumed field means.
10. **Nullable/missing-field behavior** — what Printer does when a field is absent.
11. **Rate limits and bounded-use rules** — upstream limits + Printer Governor budgets.
12. **Evidence strength** — which evidence tier (T1–T5 / OBSERVED_LIVE_LAUNCH / context-only) this can produce.
13. **Normalization and failure rules** — normalizer contract, failure statuses (FAILED/STALE/etc.).
14. **Security/redaction rules** — host-only redaction, no keys/paths in stored payloads.
15. **Known upstream quirks** — undocumented fields, relabels, beta status.
16. **Known Printer mistakes** — historical bugs (e.g., Token-2022 byte-82 error) and their fix commit.
17. **Required fixtures/proofs** — what fixture/proof must exist before live use.
18. **Code and DB integration points** — adapter file, request kinds, DB tables/columns.
19. **Unresolved questions** — `UNKNOWN_REQUIRES_RESEARCH` items.
20. **Change history** — dated log of edits to the module.

Rationale for the template: every field maps to a decision a future agent must make before touching the component. §4 requires the five-dimension status model so an upstream-active provider can still remain fixture-only, unknown-auth, or prohibited for a specific V1 use. §12 (evidence strength) and §14 (redaction) exist specifically to keep the memory corpus clean and secrets out of stored payloads.

---

## 6. Status Vocabulary

SB-1.1 supersedes the earlier single-primary-status model. A module now carries separate dimensions so a provider can be, for example, upstream-active but Printer-fixture-only:

- `upstream_lifecycle`: `ACTIVE`, `SUPERSEDED`, `DEPRECATED`, `UNKNOWN_REQUIRES_RESEARCH`.
- `printer_readiness`: `ACTIVE_READY`, `PARTIAL_WITH_BLOCKER`, `REGISTERED_NOT_READY`, `REFERENCE_ONLY`, `DEFERRED`.
- `printer_role`: `DISCOVERY`, `TOKEN_AGE`, `SAFETY`, `PAPER_REALISM_ONLY`, `CONTEXT_ONLY`, `LABEL_CONTEXT`, `EVIDENCE_RULES`.
- `access_policy`: `KEYLESS_PUBLIC`, `FREE_KEY_REQUIRED`, `UNKNOWN_REQUIRES_RESEARCH`, `PROHIBITED_PAID`.
- `v1_permission`: `ALLOWED_GOVERNED`, `ALLOWED_FIXTURE_ONLY`, `OPERATOR_APPROVAL_REQUIRED`, `PROHIBITED_V1`.

The historical status labels below remain useful shorthand, but they must not collapse these dimensions.

| Status | Meaning | Current holders |
|---|---|---|
| `ACTIVE_READY` | Live transport exists, governed, and fixture/live-proven for its role | Solana public RPC (T3 transport); PumpPortal (transport; T2 not positively live-proven) |
| `REGISTERED_NOT_READY` | Registered in Printer but no working adapter/transport | Helius |
| `PARTIAL_WITH_BLOCKER` | Implemented + fixture-proven but has an open blocker | T3 (DB-persistence gap; live proof pending) |
| `REFERENCE_ONLY` | Documented for correctness; not called by Printer | PumpSwap program ID; Pump bonding-curve program ID |
| `PAPER_REALISM_ONLY` | May only inform paper entry/exit realism, never execution | Jupiter Quote |
| `OPTIONAL_FREE_FALLBACK` | Free, optional; not a required dependency | CoinGecko keyless; Helius free (if ever wired) |
| `DEFERRED` | Deliberately postponed | Metaplex metadata; direct-signature T3 path; T1 |
| `PROHIBITED_V1` | Forbidden in V1 | any paid tier, execution/signing, wallet, private keys |
| `LEGACY_OR_DEPRECATED` | Upstream has superseded what Printer uses | DexScreener `/latest/dex/tokens/`; Jupiter `lite-api` free path; `dex:"raydium"` label |
| `UNKNOWN_REQUIRES_RESEARCH` | Not resolvable from primary sources yet | PumpPortal event schema stability; lite-api keyless guarantee |

---

## 7. Module Inclusion Criteria

A protocol or provider gets a module **only if** it meets at least one inclusion trigger AND passes the exclusion filter.

**Inclusion triggers (any one):**
- Printer currently registers, calls, or normalizes it (A6 evidence).
- Printer stores a field that requires it to interpret (e.g., `dex` label → Raydium context).
- It is a Solana core primitive Printer's evidence path depends on (RPC, SPL Token, Token-2022, tx parsing).
- It is an explicitly planned V1 source in `AGENTS.md` §Source Rules (free-first list).

**Exclusion filter (all must hold):**
- It is free/public or keyless-capable, or explicitly registered as `free_tier_optional`. Paid-only components are `PROHIBITED_V1` and get at most a one-line exclusion note, not a module.
- It is Solana-relevant to Printer's memecoin memory/paper path. Popular but unused protocols (Meteora, Orca, Serum/OpenBook) are **excluded** — SB-0 confirmed they appear only in historical fixtures.
- Including it does not imply execution, signing, or wallet capability.

**Result:** the 21 modules in §4. Meteora/Orca/Serum/OpenBook are excluded by the filter and recorded here as excluded so a future agent does not re-add them "because they are popular."

---

## 8. Task-to-Required-Module Routing

When an agent picks up a Solana task, it MUST read the routed modules before writing anything.

| Task | Required modules |
|---|---|
| Any T3 / token-age work | solana-core-rpc-reference, solana-transaction-instruction-parsing, solana-spl-token-program, solana-token-2022-program, pump-fun-bonding-curve-protocol, pumpportal-api-contract, token-age-evidence-tier-registry, source-governor-evidence-rules |
| Direct-signature T3 design | all of the above (§13) |
| Discovery/selection intake | dexscreener-api-contract, geckoterminal-api-contract, pumpportal-api-contract, solana-mint-addresses |
| Migration/graduation handling | pump-fun-bonding-curve-protocol, pumpswap-amm-protocol, raydium-amm-label-context, pumpportal-api-contract |
| Safety / rug evidence | goplus-api-contract, solana-public-rpc-contract, solana-spl-token-program, solana-token-2022-program |
| Paper quote realism | jupiter-quote-api-contract, jupiter-routing-protocol |
| Market/chain-heat context | coingecko-api-contract, defillama-api-contract, alternative-me-api-contract, geckoterminal-api-contract |
| Any new source adapter | source-governor-evidence-rules + the target provider module + solana-core if on-chain |

---

## 9. Conflict-Resolution Rules

1. **Authority roles stay separate.** Upstream A1-A5 defines the external protocol/API contract. Printer A6 defines current local implementation. A disagreement becomes a documented implementation gap; neither side silently rewrites the other.
2. **Silence is not permission.** If the highest available tier does not formally define a field (e.g., PumpPortal event schema), the conclusion is `UNKNOWN_REQUIRES_RESEARCH`; record each source's role; do not silently pick one interpretation.
3. **Preserve roles on conflict.** When two primary sources disagree (e.g., a program ID asserted by A1 vs an explorer A7), keep both, mark the A7 as corroboration-only, and adopt the A1 value.
4. **Deprecation flags, never silent swaps.** If upstream supersedes a Printer endpoint, mark Printer `LEGACY_OR_DEPRECATED` and record the replacement; do not assume the legacy path still works and do not "fix" it in this reference lane.
5. **Locator vs proof.** A third-party-provided identifier (e.g., a PumpPortal `signature` or pool address) is **locator evidence**. It becomes proof only when an A1–A3 on-chain read independently confirms the exact transaction/account. This rule is binding for all evidence tiers (§13).
6. **No fabrication.** Missing data is recorded as missing/failed (per clean-master-spec §0.7). No source may invent a program ID, endpoint, or field.

---

## 10. Freshness and Stale-Document Policy

- Each module carries a **last-verified date** (§5 field 3), but SB-1.1 replaces the universal 90-day rule with risk-based freshness.
- Provider endpoints, auth policy, quotas, and response schema are `STALE_REVERIFY_REQUIRED` after **30 days** and before any live proof.
- Program layouts, IDLs, instruction semantics, and account layouts are `STALE_REVERIFY_REQUIRED` after **90 days**, and sooner if a protocol migration, program release, or failing proof suggests drift.
- Unresolved high-risk contracts (`UNKNOWN_REQUIRES_RESEARCH`) must be rechecked before every live proof that depends on them.
- Program IDs must be pinned to official repo/tag/commit or official docs where possible, and rechecked on any migration notice.
- **Trigger re-verification immediately** (regardless of age) when: an adapter starts failing with auth/HTTP errors; an upstream changelog announces an endpoint/version change; a Printer live proof contradicts the module; or a program migration/relabel is observed.
- Fixture-only status does **not** exempt a module from freshness. SB-0 showed fixture-only masks drift. Reference correctness is still required.
- Re-verification updates §3 (last-verified) and §20 (change history); it never silently rewrites a rule without a dated entry.

---

## 11. Changelog, Versioning, and Adoption/Verification Gates

### 11.1 Versioning
- The stack is versioned as a set: `SB-STACK v0.1` at first adoption (SB-2). Each module has an independent §20 change history. Program IDs and endpoint URLs are treated as **pinned facts** — changing one requires a dated change-history entry citing the A-tier source that changed.

### 11.2 Adoption gate (what SB-2 must satisfy before the stack is "active")
- The stack does not become authoritative merely by existing. Adoption requires: (a) `README.md` states the authority order and that the stack is **subordinate** to `AGENTS.md` / clean-master-spec / post-rc-build-order / memory-factory-guide / memory-growth-build-order-v2; (b) an independent verifier (SB-1.1) confirms this architecture; (c) each first-batch module is authored to the §5 template with cited authorities; (d) no module unlocks execution, paid tiers, A3, V2-3, or memory/retrieval.

### 11.3 Verification gate
- Every module must pass an independent read (SB-1.1/SB-1.1A then per-module SB-2 verification): authority citations resolve to A1-A5 hosts; all five status dimensions match upstream contract and Printer implementation reality; no prohibited capability is implied; no live endpoint testing was used to author it.

### 11.4 Relationship to the active Printer stack (subordination)
- This stack is a **reference library beneath** the active build order. It never introduces lanes, never reorders V2, never unlocks anything. `AGENTS.md` remains build-discipline law; clean-master-spec remains product law; the V2 memory-growth build order remains the active roadmap. If this stack and the active stack ever conflict, the active stack wins and the stack module is corrected.

---

## 12. Disposition of Every High-Risk SB-0 Blocker

Each disposition cites the primary authority consulted 2026-07-12 and states the Printer rule + status. No production repair is made in this lane.

### 12.1 Jupiter `lite-api.jup.ag` vs `api.jup.ag` + API key — HIGH
**Authority (A3):** Current Jupiter developer docs show a Lite Swap quote path at `https://lite-api.jup.ag/swap/v1/quote`, while broader Jupiter API/portal documentation has separate API-key and Ultra/Swap lifecycle guidance.
**Finding:** Printer uses `lite-api.jup.ag/swap/v1/quote` (primary) and `quote-api.jup.ag/v6/quote` (legacy), with no key header, and the adapter is fixture-only. SB-1.1 does not prove a stable keyless live contract across Jupiter Lite/API/Ultra docs.
**Disposition:** `PAPER_REALISM_ONLY` + `UNKNOWN_REQUIRES_RESEARCH` for live wiring. **Contained:** Printer makes no live Jupiter call today. Rule: keep fixture-only; do not wire live Jupiter without first reconciling current Jupiter Lite/API/Ultra auth and endpoint guidance. Do not adopt an API-key path silently.

### 12.2 Jupiter Metis / Legacy Swap vs current Router/API generations — MEDIUM
**Authority (A3):** Jupiter docs distinguish Lite/API/Ultra paths and still expose Swap quote fields Printer fixtures consume (`outAmount`, `priceImpactPct`, `routePlan`). Metis / Legacy Swap should be treated as historical or superseded upstream, while newer Jupiter Meta-Aggregator / Router / API generations are current upstream paths.
**Disposition:** No schema break is proven for the fixture fields Printer reads. Keep `PAPER_REALISM_ONLY`, fixture-only, and no transaction execution. Treat exact live endpoint/auth/lifecycle as `UNKNOWN_REQUIRES_RESEARCH` before any live paper-realism quote lane.

### 12.3 Stale `dex:"raydium"` migration label — HIGH
**Authority (A1/A3):** Pump public docs confirm a permissionless `migrate` instruction to an AMM. PumpSwap/PumpPortal references indicate PumpSwap support, but SB-1.1 did not verify an official percentage share for graduations.
**Finding:** Printer sets `"dex":"raydium"` for `pumpfun_migration_stream` and extracts `newRaydiumPool`. The field name and label are not safe venue proof.
**Disposition:** `LEGACY_OR_DEPRECATED` label. Rule for SB-2+: the migration destination must be treated as `UNKNOWN_UNTIL_ONCHAIN_VERIFIED`; the literal `raydium` label must not be trusted as the venue. Confirm the actual pool owner/program on-chain before it drives any memory label. No code change in this lane.

### 12.4 DexScreener legacy token endpoint — MEDIUM
**Authority (A4):** `docs.dexscreener.com/api/reference` lists `/tokens/v1/{chainId}/{tokenAddresses}`, `/token-pairs/v1/{chainId}/{tokenAddress}`, `/token-profiles/latest/v1`. There is **no** `/latest/dex/tokens/{tokenAddresses}` endpoint. No API key; 60 req/min (pairs up to ~300).
**Finding:** Printer's `DEXSCREENER_TOKEN_URL_TEMPLATE = /latest/dex/tokens/{token_mint}` is not in current docs.
**Disposition:** `LEGACY_OR_DEPRECATED`. Rule: migrate to `/tokens/v1/{chainId}/{tokenAddresses}` when the token endpoint is next used live. Pair endpoint `/latest/dex/pairs/{chainId}/{pairId}` and `/latest/dex/search` remain valid. Fixture-only today, so no live breakage.

### 12.5 CoinGecko no-key vs demo-key — MEDIUM → downgraded to LOW
**Authority (A4):** `docs.coingecko.com/docs/keyless-public-api` — CoinGecko **officially supports a keyless public API** (no key, no sign-up) at `api.coingecko.com/api/v3`, with lower rate limits "not suitable for production/high-frequency"; the demo key raises this to 100 calls/min.
**Finding:** Printer's keyless `api.coingecko.com/api/v3/simple/price` path is officially supported.
**Disposition:** `OPTIONAL_FREE_FALLBACK`. Rule: keyless is acceptable for **low-frequency** SOL/BTC/ETH context only (Printer uses it as context, ~15–20 min cadence per clean-master-spec §3.8). Not a blocker. If cadence ever rises, a free demo key is the sanctioned upgrade — an operator decision, not automatic.

### 12.6 PumpPortal `newRaydiumPool` field accuracy — MEDIUM
**Authority (A4):** PumpPortal real-time docs do not publish a stable event schema with authoritative venue semantics. SB-1.1 also did not verify keyless/auth policy as a stable official production contract.
**Disposition:** `UNKNOWN_REQUIRES_RESEARCH`. Rule: treat `newRaydiumPool` as a **pool-address locator**, not a venue assertion; confirm venue on-chain (pool owner program). Do not rely on the field name.

### 12.7 PumpPortal event field schema (`tokenCreatedAt`, etc.) — MEDIUM
**Authority (A4):** No official schema for `subscribeNewToken` event fields. Printer's `tokenCreatedAt → createdTimestamp → timestamp` priority chain is derived from V2-2AF design + V2-2AE live diagnostics (A6), not from A4.
**Disposition:** `UNKNOWN_REQUIRES_RESEARCH`. Rule: T2 evidence from these fields is **best-effort**; a schema change could silently break it. The safer authoritative age path is T3/on-chain. Record that T2 is fixture-proven but not positively live-proven (V2-2AH inconclusive).

### 12.8 `confirmed` vs `finalized` commitment for token-age — LOW
**Authority (A3):** Solana RPC overview documents commitment levels and the tradeoff between recency and finality.
**Disposition:** Do not pre-decide that `confirmed` is always sufficient for T3. The commitment level, any minimum-finality condition, and any extremely-recent-mint handling must be explicit SB-6 design decisions. No token-age evidence may satisfy A3 until the approved finality contract passes.

### 12.9 Helius free-tier role — LOW
**Authority (A4):** `helius.dev/docs/billing/plans` — the free plan **requires a free dashboard API key** (1M credits/mo, 10 RPC req/s); there is no keyless Helius path.
**Finding:** `helius_free` is registered (`free_tier_optional`) but has **no adapter**.
**Disposition:** `REGISTERED_NOT_READY` / `OPTIONAL_FREE_FALLBACK` / `DEFERRED`. Rule: the keyless **Solana public RPC is the primary** on-chain path; Helius stays deferred. If ever wired, it needs a free key (operator sign-up decision) and must never become a required dependency. A free key is not a *paid* dependency, but adopting it is an explicit choice, not a default.

### 12.10 Program IDs not in Printer source — LOW
**Authority (A1):** Pump bonding-curve `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` confirmed from `pump-public-docs`; PumpSwap `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` confirmed (A3/A7 corroboration). Neither is hardcoded in Printer.
**Disposition:** `REFERENCE_ONLY`. Rule: record both IDs in their protocol modules. They become required only when Printer needs to **verify a pool/mint belongs to a program** (e.g., §12.3 venue confirmation, or Pump-`create` verification in direct-signature T3). Not needed for current fixture-only posture.

### 12.11 T3 failure-provenance DB persistence gap — MEDIUM
**Authority (A6):** V2-2AL.4B (`VERIFICATION_PARTIAL_WITH_BLOCKER`) — the 8 provenance fields survive the normalizer and governed execution result but are **not persisted**; `printer_source_failures` has no `normalized_payload_json` column.
**Disposition:** This is **observability hardening**, not required evidence-generation infrastructure. Justification: the missing fields are failure audit trace, not age evidence; T3 success and A3 gating do not depend on them; fail-closed behavior is intact. Classify as `PARTIAL_WITH_BLOCKER` -> **deferred observability hardening**, not a prerequisite for direct-signature T3 design or fixture proof. Before a bounded live T3 proof, the eight failure fields should be preserved either in durable DB storage or explicitly in the proof artifact. No migration is authorized by SB-1.1.

### 12.12 T1/T2/T3/T4/T5 definitions and current status — resolved (from SB-0.1)
- **T1** (`DEFINED_HISTORICALLY_BUT_TECHNICAL_CONTRACT_UNRESOLVED`): highest-trust direct creation timestamp; defined in V2-2O; never implemented. `getAccountInfo` does not return the mint creation transaction block time, so it must not be listed as a T1 source by itself. Candidate future paths require an independently verified creation signature/transaction, an upstream canonical creation event with a timestamp, or another explicitly designed source contract. A direct-signature T3 (§13) may reach T1-grade reliability; whether that is relabeled T1 or "upgraded T3" is an SB-2 naming decision.
- **T2** (`ACTIVE_READY` impl / not positively live-proven): PumpPortal timestamp fields; fixture-proven (82 tests); V2-2AH inconclusive.
- **T3** (`PARTIAL_WITH_BLOCKER`): on-chain history-walk; fixture-proven (132 tests); two live proofs failed safely; AL.4A/AL.4B done; AL.5 pending.
- **OBSERVED_LIVE_LAUNCH** (impl / not positively live-proven): PumpPortal event without timestamp; does not satisfy A3.
- **T4_PAIR_ONLY** (`REFERENCE_ONLY` for age): pair-age context; never `token_age_seconds`.
- **T5_UNKNOWN**: null sentinel; current universal state.
- **A3 gate:** only T2/T3 success can satisfy `token_age_seconds is not None`.

### 12.13 Metaplex token metadata — LOW / DEFERRED
**Authority:** SB-0 §7 — not in production; name/symbol come from DEX sources. **Disposition:** `DEFERRED`. Add a note in `solana-core` that on-chain name/symbol verification (Metaplex) is a future safety option, not a V1 requirement.

---

## 13. First Modules Required for Direct-Signature T3

**Design premise (Rule 5, §9):** the PumpPortal `signature` is **locator evidence only**. Confirmed by A1: `pump-public-docs` describes a `create` instruction but carries **no timestamp**; therefore the authoritative creation time can only come from Solana RPC independently proving the exact mint-initialization transaction and reading its `blockTime`.

**Direct-signature T3 (concept, not implemented here):** instead of walking `getSignaturesForAddress` history (which exhausted the page cap on high-history mints in V2-2AL.3), start from a **known creation signature** (from a PumpPortal launch/create event, or the oldest signature page for the mint), call `getTransaction`, and require that the transaction **independently contains** an exact requested-mint creation or mint-initialization path. The design must cover current and historical Pump creation instructions found in the pinned official IDL/docs, plus SPL Token / Token-2022 `initializeMint` / `initializeMint2` where relevant. It must handle top-level and inner instructions, parsed and compiled forms, versioned transactions, and address lookup tables where relevant. Only then, and only after the SB-6-approved finality contract passes, is `blockTime` accepted as creation time. If RPC does not confirm the exact instruction on the exact requested mint, the signature is rejected and the result is fail-closed (no age).

**Minimum module set that must exist and be authored before direct-signature T3 can be safely designed:**

1. `solana-core-rpc-reference.md` — `getTransaction`, `getSignaturesForAddress`, `getAccountInfo`, `getBlockTime`; commitment policy (§12.8); encodings.
2. `solana-transaction-instruction-parsing.md` — `jsonParsed` vs compiled instructions; **inner instructions** (a mint-init can be a CPI inside the Pump `create` tx); **versioned transactions + address lookup tables** (must resolve accounts correctly to attribute an instruction to the target mint); `blockTime` semantics.
3. `solana-spl-token-program.md` — `initializeMint` / `initializeMint2` identification; `Mint::LEN=82`.
4. `solana-token-2022-program.md` — AccountType@165 / extensions@166 (the V2-2AL byte-82 bug is the canonical failure to avoid).
5. `pump-fun-bonding-curve-protocol.md` — program `6EF8...`; current and historical Pump creation instructions from pinned official IDL/docs; bonding-curve PDA; exact requested-mint attribution requirements.
6. `pumpportal-api-contract.md` — the launch/create event and its `signature`, explicitly framed as **locator only**.
7. `token-age-evidence-tier-registry.md` — where direct-signature output lands (upgraded T3 vs T1), and the A3 gate.
8. `source-governor-evidence-rules.md` — governed single-`getTransaction` execution, per-token RPC budget, failure provenance, host-only redaction, fail-closed semantics.

**Blocker acknowledgement:** direct-signature T3 remains **undesigned and unimplemented**. This lane only identifies the module prerequisites; T3 stays paused, A3 stays locked. The DB-persistence gap (§12.11) should be closed before the next *live* T3 proof, though it is not a prerequisite for the *design*.

---

## 14. Phased SB-2+ Build Sequence

Each phase is documentation/architecture-first and preserves all V1 locks. No phase here unlocks execution, A3, V2-3, memory, or retrieval.

- **SB-1.1** — Independent architecture verification. Complete at commit `b0b04e8`.
- **SB-1.1A** — Consistency cleanup recorded in this document with `ARCHITECTURE_CONSISTENCY_PASS`.
- **SB-2** — Author the Solana-core module batch (rpc-reference, transaction-instruction-parsing, spl-token, token-2022, mint-addresses) to the §5 template, cited to A1-A3. Adopt `SB-STACK v0.1` README with subordination statement.
- **SB-3** — Author the protocol modules (pump-fun, pumpswap, raydium-context, jupiter-routing), cited to A1/A3, including the §12.3 venue-confirmation rule and §12.10 program IDs.
- **SB-4** — Author the provider modules (10), cited to A4, encoding the §12 dispositions (Jupiter key policy, DexScreener token endpoint, CoinGecko keyless, Helius deferred, PumpPortal locator rule).
- **SB-5** — Author the two cross-cutting modules (token-age-evidence-tier-registry, source-governor-evidence-rules).
- **SB-6** — Direct-signature T3 **design** (not implementation), consuming SB-2/3/5 modules; keep T3/A3 paused.
- **SB-7** — Optional: DexScreener `/tokens/v1` + `dex` venue-confirmation reference-code proposal (design only; still fixture-first).

This sequence is a **reference-authoring** sequence; it does not reorder or compete with the active V2 memory-growth build order.

---

## 15. Money-Usefulness Contribution

Printer's path to a realistic paper money-machine runs through **clean, correctly-labeled memory**. This stack contributes by:

- **Preventing dirty labels at the source.** The stale `dex:"raydium"` relabel (§12.3) and legacy endpoints (§12.1, §12.4) would otherwise write mislabeled venue/age evidence into memory, corrupting future retrieval and paper decisions. Correct upstream facts keep the corpus honest.
- **Protecting the age-evidence spine.** T2/T3/A3 correctness (§12.7, §12.12, §13) is what lets Printer ever gate on token age — a core memecoin-risk signal (late-buy traps, fresh-mint rugs). Locator-vs-proof discipline (§9 Rule 5) stops a mislabeled creation time from faking a "known-age" setup.
- **Keeping V1 free and safe.** Confirming keyless/free paths (CoinGecko keyless, public RPC) and flagging key/paid tiers (Jupiter, Helius) preserves the "no paid API dependency" law while still letting Printer collect context.
- **Reducing agent re-derivation cost.** A single cited module per component means future Solana lanes start from verified facts instead of re-guessing endpoints — fewer failed live proofs (e.g., the Token-2022 byte-82 and page-cap failures), faster clean-memory growth.

This is a **learning-efficiency and correctness** contribution, not a profit claim.

---

## 16. What This Lane Still Does Not Unlock

- No production code, tests, or migrations changed.
- No source-stack files created (design only); the stack is **not adopted**.
- No `AGENTS.md` change.
- T3 remains paused; A3 remains locked; the direct-signature path remains undesigned/unimplemented.
- V2-3 remains paused; the staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.
- No memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD, no positions/trades/audits/PnL.
- No live RPC/API calls, no DB mutation, no discovery/source fetching, no live endpoint testing.
- No paid dependency added; no Source Governor / Central Scheduler rule weakened.

---

## 17. Proof Required Before Adoption

Before the stack becomes authoritative (SB-2 adoption), the following must hold:

1. **SB-1.1 independent verification and SB-1.1A consistency cleanup** pass: authority order, module tree, five-dimension status model, template, and every §12 disposition are internally consistent; no live endpoint testing used.
2. Each first-batch module is authored to the **20-section template** with resolvable A-tier citations and a last-verified date.
3. `README.md` states subordination to `AGENTS.md` / clean-master-spec / post-rc-build-order / memory-factory-guide / memory-growth-build-order-v2, and the authority order (A1–A7).
4. A risky-language / lock-preservation scan confirms no module implies execution, paid tiers, A3 unlock, V2-3 unlock, memory/retrieval unlock, scoring/ranking/confidence, or embeddings/vectors.
5. Program IDs and endpoints in modules match their cited A-tier source exactly (pinned-fact check).

---

## 18. Checks Run and Commit

Static/read-only only (no runtime, no DB, no live calls):

- `git diff --check`
- `git status --short`
- `git diff --stat`
- `git diff --name-only`

Commit contains **only** this architecture report:
`Add SB-1 Solana builder source-stack architecture`

SB-1.1 verification commit:
`b0b04e8 Verify and correct SB-1 Solana source-stack architecture`

SB-1.1A consistency cleanup:
`Finish SB-1 Solana architecture consistency cleanup`

---

## 18A. SB-1.1 Independent Verification and Correction Record

**Lane:** SB-1.1 - Independent Solana Source-Stack Architecture Verification and Correction
**Type:** Verification/correction only. No production code, tests, migrations, DB mutation, live RPC/API calls, discovery, scheduler/runtime, source-stack adoption, or AGENTS.md modification.
**Executor:** Codex standard/balanced
**Date:** 2026-07-12
**Target SB-1 commit verified:** `606287e Add SB-1 Solana builder source-stack architecture`
**Verdict:** `ARCHITECTURE_VERIFICATION_PASS_WITH_BLOCKERS`

### 18A.1 Scope and boundaries

SB-1.1 verifies and corrects the SB-1 report only. It does not create files under `docs/solana-builder-source-of-truth/`, does not adopt the source stack, does not resume T3, does not unlock A3, does not resolve staged/native 15m, and does not allow V2-3.

### 18A.2 Official authorities verified

- Solana clusters and RPC documentation: `https://solana.com/docs/references/clusters`, `https://solana.com/docs/rpc`, `https://solana.com/docs/rpc/http/gettransaction`
- SPL Token official repository: `https://github.com/solana-program/token`
- Token-2022 official repository: `https://github.com/solana-program/token-2022`
- Pump.fun public docs: `https://github.com/pump-fun/pump-public-docs`
- PumpPortal real-time and PumpSwap docs: `https://pumpportal.fun/data-api/real-time/`, `https://pumpportal.fun/data-api/pump-swap/`
- Jupiter developer docs: `https://dev.jup.ag/docs/swap-api/get-quote`
- DexScreener API docs: `https://docs.dexscreener.com/api/reference`

### 18A.3 Corrections made

1. **Authority model corrected.** Upstream authorities define external protocol/API contracts. Printer code, tests, migrations, and adopted docs define current Printer implementation. A disagreement is now a documented implementation gap; neither source silently rewrites the other.
2. **Status model corrected.** The single status vocabulary is superseded by dimensions: `upstream_lifecycle`, `printer_readiness`, `printer_role`, `access_policy`, and `v1_permission`.
3. **Freshness policy corrected.** Provider endpoint/auth/schema facts require 30-day freshness before live proof; program layouts/IDL/instruction facts use 90-day freshness plus change triggers; unresolved high-risk contracts require recheck before each dependent live proof.
4. **Solana cluster endpoint corrected.** Official docs now list `https://api.mainnet.solana.com`; Printer currently uses `https://api.mainnet-beta.solana.com`. This is an implementation gap/reverify item, not an automatic code change.
5. **Token-2022 authority corrected.** The canonical module should cite `https://github.com/solana-program/token-2022`, not the archived `solana-labs/solana-program-library` path.
6. **Jupiter lifecycle/auth corrected.** SB-1.1 no longer states a solved `api.jup.ag` key rule for Printer. Current docs show `lite-api.jup.ag`, but Lite/API/Ultra auth guidance remains `UNKNOWN_REQUIRES_RESEARCH` before live wiring. Printer remains fixture-only and paper-realism-only.
7. **PumpPortal auth corrected.** SB-1.1 no longer equates subscription methods with a guaranteed no-key production policy. PumpPortal auth/keyless status remains `UNKNOWN_REQUIRES_RESEARCH`.
8. **Pump migration venue corrected.** The unsupported PumpSwap graduation-percentage statement is removed. `newRaydiumPool` is a pool-address locator only. `dex:"raydium"` is label context only. Actual venue is unknown until on-chain owner/program verification.
9. **T1 definition corrected.** `getAccountInfo` does not return creation-transaction block time and must not be described as a T1 source by itself. T1 is `DEFINED_HISTORICALLY_BUT_TECHNICAL_CONTRACT_UNRESOLVED`.
10. **T3 provenance status corrected.** Failure-provenance persistence is observability hardening. It does not block direct-signature design or fixture proof, but the eight failure fields should be preserved in durable storage or an explicit proof artifact before bounded live proof.
11. **Direct-signature T3 requirements corrected.** The design must handle top-level and inner instructions, parsed and compiled forms, versioned transactions, and address lookup tables where relevant.

### 18A.4 Remaining unknowns and blockers

- Jupiter Lite/API/Ultra live quote auth and lifecycle contract remains `UNKNOWN_REQUIRES_RESEARCH`.
- PumpPortal event schema stability remains `UNKNOWN_REQUIRES_RESEARCH`.
- PumpPortal auth/keyless production policy remains `UNKNOWN_REQUIRES_RESEARCH`.
- `newRaydiumPool` venue accuracy remains `UNKNOWN_REQUIRES_RESEARCH` until on-chain owner/program verification.
- Direct-signature T3 remains undesigned and unimplemented.
- T3 failure-provenance durable persistence remains a live-proof auditability concern.
- Staged/native 15m remains `PARTIAL - DEFERRED, NOT RESOLVED`.

### 18A.5 Final module count and T3-critical module set

The final proposed module count remains **21**:

- 5 Solana core modules
- 4 protocol authority modules
- 10 provider API contract modules
- 2 cross-cutting governance/evidence modules

The T3-critical module set remains **8**:

1. `solana-core-rpc-reference.md`
2. `solana-transaction-instruction-parsing.md`
3. `solana-spl-token-program.md`
4. `solana-token-2022-program.md`
5. `pump-fun-bonding-curve-protocol.md`
6. `pumpportal-api-contract.md`
7. `token-age-evidence-tier-registry.md`
8. `source-governor-evidence-rules.md`

### 18A.6 Locked-state confirmation

SB-1.1 does not adopt the source stack and does not unlock any downstream capability. T3 remains paused. A3 remains locked. Staged/native 15m remains deferred. V2-3 remains paused. Retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper audits, PnL, runtime expansion, scheduler expansion, wallet/private-key/signing/live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors remain locked.

### 18A.7 Exact next lane

If the operator accepts this corrected architecture, the exact next lane is:

`SB-2 - Author Solana Core Source-Stack Modules`

SB-2 must still be documentation/module authoring only unless the operator explicitly approves a narrower implementation lane.

---

## 18B. SB-1.1A Consistency Cleanup Record

**Lane:** SB-1.1A - Solana Source-Stack Architecture Consistency Cleanup
**Type:** Narrow documentation correction only. No source-stack adoption, production code, tests, migrations, DB mutation, live RPC/API calls, discovery, scheduler/runtime, AGENTS.md modification, T3 resume, A3 unlock, staged/native 15m unlock, or V2-3 unlock.
**Executor:** Codex standard/balanced
**Date:** 2026-07-12
**Anchors:** SB-1 `606287e`; SB-1.1 `b0b04e8`
**Verdict:** `ARCHITECTURE_CONSISTENCY_PASS`

### 18B.1 Corrections made

1. Removed the remaining statement that upstream automatically wins over Printer implementation. The consistent rule is now: upstream authorities define external protocol/API contracts; Printer code, tests, migrations, and adopted docs define current implementation; disagreement creates an implementation gap; neither silently rewrites the other.
2. Updated the 20-section module template so each module must record `upstream_lifecycle`, `printer_readiness`, `printer_role`, `access_policy`, and `v1_permission`.
3. Clarified that historical shorthand labels are explanatory only and must not collapse the five-dimension model.
4. Corrected PumpSwap authority: official `pump-fun/pump-public-docs` repository docs, IDL, and SDK are A1/A2 protocol authority; PumpPortal PumpSwap material is A4 provider documentation. SB-3 must pin exact official repo commit/file paths where available.
5. Corrected direct-signature T3 prerequisites so they cover current and historical Pump creation instructions found in pinned official IDL/docs, preserve exact requested-mint attribution, and keep top-level/inner, parsed/compiled, versioned-transaction, and ALT requirements.
6. Changed the T3 commitment conclusion so `confirmed` vs `finalized` and any minimum-finality condition are explicit SB-6 design decisions. No token-age evidence may satisfy A3 until the approved finality contract passes.
7. Corrected Jupiter wording: Metis / Legacy Swap is historical or superseded upstream; newer Jupiter Meta-Aggregator / Router / API generations are current upstream paths; exact live auth and endpoint contract remains `UNKNOWN_REQUIRES_RESEARCH`; Printer remains `PAPER_REALISM_ONLY` and fixture-only; transaction execution remains prohibited.
8. Removed stale process text that treated SB-1.1 as the next lane. The next lane is now consistently `SB-2 - Author Solana Core Source-Stack Modules`.

### 18B.2 Remaining unknowns

- Jupiter live auth/endpoint/lifecycle contract remains `UNKNOWN_REQUIRES_RESEARCH`.
- PumpPortal event schema and production auth/keyless policy remain `UNKNOWN_REQUIRES_RESEARCH`.
- `newRaydiumPool` venue accuracy remains `UNKNOWN_REQUIRES_RESEARCH` until on-chain owner/program verification.
- Direct-signature T3 remains undesigned and unimplemented.
- T3 failure-provenance durable persistence remains a live-proof auditability concern.
- Staged/native 15m remains `PARTIAL - DEFERRED, NOT RESOLVED`.

### 18B.3 Lock confirmation

SB-1.1A does not adopt the source stack. T3 remains paused. A3 remains locked. Staged/native 15m remains deferred. V2-3 remains paused. Retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper audits, PnL, source fetching, scheduler/runtime expansion, wallet/private-key/signing/live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors remain locked.

---

## 19. Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality / money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Stale `dex:"raydium"` label persists | Mislabels migration venue because the field/label is not venue proof | Wrong venue evidence -> dirty migration memory | False continuity between token and pool | §12.3 venue-confirmation rule; treat venue as unknown until on-chain owner/program verification | On-chain pool-owner check design (SB-3) | Label trusted as venue without on-chain confirmation |
| Jupiter live wiring with unresolved endpoint/key contract | Lite/API/Ultra auth and lifecycle guidance needs recheck | Failed quotes -> missing exit-realism evidence, or accidental key/paid dependency | Broken paper-realism path or lock violation | Keep fixture-only; operator-explicit before any live/keyed wiring | §12.1 disposition honored in jupiter module | Live Jupiter call added without operator sign-off |
| DexScreener legacy token endpoint used live | `/latest/dex/tokens/` not in current docs | Silent 404 → missing token evidence, dirty intake | Discovery/intake gaps | Migrate to `/tokens/v1/` before live token calls | §12.4 rule in dexscreener module | Legacy endpoint called live |
| PumpPortal schema drift | No official event schema | T2 age evidence silently breaks | Fake/absent token age | Treat T2 as best-effort; prefer T3; locator-vs-proof rule | §12.7 in pumpportal module | T2 trusted without schema contract |
| PumpPortal signature treated as proof | Pump docs carry no timestamp | Fake creation time → fake known-age setup | A3 gated on bad age | §9 Rule 5: RPC must confirm exact init tx | §13 direct-signature design | Signature accepted without RPC confirmation |
| T3 failure-provenance gap unaddressed before live proof | Failure trace may be lost outside direct proof artifacts | Live T3 failures hard to diagnose | Repeated blind live-proof failures | Preserve eight failure fields either in durable storage or explicit live-proof artifact | V2-2AL.4C verification or proof-artifact acceptance | Live proof proceeds without enough failure trace |
| Stack treated as a competing build order | Could reorder/skip V2 lanes | Roadmap drift, premature unlocks | False readiness | Subordination statement + adoption gate (§11) | SB-1.1/SB-1.1A verification | Any module introduces a lane or unlock |
| Fixture-only masks further drift | Endpoints change unnoticed | Reference rot -> future live breakage | Silent staleness | Risk-based freshness: 30 days for provider endpoint/auth/schema, 90 days for program layouts, event triggers anytime (§10) | Freshness re-verify log | Stale module used for live work |
| Helius/CoinGecko key creep | Free-but-keyed tiers | Sign-up/paid dependency creep vs V1 law | Lock violation | Keep public RPC primary; keyless CoinGecko; key = operator decision | §12.5/§12.9 dispositions | Key added as default dependency |
| Over-inclusion of popular protocols | Meteora/Orca/Serum not used | Wasted modules, false coverage | Scope creep | Inclusion/exclusion filter (§7) | Module-count check | Unused protocol module added |
| Metaplex metadata gap | Name/symbol from DEX only | Impersonation/copycat risk in safety memory | Weak safety labels | Deferred note in solana-core (§12.13) | SB-3 safety review | Name/symbol trusted as verified on-chain |

---

## 20. Final Verdict

```text
VERDICT: ARCHITECTURE_COMPLETE_WITH_BLOCKERS
SB_1_1_VERDICT: ARCHITECTURE_VERIFICATION_PASS_WITH_BLOCKERS
SB_1_1A_VERDICT: ARCHITECTURE_CONSISTENCY_PASS
LANE: SB-1
EXECUTOR: Claude Opus 4.8
DATE: 2026-07-12
SB_1_1_EXECUTOR: Codex standard/balanced

AUTHORITY_HIERARCHY: A1 deployed-program/official repo > A2 IDL/official SDK >
  A3 protocol dev docs > A4 provider API docs > A5 changelog/release notes >
  A6 governed Printer payloads/local evidence > A7 third-party (corroboration only)

UPSTREAM_AUTHORITIES_REVIEWED (primary sources, 2026-07-12):
  - Solana RPC/commitment/clusters (solana.com/docs)
  - SPL Token (github.com/solana-program/token)
  - Token-2022 (github.com/solana-program/token-2022)
  - Pump.fun program (github.com/pump-fun/pump-public-docs) — program 6EF8…
  - PumpSwap (github.com/pump-fun/pump-public-docs docs/IDL/SDK; PumpPortal PumpSwap docs are A4 provider material)
  - Jupiter Swap API (dev.jup.ag) — lite/api/ultra auth and lifecycle need recheck
  - DexScreener (docs.dexscreener.com) — /tokens/v1 current; /latest/dex/tokens legacy
  - CoinGecko (docs.coingecko.com) — keyless public API officially supported
  - Helius (helius.dev/docs) — free tier requires free key; 10 RPC req/s
  - PumpPortal, GeckoTerminal, GoPlus, DefiLlama, Alternative.me (provider docs)

MODULE_TREE: docs/solana-builder-source-of-truth/ (21 modules: 5 core, 4 protocol,
  10 provider, 2 cross-cutting) with protocol/provider separation

MAJOR_DECISIONS:
  - Authority order A1-A7; upstream defines external contracts; Printer code defines current implementation; disagreement => documented implementation gap
  - Locator-vs-proof rule binds all evidence tiers (PumpPortal signature = locator only)
  - dex:"raydium" label = LEGACY_OR_DEPRECATED; venue is UNKNOWN until on-chain verified
  - Jupiter lite-api = PAPER_REALISM_ONLY; live auth/lifecycle UNKNOWN_REQUIRES_RESEARCH; fixture-only contains it
  - CoinGecko keyless = OPTIONAL_FREE_FALLBACK (blocker downgraded to LOW)
  - Helius = REGISTERED_NOT_READY/DEFERRED (needs free key; public RPC stays primary)
  - T3 confirmed-vs-finalized commitment and minimum finality are SB-6 design decisions
  - T3 failure-provenance gap = observability hardening; live proof needs durable trace or explicit proof artifact
  - 20-section module template; risk-based freshness; subordinate to active stack

UNRESOLVED (UNKNOWN_REQUIRES_RESEARCH):
  - Jupiter lite-api.jup.ag keyless guarantee
  - PumpPortal event schema stability
  - PumpPortal auth/keyless production policy
  - newRaydiumPool field venue accuracy (confirm on-chain)

FIRST_MODULES_FOR_T3 (8): solana-core-rpc-reference, solana-transaction-instruction-parsing,
  solana-spl-token-program, solana-token-2022-program, pump-fun-bonding-curve-protocol,
  pumpportal-api-contract, token-age-evidence-tier-registry, source-governor-evidence-rules

SOURCE_STACK_ADOPTED: NO (design only; no docs/solana-builder-source-of-truth/ files created)
PRODUCTION_CODE_CHANGES: NONE
LIVE_RPC_API_CALLS: NONE
LIVE_ENDPOINT_TESTING: NONE
DB_MUTATION: NONE
AGENTS_MD_CHANGED: NO
A3_STATUS: LOCKED
V2_3_STATUS: PAUSED
T3_STATUS: PAUSED (direct-signature path undesigned; AL.5 pending)
STAGED_NATIVE_15M_BLOCKER: PARTIAL - DEFERRED, NOT RESOLVED
NEXT_LANE: SB-2 - Author Solana Core Source-Stack Modules
```

---

## 21. Sources (primary, verified 2026-07-12)

- Solana RPC / commitment / clusters — https://solana.com/docs/rpc , https://solana.com/docs/references/clusters , https://solana.com/docs/rpc/http/gettransaction
- SPL Token — https://github.com/solana-program/token
- Token-2022 — https://github.com/solana-program/token-2022
- Pump.fun program — https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md
- PumpSwap — https://github.com/pump-fun/pump-public-docs , https://pumpportal.fun/data-api/pump-swap/
- Jupiter Swap API — https://dev.jup.ag/docs/swap-api/get-quote
- DexScreener — https://docs.dexscreener.com/api/reference
- CoinGecko keyless — https://docs.coingecko.com/docs/keyless-public-api
- Helius plans — https://www.helius.dev/docs/billing/plans
- PumpPortal — https://pumpportal.fun/data-api/real-time/
- GeckoTerminal — https://apiguide.geckoterminal.com/
- GoPlus — https://docs.gopluslabs.io/reference/solanatokensecurityusingget
- DefiLlama — https://api-docs.defillama.com/
- Alternative.me — https://alternative.me/crypto/api/
