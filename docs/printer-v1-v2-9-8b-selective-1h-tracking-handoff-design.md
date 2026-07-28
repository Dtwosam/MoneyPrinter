# Printer V1 V2-9.8B Selective-1h Tracking Handoff Design

## Goal

Make discovery selection, holder admission, and tracking handoff share one
categorical view of the latest exact token/pair/lane queue state. Preserve
existing lifecycle revival ownership, atomic two-slot activation, Source
Governor and Central Scheduler ownership, and truthful terminal causes.

## Exact identity and current state

The handoff identity is:

```text
(token_mint, pair_address, tracking_lane)
```

The corresponding row is resolved through the canonical token, pair, and queue
tables. If history exists, the highest queue-row id for that exact identity is
the current categorical state. A different pair for the same mint is a distinct
handoff identity. No row is fresh.

## Categorical state contract

| Latest exact status | Category | Selection/holder behavior | Handoff behavior |
|---|---|---|---|
| no row | `FRESH_TRACKING_IDENTITY` | eligible | one new `QUEUED` row may be created |
| `QUEUED` | `DUPLICATE_ACTIVE_TRACKING` | exclude; continue bounded reserve | fail closed; do not enqueue |
| `ACTIVE` | `DUPLICATE_ACTIVE_TRACKING` | exclude; continue bounded reserve | fail closed; do not enqueue |
| `PAUSED` | `DUPLICATE_ACTIVE_TRACKING` | exclude; continue bounded reserve | fail closed; do not enqueue |
| `COOLDOWN` | `COOLDOWN_REOPEN_REQUIRED` | exclude; continue bounded reserve | fail closed; do not enqueue or reopen |
| `SKIPPED` | `TERMINAL_TRACKING_STATE` | exclude | fail closed; no implicit reopen |
| `ARCHIVED` | `TERMINAL_TRACKING_STATE` | exclude | fail closed; no implicit reopen |
| unknown/null | `UNSUPPORTED_TRACKING_QUEUE_STATE` | exclude | fail closed |

`COOLDOWN` is deliberately neither fresh nor active ownership. This removes the
mislabel while retaining the no-duplicate/no-silent-reactivation boundary.

## Revival ownership

The existing `lane_x3_post_cycle_lifecycle.reopen_token()` owner remains the
only committed categorical reopen operation reviewed for this repair. It:

- records `REOPEN_REVIVED_TOKEN`;
- preserves the prior cooldown/archive history;
- appends a `WATCH_ONLY` / `QUEUED` row.

The combined discovery path does not call, copy, or broaden that operation. A
valid reopen is already live ownership under `WATCH_ONLY`; discovery must not
add a second live row or silently promote it into the selective-1h
`TRACK_NORMAL` handoff.

## Owner flow

```text
bounded graduated reserve
-> exact queue assessment before holder admission
-> skip known conflict without holder maturation/source work
-> keep walking bounded reserve until two holder-eligible candidates or exhaustion
-> combined discovery exact queue gate before uniform selection
-> atomic two-slot preflight
-> exact queue assessment immediately before enqueue
-> queue owner enqueue
-> Central Scheduler owner creates first-15m jobs
-> both slots commit or both roll back
```

The pre-holder assessment saves avoidable holder budget. The selection gate
allows a lawful reserve alternative to replace a conflict. The immediate
pre-enqueue assessment is defense in depth and reports the actual category if
state changes between selection and handoff.

## Truthful terminal behavior

- If two eligible alternatives remain, the conflict is non-terminal and the
  campaign proceeds with those alternatives.
- If queue exclusions reduce the initial pool below two, the first deterministic
  queue category becomes the first terminal cause.
- A genuine latest `QUEUED`, `ACTIVE`, or `PAUSED` collision remains
  `DUPLICATE_ACTIVE_TRACKING`.
- A cooldown collision is `COOLDOWN_REOPEN_REQUIRED`, never active duplication.
- Atomic handoff exceptions retain their existing all-or-neither rollback and
  first-fault reporting.

No retry, restart, successor, or implicit reopen follows any category.

## Implementation scope

Allowed code owners:

- `src/printer_v1/lifecycle/tracking_queue.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- focused temporary-DB tests

No migration or parallel tracking subsystem is required.

## Proof matrix

| Requirement | Offline proof |
|---|---|
| Fresh creates one row | enqueue twice; first succeeds, second refuses; count one |
| `QUEUED`/`ACTIVE`/`PAUSED` excluded | category unit proof plus executor reserve substitution for each |
| cooldown without revival excluded | category proof plus executor reserve substitution/shortfall proof |
| valid revival canonical | call existing reopen owner; verify event, preserved cooldown, one live `WATCH_ONLY` row |
| skipped/archive rules | exact category/enqueue refusal |
| same mint/pair vs new pair | first conflicts; second is fresh and enqueues |
| alternative survives conflict | three-candidate executor fixture selects the two fresh identities |
| atomic two-slot | existing before-first/during-second/scheduler-failure regressions |
| active reason | injected latest `ACTIVE` collision remains exact |
| cooldown reason | insufficient pool reports `COOLDOWN_REOPEN_REQUIRED` |
| no duplicates/orphans | row/job counts after success and rollback |
| governor/scheduler ownership | owner-port executor regressions and job-kind checks |
| no downstream unlock | locked-table and forbidden-window assertions |

## Rollback

Revert the three code-owner changes and focused tests/docs in the repair commit.
No DB rollback, migration reversal, historical-row cleanup, or proof-ceiling
change is part of rollback.

## Functionality Risks / Setbacks / Efficiency Blockers

- Exact latest-row semantics depend on lifecycle owners appending or updating
  state consistently; unsupported values therefore fail closed.
- Reserve exhaustion after correct exclusions can reduce activation yield.
- The repair avoids holder work only when the conflict is already present in
  the local queue; it cannot avoid source work needed to discover identity.
- Revival remains deliberately conservative and may require a separate approved
  operator/lifecycle action before a useful token can return.
- The current schema has no handoff-specific uniqueness constraint; defense is
  provided by canonical assessment plus transactional enqueue. Adding a schema
  constraint would require a separately approved migration and is out of scope.

## Locked capabilities

No 1h/4h runtime expansion, no proof-ceiling change, no real source call, no
retrieval, no paper decision, no BUY/SELL/HOLD, no position/trade/audit/PnL, no
wallet/signing, and no scoring/ranking/confidence logic.
