# Printer V1 V2-9.7C Solana Agent-Assistance & Source-Contract Readiness Audit

## 1. Executive Verdict

`V2_9_7C_SOLANA_AGENT_ASSISTANCE_READINESS_AUDIT_PASS`

There is a grounded, minimal recommendation for restricted developer assistance
and targeted source-contract documentation, and the one pre-design dependency is
explicit.

Headline findings, each grounded in a primary official source verified during
this audit (access date 2026-07-18):

- An **official Solana Developer MCP exists**, owned by the Solana Foundation,
  hosted at `https://mcp.solana.com/mcp` over Streamable HTTP, **keyless**, and
  **read-only** (documentation retrieval/search + static Rust analysis; no
  wallet, signing, transaction, or RPC-mutating tools). Recommended
  `ALLOW_WITH_RESTRICTIONS` for its four documentation tools only.
- **Both Codex and Claude Code support remote MCP**, so the Solana server is
  technically connectable from either — but this audit **installs and connects
  nothing**.
- A **custom Printer MCP is not justified** and is recommended `DEFERRED`
  (effectively rejected for now): the repository shows no evidence that
  file-based navigation is insufficient.
- The two unsourced evidence pillars from V2-9.7C.0 — **wallet/participant
  authenticity (R12)** and **quantitative event-time execution (R13)** — are
  **not** resolved by any documentation or MCP. A documentation helper improves
  implementation accuracy; it does not create evidence Printer cannot collect.
- The only dependency that is `REQUIRED_BEFORE_V2_9_7C_DESIGN` is a small,
  documentation-only governance step (an authority/reproducibility policy for
  external research), which the existing Solana Builder README already 90%
  satisfies. Everything else is `OPTIONAL_DEVELOPER_ASSISTANCE`, `DEFERRED`, or
  gated to later lanes.

This PASS authorizes no MCP installation, connection, custom MCP development,
documentation adoption, code, schema, runtime, memory growth, retrieval,
decision, position, PnL, wallet, signing, execution, or real-funds capability.
The full V2-9.7C Operational Memory Factory design is **not** begun here.

## 2. Scope and Preflight

Audit and documentation only. No MCP installed or connected; no Codex/Claude/
machine/user/repository MCP configuration changed; no custom MCP created; no
code/test/schema/migration/command/runtime change; no discovery/source/API/RPC/
adapter/scheduler/factory/proof/memory/DB action.

- HEAD: exact `704fa51` (`Adopt manipulation-aware money-usefulness laws`).
- Tracked tree: clean (zero tracked modifications).
- Runtime: no Python process; the only proof/campaign-pattern process match
  (PID 18848) was this audit's own transient `Get-CimInstance` query and had
  already exited. `Get-CimInstance` was available, so no honesty limitation on
  process inspection applies.
- Locks: no proof or campaign lock; `operator-runs/v2-9-one-proof.lock.json`
  absent; no `.lock.json` under the repository root.
- Persistent DB hash (unchanged, not read for content):
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.
- Unrelated untracked artifacts: 165 baselined and untouched.

**Web research used** primary official sources only (Anthropic, OpenAI, and
Solana Foundation domains). One official page (`solana.com/developers/guides/
getstarted/intro-to-ai`) returned a connection error and is recorded as
`CURRENT_DOCUMENTATION_GAP` where it would have added detail; the hosted MCP
endpoint and the Foundation's own repository were both reachable and are the
primary basis for the Solana MCP findings.

### Source stack read

Active Printer V1 stack (AGENTS.md, clean-master-spec, post-rc-build-order,
memory-factory-guide, current-state audit, build-order-v2, and the adopted
manipulation-aware money-usefulness product law), plus the V2-9.7C.0 requirements
audit, the V2-9.7C.0A adoption closeout, and the V2-9.7B focused closeout. The
complete subordinate Solana Builder stack (12 modules + the SB-1 architecture
doc) was inventoried (§8).

## 3. Official Solana Resource Inventory

