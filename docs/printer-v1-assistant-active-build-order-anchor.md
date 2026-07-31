# Printer V1 Assistant Active Build Order Anchor

## 1. Purpose

This document aligns Claude, ChatGPT, Codex and future assistants before
Printer V1 memory-growth work.

It does not replace:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`; or
- `docs/printer-v1-memory-growth-build-order-v2.md`.

Inside that source stack, the active memory-growth build order remains:

`docs/printer-v1-memory-growth-build-order-v2.md`.

## 2. Active lane

V2-9 is closed PASS. V2-9.7A through V2-9.7F are closed. V2-9.7F verdict is:

`V2_9_7F_ACTIVATION_READINESS_PASS`.

V2-9.8A is closed:

`V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS`.

The active lane remains:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

The current completed work inside V2-9.8B is the **Accounting and Exact-Identity
Report-Only Repair** after the first authoritative `WINDOW_15M` campaign
attempt. Its implementation verdict is:

`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_IMPLEMENTATION_PASS`.

Its independent operator-review verdict is:

`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_OPERATOR_REVIEW_PASS`.

Its closeout verdict is:

`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_CLOSEOUT_PASS`.

Reviewed branch:
`codex/v2-9-8b-accounting-report-only-repair`

Reviewed HEAD:
`0118a37e32929501c45f97ea9353b799b29fef7b`

Design baseline:
`e71e543d197154eba427b41e2e01574a59f527f5`

Implementation commits: `b168c57`, `fd35b41`, `0118a37`.

This repair closes the July 31 forensic defects: missing complete stage-evidence
handoff under bounded shortage, sealed-stage self-comparison for action-local
truth, and global latest-report `report-only` selection. The public coordinator
now uses an independent pre-seal transport observer, exact owner/action-local
identity reconciliation, exception-safe stage sealing, and exact-identity
report-only behavior with deterministic blocked replay when the exact attempt
has no terminal report.

Focused proof: 31 repair tests and 103 combined focused affected tests passed.
Authoritative DB SHA-256 remained unchanged at
`f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511`.

The historical first authoritative campaign remains:

`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`

The permanent no-rerun marker for execution
`20260731T002406Z-7612696c7295` remains valid. This repair does not backfill
that attempt and does not authorize another campaign.

Earlier terminal-safety finalization remains closed PASS and is preserved as
prior completed work:

- `V2_9_8B_TERMINAL_SAFETY_ACCOUNTING_FINALIZATION_PASS`
- `V2_9_8B_TERMINAL_SAFETY_ACCOUNTING_FINALIZATION_OPERATOR_REVIEW_PASS`

Active repair documents:

- `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-design.md`
- `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-implementation.md`
- `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-first-authoritative-15m-forensic-audit.md`
- `docs/printer-v1-v2-9-8b-first-authoritative-15m-campaign-closeout.md`

Prior terminal-safety / reconciliation documents (evidence):

- `docs/printer-v1-v2-9-8b-terminal-safety-accounting-finalization-audit.md`
- `docs/printer-v1-v2-9-8b-terminal-safety-accounting-finalization-design.md`
- `docs/printer-v1-v2-9-8b-terminal-safety-accounting-finalization-closeout.md`
- `docs/printer-v1-v2-9-8b-terminal-safety-accounting-finalization-operator-review.md`
- `docs/printer-v1-v2-9-8b-active-build-order-reconciliation.md`

The operational factory active-path restoration remains the restored intake
anchor:

`docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration.md`.

## 3. Restoration authority

The selected last-good operational implementation checkpoint is:

`7c38f13816169c69697ed19893b7e12802d9b1b7`

The first commit where candidate-acquisition adoption entered the active
operational critical path is:

`219ad8125a75f52686bfbf5953be0fa4cdca4712`

The restored active route is:

```text
public operational `run`
-> operator approval and exact preflight
-> verified backup / disposable restore rehearsal
-> proven governed discovery
-> deterministic selection with persisted reasons
-> atomic exact two-token tracking handoff
-> Source Governor + Central Scheduler
-> two isolated WINDOW_15M lifecycles
-> clean / dirty / blocked audit
-> terminal report and deterministic zero-source replay
-> safe stop with no successor
```

It preserves independent later:

- holder-condition / memory-quality separation;
- source-operation and Scheduler accounting;
- Git provenance;
- action-local blocked counters;
- exact DB-mode and migration-ledger checks;
- batch-scoped discovery persistence;
- reporting and deterministic replay;
- heartbeat, lease, lock and terminalization protections;
- token-local identity and tracking reconciliation; and
- ordinary `run` mode's fixed two-token, 15m-only policy.

Migration 049 remains the supported schema head.

## 4. Deferred candidate-acquisition state

Candidate-acquisition foundation, N2/N7, live acquisition transport, global
Pump cursors, cursor recovery, migration-observation admission and
optional-global accounting are deferred/experimental.

Their implementation, migrations 048/049, tables, tests, closeouts and blocked
live-proof evidence remain preserved. They are not:

- an active operational prerequisite;
- an active factory intake authority;
- a public operational command mode;
- a cursor or recovery authority for the active factory; or
- permission for a retry, recovery, N7 or successor.

The active operational path must not read, reset, advance or interpret
candidate-acquisition cursors or recovery rows.

Historical foundation and live-proof documents remain evidence only. Their
former "next task" pointers are superseded by this restoration anchor.

## 5. Assistant behavior

Assistants must:

- use exactly two active tokens;
- use the proven operational discovery/selection/tracking path;
- preserve Source Governor and Central Scheduler ownership;
- preserve auditable selection/rejection reasons;
- keep token/pair identities isolated;
- keep `WINDOW_5M_MICRO_EVENT` support-only;
- keep ordinary restoration proof at `WINDOW_15M`;
- keep 1h/4h/12h/24h inactive in the restoration proof;
- preserve clean, dirty, blocked and `DO_NOT_TRAIN` separation;
- preserve deterministic report-only replay and safe stop;
- use disposable migration-049 databases for proof;
- keep the authoritative database byte-identical; and
- stop after the requested lane and factual verdict.

Assistants must not:

- run providers, RPC, WebSockets, N2, N7, recovery or backfill;
- run a campaign, tracking lifecycle, snapshot, window or memory operation
  against the authoritative database;
- create another scheduler, source loop, DB authority or campaign runner;
- reset or reinterpret any candidate cursor;
- weaken pair identity, freshness, holder, liquidity, tradeability, evidence
  quality or safe-stop gates;
- auto-retry or auto-restart after terminal failure;
- start V2-10 or any 12h/24h work;
- activate retrieval or dirty-memory training;
- create paper decisions, BUY/SELL/HOLD, positions, trades, audits or PnL;
- add wallets, private keys, signing, real funds or live execution;
- add paid APIs, scoring, ranking, confidence, weighting, embeddings or vectors.

## 6. Source boundary

The restored active factory ordinary locator is the direct, stateless, one-page
finalized Pump-program live tail with exact pinned Pump migrate (25 roles) and
PumpSwap pool join under Source Governor and Central Scheduler. PumpPortal has
no ordinary-run authority, import, secret, wallet, funding, metered stream or
fallback path.

DexScreener, GeckoTerminal (conditional), GoPlus (conditional), one resolved
Solana RPC endpoint (including holder evidence), conditional free Helius holder
backup, CoinGecko context and keyless Jupiter paper quotes remain the ordinary
graph. The locator makes no historical completeness claim and safe-stops on
honest insufficient eligible supply.

Direct Pump/PumpSwap candidate-acquisition foundation, N2/N7, global cursors,
recovery and migration-observation admission remain deferred/experimental. Their
exact-claim rules remain valid inside that subsystem but do not make N2, a
global cursor, recovery or migration-observation admission an operational
prerequisite.

DexScreener and GeckoTerminal may provide their supported nomination/current
market facts. No aggregator fact may weaken exact current token/pair,
liquidity, freshness, holder, safety or tradeability requirements.

## 7. Exact next permitted task

On:

`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_CLOSEOUT_PASS`

the exact next permitted task is:

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit
```

This next task is audit/readiness only. It may statically inspect the repaired
ordinary command, accounting handoff, exact-identity report-only surface, and
route; read the authoritative database in read-only mode; verify the permanent
no-rerun marker and residual campaign state; verify the exact non-placeholder
operator command and environment-variable names; and document a factual
PASS/BLOCKED verdict.

It must not run providers/RPC, fetch sources, mutate the database, execute a
campaign, repair or reclassify the July 31 attempt, generate memory, rerun a 1h
proof, activate longer windows, start V2-10, enable retrieval, or create any
paper/financial capability. A readiness PASS may authorize only the next approved
design/specification or final-authorization step; it does not directly authorize
campaign execution.
