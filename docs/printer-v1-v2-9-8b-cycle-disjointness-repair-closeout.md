# Printer V1 — V2-9.8B Cycle-1/Cycle-2 Disjointness Repair Closeout

Date: 2026-08-26

## Verdict

`V2_9_8B_CYCLE_DISJOINTNESS_REPAIR_CLOSEOUT_PASS`

This closeout retires the specific V2-9.8B defect in which a token already admitted in an earlier campaign cycle could remain eligible for a later-cycle fresh-slot freeze and be selected again before the existing admission-time historical-identity guard ran.

This closeout does **not** authorize another campaign, a new authorization, a retry, a successor, retrieval, paper decisions, positions, trades, PnL, 12h/24h work, or live execution.

## Repository baseline

Branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Pre-repair closeout baseline:

`c89849425899a2b4cecea395d155d7e2e5c3cfa5`

Final implementation HEAD before this closeout:

`1ac9cc3bd0adf5c5a789091270537c2b62ca047b`

Implementation chain:

1. `2def9362b445e048a993d99f2557ec949cb5083a` — Repair later-cycle campaign disjointness gate
2. `1ac9cc3bd0adf5c5a789091270537c2b62ca047b` — Wire campaign disjointness into authoritative freeze path and fail closed on unavailable history

## Governing sequence completed

The required major-capability sequence was preserved:

1. readiness/audit — PASS
2. design/specification — PASS
3. bounded implementation — PASS
4. independent implementation review — PASS after one freeze-wiring amendment
5. independent bounded proof — PASS
6. production-caller proof supplement — PASS
7. closeout — PASS

Relevant verdicts:

- `V2_9_8B_CYCLE_DISJOINTNESS_READINESS_AUDIT_PASS`
- issue classification: `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`
- `V2_9_8B_CYCLE_DISJOINTNESS_REPAIR_DESIGN_PASS`
- `V2_9_8B_CYCLE_DISJOINTNESS_REPAIR_IMPLEMENTATION_PASS`
- `V2_9_8B_CYCLE_DISJOINTNESS_FREEZE_WIRING_AMENDMENT_PASS`
- `V2_9_8B_CYCLE_DISJOINTNESS_REPAIR_IMPLEMENTATION_REVIEW_PASS`
- `V2_9_8B_CYCLE_DISJOINTNESS_BOUNDED_PROOF_PASS`
- `V2_9_8B_CYCLE_DISJOINTNESS_PRODUCTION_CALLER_PROOF_PASS`

## Proven defect

The Aug-26 campaign had already admitted Cycle-1 identities including:

- `HQKhWkrPtdLyRxWGVZAajfxoja2y8FMJeckKqZEFpump`
- `GkUnjBvGx9sXf5jEpXWSucgNoT8G1xUo2Dq9vryApump`

The canonical admission coordinator already prohibited historical identity reuse at admission through the campaign token-slot history and `_validate_fresh_slots`.

The missing boundary was earlier: the later-cycle eligible/freeze-selection path did not consume that campaign historical identity set before the existing seeded selector ran.

Therefore a historical token such as `GkUnj...` could survive into the later-cycle frozen selected pair even though admission would have rejected it later.

The defect was not the cause of the separately repaired Cycle-2 timestamp/provenance failure. The two issues remain causally separate.

## Canonical repaired rule

Discovery remains diagnostic and may observe a historical token again.

Later-cycle fresh-slot selection now follows:

```text
later-cycle eligible inventory
-> exact campaign/run historical admitted-slot identities
-> historical-disjointness filter
-> existing freeze reserve
-> existing deterministic seeded selector
-> fresh selected pair only
```

The history owner remains the existing campaign coordinator and:

`printer_memory_factory_campaign_token_slots`

The candidate-resolvable historical identities enforced are:

- `mint_identity`
- `pair_identity`
- `token_row_id`
- `pair_row_id`
- `token_identity`

`token_slot_id` remains admission-level defense because an unadmitted candidate has no new persisted slot identity.

`lifecycle_identity` was not added as a new pairwise disjointness policy.

The existing admission-time historical-reuse rejection remains unchanged as defense-in-depth.

## Authoritative production wiring

The final amendment proved the real production owner path:

```text
AuthoritativeLiveOperationalCampaignOwner.run
-> run_operational
-> prior_cycle_count
-> freeze_eligible_reserve_for_campaign(
     enforce_campaign_historical_disjointness = prior_cycle_count >= 1
   )
```

First-cycle behavior:

```text
prior_cycle_count == 0
-> campaign-history enforcement OFF
-> no historical slots required
-> existing seeded freeze behavior preserved
```

Later-cycle behavior:

```text
prior_cycle_count >= 1
-> campaign-history enforcement ON
-> load exact campaign_id/run_id admitted-slot history
-> require established history
-> remove historical collisions before selector
-> select only from remaining fresh candidates
```

The separately exposed later-cycle graduated-supply entry also forces historical disjointness on and cannot be caller-disabled.

## Fail-closed history rule

For a genuine later-cycle enforcement path, campaign historical identity state must be established.

These conditions fail closed with the existing narrow internal diagnostic:

`INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE`

Covered conditions include:

