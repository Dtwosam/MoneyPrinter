# Printer V1 Post-RC Lane 9 BUY Unlock Preconditions

## 1. Status and Authority

This is Post-RC Lane 9 documentation-only policy.

This document is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`

This document does not enable BUY.

This document does not allow paper positions, trade events, paper trade audits, PnL, wallet logic, live trading, real funds, private keys, signing, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

This document only defines future preconditions for a later operator-approved BUY review lane.

Current BUY status: locked.

Until a separate future operator-approved BUY unlock lane exists, WAIT, AVOID, and NO_ACTION remain the only conservative actions Printer may use when data, memory, context, or realism is weak.

## 2. Explicit Non-Approval Statement

Lane 9 is policy documentation only.

Lane 9 does not authorize:

- BUY decisions
- SELL decisions
- HOLD decisions
- paper position opening
- paper trade monitoring activation
- paper trade events
- PnL calculation
- live trading
- any code path that treats this policy as an executable approval

Any future BUY review must start from the position that BUY is still locked and must prove every gate below before an operator may consider a later unlock lane.

## 3. Minimum Clean Memory Review Gates

BUY must not be reviewed seriously until Printer has enough completed, clean, main-window memory to compare current setups against past outcomes.

Suggested planning thresholds only:

- 50-100 clean 15m memories before serious BUY or holding review
- 30+ clean 1h memories before continuation behavior is trusted
- 10+ clean 4h memories before medium-term holding behavior is trusted

These are review gates, not automatic approval.

Clean memory used for review must be:

- CLEAN_MEMORY
- retrieval-ready
- source-governed
- linked to complete main outcome windows
- backed by target-matched evidence
- audited without hidden blockers
- free of do_not_train flags
- free of stale, failed, conflicting, missing-critical, audit-only, or dirty evidence

Dirty, stale, audit-only, do_not_train, missing-critical, failed, or conflicting memory cannot count toward BUY review.

WINDOW_5M_MICRO_EVENT evidence cannot count as a main clean memory window and cannot unlock BUY by itself.

## 4. Memory Diversity Requirements

Printer must not treat one token, one pair, one source condition, or one repeated evidence shape as broad market proof.

A future BUY review must show:

- multiple distinct token/pair examples
- multiple market and Solana context conditions
- successful and failed outcomes
- WAIT and AVOID examples, not only pump examples
- examples where entry was realistic
- examples where exit was realistic
- examples where late entry failed or profit was unrealistic
- no indistinguishable duplicate evidence inflation
- no same-token concentration presented as broad confirmation

Same-token memories may remain useful, but they must be labeled as same-token evidence and must not be counted as broad market diversity.

## 5. Clean-Only Retrieval Requirements

Future BUY review may only use retrieval results from clean eligible memory.

Retrieval must exclude:

- DIRTY_MEMORY
- AUDIT_ONLY memory
- DO_NOT_TRAIN memory
- stale memory
- failed-source memory
- conflicting memory
- missing-critical memory
- 5m-only support evidence
- indistinguishable duplicate evidence

Retrieval must report:

- similar clean memories found
- distinct token count
- dominant token or pair concentration
- best historical action
- worst historical action
- failed comparable outcomes
- limited diversity warnings
- whether broader clean memory is still needed

Retrieval must not use scores, ranks, confidence percentages, weighted outputs, or numeric decision scores.

## 6. Current Token Context Requirements

A current token setup cannot be considered for future BUY review unless its context is fresh, source-governed, target-matched, and attached to the current evidence window.

Required current-token context includes:

- token-level snapshots
- market regime context
- Solana chain heat context
- safety and rug evidence
- liquidity and exit realism evidence
- entry realism evidence
- trading flow direction and pressure
- chart and volatility context
- micro-event support evidence when relevant
- source request, response, and failure visibility

Market regime and Solana chain heat are context only. They must not become direct trade signals.

Safety is protection only. It must not create BUY by itself.

Liquidity, entry realism, and exit realism determine whether a paper trade would have been realistic.

## 7. Safety Requirements

Safety must be known, current enough for the evidence window, and target-matched before any future BUY review.

Safety review must include, where supported:

- mint authority state
- freeze authority state
- metadata mutability
- token program
- supply sanity
- holder concentration or an honest unknown label
- liquidity lock, burn, or availability evidence
- known risk flags
- source trace linkage
- target status
- data quality label

Severe safety risk must block BUY review.

Unknown, failed, stale, dirty, mismatched, or audit-only safety evidence cannot support BUY.

## 8. Liquidity and Exit Realism Requirements

A future BUY review must prove realistic paper entry and realistic paper exit before any later lane can consider a paper position.

Required realism context includes:

- entry route availability
- exit route availability
- liquidity depth or available proxy
- quote freshness
- slippage context
- price impact context
- no-route reasons when routes fail
- source failure visibility
- target match to the current token/pair/snapshot/window

Paper profit must not be claimed if entry or exit would not have been realistic.

No-route, stale quote, failed quote, target mismatch, non-paper-only evidence, or missing quote evidence must remain blocking or audit-only.

## 9. Snapshot and Evidence Requirements

Every future BUY review candidate must be backed by complete, governed, target-matched evidence.

Required evidence properties:

- source-governed
- scheduler-compatible
- source requests recorded
- source responses recorded
- source failures visible
- captured_at or equivalent timing visible
- evidence identity linked to the memory window
- complete main memory window coverage
- no fabricated context
- no stale old evidence used as fresh evidence
- no dirty evidence promoted to clean

Incomplete evidence can remain stored for audit, but it cannot support BUY review.

## 10. 5m Support-Only Rule

WINDOW_5M_MICRO_EVENT remains support-only.

5m support evidence may help explain:

- fast pump behavior
- fast dump behavior
- late-buy traps
- wick-only movement
- micro-exit realism
- held-to-15m results

5m support evidence must not:

- satisfy a 15m, 1h, 4h, 12h, or 24h main memory requirement
- unlock retrieval by itself
- unlock BUY by itself
- open paper positions
- create paper trade events
- create PnL

Dirty or audit-only 5m support remains audit-only.

## 11. Required Future BUY Explanation Template

Any future operator-approved BUY review lane must require a written explanation in this shape before a BUY can be considered:

```text
Decision:
Current setup:
Market condition:
Solana condition:
Safety state:
Liquidity and entry realism:
Exit realism:
Trading flow and chart context:
Similar clean memories found:
Memory diversity:
What happened in those memories:
Best historical action:
Worst historical action:
Current action:
Reason:
Invalidation condition:
Paper trade status:
Audit requirements:
```

This template is not an approval to create BUY now.

## 12. Invalidation Requirements

A future BUY review must define clear invalidation conditions before any later paper position lane can be considered.

Invalidation may include:

- safety status worsens
- liquidity collapses
- entry route becomes unrealistic
- exit route becomes unrealistic
- quote evidence becomes stale
- source status fails
- Solana chain context becomes unstable
- current setup no longer matches the clean memory comparison
- flow or chart behavior contradicts the intended setup
- required monitoring cadence cannot be maintained

Invalidation must be written before paper entry is considered in any later lane.

## 13. Paper-Position Prerequisites for a Later Lane Only

Paper positions remain locked in Lane 9.

A later paper-position lane may only be reviewed after:

- a separate operator-approved BUY unlock lane exists
- a valid clean-memory-backed BUY exists
- entry realism is valid
- exit realism is valid
- safety is acceptable
- paper size bucket policy exists
- invalidation condition exists
- monitoring cadence exists
- audit path exists

Lane 9 does not authorize that later lane.

## 14. Audit Prerequisites

Future BUY review must be auditable before and after any decision.

Audit prerequisites include:

- clean memory audit passed
- retrieval audit passed
- source failures visible
- dirty memory remains blocked
- audit-only memory remains blocked
- no fake-profit path
- no hidden no-route quote
- no hidden safety warning
- no hidden liquidity or exit realism warning
- no broad-context-only trade justification

If any audit blocker remains unresolved, BUY remains locked.

## 15. Anti-Bias Rules

Future BUY review must avoid:

- cherry-picking only winning memories
- ignoring WAIT, AVOID, and NO_ACTION lessons
- treating one token as broad market proof
- treating same evidence duplicates as independent support
- treating 5m support as main outcome memory
- treating market regime as a direct signal
- treating Solana chain heat as a direct signal
- treating safety as a BUY creator
- treating green chart movement as proof
- converting labels into scores, ranks, confidence percentages, or weighted decisions

BUY review must show both why buying might have worked historically and why it failed or became unrealistic in similar conditions.

## 16. BUY Review Checklist

Before any future operator-approved BUY review lane, the operator must be able to answer yes to every item:

- BUY is still locked before the review starts.
- Clean 15m memory threshold is met or the operator explicitly keeps review in planning-only mode.
- Clean 1h memory threshold is met for continuation review.
- Clean 4h memory threshold is met for medium-term holding review.
- Clean memories come from diverse token/pair examples.
- Retrieval is clean-only.
- Retrieval reports memory diversity and concentration.
- Current token evidence is fresh and target-matched.
- Safety evidence is known and acceptable.
- Entry realism is known and acceptable.
- Exit realism is known and acceptable.
- Liquidity evidence supports realistic paper entry and exit.
- Flow and chart context are known but not used as standalone signals.
- Market and chain context are known but not used as standalone signals.
- 5m support evidence is support-only.
- Invalidation condition is written.
- Audit requirements are written.
- No score, rank, confidence percentage, or weighted logic is used.
- No wallet, private key, signing, transaction, live execution, or real-fund path exists.

If any item is no, BUY remains locked.

## 17. Lane 9 Acceptance Checklist

Lane 9 is complete only when:

- this policy exists
- `AGENTS.md` references this policy
- BUY remains locked
- positions remain locked
- PnL remains locked
- retrieval remains clean-only
- dirty memory remains blocked
- 5m support remains support-only
- WAIT, AVOID, and NO_ACTION remain the conservative actions
- thresholds are documented as planning gates only
- no code, migrations, runtime, source fetching, scheduler change, memory creation, retrieval run, paper decision, BUY, position, trade event, or PnL is introduced

Next work after Lane 9 should continue the Post-RC build order without treating this document as an executable unlock.
