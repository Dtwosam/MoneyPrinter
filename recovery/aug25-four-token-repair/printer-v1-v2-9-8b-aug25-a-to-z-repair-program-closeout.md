# Printer V1 V2-9.8B — Aug-25 Four-Token A-to-Z Repair Program Closeout

Date: 2026-08-25

## Authority and scope

This closeout is bounded to the byte-verified Aug-25 forensic capture rooted at
`d9c73432f9155c39d75c692867d5c7e73b5c83a1` and the consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd`.

The governing Printer V1 locks remain unchanged: Solana memecoin only, paper only,
no live wallet/signing/funds/execution, no paid API dependency, no scoring/ranking,
no embeddings, no Source Governor bypass, no Central Scheduler bypass, no dirty
memory decision use, and no premature retrieval/financial capability.

No consumed authorization was reused, retried, resumed, restarted, or succeeded.
No new authorization was created. No provider/RPC/WebSocket campaign was run and no
authoritative campaign database was mutated during this repair program.

## Forensic baseline

The supplied audit archive SHA-256 was
`408132e1e292f8e3f44d878a54a5faa1dbc49ff0adfe563a38701c281b9e537f`.
All 1,383 captured repository files were independently checked against the archive
manifest with zero SHA-256 or size mismatches.

The failed Aug-25 execution was `20260825T135710Z-bd7d834a6277`. Its authoritative
DB SHA-256 was unchanged before/after the read-only forensic audit:
`2fe2106be9ab9a7959b644aff883cece9e59e9894352eb02cd08fa24d32cb5ab`.

## Proven production-code repairs

1. **Cycle-2 frozen-lane evidence projection** — already-linked governed exact-pair
   DexScreener/GeckoTerminal evidence may supplement only missing classifier market
   fields. No provider call is created, canonical evidence is not overwritten, and
   the canonical classifier remains the only lane authority.
2. **Scheduler cooperative-yield ownership projection** — campaign Scheduler-work
   may mirror `RUNNING -> PENDING` only when the exact bound Central Scheduler job
   is already released `PENDING` with lock/start ownership cleared.
3. **Heartbeat compatibility** — absence of optional `failure_event` on a no-op
   heartbeat no longer crashes pre-lifecycle owner construction.
4. **Opening-failure proof-cycle lifetime** — `owned_proof_cycle_id` exists before
   any Scheduler claim, so the original opening fault is not masked by
   `UnboundLocalError`.
5. **Exact Aug-25 historical disposition** — the exact consumed authorization ID is
   diagnostically recorded as `CONSUMED_CHILD_EXITED_ZERO`; this is not campaign
   success and creates no reuse authority.
6. **Zero-request pre-close reservation law** — a truthful zero projected request
   count emits zero source reservations; positive projected work still requires a
   bound source-unit identity and remains fail-closed.
7. **Split pre-close terminal accounting correspondence** — the three approved
   `*_PRE_CLOSE_CRITICAL` Scheduler step kinds are recognized by the existing
   canonical 15m/1h/4h terminal correspondence owner.

## Original Aug-25 failure reproof

The original 40 failed nodes were reclassified, repaired where product defects were
proven, and fixture-aligned only where the old test no longer represented the
approved contract.

- Group A authority/authorization/wrapper: **12/12 GREEN** in one fresh consolidated run.
- Group B operational entry/capacity: **GREEN**; capacity tests now derive from the
  canonical 4-token capacity authority rather than copied historical literals.
- Group C Cycle-1 lifecycle/memory: **5/5 GREEN**.
- Group D Cycle-2 wake/health/pre-admission: **5/5 GREEN**.
- Group E Cycle-2 consume/materialize: **3/3 GREEN**.
- Group F terminal accounting/acceptance: **8/8 GREEN**.
- Group G terminal closure/cleanup: **5/5 GREEN**, including genuine Migration-055
  historical reconciliation **3/3 GREEN** locally and **3/3 GREEN** in GitHub Actions.

## Focused regression proof

Fresh focused production regression suite:

- frozen-lane evidence conformance;
- Scheduler-yield ownership conformance;
- exception/terminal compatibility;
- exact Aug-25 consumed-authorization historical disposition.

Result: **14/14 GREEN**.

All seven changed production modules compile successfully and `git diff --check`
passes.

## Disposable current-schema proof

The forensic ZIP omitted `migrations/`. Canonical migrations 001–058 were recovered
from an immutable reachable repository lineage and verified by Git blob identity.
Exact original Migration 059–061 bytes were not recoverable from the archive or any
reachable ref.

For testing only, 059–061 were reconstructed from preserved approved contracts and
validated as follows:

- genuine 058→059 upgrade behavior: PASS;
- Migration 060/061 schema-gate positive and destructive-negative checks: PASS;
- reconstructed current DB versus captured Aug-25 final `db_schema.json`:
  **119/119 tables, zero missing/extra tables, zero column differences, zero primary-key differences**.

These reconstructed files are **proof-only** and are not asserted to be canonical
migration provenance.

The canonical bounded offline four-token standard-4h proof
`test_one_operational_invocation_proves_four_two_two` passes **1/1** after replacing
obsolete copied capacity literals with the canonical capacity authority. It uses a
disposable DB, frozen time, fake/frozen candidate supply, zero network/provider/RPC,
no authorization, exactly two fresh two-token cycles, no 12h/24h planning, and one
shared terminal closure.

## Fresh operational rereadiness checks

- controller + pre-admission zero-state + operational provenance + Scheduler-yield
  ownership: **32 tests GREEN + 20 subtests GREEN**;
- standard four-hour operational command: **23/23 GREEN**;
- current Lane-4 schema-gate contract: **18/18 core current-schema tests GREEN** plus
  **8/8 applicable caller/guard tests GREEN**.

One historical schema-gate test intentionally asserts the pre-application state
`Migration 059 / no 060-061 objects`. That assertion is historical and is not a valid
current Aug-25 Migration-061 readiness condition; it is not counted as current-schema
proof.

## Verdict

`AUG25_FOUR_TOKEN_A_TO_Z_REPAIR_BOUNDED_PROOF_PASS`

The seven product defects above are repaired on the byte-verified forensic source,
the original 40-failure set is re-proven GREEN by group, the bounded disposable 4/2/2
path passes, and the relevant current-schema/ownership/zero-state/operational checks
pass.

However:

`FRESH_LIVE_AUTHORIZATION_PREPARATION_NOT_AUTHORIZED_FROM_FORENSIC_CAPTURE`

Reason: the forensic capture does not contain the exact original Migration 059–061
SQL bytes. The schema-equivalent reconstructions are sufficient for bounded disposable
proof but must not be promoted to canonical migration provenance. A production checkout
must supply its exact canonical 059–061 files and pass the same rereadiness checks before
any later authorization-preparation lane can be considered.
