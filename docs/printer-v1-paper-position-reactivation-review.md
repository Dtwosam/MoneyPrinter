# Printer V1 Post-RC Lane 10 Paper Position Re-Activation Review

## 1. Status and Authority

This is Post-RC Lane 10 review-only policy.

This document is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-buy-unlock-preconditions.md`

This document does not reactivate paper positions.

This document does not allow BUY.

This document does not allow SELL or HOLD.

This document does not allow paper trade events, paper trade audits, PnL, wallet logic, live trading, real funds, private keys, signing, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

This document only defines future conditions for a later operator-approved paper-position reactivation lane.

Current paper position status: locked.

## 2. Explicit Non-Approval Statement

Lane 10 is documentation and review policy only.

Lane 10 does not authorize:

- BUY decisions
- SELL decisions
- HOLD decisions
- paper position creation
- paper trade event creation
- paper trade audit creation
- PnL calculation
- runtime activation
- live trading
- any code path that treats this policy as executable approval

WAIT, AVOID, and NO_ACTION remain the conservative non-position decisions while BUY, SELL, HOLD, and paper positions remain locked.

SELL and HOLD only matter after a paper position exists, and Lane 10 does not create or authorize that position.

## 3. Relationship to Lane 9 BUY Preconditions

Lane 10 depends on Lane 9.

A paper position can never exist without a valid clean-memory-backed paper BUY decision from a later approved lane.

Lane 10 does not approve or enable that BUY decision.

Lane 10 only defines what must be true before a future operator can review whether paper positions may be reactivated after BUY has already been separately approved.

If Lane 9 BUY preconditions are not satisfied, Lane 10 position review remains blocked.

## 4. Valid Clean-Memory-Backed BUY Requirement

Any future paper-position review must start with a valid paper BUY decision from a later operator-approved lane.

That BUY must be:

- clean-memory-backed
- retrieval-supported by clean eligible memory only
- explained with best and worst historical action
- based on diverse memory, not one token or duplicate evidence
- target-matched to the current token/pair/window
- supported by fresh current context
- blocked if safety, liquidity, entry realism, exit realism, or source status is unknown or failed

Dirty, stale, audit-only, do_not_train, missing-critical, failed, or conflicting memory cannot support positions.

## 5. Current Token Context Requirements

Before any future position review, current token context must be complete enough to explain why entry, monitoring, and exit are realistic.

Required context includes:

- current token snapshots
- source request, response, and failure visibility
- market regime context
- Solana chain heat context
- safety and rug evidence
- liquidity and exit realism evidence
- entry realism evidence
- trading flow direction and pressure
- chart and volatility context
- relevant 5m support evidence as support only

Market regime and Solana chain heat remain context only. They must not create positions.

Safety remains protection only. It must not create positions.

## 6. Paper Size Bucket Requirements

Future paper positions must use explicit size buckets.

A later lane must define:

- allowed paper size bucket names
- dollar amount or notional range per bucket
- liquidity requirements per bucket
- slippage tolerance per bucket
- price impact limits per bucket
- maximum paper exposure per token/pair
- whether the selected bucket can realistically enter and exit

The size bucket must be selected before paper entry and stored with the paper position if a later lane allows positions.

No future paper position may assume perfect liquidity or unlimited fill size.

## 7. Entry Realism Requirements

Future paper entry must be realistic before a position can be reviewed.

Entry realism must include:

- route availability or equivalent paper-only entry evidence
- fresh quote or source-backed entry proxy
- slippage context
- price impact context
- liquidity context
- source status
- data quality label
- target match to the current token/pair/snapshot/window
- no hidden no-route reason

Unknown, stale, failed, mismatched, non-paper-only, or audit-only entry evidence blocks paper position review.

## 8. Exit Realism Requirements

Future paper exit must be realistic before a position can be reviewed.

Exit realism must include:

- route availability or equivalent paper-only exit evidence
- fresh quote or source-backed exit proxy
- exit liquidity context
- slippage context
- price impact context
- no-route reason when exit is unavailable
- source status
- data quality label
- target match to the current token/pair/snapshot/window

A paper profit is not clean if Printer could not realistically exit.

Unknown, stale, failed, mismatched, non-paper-only, or audit-only exit evidence blocks paper position review.

## 9. Invalidation Condition Requirements

No future paper position may be reviewed without a written invalidation condition.

Invalidation must define what forces the paper thesis to stop, such as:

- safety worsens
- liquidity collapses
- entry or exit route disappears
- quote evidence becomes stale
- price impact becomes unrealistic
- Solana chain context becomes unstable
- market context changes outside the compared memory condition
- flow flips against the setup
- chart structure invalidates the setup
- source failures make monitoring unreliable
- monitoring cadence cannot protect exits

Invalidation must be specific enough that a later paper monitor can act without inventing judgment after the fact.

## 10. Monitoring Cadence Requirements

Paper positions remain locked until a later lane proves monitoring can protect exits.

A future review must define:

- normal monitoring cadence
- accelerated monitoring cadence during dumps, liquidity decay, flow flip, or invalidation risk
- source-governed snapshot requirements
- quote or exit-realism refresh requirements
- safety refresh requirements
- maximum tolerated stale evidence age
- stop condition if monitoring cannot continue

Monitoring must not become an unbounded runtime or independent source loop.

Open paper-trade monitoring remains the highest resource priority only after paper positions are explicitly allowed in a later lane.

## 11. Audit Path Requirements

Before paper positions can be reactivated in a later lane, the audit path must be ready.

Audit must be able to record:

- BUY explanation
- matched clean memories
- best historical action
- worst historical action
- entry source status
- entry liquidity
- entry slippage and price impact
- selected paper size bucket
- invalidation condition
- monitoring cadence
- exit source status
- exit liquidity
- exit slippage and price impact
- realistic or unrealistic result
- source failures
- safety changes
- fake-profit prevention labels

If the audit path cannot show whether the trade was realistic, paper positions remain locked.

## 12. Liquidity, Slippage, and Price Impact Requirements

Liquidity and execution realism must be checked before entry and before exit.

Future paper position review must reject or block:

- thin liquidity
- missing liquidity
- stale liquidity
- unrealistic slippage
- excessive price impact
- no-route entry
- no-route exit
- source-failed quotes
- target-mismatched quotes
- paper size bucket larger than realistic liquidity

Printer must not claim paper profit from chart movement alone.

## 13. Safety Requirements

Safety must be acceptable before any future paper position review.

Required safety review includes:

- mint authority
- freeze authority
- metadata mutability
- token program
- supply sanity
- holder concentration or honest unknown blocker
- liquidity lock, burn, or availability evidence where supported
- known risk flags
- source trace linkage
- target status
- data quality label

Severe safety risk blocks paper position review even if memory comparison appears favorable.

## 14. No 5m-Only Position Unlock Rule

WINDOW_5M_MICRO_EVENT remains support-only.

5m support evidence may inform:

- late-buy trap risk
- fast dump risk
- fast pump behavior
- micro-exit realism
- held-to-15m outcome

5m support evidence must not:

- unlock paper positions by itself
- satisfy main 15m, 1h, 4h, 12h, or 24h memory requirements
- create BUY
- create SELL
- create HOLD
- create PnL

Dirty or audit-only 5m support remains audit-only.

## 15. No Dirty-Memory Position Support Rule

Paper position review must use clean eligible memory only.

The following cannot support positions:

- DIRTY_MEMORY
- AUDIT_ONLY memory
- DO_NOT_TRAIN memory
- stale memory
- failed-source memory
- conflicting memory
- missing-critical memory
- duplicate evidence treated as independent support
- 5m-only support evidence

If clean memory is insufficient, Printer must remain in WAIT, AVOID, or NO_ACTION.

## 16. No Fake Profit and No Perfect-Top Exit Rule

Future paper positions must not assume perfect entry, perfect exit, or perfect top selling.

Audit must mark outcomes honestly:

- realistic paper profit
- fragile paper profit
- unrealistic paper profit
- paper loss
- round-trip
- missed entry
- late entry trap
- correct wait
- correct avoid
- wrong wait
- wrong avoid

If Printer could not realistically enter or exit at the required size bucket, the result must not be counted as clean profit.

## 17. Future Paper Position Review Checklist

Before any later paper-position reactivation lane, every item must be true:

- Paper positions are still locked before review starts.
- A separate operator-approved BUY unlock lane has already approved BUY.
- The current BUY is valid and clean-memory-backed.
- Retrieval uses clean eligible memory only.
- Memory diversity and concentration are reported.
- Current token context is fresh and target-matched.
- Safety is acceptable.
- Entry realism is valid.
- Exit realism is valid.
- Liquidity supports the selected paper size bucket.
- Slippage and price impact are realistic for the size bucket.
- Invalidation condition is written.
- Monitoring cadence is defined.
- Audit path can record entry, monitoring, exit, and realism.
- 5m evidence is support-only.
- Dirty, stale, audit-only, do_not_train, missing-critical, failed, or conflicting memory is excluded.
- No score, rank, confidence percentage, or weighted logic is used.
- No wallet, private key, signing, transaction, live execution, or real-fund path exists.

If any item is false, paper positions remain locked.

## 18. Lane 10 Acceptance Checklist

Lane 10 is complete only when:

- this review policy exists
- `AGENTS.md` references this policy
- paper positions remain locked
- BUY remains locked unless a separate future lane explicitly approves it
- SELL and HOLD remain locked because no paper position exists
- PnL remains locked
- trade events remain locked
- paper trade audits remain locked
- WAIT, AVOID, and NO_ACTION remain conservative non-position decisions
- 5m support remains support-only
- dirty memory remains blocked
- no code, migrations, runtime, source fetching, scheduler change, memory creation, retrieval run, paper decision, BUY, SELL, HOLD, position, trade event, paper trade audit, or PnL is introduced

Next work after Lane 10 should continue the Post-RC build order without treating this document as an executable reactivation.
