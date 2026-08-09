# Printer V1 V2-9.8B post-DTW95 WINDOW_15M consumed-attempt closeout

Verdict: `V2_9_8B_POST_DTW95_WINDOW_15M_ONE_SHOT_BLOCKED_CONSUMED_SQLITE_LOCK_CONTENTION`

## Controlling attempt

- Authorization: `V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z`
- Authorized Git branch: `agent/v2-9-8b-post-dtw94-window15m-authorization-preparation`
- Authorized Git HEAD: `b44e7156dfd1979582502190385a0f45f67c41e6`
- Authorization SHA-256: `27f6ec95b7de6cdfeed92c12bcb6f8b095c3c1d7c870efba112ac85ae8ca6778`
- Campaign: `20260809T090333Z-56eeebf551fa-campaign`
- Campaign run: `20260809T090333Z-56eeebf551fa-campaign-run`
- Factory run: `5f16f9d4-b0bb-4929-affe-8979d38de962`
- Wrapper invocation count: exactly one
- Retry / rerun / restart / resume / successor: zero
- Host-awake guard: used (`caffeinate -dimsu`)

The authorization application marker was consumed. This authorization is permanently non-reusable regardless of outcome.

## Terminal truth

The wrapper child exited zero, but the campaign did not pass. The factory terminal was `SAFE_STOP_PREFLIGHT_FAILED`; the authoritative factory report preserved the underlying exception as:

`OperationalError: database is locked`

The run entered lifecycle. Both tokens completed snapshot steps `00` through `07` (eight snapshots each). Neither `WINDOW_CLOSE` started. Both close jobs were still pending and were terminally cancelled during cleanup.

The first close was scheduled for `2026-08-09T09:18:50.231583+00:00`. The run safe-stopped at approximately `2026-08-09T09:17:34.53+00:00`, before either close was due.

Campaign supervision remained healthy: the heartbeat successfully advanced at `2026-08-09T09:17:34.512219+00:00`, lease expiry advanced to `2026-08-09T09:19:04.512219+00:00`, and no heartbeat-failure row exists. Cleanup completed and the lease was released.

## Classification

This attempt does not prove a clean 15-minute memory closeout. It also does not prove a memory-quality blocker, holder blocker, source blocker, or lease-expiry blocker. The controlling blocker is SQLite lock contention during the live lifecycle before either close became due.

The generic `SAFE_STOP_PREFLIGHT_FAILED` label is not the root cause; the underlying runtime exception is authoritative for this audit.

## Safety / capability state

No authorization reuse is allowed. No new `WINDOW_15M` run is allowed until the SQLite contention defect is audited, designed, implemented if approved, proven with bounded offline/fixture evidence, and closed out, followed by fresh read-only rereadiness and a new one-use authorization.

No change is authorized to lease duration, heartbeat cadence, Source Governor, Central Scheduler, source budgets, holder rules, memory-quality rules, retrieval, decisions, BUY/SELL/HOLD, paper positions, trade events, audits, or PnL.

## Money-usefulness contribution

This closeout preserves the only useful interpretation of the attempt: Printer successfully progressed through live two-token observation but lost the campaign to infrastructure contention before memory close. Fixing that contention improves the probability that paid-free public evidence already collected reaches a durable 15-minute memory result without weakening evidence or trading safeguards.

## Functionality Risks / Setbacks / Efficiency Blockers

- A legitimate concurrent SQLite writer can currently abort the lifecycle before close.
- The outer factory label hides the specific runtime lock cause as `SAFE_STOP_PREFLIGHT_FAILED`.
- Re-running without repair would waste another one-use authorization and live-source budget.
- Widening leases or adding source retries would not address the observed defect and is forbidden.
