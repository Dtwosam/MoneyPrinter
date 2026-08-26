# V2-9.8B Cycle-1 Historical-Disjointness Repair Design

**Design verdict:** `V2_9_8B_CYCLE1_HISTORICAL_DISJOINTNESS_REPAIR_DESIGN_PASS`

**Triage verdict:** `V2_9_8B_CYCLE1_HISTORICAL_IDENTITY_FAILURE_TRIAGE_AUDIT_PASS`

**Primary classification:** `COMMITTED_CODE_DEFECT`

**Consumed authorization (permanently non-reusable):**
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T185611Z_b861fd4c`

**Failed campaign evidence to preserve:**

- campaign: `20260826T190349Z-fd22410474f7-campaign`
- run: `20260826T190349Z-fd22410474f7-campaign-run`
- cycle: `20260826T190349Z-fd22410474f7-cycle`

---

## Defect

The committed defect is in the production freeze-gate wiring in
`AuthoritativeLiveOperationalCampaignOwner.run_operational`.

Current production behavior used:

```text
COUNT(*) of persisted campaign-cycle rows
-> enforce_campaign_historical_disjointness = prior_cycle_count >= 1
```

Real production persists Cycle 1 before freeze selection. Therefore real
Cycle 1 already produces `COUNT(*) = 1` and is incorrectly treated as a later
cycle.

The history loader correctly returns zero prior admitted slots for Cycle 1,
then correctly fails closed because enforcement was incorrectly enabled.

- The history loader is **not** the defect.
- Persistence-before-freeze ordering is **not** to be changed.

---

## Repair invariant

Historical-disjointness enforcement must depend on the authoritative identity
of the **currently executing** campaign cycle.

Required semantics:

```text
current cycle ordinal == 1
-> enforce_campaign_historical_disjointness = False

current cycle ordinal > 1
-> enforce_campaign_historical_disjointness = True

missing / malformed / contradictory / invalid current-cycle identity
-> FAIL CLOSED
```

Never derive enforcement from:

- `COUNT(*)` of campaign-cycle rows
- historical slot count
- `bool(history)`
- presence of admitted history
- reserve/MOE/discovery contents

History availability is evidence **required by** genuine later-cycle
enforcement; it cannot decide whether enforcement applies.

---

## Canonical current-cycle identity

The discriminator is the current persisted/executing `cycle_ordinal`
associated with the exact current:

- `campaign_id`
- `campaign_run_id` / `run_id`
- `cycle_id`

Do not invent a second cycle counter.
Do not infer ordinal from `COUNT(*)`.

Require:

- exact current campaign/run/cycle match
- `cycle_ordinal` is integer
- `cycle_ordinal >= 1`

---

## Replacement gate

Expected owner:

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

Replace:

```text
prior_cycle_count = COUNT(...)
enforcement = prior_cycle_count >= 1
```

with:

```text
enforcement = current_cycle_ordinal > 1
```

If the old `prior_cycle_count` query has no remaining valid owner after the
repair, remove it.

Do not leave `COUNT(*)` as a fallback.
Do not use history presence as a fallback.

---

## Invalid current-cycle identity

Unknown current cycle must never silently become Cycle 1.

If exact current cycle identity / ordinal is missing, ambiguous, malformed,
non-integer, `< 1`, or inconsistent with active campaign/run/cycle context,
fail closed before freeze selection.

Minimum precise internal failure reason:

`CURRENT_CYCLE_IDENTITY_INVALID`

Do not weaken any downstream history guard.

---

## Preserve Cycle-2 safety

For `current_cycle_ordinal > 1`:

- historical enforcement MUST remain `True`
- preserve `load_campaign_historical_slot_identity_sets(...)`
- preserve `require_established_campaign_historical_identity_sets(...)`
- missing/structurally incomplete prior admitted history on genuine Cycle 2+
  must still fail closed with
  `INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`

Do **not** implement:

```text
history exists -> enable safety
history missing -> disable safety
```

---

## Preserve pre-selection disjointness

For later cycles preserve current behavior:

- old identities may remain in discovery diagnostics
- old identities may remain in reserve/MOE input
- historical campaign identities are filtered BEFORE seeded freeze selection
- select-then-reject remains forbidden
- admission disjointness remains a final defense

Preserve comparison dimensions:

- `mint_identity`
- `pair_identity`
- `token_row_id`
- `pair_row_id`
- `token_identity`

Preserve `token_slot_id` final admission defense where already present.
Do not add lifecycle identity.

---

## Explicit non-goals

Do not change:

- campaign graph initialization ordering
- DB schema/migrations
- history loader semantics
- historical identity require function
- seeded selector
- discovery/MOE logic
- tracking / cooldown / rotation
- Source Governor / Central Scheduler
- provider code / request ceilings
- 4/2/2 capacity
- `15m -> 1h -> 4h` lifecycle
- `12h`/`24h` locks
- `WINDOW_5M_MICRO_EVENT` support-only rule
- authorization / one-shot / retry / resume / restart / successor rules
- failed campaign evidence / consumed authorization evidence

GeckoTerminal rate-limit failures from the failed run were non-causal and are
outside scope.

---

## Next after implementation

1. Independent implementation diff review
2. Full four-case bounded production proof (separate later lane)

No automatic authorization, Printer run, provider call, or Scheduler tick is
authorized by this design.
