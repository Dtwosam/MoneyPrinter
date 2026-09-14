# Printer V1 Handoff

## Current capability

Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` at
telemetry-change basis `f6412fe4276409c2e69b627fefda470f76ec1200`. Printer remains
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

Migration 064 development repair exists for the separate immutable
`CYCLE1_LIFECYCLE_STARTED_PRE_CYCLE2_ATTEMPT` provenance shape; the
authoritative DB remains at migration 063. The consumed authorization remains
permanently non-reusable. The primary operational blocker remains an
unidentified SQLite writer: attribution telemetry now records bounded,
per-invocation application connection/transaction evidence outside SQLite, but
has not yet observed another operational contention event.

## Exact next permitted action

No new operational run has occurred. The next permitted action is a separate
review of the telemetry change, then the existing read-only migration-064
application preflight and authorization process against then-current Git/DB
identity. Do not run Standard-4H or reuse the consumed authorization.
