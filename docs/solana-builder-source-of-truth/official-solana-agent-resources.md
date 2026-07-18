# Official Solana Agent Resources

**Status:** INFORMATIONAL REGISTER - SUBORDINATE TO INTERNAL PRINTER POLICY

**Register date / access date:** 2026-07-18

This register records official-resource facts verified by the V2-9.7C Solana
agent-assistance readiness audit. It is subordinate to
`solana-agent-assistance-policy.md` and grants no operational authority.

## 1. Official Solana Developer MCP

| Field | Verified record |
|---|---|
| Owner | Solana Foundation |
| Hosted endpoint | `https://mcp.solana.com/mcp` |
| Transport | Streamable HTTP |
| Hosted authentication | Keyless when verified |
| Resource boundary | Read-only |
| Access date | 2026-07-18 |

The verified tool list was:

| Tool | Printer classification | Restriction |
|---|---|---|
| `list_sections` | ALLOWED_WITH_RESTRICTIONS | Official documentation navigation only |
| `get_documentation` | ALLOWED_WITH_RESTRICTIONS | Official documentation retrieval only |
| `Solana_Documentation_Search` | ALLOWED_WITH_RESTRICTIONS | Official documentation search only |
| `Solana_Expert__Ask_For_Help` | ALLOWED_WITH_RESTRICTIONS | Troubleshooting and static developer assistance only |
| `program_autofixer` | REJECTED_OUT_OF_SCOPE_FOR_PRINTER_V1 | Targets Anchor or Pinocchio Rust programs; Printer is a Python, paper-only system |

All returned content remains untrusted, non-authoritative research until a
finding is reviewed and committed under the reproducibility policy.

## 2. Client Compatibility Boundary

- Codex is technically compatible through Streamable HTTP.
- Claude Code is technically compatible through HTTP / Streamable HTTP.
- The verified Solana resource did not explicitly name Codex or Claude Code.
  Client naming therefore remains a documentation limitation, not a direct
  Solana claim.

Technical compatibility is not installation approval. No MCP is installed or
connected by this adoption, and no Codex, Claude, user, machine, or repository
MCP configuration is changed.

## 3. Authority and Evidence Boundary

This register is informational and subordinate to
`solana-agent-assistance-policy.md`, the active Printer V1 source stack, the
committed Solana Builder stack, Source Governor, and Central Scheduler.

It does not:

- make an MCP a Source Governor evidence source;
- approve any provider or community resource;
- create market, wallet, participant, or execution evidence;
- prove wallet authenticity or participant coordination;
- supply quantitative event-time route, slippage, impact, duration, or exit
  evidence;
- unlock runtime, memory, retrieval, decisions, positions, trades, audits, PnL,
  signing, execution, or real funds.

Community resources are intentionally not listed as approved entries.

## 4. Freshness Rule

Before any future connection or material reliance, reverify:

- endpoint ownership;
- transport;
- authentication;
- tool list;
- read-only boundaries.

Record changed findings through a new committed review. Fail closed when current
official verification is unavailable. Never replace this historical record
silently.
