# V2-9.8B Cycle-1 Historical-Disjointness Repair Design

**Design verdict:** `V2_9_8B_CYCLE1_HISTORICAL_DISJOINTNESS_REPAIR_DESIGN_PASS`

**Triage verdict:** `V2_9_8B_CYCLE1_HISTORICAL_IDENTITY_FAILURE_TRIAGE_AUDIT_PASS`

**Primary classification:** `COMMITTED_CODE_DEFECT`

---

## 1. Governing evidence

Repository:

`/Users/Dtwo1/Developer/MoneyPrinter`

Required branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Baseline HEAD at design/implementation start:

`abe4f5ac7f173fd42c312f068b64d7e84ef68bfa`

Authoritative DB:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

Post-failed-run authoritative DB SHA:

`fa2fd9b5469cade5479fd8c5ef1e854d681d1a90b95dc2bc64b66c17019f7ab8`

No authoritative WAL/SHM/journal is permitted at the design or implementation
boundary.

Failed campaign evidence to preserve:

- campaign: `20260826T190349Z-fd22410474f7-campaign`
- run: `20260826T190349Z-fd22410474f7-campaign-run`
- cycle: `20260826T190349Z-fd22410474f7-cycle`

Consumed authorization (permanently dead / non-reusable):

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T185611Z_b861fd4c`

That authorization must never be retried, resumed, restarted, reused, or used
as successor authority. This design creates no fresh authorization.

---

## 2. Proven defect

The committed defect is in the production freeze-gate wiring in
`AuthoritativeLiveOperationalCampaignOwner.run_operational`.

Broken production behavior used:

```text
COUNT(*) of persisted campaign-cycle rows
-> prior_cycle_count
-> enforce_campaign_historical_disjointness = prior_cycle_count >= 1
```

Real production persists Cycle 1 before freeze selection. Therefore real
Cycle 1 already produces:

```text
COUNT(*) = 1
```

and is incorrectly treated as a later cycle.

Observed causal chain:

1. campaign/run/Cycle-1 graph is persisted first;
2. freeze selection then runs while the Cycle-1 row already exists;
3. `COUNT(*)` therefore equals `1` for genuine Cycle 1;
4. enforcement is incorrectly enabled;
5. the history loader correctly returns zero prior admitted slots for Cycle 1;
6. enforcement then correctly fails closed on empty required history, producing
   `INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`.

Classification of causes:

- **Defect:** deriving enforcement from persisted campaign-cycle row count
  (`COUNT(*)` / `prior_cycle_count >= 1`).
- **Not the defect:** the history loader.
- **Not the defect:** persistence-before-freeze ordering.
- Persistence-before-freeze ordering must remain unchanged.

GeckoTerminal rate-limit failures from the failed run were non-causal and are
outside scope.

---

## 3. Authoritative current-cycle identity

Historical-disjointness enforcement must depend on the authoritative identity
of the **currently executing** campaign cycle.

The discriminator is the current persisted/executing `cycle_ordinal`
associated with the exact current:

- `campaign_id`
- `campaign_run_id` / `run_id`
- `cycle_id`

Prefer an already-carried current cycle ordinal if the production owner already
has it available. If it is not already carried at the freeze gate, resolve the
exact CURRENT cycle by its existing cycle identity and read its persisted
`cycle_ordinal`.

Requirements:

- exact current campaign/run/cycle match;
- `cycle_ordinal` is an integer;
- `cycle_ordinal >= 1`;
- do **not** invent a second / parallel cycle counter;
- do **not** infer ordinal from `COUNT(*)`;
- do **not** infer enforcement from historical slot count, `bool(history)`,
  presence of admitted history, or reserve/MOE/discovery contents.

History availability is evidence **required by** genuine later-cycle
enforcement; it cannot decide whether enforcement applies.

---

## 4. Production gate

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

or the exact canonical-code equivalent.

Required semantics:

```text
current cycle ordinal == 1
-> enforce_campaign_historical_disjointness = False

current cycle ordinal > 1
-> enforce_campaign_historical_disjointness = True

