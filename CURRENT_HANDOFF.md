# Printer V1 Handoff

## Current capability

Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`. Printer remains
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
authoritative DB remains at migration 63/063. Dedicated migration-only,
exact-one-migration authorization infrastructure now supports separate
prepare/review/marker-first consume/apply evidence without granting runtime
authority. It is hardened against marker-namespace switching and migration
SQL-byte TOCTOU. The primary operational blocker remains an unidentified
SQLite writer: attribution telemetry exists but has not yet observed another
operational contention event. Consumed authorizations remain permanently
non-reusable.

## Exact next permitted action

No new operational run has occurred. The next permitted action is a fresh
read-only migration-064 preflight, then real migration-064 authorization
preparation/review through the hardened mechanism. Application requires
separate explicit operator approval. Do not run Standard-4H or reuse the
consumed authorization.
