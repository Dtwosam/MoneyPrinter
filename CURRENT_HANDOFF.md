# Printer V1 Handoff

## Current capability

Active branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`. Printer remains
Solana-only, memecoin-only, and paper-only. Source Governor remains the sole
source-request owner and Central Scheduler the sole scheduler owner; all
evidence, provenance, freshness, clean-memory, and capability gates fail
closed.

The authoritative DB at `data/printer_v1.sqlite3` is now at migration `64 /
064_four_token_started_lifecycle_zero_attempt_provenance.sql`; post-application
SHA-256 is `f4371a5774af25351c3a1c6a2c158b05d56bd9e6ff4673ccc6b27732349cf13e`.
Dedicated migration-only exact-one-migration authorization infrastructure remains
separate from runtime authority.

## Latest meaningful result

Migration authorization `V2_9_8B_MIGRATION_064_AUTH_20260914T115201Z_1506c3c7`
remains consumed exactly once and migration `64/064` remains healthy.

Standard-4H authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260914T123005Z_565f8c31` was consumed exactly
once. Its run failed before lifecycle start with
`planned-lifecycle zero-attempt provenance requires a fresh transaction`.
The repair rolls back an incomplete transaction when `_ExternalStop` crosses
the factory boundary, preserving the provenance recorder's independently-owned
fresh `BEGIN IMMEDIATE`; focused disposable integration coverage passes.

The post-failed-run authoritative DB is
`98232a9cb09072c854a679c1cfba8ea5461a0ada6cb2bea3c41a34d9e999b0d0`.
The failed campaign remains active with cleanup/lease/Scheduler residue; no
future Standard-4H authorization may be prepared before zero state is restored.

## Proven blocker

The primary operational blocker remains an unidentified SQLite writer.
Attribution telemetry recorded failed `BEGIN` attempts but no qualifying
contention attribution, so the SQLite writer root cause is still unproven.

## Exact next permitted action

The next permitted action is a separate read-only reconciliation preflight/design
for failed execution `20260914T123749Z-f4617e1d5431`, followed by explicit
operator approval before any cleanup mutation. Do not reuse a consumed
authorization or describe a Standard-4H rerun as permitted.
