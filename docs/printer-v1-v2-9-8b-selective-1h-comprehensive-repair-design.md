# Printer V1 V2-9.8B Selective-1h Comprehensive Repair Design

Date: 2026-07-28
Depends on: `printer-v1-v2-9-8b-selective-1h-comprehensive-blocker-audit.md`
Baseline: `043f9eac4740172e92a4fb4daeb060e31628f9f8`
Mode: coordinated in-repository repair plus offline proof only

## Design decision

Repair the campaign as one ordered admission state machine:

```text
graduated identity
  -> read-only exact tracking disposition
  -> skip unavoidable active/terminal blockers before market work
  -> fresh governed market evidence
  -> durable eligible reserve
  -> fresh governed holder/admission evidence
  -> atomic exact-lane claim or expired-cooldown requalification
  -> atomic two-token handoff
  -> existing Scheduler-owned 15m/selective-1h path
```

Raw reserve eligibility is no longer treated as proof of handoff capacity.
Active cooldown identities remain blocked. Expired cooldown identities become
requalification candidates, never automatically eligible: they must pass the
same fresh market, holder, safety, and admission requirements as a new identity
before the exact operational lane can be claimed.

This design does not add a retry, runner, source adapter, scheduler loop,
ranking device, or capability unlock.

## 1. Lifecycle-owned cooldown clock

The existing categorical `BACKUP_SOURCE_CHECK` cadence is 1800 seconds in the
Central Scheduler resource policy. The repair reuses that established cadence
as the lifecycle cooldown duration; it does not invent a competing timer and
does not reuse the separate one-hour market-floor exclusion.

For a newly terminal main-window lifecycle placed into `COOLDOWN`:

- `last_checked_at` is the terminal transition time;
- `next_check_at` is the terminal transition time plus 1800 seconds;
- the lifecycle event payload records `cooldown_started_at`, `cooldown_until`,
  `cooldown_seconds`, and the exact queue id.

For historical rows, effective expiry is derived without mutation:

1. use `next_check_at` only when it is strictly later than
   `last_checked_at`;
2. otherwise derive `last_checked_at + 1800 seconds`;
3. if the timestamps are absent or malformed, fail closed as
   `COOLDOWN_REOPEN_REQUIRED`.

This rule explains rows `28` and `29`: their stored `next_check_at` predates
their cooldown transition, so the effective expiry derives from
`last_checked_at`. They were expired by the third campaign's admission time
and should have been requalification candidates, not permanently trapped
reserve.

## 2. Exact tracking dispositions

The read-only handoff assessment is extended with:

- `requalification_eligible`;
- `cooldown_until`;
- `historical_cooldown_expiry_derived`.

It returns these categorical outcomes:

| Latest exact token/pair/lane state | Outcome |
| --- | --- |
| No row | `FRESH_TRACKING_IDENTITY`, directly claimable after admission |
| `QUEUED`, `ACTIVE`, or `PAUSED` | `DUPLICATE_ACTIVE_TRACKING`, blocked before source work |
| `COOLDOWN`, now before effective expiry | `COOLDOWN_REOPEN_REQUIRED`, blocked before source work |
| `COOLDOWN`, now at/after effective expiry | `COOLDOWN_REQUALIFICATION_REQUIRED`, source work allowed but claim requires fresh requalification |
| `SKIPPED` or `ARCHIVED` | `TERMINAL_TRACKING_STATE`, blocked/manual review |
| Unknown or malformed state/time | fail closed |

Callers that do not provide an assessment time preserve the old conservative
behavior. Only the V2-9.8B operational owner supplies its fixed campaign time
and consumes expired-cooldown requalification.

## 3. Atomic exact-lane claim

One canonical tracking owner performs the final claim in the same transaction
used by the two-slot handoff:

- a fresh identity appends the ordinary `QUEUED` `TRACK_NORMAL` row;
- an expired cooldown appends a new `QUEUED` row in the same exact
  `TRACK_NORMAL` lane with action `REOPEN_REVIVED_TOKEN`;
- the historical cooldown row is preserved;
- a lifecycle event records the predecessor queue id, predecessor lane/status,
  effective expiry, whether expiry was derived, and a categorical
  `fresh_evidence_requalification=true` fact;
- an active, terminal, not-yet-expired, or malformed predecessor fails closed;
- a competing claim observed inside the transaction cannot append a duplicate.

The existing manual `WATCH_ONLY` revival remains available for its historical
operator workflow. It is not used to satisfy this operational exact-lane
handoff.

## 4. Tracking-aware reserve progression and replacement

Before the first exact-pool market request for known inventory, the campaign
owner obtains a read-only exact `TRACK_NORMAL` disposition for every known
mint/pair identity at one fixed admission instant.

- Active cooldown, active ownership, terminal/manual-review, unsupported, and
  malformed identities are excluded from current campaign capacity before
  market calls.
- Expired cooldown identities are retained as requalification candidates but
  all market and holder evidence must be recollected under current freshness
  rules.
- New discoveries have no historical tracking blocker and follow normal
  admission.
- Excluded durable reserve records retain their historical evidence but are
  not returned as `ELIGIBLE_FRESH` for the current campaign.
- The deterministic front door continues walking inventory until it has two
  post-tracking-admissible eligible candidates or reaches the unchanged source,
  duration, provider, or genuine-market bound.