| Resource | Owner | Primary source (access 2026-07-18) | Purpose |
|---|---|---|---|
| Solana Developer MCP (hosted) | Solana Foundation | `https://mcp.solana.com/mcp` | Live Solana docs retrieval + semantic search + Anchor/Pinocchio Rust autofixer |
| Solana Developer MCP (repo) | Solana Foundation | `github.com/solana-foundation/solana-mcp-official` | Source of the hosted server; self-host needs `DATABRICKS_*` env vars |
| Solana AI getting-started guide | Solana | `solana.com/developers/guides/getstarted/intro-to-ai` | Official AI-tooling intro (page unreachable this session → `CURRENT_DOCUMENTATION_GAP`) |
| Solana developer docs | Solana | `solana.com/docs` (A3, per Builder README) | Protocol/developer documentation corpus |

**Verified tool set (5), from `mcp.solana.com` and the official repo:**
`list_sections`, `get_documentation`, `Solana_Documentation_Search`,
`Solana_Expert__Ask_For_Help` (four documentation tools), and `program_autofixer`
(static Rust checks for Anchor/Pinocchio programs).

**Behaviour:** read-only. The hosted endpoint requires **no API key**. It exposes
no wallet, signing, transaction, arbitrary-RPC, shell, filesystem, secret, or
database tool.

**Smallest useful subset for Printer:** the **four documentation tools only**.
`program_autofixer` targets on-chain Rust programs (Anchor/Pinocchio); Printer V1
is a Python, paper-only, non-on-chain system, so the autofixer is **not useful**
and should be treated as out-of-scope, not merely unused.

**Prompt-injection / security note:** documentation-retrieval output is untrusted
text. Even a read-only doc server can return content that attempts to steer the
agent. Any adoption must treat MCP output as subordinate background (§7), never as
authority over the Printer stack, Source Governor, Central Scheduler, or locks.

**Non-official / community servers seen during research (NOT authoritative):**
`sendaifun/solana-mcp` (Solana Agent Kit — wallet/execution capable → REJECT),
`openSVM/solana-mcp-server` (arbitrary RPC methods → REJECT, would bypass the
Source Governor), memecoin-analysis community servers (→ REJECT). These must not
become Printer sources merely because they exist.

## 4. Codex Compatibility Findings

Grounded in OpenAI's official Codex MCP documentation
(`learn.chatgpt.com/docs/extend/mcp`, access 2026-07-18):

- Codex CLI supports MCP with **STDIO** and **Streamable HTTP** transports.
- Configuration lives in `config.toml` (`[mcp_servers]`), with
  `startup_timeout_sec` (default 10) and `tool_timeout_sec` (default 60).
- Remote documentation MCP servers are explicitly supported (OpenAI's docs cite
  "OpenAI Docs MCP" and "Context7" as examples).
- ChatGPT desktop, Codex CLI, and the IDE extension share MCP configuration.

**Conclusion:** the Solana Developer MCP (Streamable HTTP, keyless) is
**technically compatible** with Codex. The Solana repo README does not itself name
Codex, so client-naming is `CURRENT_DOCUMENTATION_GAP`; compatibility is inferred
from the standard transport, not asserted by Solana.

## 5. Claude Code Compatibility Findings

Grounded in Anthropic's official Claude Code MCP documentation
(`code.claude.com/docs/en/mcp`, access 2026-07-18):

- Claude Code connects to MCP servers over **HTTP** (recommended;
  `streamable-http` alias), **SSE** (deprecated), and **stdio**.
- Servers are added with `claude mcp add --transport http <name> <url>` at
  **local / project / user** scope (`--scope`).
- Remote servers requiring **OAuth 2.0** authenticate via `/mcp`; the Solana
  endpoint needs none.
- Project-scoped `.mcp.json` servers require explicit approval; a
  `disabledMcpjsonServers` entry rejects a server. Tool availability is subject to
  Claude Code's permission model.

**Conclusion:** the Solana Developer MCP is **technically compatible** with Claude
Code as a keyless remote HTTP server. As with Codex, Solana does not itself name
Claude Code, so client-naming is `CURRENT_DOCUMENTATION_GAP`.

## 6. Allowed / Prohibited Capability Matrix

Applies to any future decision to connect the official Solana MCP (not done here):

