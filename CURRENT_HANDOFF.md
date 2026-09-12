# Printer V1 Handoff

## Current capability
Branch: `assistant/v2-9-8b-cycle2-admission-deadline-repair`, based on `15a17e61083b7cad37160b3406f08218c4d6cfdb`. Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor remains the sole source-request owner and Central Scheduler the sole scheduler owner. Only clean evidence may become training memory.

## Latest meaningful result
The Standard-4H campaign `20260911T212849Z-8a031170186f-campaign` ended at `2026-09-12T01:16:29Z`: factory run `66679371-3317-466e-9e30-93487fee5f67` is `SAFE_STOPPED`; campaign/Cycle 1 are `TERMINAL_BLOCKED / LEASE_RENEWAL_LEASE_EXPIRED`. Canonical read-only active-work accounting reports `clean_terminal=true` with zero active jobs/work, zero pending/running run steps, zero active factory runs, zero refresh waits/pre-admission attempts, and no locked jobs.

The lease terminal is environmental, not a newly proven Printer defect. Durable heartbeat evidence shows last heartbeat `00:58:53Z`, lease expiry `01:00:23Z`, and delayed renewal attempt `01:16:28Z`. macOS power logs prove Clamshell Sleep began `01:59:01 +0100` (`00:59:01Z`) and the first sleep-service wake occurred `02:16:06 +0100`, exactly spanning the missing renewal interval.

## Proven blocker and repair
Cycle 2 had independently terminalized `NO_PAIR / DURATION_EXHAUSTION` while clean provider work, discovery capacity, eligible reserves, and unexplored candidates remained. Root cause: the canonical admission boundary anchors the later-cycle deadline to the later of Cycle-1 admission and authoritative factory `started_at`, then adds 600 seconds; the rebound temporal owner used only the earlier Cycle-1 timestamp and therefore created an already-expired owner deadline.

Repair: `PreLifecycleTemporalRefreshOwner.for_cycle()` preserves the durable Cycle-1 anchor and, when canonical campaign/factory run tables are present, resolves the authoritative factory run and uses the later factory `started_at` before applying the 600-second window. Minimal fixtures without those tables retain fallback behavior.

TDD proof: before the production change, the focused regression expected `00:18` from factory start `00:08` but received stale `00:10`. Focused isolated verification after the fix: later-cycle suite 7 passed; wake-ordering suite 9 passed; `git diff --check` passed. The consumed authorization remains permanently non-reusable.

## Exact next permitted action
Integrate this repair into the idle parent branch after fresh focused verification. Do not operationally rerun from the consumed authorization. Any future provider-driven attempt requires a fresh one-shot authorization bound to the then-current HEAD and DB, all health/zero-active-work gates, and new explicit operator approval.
