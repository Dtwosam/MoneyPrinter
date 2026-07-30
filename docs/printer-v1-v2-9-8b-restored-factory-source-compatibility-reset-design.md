# Printer V1 V2-9.8B Restored Factory Source Compatibility Reset Design

Date: 2026-07-30

Lane: `V2-9.8B Restored Factory Source Compatibility Reset`

Status: IMPLEMENTATION AUTHORIZED BY OPERATOR PROMPT

## Work gate

- Baseline branch / HEAD: `master` / `e54ce92aef59d0c9edd2266f69e3572d4b084c97`
- Authoritative database identity: `data/printer_v1.sqlite3`, SHA-256
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Allowed: source-boundary confirmation, this design, source-contract reset,
  frozen offline proof on disposable migration-049 databases, and closeout.
- Forbidden: provider/RPC/WebSocket execution; authoritative-database writes;
  Memory Factory, N2, N7, recovery, cursor, tracking, snapshot, window or memory
  execution; retrieval or financial capability activation.
- Runtime owners remain Source Governor and Central Scheduler.
- Stop condition: one PASS/BLOCKED verdict and, on PASS, one commit.
- Locked capabilities: retrieval, decisions, BUY/SELL/HOLD, positions, trades,
  audits, PnL, wallets, keys, signing and execution.

## Mandatory source-grounded blocker investigation

BLOCKER CLASSIFICATION: `CONTRACT_DRIFT`

EVIDENCE:

1. The restored ordinary command builds a PumpPortal migration WebSocket
   transport when no fixture is injected.
2. the official PumpPortal real-time contract now requires an API key whose
   setup creates a linked Lightning wallet. That contract is incompatible with
   Printer's wallet/key/funding locks.
3. Jupiter runtime still uses `lite-api.jup.ag`; current Jupiter Portal
   documentation adopts `api.jup.ag`, with keyless access capped at 0.5 RPS.
4. active Solana transports embed the undocumented legacy
   `api.mainnet-beta.solana.com` hostname while current Solana cluster
   documentation publishes `https://api.mainnet.solana.com`.
5. the old readiness preflight covers only five evidence sources and can report
   READY without the migration locator, Pump/PumpSwap contracts, DexScreener
   discovery endpoints, CoinGecko or Jupiter entry/exit quote contracts.

OFFICIAL-SOURCE COMPARISON:

- Pump's official public IDL publishes the Pump program, exact `migrate`
  discriminator and ordered accounts.
- PumpSwap's official public IDL publishes the AMM program and pool account
  layout.
- Solana publishes `https://api.mainnet.solana.com` as the mainnet public RPC.
- Jupiter publishes `https://api.jup.ag`, keyless access at 0.5 RPS, and the
  quote identity/amount/slippage/route/price-impact response fields.

PRINTER-CONTRACT COMPARISON:

- `pump_contracts.py` already pins and strictly verifies the current Pump and
  PumpSwap IDLs, exact instruction discriminator, account order, PDA joins,
  program owner, pool discriminator and base/quote mint identities.
- Runtime endpoint literals, migration locator composition, the older
  `pump_migration.py` verifier and readiness preflight lag that strict contract.

ROOT CAUSE: independently maintained provider literals and an older
PumpPortal-shaped locator boundary drifted from both current official contracts
and Printer's later strict Pump/PumpSwap parser.

CODE CHANGE JUSTIFIED: YES. The operator explicitly authorized a cohesive
contract-drift reset and the supported cursor-free design below.

MINIMUM SAFE RESPONSE: replace only the locator input boundary; centralize
active source contracts and RPC selection; harden Jupiter and finalized Solana
validation; rebuild complete ordinary-run preflight; leave selection, tracking,
eligibility, evidence thresholds, schema, ceilings and locks unchanged.

FOCUSED PROOF: frozen source transports plus disposable migration-049 databases
cover the 17 operator-required cases.

UNTOUCHED SCOPE: candidate acquisition, N2/N7, historical/global cursors,
recovery/backfill, optional-global observer, capacity above two, schema,
eligibility rules, evidence thresholds, authoritative DB and all locked
capabilities.