| Capability | Status | Basis |
|---|---|---|
| Documentation retrieval (`get_documentation`, `list_sections`) | ALLOW_WITH_RESTRICTIONS | read-only, official, directly useful |
| Documentation semantic search (`Solana_Documentation_Search`) | ALLOW_WITH_RESTRICTIONS | read-only, official |
| Troubleshooting / static developer help (`Solana_Expert__Ask_For_Help`) | ALLOW_WITH_RESTRICTIONS | read-only; output is untrusted background |
| Program autofixer (Anchor/Pinocchio Rust) | REJECT (out of scope) | Printer is Python paper-only, not an on-chain Rust program |
| Wallet access | PROHIBITED | not offered; permanently barred |
| Signing / transaction creation or submission | PROHIBITED | not offered; permanently barred |
| Arbitrary RPC execution | PROHIBITED | would bypass Source Governor |
| Arbitrary shell / filesystem access | PROHIBITED | outside read-only doc boundary |
| Secret / credential access | PROHIBITED | no secrets to any external tool |
| Database access | PROHIBITED | persistent corpus is Printer-owned only |
| Printer runtime control | PROHIBITED | Central Scheduler owns runtime |
| Operational memory collection | PROHIBITED | Source Governor owns evidence |
| Source Governor / Central Scheduler bypass | PROHIBITED | permanent invariant |

The preferred boundary — documentation retrieval, documentation search,
troubleshooting, static developer assistance — is exactly what the official
Solana server's four documentation tools provide, and nothing more.

## 7. Authority and Reproducibility Recommendation

Recommended authority order (the Solana Builder README §1-§2 already establishes
almost exactly this; adopt it explicitly for external MCP/doc research):

1. Active Printer V1 source stack (AGENTS.md → clean-master-spec →
   post-rc-build-order → memory-factory-guide → build-order-v2 → manipulation-
   aware money-usefulness product law).
2. Committed Solana Builder and provider-contract modules (authority tiers A1-A6
   from the Builder README).
3. Verified official external documentation or MCP research (this audit's
   primary-source findings).
4. Model memory — non-authoritative background only.

External MCP or documentation output **must never silently override** AGENTS.md,
the Clean Master Spec, the active build order, the manipulation-aware
money-usefulness law, the Source Governor, the Central Scheduler, capability
locks, or paper-only restrictions. On any conflict, the Printer stack wins and the
external finding is recorded as a gap.

An external finding becomes reproducible enough to rely on only when a committed
module records: the canonical official source URL; the access/retrieval date; the
exact capability or contract statement; supported boundaries; unsupported
boundaries; a committed repository summary; a freshness/staleness review
requirement; and **no** credentials, secrets, wallet data, private data, or raw
sensitive payloads. This matches the Builder stack's existing "VERIFIED
<date> / Authority <tier>" module convention.

## 8. Existing Solana Builder Module Inventory

All twelve modules plus the SB-1 architecture doc were inventoried read-only. The
stack self-declares **AUTHORED / SB-2.1 VERIFIED, NOT ADOPTED** and **subordinate**
to the active Printer stack.

