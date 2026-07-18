# Printer V1 V2-9.7D.4A Token-Local Selective Continuation Closeout

## Status

`V2_9_7D_4A_TOKEN_LOCAL_SELECTIVE_CONTINUATION_PASS`

V2-9.7D.4A adds a pure, fail-closed policy for exactly two campaign tokens.
Each token is evaluated independently for `WINDOW_15M -> WINDOW_1H` or
`WINDOW_1H -> WINDOW_4H`. Shared DB, lease, integrity, and campaign-budget
failures block both tokens. No runtime or persistence path is added.

## Money-Usefulness Contribution

The policy spends longer-window attention only when a clean, exact,
traceable predecessor has an unresolved longer-window learning need. It avoids
wasting source and scheduler budgets on every timeframe for every token while
preserving useful survival, collapse, revival, distribution, transition, and
liquidity-deterioration lessons.

## What 4A Improves

- Fixed categorical continuation and stop verdicts for 15m-to-1h and 1h-to-4h.
- Exact campaign, configuration, slot, token, mint, pair, lifecycle, and
  predecessor-window identity checks using the V2-9.7D.3A validator.
- Clean evidence, completeness, freshness, governed provenance, safety,
  continuity, learning-need, lifecycle, and budget gates.
- Token-local isolation: one token's dirty evidence, blocker, or exhausted
  token budget does not stop the other eligible token.
- Shared-failure handling that blocks both tokens when campaign safety is no
  longer trustworthy.
- Deterministic, idempotent evaluation with immutable inputs and no mutation.

## What 4A Does Not Unlock

4A does not fetch sources, execute scheduler work, orchestrate campaigns,
mutate a database, collect 15m/1h/4h data, capture 5m support evidence, create
trajectory or checkpoint objects, rotate tokens, or provide an operational
PowerShell command. It does not create clean memory, activate retrieval, create
paper decisions, unlock BUY/SELL/HOLD, create positions, trades, paper audits,
or PnL. Live execution, wallets, private keys, paid APIs, scoring, ranking,
confidence percentages, weighted logic, embeddings, and vectors remain locked.

## Proof Completed

Focused tests prove only token A continues 15m-to-1h; only token B continues
1h-to-4h; both stop cleanly after 15m; one blocks while the other continues;
dirty or stale evidence is token-local; identity and predecessor mismatch fail
closed; missing safety context blocks; token-local budget exhaustion is
isolated; shared campaign budget and shared infrastructure failures block both;
repeated evaluation is deterministic and idempotent; and no locked-capability
rows are created.

Directly affected window-continuity, clean-evidence, and safety regressions also
passed. Timeout diagnosis proved that sandbox-denied directory creation under
the mandated `C:\tmp` caused Python's Windows `tempfile.mkdtemp()` permission
retry path to appear hung before SQLite setup began. No 3A production or test
behavior had changed, and no harness repair was required.

With temporary-directory access available outside that denying filesystem
sandbox, all five `ReportPredecessorTests` passed in 17.13 seconds (18.672
seconds wall time). All 23 focused 3A tests plus 23 subtests then passed in
17.22 seconds, and all 14 focused 3B tests plus 4 subtests passed in 3.72
seconds. Focused 4A tests were not rerun because neither implementation nor
test code changed after their prior PASS.

## Functionality Risks / Setbacks / Efficiency Blockers

- This policy consumes already-evaluated categorical evidence. A later runtime
  must exact-link those values without weakening their source contracts.
- Production campaign and token budget allocation values are not established
  here; exhausted budgets block continuation instead of being inferred.
- A valid close with no unresolved learning need stops normally. Unsupported
  learning-need vocabulary blocks instead of guessing.
- The policy does not enqueue a successor window. Scheduler execution and
  campaign orchestration remain later, separately approved work.
- `WINDOW_5M_MICRO_EVENT` remains support-only and has no continuation authority.
- Tests that create temporary SQLite databases under `C:\tmp` require actual
  write permission to that directory; a denying filesystem sandbox can mimic a
  test hang before SQLite setup starts.

## Next Recommended Phase

Stop after the scoped PASS commit. Do not begin conditional 5m capture or any
later V2-9.7D lane without an explicit operator request.