Selection remains deterministic. No score, ranking, confidence, weighting,
stale reuse, or ungoverned fallback is introduced.

## 5. Evidence freshness and requalification

An expired cooldown is only a permission to reconsider the identity. It is not
evidence of eligibility. Final claim requires:

- exact current mint and pair identity;
- approved origin and graduation evidence;
- current liquidity/quote, token-age, and pair-age evidence;
- current holder evidence under the approved aggregate provider policy;
- all existing safety and admission gates;
- a second exact tracking assessment at atomic claim time.

The claim record carries the fresh evidence campaign/run lineage. A stale
reserve row, prior holder result, prior safety composite, or previous campaign
decision cannot be used as requalification proof.

## 6. Truthful terminal classification and reporting

Pre-lifecycle classification follows evidence ownership:

1. explicit governed provider/source unavailability;
2. bounded market shortage after available sources completed;
3. exact tracking/admission blockers;
4. holder/safety/evidence blockers;
5. generic bounded shortfall only when no more specific fact exists.

Tracking facts do not hide a concurrent provider outage, and a provider outage
does not fabricate eligible supply.

Every pre-lifecycle terminal persists a `pre_lifecycle_admission` section with:

- required and admitted capacity;
- each exact mint/pair identity and reserve status;
- tracking category, queue id/status, cooldown expiry, and derived-expiry flag;
- whether the identity was excluded before source work, replaced, or freshly
  requalified;
- holder aggregate status and source availability categories;
- the selected terminal classification;
- source and Scheduler totals.

The campaign's immutable configuration remains the authorization source when
no authoritative factory run exists. A selective-1h campaign that stops before
lifecycle therefore reports `EVALUATION_NOT_REACHED`. The same stored report is
returned by zero-source replay with no reconstruction or source request.

## 7. Downstream path preservation

No downstream architecture owner is replaced. The existing repaired owners
continue to enforce:

- atomic two-token activation and Scheduler ownership;
- leases, deadlines, close-step reservations, and bounded safe stop;
- either 15m token close order;
- exact safety/predecessor linkage and clean-memory quality gates;
- immutable zero/one/two continuation decisions;
- at most one 1h decision, window, and Scheduler job per exact slot;
- bounded 1h collection and terminal closeout;
- terminal campaign-window mapping, zero active/orphan work, and zero-source
  replay;
- hard locks on 4h+, retrieval, and every financial capability.

Focused offline proof will cover those existing owners together with the new
front-door repair. A broad suite is not planned because no shared source,
Scheduler, schema, migration, or memory-quality architecture is changed.

## 8. Dependency order

1. Add lifecycle cooldown constants and read-only effective-expiry assessment.
2. Write future cooldown expiry at lifecycle terminal reconciliation.
3. Add the atomic fresh-or-requalified exact-lane claim.
4. Add tracking-aware pre-source exclusions to eligible-supply progression.
5. Bind holder/admission and final handoff to the same fixed-time dispositions
   and fresh requalification requirement.
6. Persist truthful pre-lifecycle admission and selective-mode reporting.
7. Run focused unit/contract tests with temporary databases and mocks.
8. Run the nearest lifecycle, eligible-supply, handoff, continuation, terminal
   report, and replay regressions.
9. Recheck authoritative database hash and repository cleanliness, write the
   closeout, and commit only on PASS.

## 9. Offline proof matrix

| Required proof | Fixture/mocked evidence |
| --- | --- |
| Fresh replacement | Two blocked reserve identities plus fresh deterministic inventory produce two claimable candidates without calling sources for active blockers. |
| Cooldown behavior | Future expiry is persisted; pre-expiry blocks; post-expiry demands fresh requalification; malformed time fails closed; historical stale `next_check_at` derives expiry. |
| No stale reuse | Requalification cannot claim without current campaign evidence and a final atomic assessment. |
| Provider vs market | Mixed and pure cases retain the correct distinct classification. |
| Close order | Both token 1/token 2 and token 2/token 1 15m completion orders cross the close barrier once. |
| Continuation cardinality | Zero, one, and two immutable continuation decisions create exactly matching 1h work. |
| Linkage/idempotency | Exact safety/predecessor lineage; no duplicate decisions, windows, or Scheduler jobs. |
| 1h bounded close | Collection respects source/Scheduler/duration ceilings; terminal campaign windows and cleanup are correct. |
| Reporting/replay | Pre-lifecycle detail and `EVALUATION_NOT_REACHED` persist; replay makes zero source calls. |
| Locks | No 4h+, retrieval, paper decisions, positions, trade events, audits, PnL, wallet, signing, or live execution capability. |
| DB integrity | Authoritative SHA-256 remains exactly equal to the captured before hash. |

## 10. Rollback

Rollback is the single repair commit. No migration or authoritative data repair
is planned. Reverting the commit restores previous code and tests; retained
artifacts and the authoritative database remain untouched. A rollback would
also restore the permanent historical-cooldown trap, so no operator proof
should run on the reverted state without a new review.

## Hard boundaries

All proof inputs are mocks, fixtures, retained artifacts, copied or temporary
databases, and zero-network replay. No live sources, discovery, Scheduler,
campaign, lifecycle, memory runtime, authoritative cleanup, proof retry,
restart, resume, or successor is permitted. Nothing in this design authorizes
another live proof.
