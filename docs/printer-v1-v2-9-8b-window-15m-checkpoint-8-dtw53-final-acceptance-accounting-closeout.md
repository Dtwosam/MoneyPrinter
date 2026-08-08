# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-53 Final Acceptance Accounting Closeout

Date: 2026-08-08

Linear: `DTW-53`

Frozen C8 baseline: `fe35f1bf7bb24118797f273b753c05a7dc165bec`

Design commit: `8d71bc82cb2586a593d21064f4726f2c4bc00d48`

Accepted RED head: `a95cc280b0cfa88cf64acb8d8cc3446f8b2ad8a8`

Implementation commit: `e01b282ff22e159a807146321371a3cd6af0c12c`

## Verdict

`DTW53_FINAL_ACCEPTANCE_ACCOUNTING_OFFLINE_CLOSEOUT_PASS`

DTW-53's two deterministic final-acceptance accounting defects are repaired offline without weakening owner/action-local equality, six-unit accounting, reservation law, Source Governor ownership, Central Scheduler ownership, or any downstream capability lock.

No new Checkpoint 8 controlling proof, provider/source/network execution, authoritative DB mutation, operational WINDOW_15M activation, WINDOW_1H+, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, or PnL work occurred in this lane.

## Defect A closeout — LOCAL_VALIDATION_STEP equality

The four real `DIRECT_MIGRATION / PUMPSWAP_GRADUATION_VERIFIED` identities remain owner evidence exactly as before.

The repair adds one verification-only `local_validation_identity_observer` path from the real producer through:

`operational_memory_factory_command`
→ `AuthoritativeLiveOperationalCampaignOwner.run_operational`
→ `build_graduated_supply`
→ `run_persistent_eligible_token_supply`
→ `run_direct_migration_discovery`

`run_direct_migration_discovery` now emits the same `LocalValidationIdentity` to the independent action-local observer at creation time, before stage sealing. The public command binds that observer to `CampaignActionLocalLedger.observe_local_validation`.

No identity is copied from sealed owner evidence, reconstructed from counts, or synthesized after the fact.

## Defect B closeout — reservation/attempt outcome scope

Campaign-wide `SOURCE_TRANSPORT_OPERATION` accounting remains unchanged.

`project_lifecycle_reservation_outcomes()` now projects the reservation-attempt subdomain only from transports whose stage identity is one of the exact sealed `WINDOW_15M_SLOT_1` / `WINDOW_15M_SLOT_2` stages.

Every included lifecycle attempt must carry a valid `reserved_from` namespace bound to the authoritative factory run. Missing, malformed, or duplicate reservation linkage fails closed. Unexpected lifecycle outcome vocabulary also fails closed.

For the frozen Checkpoint 8 composition shape, the repaired semantic target remains:

- reserved: 28
- attempted: 26
- succeeded: 26
- failed: 0
- malformed linkage: 0

The 20 pre-lifecycle campaign transports remain in campaign-wide accounting and are no longer incorrectly compared against lifecycle reservations.

## RED evidence

Accepted deterministic RED:

- Actions run: `31229952736`
- job: `93031689797`
- exact test-only delta from design commit
- zero production changes before RED
- compile passed
- pytest: `3 failed in 0.56s`

The three intentional failures proved:

1. missing direct-migration local-validation observer surface;
2. missing lifecycle reservation outcome projector;
3. malformed/unlinked lifecycle safety could not yet be enforced through that projector.

Earlier orchestration/test-fixture mistakes were rejected and were not counted as RED.

## Implementation and GREEN evidence

Implementation run:

- Actions run: `31230440022`
- job: `93033091993`
- implementation commit: `e01b282ff22e159a807146321371a3cd6af0c12c`
- production delta: exactly 6 designed files
- `git diff --check`: PASS
- Python compile of all 6 changed production files: PASS
- DTW-53 regression: `3 passed in 0.47s`
- nearest focused compatibility set: `82 passed, 6 subtests passed in 57.27s`

Changed production files:

1. `src/printer_v1/discovery/direct_migration_discovery.py`
2. `src/printer_v1/discovery/eligible_token_supply.py`
3. `src/printer_v1/operator_cli/graduated_supply_front_door.py`
4. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
5. `src/printer_v1/operator_cli/operational_memory_factory_command.py`
6. `src/printer_v1/operator_cli/campaign_full_run_accounting.py`

## Fresh post-commit verification

Read-only post-commit verification from immutable implementation head:

- Actions run: `31230603270`
- job: `93033544906`
- exact head: `e01b282ff22e159a807146321371a3cd6af0c12c`
- exact six-production-file implementation delta from RED: PASS
- `git diff --check`: PASS
- compile of all six changed production files: PASS
- DTW-53 regression: `3 passed in 0.56s`
- same focused compatibility set: `82 passed, 6 subtests passed in 49.82s`
- workflow token permission: read-only

## Money-usefulness contribution

Printer can now distinguish real campaign-wide source work from the narrower lifecycle reservation-attempt domain while independently witnessing the validations that justify candidate acceptance. This removes two false final-acceptance blockers without reducing the evidence required to trust future clean-memory growth.

## What this lane improves

- exact producer-time action-local coverage for direct-migration validation identities;
- exact lifecycle-only reservation-attempt accounting;
- fail-closed malformed/duplicate lifecycle reservation linkage;
- truthful preservation of all campaign-wide transport work;
- deterministic regression coverage for both original blockers.

## What this lane still does not unlock

This closeout does not itself authorize or prove a new Checkpoint 8 controlling run.

It does not unlock:

- operational WINDOW_15M activation;
- WINDOW_1H / 4H / 12H / 24H;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- wallets, signing, live execution, real funds, or paid APIs.

A new Checkpoint 8 controlling proof still requires the separate readiness/authorization boundary and a new explicit operator authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- A future caller that bypasses the propagated local-validation observer would reintroduce action-local incompleteness; the DTW-53 signature regression guards this path.
- A lifecycle transport with missing, malformed, or duplicated `reserved_from` evidence fails closed rather than being silently excluded.
- This lane did not execute the full C8 composition after repair; offline evidence proves the deterministic defects are repaired, not that a future controlling proof will necessarily pass every unrelated acceptance condition.
- Temporary GitHub Actions orchestration was removed after each bounded use and no orchestration PR was merged.

## Next boundary

Proceed only to an independent DTW-53 readiness review against this implementation and closeout.

If that review passes, the result may support requesting a fresh operator authorization for one new bounded Checkpoint 8 controlling proof. It must not be treated as authorization itself.