| Module | Authority | Purpose | Supports (R#) | Disposition |
|---|---|---|---|---|
| `README.md` | internal index | authority hierarchy A1-A7, subordination, adoption gate | all | REMAIN (basis for §7) |
| `source-governor-evidence-rules.md` | internal policy (ACTIVE) | per-source evidence contribution rules | R9, R11, R12 | REMAIN |
| `token-age-evidence-tier-registry.md` | internal policy (ACTIVE) | T2/T3/T4 token-age tiers; PumpPortal T2 BLOCKED | R1, R9 | REMAIN |
| `solana-core-rpc-reference.md` | official Solana (A3/A4) | RPC methods, commitment/finality, slots/block time | R12, R13 | REMAIN; source for a public-RPC-contract section |
| `solana-transaction-instruction-parsing.md` | official Solana (A1/A3) | instruction/inner-instruction/account parsing; observability limits | R12 | REMAIN |
| `solana-spl-token-program.md` | official Solana (A1) | SPL Token layout | R9 (token identity) | REMAIN |
| `solana-token-2022-program.md` | official Solana (A1) | Token-2022 layout; T3 decoder | R9 | REMAIN |
| `solana-mint-addresses.md` | official Solana (A1) | canonical mint addresses | R9 | REMAIN |
| `dexscreener-api-contract.md` | provider-primary (A4) | discovery/price/liquidity/volume/txns | R9, R13 | REMAIN |
| `pumpportal-api-contract.md` | provider-primary (A4/A6) | launch stream schema | R9 | REMAIN |
| `pump-fun-bonding-curve-protocol.md` | official/A6 | bonding-curve behaviour | R9, R11 | REMAIN |
| `pumpswap-pool-confirmation-contract.md` | official on-chain (A1) | pool confirmation (narrow) | R9, R11 | REMAIN; consider renaming/expanding vs. a full `pumpswap-amm-protocol` |
| `printer-v1-sb-1-...-architecture.md` | internal | stack architecture | all | REMAIN |

No module conflicts with another. No module is stale enough to deprecate; the
newest verification date observed is 2026-07-12. No module is modified in this
audit.

## 9. Missing Module and Consolidation Analysis

The V2-9.7C.0 audit flagged six "missing" named modules. Re-evaluated here against
the actual stack and named official sources:

| Proposed module | Need | Official primary source | Current code/adapter dep | Gap | Supports | Required before | Separate provider audit? |
|---|---|---|---|---|---|---|---|
| `solana-public-rpc-contract.md` | commitment/finality, slot/block-time, pagination, nullability, history retention, rate limits, holder/participant limits | `solana.com/docs` (A3); Helius `helius.dev/docs` (A4) | `sources/*rpc*`, safety composite | partial — content is spread in `solana-core-rpc-reference.md`; **consolidate a "Public RPC contract & limits" section there rather than a new file** | R12, R13 | V2-9.7D impl (not design) | no |
| `jupiter-routing-protocol.md` + `jupiter-quote-api-contract.md` | route/quote availability, price impact, slippage, fees, failed routes | `developers.jup.ag` (A3, named in Builder README) | `sources/jupiter_quote*`, `paper_quote_evidence` | **absent** — no dedicated module | R13 | V2-9.7D impl; quantitative fields before paper-decision readiness | **yes** — a Jupiter provider audit |
| `goplus-api-contract.md` | safety fields, holder concentration boundaries | `docs.gopluslabs.io` (A4, named in Builder README) | `sources/goplus*`, safety composite | **absent** | R11, R12 (coarse concentration only) | V2-9.7D impl | yes — a GoPlus provider audit |
| `geckoterminal-api-contract.md` | pool discovery, OHLCV/candle, trades window, rate limits | `apiguide.geckoterminal.com` (A4, named in Builder README) | `sources/geckoterminal*` | **absent** (rules exist in source-governor-evidence-rules) | R9, R13 | V2-9.7D impl | yes — a GeckoTerminal provider audit |
| `pumpswap-amm-protocol.md` | full AMM protocol (vs. narrow pool-confirmation) | Pump A1 repo + on-chain | `sources/pumpswap*` | partial — `pumpswap-pool-confirmation-contract.md` covers confirmation only | R9, R11 | V2-9.7D impl | maybe |
| `solana-agent-assistance-policy.md` + `official-solana-agent-resources.md` | governance for external MCP/doc use; official-resource register | this audit + Builder README §1-§2 | none | **absent** as a named policy | authority/reproducibility (§7) | **V2-9.7C design** (governance only) | no |

**Consolidation recommendation:** do **not** create six separate files. Fold the
public-RPC content into the existing `solana-core-rpc-reference.md`; author the
four provider-primary contracts (Jupiter route+quote can be one module, GoPlus,
GeckoTerminal, and optionally a PumpSwap AMM expansion) each behind a **separate
provider-specific source audit**; and add a single small internal governance
module for agent-assistance policy and the official-resource register. None of
these is required before V2-9.7C **design** except the governance policy, which
this audit's §7 already supplies in draft.

## 10. Wallet / Participant Evidence Boundary

**What official Solana documentation / the official MCP can help a developer
understand** (observability — grounded in `solana-core-rpc-reference.md` and
`solana-transaction-instruction-parsing.md`): signatures; transaction history
(subject to RPC retention/pruning); account and token-account ownership;
instructions and inner instructions; token balances and inventory changes; slots;
block times; transaction ordering and timing.

**What these resources cannot prove by themselves** (and must remain UNKNOWN):
common control of multiple wallets; related-wallet clusters; bundled participants;
insider identity; coordinated ownership; genuine new-participant authenticity;
wash trading; manipulation intent; probable insider distribution. The
instruction-parsing module already records history-walk depth beyond RPC retention
and non-Pump inner-instruction coverage as `UNKNOWN_REQUIRES_RESEARCH`.

On-chain **observability is not identity, intent, or coordination**. Documentation
and MCP access do not convert observable transactions into authenticity proof.
Consistent with product law ("wallet and participant authenticity remains UNKNOWN
when unproven").

**A later dedicated Wallet and Participant Evidence Source Audit is still
required** before any paper-BUY readiness. It is not required before V2-9.7C
design (design labels R12 evidence UNKNOWN and gates dependent behaviour).

## 11. Event-Time Execution Documentation Boundary

Separated by who can ground each field:

| Field | Grounding source | Status |
|---|---|---|
| Route availability | Jupiter (A3, `developers.jup.ag`) | provider — module absent |
| Quote availability / freshness | Jupiter | provider — module absent |
| Price impact / slippage (quantitative) | Jupiter | provider — module absent |
| Fees | Jupiter + Solana fee model | provider + Solana |
| Failed routes | Jupiter | provider — module absent |
| Max realistically executable size | Jupiter + pool depth (DexScreener/pool provider) | provider + derived |
| Partial / complete exit capability | Jupiter + pool liquidity | provider + derived |
| Wick-only vs durable opportunity | **Printer-derived** from snapshot trajectory | internal derivation |
| Configured paper position size | **Printer-configured** | internal |
| Position-size-aware price impact | Jupiter quote at that size | provider — module absent |
| Observation / decision / simulated-execution delay | **Printer-derived** from scheduler + snapshot timing | internal |
| Opportunity duration | **Printer-derived** from snapshot spacing | internal |

Printer today holds only **categorical** route/slippage/impact/liquidity/realism
labels (`paper_quote_evidence`, migration 023). Those must **not** be read as full
quantitative executability. The quantitative fields require an official **Jupiter
provider source audit** and a later evidence/implementation lane; several timing
and duration fields are Printer-derived and require no external source but do
require design and implementation. Evidence that remains unavailable stays
`CURRENT_EVIDENCE_GAP`.

## 12. Official Skills / Resource Recommendation

The minimum official subset that directly supports Printer development is the
**four documentation tools of the official Solana Developer MCP**
(`list_sections`, `get_documentation`, `Solana_Documentation_Search`,
`Solana_Expert__Ask_For_Help`), used strictly as read-only, non-authoritative
background under §7.

- Keep official Solana resources separate from provider resources (Jupiter/
  GeckoTerminal/GoPlus docs) and from community resources.
- Community trading/wallet/Pump.fun/arbitrage/execution skills and MCP servers
  (e.g. Solana Agent Kit, arbitrary-RPC servers) are **REJECTED** as authoritative
  Printer sources.
- No official skill or documentation resource unlocks evidence Printer cannot
  collect (wallet authenticity, quantitative execution).

## 13. Custom Printer MCP Decision

**Decision: DEFERRED (do not build).** A recommendation to build a custom Printer
MCP is BLOCKED unless the repository proves file-based navigation is materially
insufficient with documented repeated failures, no smaller solution works, and
strict read-only/authority boundaries can be preserved. **None of these is
evidenced.**

- The active stack is well-indexed: AGENTS.md, a clean master spec, a build order,
  numbered closeouts, and a subordinate Builder stack with an explicit authority
  hierarchy. Prior lanes located committed files by ordinary navigation without
  recorded failure.
- A custom MCP adds maintenance burden, a permission surface, prompt-injection and
  secret/data-exposure risk, versioning/reproducibility overhead, and a real risk
  of bypassing lane boundaries and approved commands.
- If any future documentation-discovery need arises, a **smaller committed
  documentation index** (a Markdown file listing canonical sources and their
  authority tiers — the §7 register) solves it without a server.

## 14. Exact Recommended Follow-Up Files

None created in this audit. For a **later** governance step (documentation-only):

- `docs/solana-builder-source-of-truth/solana-agent-assistance-policy.md` — the
  §7 authority/reproducibility policy for external MCP/doc research.
- `docs/solana-builder-source-of-truth/official-solana-agent-resources.md` — the
  official-resource register (Solana MCP endpoint, tools, boundaries, access date,
  freshness-review requirement).

For **later provider/RPC source audits** (each its own lane, not now):

- Consolidate public-RPC limits into `solana-core-rpc-reference.md` (no new file).
- `jupiter-route-and-quote-contract.md` (one module, from `developers.jup.ag`).
- `goplus-api-contract.md` (from `docs.gopluslabs.io`).
- `geckoterminal-api-contract.md` (from `apiguide.geckoterminal.com`).
- Optional `pumpswap-amm-protocol.md` expansion.

## 15. Lane-Placement and Dependency Recommendation

Smallest roadmap-compliant next action, with each recommendation classified:

| Recommendation | Classification |
|---|---|
| Adopt the §7 agent-assistance authority/reproducibility policy (documentation-only) | REQUIRED_BEFORE_V2_9_7C_DESIGN |
| Optionally connect the official Solana MCP's four doc tools as read-only developer assistance | OPTIONAL_DEVELOPER_ASSISTANCE |
| Author Jupiter route/quote provider contract | REQUIRED_BEFORE_V2_9_7D_IMPLEMENTATION (quantitative fields: REQUIRED_BEFORE_PAPER_DECISION_READINESS) |
| Author GoPlus / GeckoTerminal provider contracts | REQUIRED_BEFORE_V2_9_7D_IMPLEMENTATION |
| Consolidate public-RPC limits into core-RPC reference | REQUIRED_BEFORE_V2_9_7D_IMPLEMENTATION |
| Wallet and participant evidence source audit | REQUIRED_BEFORE_PAPER_DECISION_READINESS |
| Build a custom Printer MCP | DEFERRED |
| Community wallet/execution/RPC MCP servers | REJECTED |
| Proceed to full V2-9.7C design after the §7 policy | REQUIRED_BEFORE_V2_9_7C_DESIGN is the only gate |

**Net:** V2-9.7C **design** may proceed after a small documentation-only
governance adoption. No provider/RPC contract module and no wallet audit blocks
*design*; they block *implementation*, *pilot*, or *paper-decision readiness*.

## 16. Money-Usefulness Contribution

Restricted official documentation assistance and targeted provider-primary
contracts improve: **implementation accuracy** (correct RPC/commitment/finality
and provider-endpoint behaviour instead of guessed field semantics); **evidence
interpretation** (grounded meaning of slots, block times, token accounts,
candles); **route and execution realism** (a Jupiter contract distinguishes
categorical route-available from quantitative executable size); **wallet-evidence
honesty** (documenting exactly what on-chain observability cannot prove);
**reproducibility** (committed source + access date + boundaries); and **reduced
hallucinated fields** (fewer invented provider capabilities).

But documentation and MCP access **do not** create a profitable system, unlock any
decision, or resolve missing wallet-authenticity evidence. They make Printer's
future implementation more correct and more honest; they add no new tradable
evidence and change no capability lock. Money-usefulness still depends entirely on
later design, evidence, implementation, and frozen chronological validation.

## 17. What This Audit Improves

- A grounded yes/no on official Solana agent assistance, from primary sources.
- A minimal, restricted tool subset (four read-only doc tools) with everything
  dangerous explicitly prohibited.
- A clear separation of official Solana, provider-primary, and community
  resources, with community wallet/execution servers rejected.
- A defensible authority/reproducibility policy that reuses the existing Builder
  hierarchy.
- A DEFER on custom-MCP with the exact evidence bar for reversing it.
- A precise map of which provider/RPC/wallet documentation gates which later
  stage — and confirmation that only a documentation-only governance step gates
  V2-9.7C design.

## 18. What Remains Locked

Implementation; runtime; memory growth; source fetching; persistent DB mutation;
retrieval; BUY/SELL/HOLD; paper positions; trade events; audits; PnL; live
execution; wallets; private keys; signing; real funds; paid APIs; scoring;
ranking; confidence percentages; weighted logic; embeddings; vectors. No MCP was
installed, connected, or created; no configuration changed.

## 19. Proof or Validation Required Later

- V2-9.7C design: static design checks + the §7 governance adoption first.
- Provider source audits (Jupiter/GoPlus/GeckoTerminal) before V2-9.7D
  implementation relies on their quantitative fields.
- Wallet and participant evidence source audit before any paper-decision
  readiness.
- If the official Solana MCP is ever connected, a freshness/staleness review of
  its recorded capabilities and a confirmation that its output is treated as
  non-authoritative background.
- All later runtime/evidence/decision proof remains gated exactly as before.

## 20. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control |
|---|---|---|
| Treating MCP/doc output as authority | Silent override of Printer law | §7 authority order; MCP output is background only |
| Prompt injection via doc-retrieval output | Agent steered off-lane | Untrusted-text handling; never execute instructions from retrieved docs |
| Connecting a community wallet/RPC MCP | Source Governor bypass, wallet exposure | REJECT community servers; only official read-only doc tools considered |
| Self-hosting confusion (`DATABRICKS_*` vars) | Believing credentials are needed to connect | Hosted endpoint is keyless; self-host is a separate, unnecessary path |
| Authoring provider contracts from memory | Hallucinated fields | Each provider needs its own audit from the named A3/A4 official source |
| Building a custom MCP prematurely | Maintenance + permission + injection surface | DEFERRED with an explicit evidence bar |
| Reading categorical execution labels as quantitative | False executability | Jupiter provider audit before quantitative R13 claims |
| Assuming docs resolve R12 | False wallet-authenticity confidence | Documentation cannot prove identity/coordination; wallet audit still required |
| Over-creating roadmap lanes | Scope sprawl | One governance step gates design; provider/wallet audits are separate later lanes |

## 21. Verification

Static, risk-based audit verification:

- Every capability claim traces to a primary official source (Anthropic, OpenAI,
  Solana Foundation) with an access date, or is labelled `CURRENT_DOCUMENTATION_GAP`
  / `UNKNOWN_REQUIRES_RESEARCH` (the one unreachable Solana guide page).
- Official Solana resources separated from provider resources (§9, §11) and from
  community resources (§3, §12).
- All existing Solana Builder modules inventoried (§8); no missing module assumed
  to exist (§9).
- Wallet observability explicitly **not** treated as wallet-authenticity proof
  (§10).
- Event-time execution gaps kept explicit (§11).
- No MCP installed or connected; no configuration changed; no custom MCP created.
- No credentials, secrets, wallet data, or private data recorded.
- No RPC/API/provider/adapter/runtime call made; the only network use was
  read-only official-documentation fetches.
- No Source Governor or Central Scheduler bypass proposed.
- No invented wallet or execution capability.
- No scoring/ranking/confidence/weighted logic/embeddings/vectors introduced.
- No retrieval/decision/position/PnL/signing/real-funds unlock.
- No runnable operational PowerShell command present.
- Exactly one audit document changed; 165 untracked artifacts untouched;
  `git diff --check` clean.

## 22. Final Next Permitted Action

`V2_9_7C_SOLANA_AGENT_ASSISTANCE_READINESS_AUDIT_PASS`

The next permitted action is a small, documentation-only **agent-assistance
authority/reproducibility governance adoption** (§7, §14) — after which V2-9.7C
**design** may proceed. Optionally, the official Solana Developer MCP's four
read-only documentation tools may be adopted as developer assistance under those
restrictions.

This PASS authorizes no MCP installation, connection, or custom development; no
documentation adoption in this audit; and no code, schema, runtime, memory,
retrieval, decision, position, PnL, wallet, signing, execution, or real-funds
capability. The full V2-9.7C Operational Memory Factory design is not begun here.

## Files Changed

- `docs/printer-v1-v2-9-7c-solana-agent-assistance-source-contract-readiness-audit.md`
  (this file).

## Sources (primary official, accessed 2026-07-18)

- Claude Code MCP: https://code.claude.com/docs/en/mcp
- OpenAI Codex MCP: https://learn.chatgpt.com/docs/extend/mcp
- Solana Developer MCP (hosted): https://mcp.solana.com/mcp
- Solana Developer MCP (repo): https://github.com/solana-foundation/solana-mcp-official
- Solana AI guide (unreachable this session; recorded as gap):
  https://solana.com/developers/guides/getstarted/intro-to-ai