AUTHORIZATION STATUS: implementation authorized by the lane prompt.

NEXT: implement, prove offline, write closeout, commit on PASS, then stop.

## Fixed replacement architecture

```text
Central-Scheduler-owned ordinary run
  -> Source-Governed Solana request: one finalized Pump-program signature page
  -> Source-Governed Solana requests: bounded finalized transaction lookups
  -> strict pinned Pump migrate instruction/account decoder
  -> governed PumpSwap transaction/account verification
  -> strict pinned Pump/PumpSwap PDA, owner, layout, base/quote-mint join
  -> existing graduated-candidate registry
  -> existing exact-pool liquidity front door
  -> existing two-token/two-pair selection, tracking and 15m lifecycle
```

The locator is a stateless live-tail snapshot. It reads one newest-first page
with explicit `finalized` commitment and examines a fixed bounded number of
transactions. It makes no continuity, backfill or historical-completeness
claim. It has no cursor input or output and does not import the deferred
candidate-acquisition owner. Each page/transaction lookup is a separate Source
Governor request, so source-request and transport-operation accounting remain
one-to-one. A missing second eligible candidate produces the existing safe
insufficient-supply stop.

PumpPortal is not a fallback. Its historical adapter and evidence remain
importable only for historical/deferred reproduction; ordinary `run` neither
imports nor constructs it.

## Reused and new components

Reused unchanged:

- pinned strict Pump/PumpSwap constants and decoders in `pump_contracts.py`;
- governed source request/recording path;
- PumpSwap normalization and graduated registry;
- eligible-supply loop, exact-pool liquidity front door and two-token selector;
- holder, safety, freshness, tradeability and clean/dirty gates;
- campaign ownership, tracking, 15m lifecycle, reporting and replay.

Reused with a narrow repair:

- graduation verifier uses the strict pinned migration verifier and explicit
  finalized RPC parameters;
- direct migration discovery keeps its registry/write boundary but consumes the
  new Solana locator adapter instead of PumpPortal frames.

New:

- a shared active source-contract registry and safe Solana RPC resolver;
- a narrow direct Pump live-tail adapter (one RPC operation per governed call);
- a complete ordinary-run source preflight and frozen contract proof.

## Solana configuration contract

`PRINTER_SOLANA_RPC_URL` is optional. When present it must be an absolute HTTPS
URL with a hostname, no fragment and no user-info. Placeholder values are
rejected. Logs/preflight expose only a redacted identity: scheme, hostname and
port plus whether a path/query exists. When absent, the bounded fallback is the
current official public endpoint `https://api.mainnet.solana.com`.

All migration, holder and PumpSwap transaction/account reads use explicit
`finalized` commitment where the method supports it. JSON-RPC errors, missing
result fields, null transactions and malformed method-specific shapes fail
closed. Helius remains only the existing conditional governed holder backup and
is never silently selected for the migration locator.

## Jupiter contract

Jupiter remains paper-quote-only on
`https://api.jup.ag/swap/v1/quote`. No API key, wallet, build, swap,
instruction or execution endpoint is allowed. Local pacing is 30 requests per
minute (0.5 RPS; minimum two seconds between requests), with zero automatic
retry.

A quote is clean only when it exactly echoes the requested input mint, output
mint, raw input amount and slippage; contains positive integer output and
threshold amounts; has a non-empty internally consistent route plan; and has a
finite, non-negative price impact. Null, throttled, error, wrong-identity,
wrong-amount, wrong-slippage, malformed or contradictory responses fail closed.
Entry and exit use the same parser with reversed exact identities.

## Complete ordinary-run dependency matrix