missing / malformed / contradictory / invalid current-cycle identity
-> FAIL CLOSED
```

If the old `prior_cycle_count` query has no remaining valid owner after the
repair, remove it.

Do not leave `COUNT(*)` as a fallback.
Do not use history presence as a fallback.

---

## 5. Cycle-1 behavior

For current `cycle_ordinal == 1`:

- `enforce_campaign_historical_disjointness = False`;
- empty prior campaign slot history is valid;
- do not raise `INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE` merely because
  Cycle 1 has no prior admitted slots;
- existing seeded freeze behavior proceeds under ordinary first-cycle rules;
- freeze may proceed when otherwise eligible.

---

## 6. Genuine later-cycle behavior

For current `cycle_ordinal > 1`:

- historical enforcement MUST remain `True`;
- preserve unchanged:
  - `load_campaign_historical_slot_identity_sets(...)`
  - `require_established_campaign_historical_identity_sets(...)`
- load exact campaign/run admitted-slot history;
- require established history;
- remove historical collisions before the existing seeded freeze/selector;
- select only from remaining fresh candidates;
- select-then-reject remains forbidden;
- admission disjointness remains a final defense.

Missing or structurally incomplete prior admitted history on genuine Cycle 2+
must still fail closed with:

`INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`

or the exact existing canonical equivalent.

Do **not** implement:

```text
history exists -> enable safety
history missing -> disable safety
```

That inversion is explicitly forbidden.

---

## 7. Historical identity dimensions

Preserve comparison dimensions:

- `mint_identity`
- `pair_identity`
- `token_row_id`
- `pair_row_id`
- `token_identity`

Preserve `token_slot_id` final admission defense where already present.

Do not add lifecycle identity as a new pairwise disjointness policy.

For later cycles preserve current behavior:

- old identities may remain in discovery diagnostics;
- old identities may remain in reserve/MOE input;
- historical campaign identities are filtered BEFORE seeded freeze selection;
- historical candidates may remain visible as diagnostic/exclusion evidence;
- historical candidates must not consume a fresh later-cycle selected slot.

---

## 8. Invalid-cycle fail-closed rule

Unknown current cycle must never silently become Cycle 1.

If exact current cycle identity / ordinal is:

- missing;
- ambiguous;
- malformed;
- non-integer;
- `< 1`;
- inconsistent with active campaign/run/cycle context;

FAIL CLOSED before freeze selection.

Prefer an existing validation/error boundary if one already expresses this
condition. If no suitable existing reason exists, introduce only the minimum
precise internal failure reason needed by the approved design:

`CURRENT_CYCLE_IDENTITY_INVALID`

Do not weaken any downstream history guard.

---

## 9. Required implementation scope

In scope:

- production freeze-gate wiring in
  `authoritative_live_operational_campaign.py`;
- resolution of authoritative current `cycle_ordinal` for the exact executing
  campaign/run/cycle;
- narrow regression coverage that reproduces real persistence-before-freeze
  ordering and instruments the actual production freeze caller;
- durable design documentation of the approved repair/proof contract.

Out of scope / do not change:

- campaign graph initialization ordering;
- DB schema / migrations;
- history loader semantics;
- historical identity require function;
- seeded selector;
- discovery / MOE logic;
- tracking / cooldown / rotation;
- Source Governor / Central Scheduler;
- provider code / request ceilings;
- 4/2/2 capacity;
- `15m -> 1h -> 4h` lifecycle;
- `12h` / `24h` locks;
- `WINDOW_5M_MICRO_EVENT` support-only rule;
- authorization mechanism;
- one-shot / retry / resume / restart / successor rules;
- failed campaign evidence;
- consumed authorization evidence.

---

## 10. Required bounded proof matrix

### CASE A — REAL CYCLE-1 PERSISTENCE ORDERING

- campaign/run/Cycle-1 graph persisted first;
- Cycle-1 row exists before freeze;
- exact current `cycle_ordinal = 1`;
- actual production freeze caller observes
  `enforce_campaign_historical_disjointness=False`;
- empty prior campaign slot history is valid;
- no `INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`;
- freeze may proceed under ordinary Cycle-1 rules.

### CASE B — REAL CYCLE 2 WITH VALID HISTORY

- Cycle-1 admitted slots exist;
- current `cycle_ordinal = 2`;
- actual production freeze caller observes
  `enforce_campaign_historical_disjointness=True`;
- Cycle-1 identities load;
- reused Cycle-1 identity may remain visible in input if applicable;
- reused identity is excluded before seeded selection;
- fresh identities may be selected.

### CASE C — CYCLE 2 WITH MISSING HISTORY

- current `cycle_ordinal = 2`;
- prior admitted history missing / structurally empty;
- enforcement remains `True`;
- missing/empty required history FAILS CLOSED;
- `INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE` remains preserved.

### CASE D — INVALID CURRENT-CYCLE IDENTITY

- current cycle identity / ordinal missing, malformed, or contradictory;
- must NOT fall back to Cycle 1;
- fail closed before freeze selection.

---

## 11. Actual production caller requirement

The bounded proof must exercise/instrument the actual path:

```text
AuthoritativeLiveOperationalCampaignOwner.run
-> run_operational
-> production pre-lifecycle path
-> freeze_eligible_reserve_for_campaign(...)
```

Required observed arguments:

```text
real persisted Cycle 1 -> enforce_campaign_historical_disjointness=False
real persisted Cycle 2 -> enforce_campaign_historical_disjointness=True
```

A helper-only proof is insufficient.

Do not merely inject a synthetic `prior_cycle_count`.

---

## 12. Previous proof gap

The previous disjointness proof injected/simulated:

```text
prior_cycle_count = 0 -> enforcement False
prior_cycle_count = 1 -> enforcement True
```

but did not reproduce real persistence-before-freeze ordering where the current
Cycle-1 row already existed.

That obsolete proxy is exactly what failed in production:

```text
real Cycle 1 already persisted
-> COUNT(*) = 1
-> enforcement incorrectly True
```

The new proof must test real state ordering, not the obsolete
`prior_cycle_count` proxy.

---

## 13. Explicit non-goals

This repair does not:

- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  or PnL;
- loosen any V1 safety boundary;
- alter Source Governor or Central Scheduler ownership;
- create authorization;
- retry, resume, restart, or succeed from the consumed authorization;
- mutate the authoritative DB;
- change campaign initialization ordering to hide the defect;
- convert later-cycle missing history into a silent pass;
- broaden capacity, windows, providers, or runtime authority.

---

## 14. Verification boundary

This lane is implementation/documentation conformance, not final bounded proof
authorization by itself.

Minimum sufficient verification only:

- syntax/import sanity for touched production/test modules when product/test
  code changes;
- directly relevant targeted regression test(s) when needed to establish the
  patch is executable;
- `git diff --check`;
- authoritative DB SHA unchanged.

Do **not** run:

- a broad pytest suite unless risk expands;
- Printer;
- providers;
- Scheduler ticks;
- authorization creation;
- authoritative DB mutation.

The full four-case bounded production proof occurs only AFTER independent
implementation diff review.

---

## 15. Implementation acceptance conditions

Implementation acceptance requires all of the following:

- `COUNT(*)` of campaign-cycle rows no longer controls enforcement;
- persisted Cycle 1 (`cycle_ordinal == 1`) yields
  `enforce_campaign_historical_disjointness=False`;
- genuine Cycle 2+ (`cycle_ordinal > 1`) yields enforcement `True`;
- invalid current-cycle identity fails closed before freeze;
- Cycle-2 missing/structurally empty required history still fails closed with
  `INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`;
- the actual production caller path is proved/instrumented:
  `AuthoritativeLiveOperationalCampaignOwner.run` -> `run_operational` ->
  production pre-lifecycle path -> `freeze_eligible_reserve_for_campaign`;
- no V1 safety boundary is weakened;
- authoritative DB SHA remains
  `fa2fd9b5469cade5479fd8c5ef1e854d681d1a90b95dc2bc64b66c17019f7ab8`;
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T185611Z_b861fd4c`
  remains permanently non-reusable.

---

## Repair invariant summary

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

---

## Next after design-conformant implementation

1. Independent implementation diff review
2. Full four-case bounded production proof (separate later lane)

No automatic authorization, Printer run, provider call, or Scheduler tick is
authorized by this design.