- missing history mapping
- required key absent
- wrong identity-set type
- structurally empty historical sets
- wrong campaign/run yielding no historical admitted-slot mint identities

No silent empty-exclusion fallback is allowed for a genuine later cycle.

## Independent proof summary

Meaningful parent characterization at `c898494...` proved that with the historical gate absent, the existing seeded freeze could select `GkUnj...` into a later-cycle pair.

Final primary repair suite:

- `tests/test_v2_9_8b_cycle_disjointness_repair.py` — `18 passed`

Focused neighboring proof:

- `120 passed`
- one known unrelated baseline migration expectation was deselected

The proof established:

- all five historical identity collision fields reject correctly
- fresh no-collision candidates remain eligible
- filtering occurs before deterministic selection
- historical candidates remain visible in input/exclusion diagnostics
- enough fresh alternates avoid a false insufficient-supply block
- fewer than two fresh candidates produce the existing honest coverage blocker
- no historical candidate is used as fallback
- first-cycle/enforcement-off behavior is unchanged
- admission-time historical-reuse defense remains active
- selection seed/order/uniformity is unchanged when exclusions are empty
- tracking, cooldown, rotation, classifier, Source Governor and Central Scheduler semantics are unchanged

## Production-caller proof supplement

The final proof supplement executed the actual production owner path rather than only the helper.

Case A:

- `prior_cycle_count = 0`
- enforcement observed `False`
- no history loaded
- historical-looking fixture candidate remained selectable under ordinary first-cycle behavior

Case B:

- `prior_cycle_count = 1`
- enforcement observed `True`
- exact campaign/run history loaded with prior Cycle-1 identities
- `GkUnj...` remained visible in input
- `GkUnj...` was excluded before selection on `mint_identity`
- final selected pair contained only fresh mints

This closes the earlier proof-review gap.

## Deferred test-harness observations

Two unrelated test observations remain outside this repair:

1. `TestMigration051::test_upgrade_from_050_applies_forward_cleanly` carries an old latest-migration expectation (`052`) while the repository migration head is later (`061`). This is pre-existing baseline expectation drift and is not evidence of a disjointness product defect.

2. `TestMemoryObservationReadiness::test_campaign_holder_extreme_memory_readiness_bundle` uses a fixture state with `prior_cycle_count=1` but no historical campaign slots. The parent already failed on that fixture with a different empty-freeze symptom; the repaired code now fails closed on unavailable required history. This is a fixture-state/test-harness mismatch, not a reason to weaken production disjointness.

Neither observation authorizes product-code loosening in this closeout.

## Authoritative DB and runtime safety

Authoritative DB:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

Required and proven SHA-256:

`7f3e725fb435c24c507f6e12fbee26789472017e6e0c63361404ab6589f7128c`

Proof results:

- `PRAGMA integrity_check = ok`
- `PRAGMA foreign_key_check = 0 rows`
- authoritative DB byte identity unchanged
- no WAL/SHM/journal residue
- provider calls = 0
- RPC calls = 0
- WebSocket = 0
- live Scheduler = 0
- Printer runtime = 0
- authorization use = 0
- migrations = 0

Pre-existing untracked `operator-runs/**` remains untouched.

## Authorization state

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T114542Z_d3bc361a`

It remains permanently non-reusable.

This repair does not convert it into a retry, resume, restart, successor, or new authorization.

## What this closeout proves

It proves the specific campaign historical-disjointness defect is repaired:

- historical Cycle-1 tokens may still be observed diagnostically
- they cannot consume a later-cycle fresh slot
- campaign historical identity state is required for genuine later cycles
- the existing deterministic selector operates only over the fresh eligible remainder
- admission still independently rejects historical identity reuse

It does **not** prove that another live Cycle-2 attempt, a 4/2/2 campaign, or the full Memory Factory will succeed end-to-end.

## Next permitted action

`V2-9.8B POST-REPAIR NEXT-BOUNDED-CAMPAIGN READINESS AUDIT ONLY`

The next lane is read-only readiness before any new authorization or live operation.

It must reconcile the closed Aug-26 repairs and determine whether any remaining proven blocker prevents a fresh bounded campaign authorization. It must not automatically authorize or run Printer.

At minimum it must carry forward as closed repairs:

- 15m→1h campaign-window bind-order repair
- Cycle-2 frozen-lane timestamp/provenance repair
- Cycle-1/Cycle-2 campaign disjointness repair

The consumed Aug-26 authorization remains dead.

A fresh authorization, if ever appropriate, requires its own explicit later approval after readiness.

## Still locked

Printer V1 remains:

- Solana-only
- Solana memecoin-only
- paper-trading only
- no live wallet/private keys/signing/real funds/live execution
- no paid API dependency
- no scoring/ranking/confidence percentages/weighted decision logic
- no embeddings/vectors
- no Source Governor bypass
- no Central Scheduler bypass
- no dirty-memory retrieval/decision use
- no retrieval before its explicit lane
- no BUY/SELL/HOLD
- no paper positions/trade events/paper audits/PnL
- no 12h/24h activation
- no automatic restart after terminal failure

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create main outcome memory, continuation, retrieval, decisions, positions, or PnL.
