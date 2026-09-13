# Printer V1 Handoff

## Current capability

Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` at
source basis `3208721c3a5f57c54cae74a5875ee8115eff060a`. Printer remains
Solana-only, memecoin-only, and paper-only. Source Governor remains the sole
source-request owner and Central Scheduler the sole scheduler owner; all
evidence, provenance, freshness, clean-memory, and capability gates fail
closed.

The authoritative DB at `data/printer_v1.sqlite3` is now at migration `63 /
063_four_token_zero_attempt_terminal_provenance.sql`; migration 064 is a
development-only schema requirement and has not been applied there.

## Latest meaningful result

The consumed operational proof
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260913T220119Z_eb53caac` ran campaign
`20260913T220442Z-79f298389601-campaign` and exited nonzero in
`CAMPAIGN_PRE_LIFECYCLE`: 20 source calls, zero Scheduler runtime calls, and
six DB writes. Cleanup completed and its lease was released; the authorization
is permanently non-reusable.

## Proven blocker

Cycle-1 lifecycle had started before a lease-renewal BLOCKED stop, with no
Cycle-2 attempt. Migration 063 correctly rejected it because it owns only the
planned-but-unstarted shape. Development repair adds the separate immutable
`CYCLE1_LIFECYCLE_STARTED_PRE_CYCLE2_ATTEMPT` provenance contract; migration
064 must be separately reviewed, authorized, and applied before any future
operational preflight can pass.

## Exact next permitted action

The next permitted operational lane is a separate read-only migration-064
application preflight and authorization process against then-current Git/DB
identity. Do not run Standard-4H and never reuse the consumed authorization.
