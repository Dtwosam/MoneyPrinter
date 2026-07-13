# Printer V1 V2-4.1 Shared Context/Evidence Closeout

## Status

`V2_4_1_SHARED_CONTEXT_EVIDENCE_PASS`

This mini-sprint audited and independently verified the shared `WINDOW_15M`
context/evidence foundations. It did not modify or prove the one-command 15m
factory, address the TRACK_NORMAL five-versus-six snapshot mismatch, or begin
V2-5.

## Audit Findings

| Area | Existing implementation | Shared readiness finding |
| --- | --- | --- |
| Market Regime | Recorder, classifier, freshness lookup, migration, governed broad-context collection, and Central Scheduler enqueue path exist. | Usable as global context. A target close may use only clean, governed context captured at or before the close. It remains context rather than a trade signal. |
| Solana Chain Heat | Recorder, classifier, freshness lookup, migration, governed broad-context collection, and Central Scheduler enqueue path exist. | Usable as global context under the same no-look-ahead and freshness rules. Migration/survival labels remain limited to fields actually supplied by governed evidence. |
| Safety / Rug | Safety engine, guarded evidence table, source trace, target/freshness labels, blocking action, GoPlus fixture normalizer, and Solana RPC fixture path exist. | Exact token, pair, and close-snapshot evidence is required. Missing, stale, failed, mismatched, or unsafe evidence resolves to `UNKNOWN_SAFETY` and blocks clean readiness. |
| Liquidity and Entry/Exit Realism | Liquidity engine and exact-target paper quote evidence table support entry/exit, slippage, price impact, and liquidity context. | Both clean paper-only ENTRY and EXIT evidence rows must match the exact token, pair, and close snapshot. Missing or invalid evidence fails closed. |
| Trading Flow | Stored snapshot normalization and categorical flow classifiers exist for direction, pressure, imbalance, volume, transactions, wallet participation, quality, and memory gating. | Flow can be derived from the governed close snapshot. Unknown direction/pressure or an audit-only/do-not-train gate blocks clean readiness. Provider-dependent side/wallet detail may remain partial. |
| Chart / Volatility | Stored snapshot parser and categorical classifiers exist for trend, volatility, range, momentum, drawdown/recovery, candle path, quality, and memory gating. | Chart context can be derived from the exact governed snapshot span without look-ahead. Unknown or audit-only/do-not-train results block clean readiness. |

All six areas already had working engine/storage foundations. The confirmed
shared gap was the absence of one reusable read-only resolver that applied the
same exact-window, no-look-ahead, provenance, freshness, and fail-closed rules
across all six areas. Legacy episode assembly can use latest context, while
generic nearest lookups do not by themselves provide this combined contract.

The referenced Solana Builder file
`docs/solana-builder-source-of-truth/geckoterminal-api-contract.md` is not
present in the repository. Provider-specific GeckoTerminal claims that are not
proved by current code/tests therefore remain `UNKNOWN_REQUIRES_RESEARCH`.

## Shared Repair

Added `build_window_15m_context_evidence()` as a shared read-only resolver.
It:

* accepts exact token, pair, start snapshot, end snapshot, and window bounds;
* requires at least 900 seconds and at least two exact-bound snapshots;
* rejects future context and evidence;
* validates governed request/response provenance;
* validates snapshot source status, data quality, critical price/liquidity
  fields, and exact identity;
* resolves fresh broad market and chain context at or before window close;
* resolves exact-target safety and ENTRY/EXIT quote evidence;
* derives flow from the governed close snapshot;
* derives chart/volatility from the exact governed snapshot span;
* returns categorical labels and explicit blockers for all six areas;
* performs no writes and reports every retrieval and financial capability as
  locked.

The safety path separately enforces freshness, target match, paper-only state,
source quality, and failure absence before the existing 15m safety policy may
be accepted. The policy cannot bypass a stale or mismatched evidence row.

No new adapter, source dependency, collection loop, scheduler loop, score,
rank, confidence value, or weighted logic was added. Existing recorders retain
their Central Scheduler enqueue helpers; external collection remains owned by
existing Source Governor paths.

## Verification

Focused shared-context tests prove:

* a complete exact bundle resolves all six foundations without writes;
* future context/evidence is not attached;
* dirty snapshots and mismatched evidence fail closed;
* missing governed snapshot trace blocks flow and chart;
* stale safety cannot bypass freshness through the 15m policy;
* timed engine collection helpers enqueue pending Central Scheduler jobs;
* short and reversed windows are rejected.

Result: `7 passed`.

Nearby individual regressions passed for market, chain heat, safety/quote,
clean-context, and Lane 3 freshness/target behavior. The aggregate nearby
pytest process exited without a normal summary in this Windows/Python 3.14
environment. The relevant tests were narrowed and run individually with normal
passing summaries; no assertion failure was found. This runner instability is
retained as an efficiency risk rather than represented as an aggregate pass.

`py_compile` passed for the new module and test. The lock-language scan found
only flow-domain `wallet_participation` references and explicit false-valued
downstream lock fields. It found no wallet connection, key, execution, scoring,
ranking, confidence, or weighted decision capability.

## One-Command Integration Remaining

This lane intentionally did not modify or prove the one-command runner. A
later explicitly approved integration lane may call the shared resolver from
the one-command close path and prove the handoff. That work must preserve the
existing timing, identity, replay, Source Governor, Central Scheduler, Lane Q,
and clean-memory gates.

The TRACK_NORMAL five-versus-six snapshot mismatch remains untouched. No live
provider behavior was tested in this mini-sprint.

## Money Usefulness

The repair makes clean-memory context evaluation more honest and reusable. It
reduces the chance that a future window is labeled clean using future, stale,
untraced, mismatched, or incomplete context. Entry/exit realism and safety stay
mandatory, while market and chain conditions remain explanatory context only.

## Functionality Risks / Setbacks / Efficiency Blockers

* The shared resolver is not yet integrated into the one-command path by
  design; this closeout proves the foundation independently.
* GeckoTerminal provider-contract claims remain
  `UNKNOWN_REQUIRES_RESEARCH` because the referenced source-stack module is
  absent.
* Flow detail depends on side-aware and wallet fields present in governed
  snapshots; unavailable fields must remain cautionary or unknown.
* Chain migration and survival context can only be as complete as the existing
  governed broad-context payload.
* The aggregate pytest runner terminated without a summary; narrowed relevant
  tests passed normally, but the environment-level runner issue remains.

## Preserved Locks

No persistent database was mutated. No one-command proof, retrieval, paper
decision, BUY/SELL/HOLD action, position, trade, audit, PnL, longer-window
activation, wallet, key, real-fund, live-execution, paid-API, embedding, vector,
score, ranking, confidence, or weighted logic was created or enabled.

## Next Step

Stop after this shared foundation closeout. The next task, only with explicit
operator approval, is a narrow one-command shared-context integration and
isolated proof lane. Do not begin it automatically, do not address the
TRACK_NORMAL mismatch here, and do not begin V2-5.