| Dependency | Class | Auth / environment | Contract and pacing | Failure effect |
|---|---|---|---|---|
| Direct Pump migration locator | MANDATORY | keyless; optional validated `PRINTER_SOLANA_RPC_URL` | Pump IDL pin; 1 finalized page + bounded tx reads | blocks before lifecycle / honest supply stop |
| Pump program contract | MANDATORY | none | pinned program, IDL hash, migrate discriminator/accounts | blocks preflight |
| PumpSwap exact join | MANDATORY | same governed RPC | pinned AMM/IDL/pool layout/PDA | candidate blocked |
| Solana tx/account verification | MANDATORY | approved HTTPS env or official bounded fallback | exact JSON-RPC, finalized, 30/min local | blocks locator/candidate |
| DexScreener latest profiles | MANDATORY | keyless | current profiles endpoint; 60/min local | discovery nomination blocked; cannot replace exact migration evidence |
| DexScreener token batch | MANDATORY | keyless | current tokens-v1 Solana batch; 60/min local | candidate supply blocked |
| DexScreener exact pair | MANDATORY | keyless | latest pair endpoint; 60/min local | Gecko fallback permitted only for eligible transient failure |
| GeckoTerminal exact pair / 15m | CONDITIONAL | keyless | API v2/version header; 10/min local | candidate/window dirty or fallback |
| GoPlus safety | CONDITIONAL | keyless | Solana security v1; 20/min local | candidate blocked only on explicit risk; unknown remains honest |
| Solana holder evidence | CONDITIONAL | same validated RPC | finalized largest-accounts + supply; 30/min local | Helius fallback only on eligible transient failure |
| Helius holder backup | CONDITIONAL | `PRINTER_HELIUS_API_KEY` only when selected | fixed HTTPS host; 30/min local; no retry | candidate remains unknown/blocked |
| CoinGecko context | MANDATORY | keyless | public API v3; 20/min local | window context dirty/fail closed |
| Jupiter entry/exit quotes | MANDATORY | keyless | current host; 30/min local; exact quote v1 semantics | paper-realism evidence dirty/fail closed |
| PumpPortal | DEFERRED | prohibited for ordinary run | no active endpoint | no fallback |
| Candidate acquisition / cursor / recovery | DEFERRED | not applicable | importable historical code only | no runtime authority |
| Alternative.me / DefiLlama | DORMANT | keyless | registered broad-context sources | absent from ordinary graph |

The preflight obtains endpoint and contract values from the same registry used
by runtime construction. It independently checks graph completeness,
classification, free/public compatibility, environment resolution, owner
boundaries, pacing, response-version pins and prohibited capability markers.
Conditional absence cannot erase a mandatory issue.

## Budget and boundary preservation

- active capacity stays exactly two;
- ordinary run stays `WINDOW_15M`; 5m remains support-only;
- admission ceiling remains 45 and source/storage/scheduler ceilings remain
  unchanged;
- the locator uses one page and at most twelve transaction reads; only exact
  migrations proceed to at most five existing two-operation PumpSwap
  verifications;
- collection rounds become one because the finalized stateless page replaces
  three WebSocket collection rounds;
- re-verification is disabled because automatic retries remain zero;
- no schema or migration is added; head stays 049.

## Frozen proof plan

The lane adds focused tests that use frozen dispatcher transports and disposable
migration-049 databases. They prove the required success and fail-closed source
cases; ordinary-graph completeness and shared constants; endpoint redaction;
zero candidate/cursor/recovery and locked-table deltas; the restored two-token
15m regression; Governor/Scheduler ownership; accounting/report/replay;
migration ledger, integrity, foreign keys and cleanup.

No test or proof performs provider I/O or opens the authoritative database for
write.

## Functionality Risks / Setbacks / Efficiency Blockers

- A one-page stateless live tail can honestly miss migrations outside that
  bounded page. It cannot backfill and therefore may stop for insufficient
  supply more often than a cursor-backed system. That is an accepted safety
  tradeoff, not evidence of market absence.
- The official public Solana endpoint is rate-limited and not intended for
  production scale. Printer remains bounded; an operator-configured approved
  HTTPS endpoint is preferred.
- Jupiter currently describes Swap v1 as superseded by v2, but v2 build/order
  surfaces are execution-oriented. Printer keeps the documented read-only quote
  endpoint because it satisfies the exact paper-only evidence contract; any
  removal requires a future explicit compatibility review.
- Frozen proof establishes composition and fail-closed behavior, not live
  provider availability. A separate operator-authorized bounded live
  source-contract probe is required after review.
