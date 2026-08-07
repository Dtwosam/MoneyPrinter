# Printer V1 V2-9.8B Checkpoint 8 Fresh Re-proof Fixture Argument-Order Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_FRESH_REPROOF_FIXTURE_ARGUMENT_ORDER_OFFLINE_REPAIR_PASS_NO_REPROOF_AUTHORIZATION`

The deterministic proof-fixture argument-order blocker from the consumed fresh Checkpoint 8 re-proof is repaired and independently rechecked offline. This closeout authorizes no new controlling proof.

## Controlling failed attempt preserved

The failed fresh attempt remains permanently recorded as:

- approved HEAD: `319e842d9b7e6b2e89f4609924341e02017795df`;
- proof ID: `C8_REPROOF_AFTER_OFFLINE_REPAIR_20260807`;
- Actions run: `31187598614`;
- job: `92896002714`;
- artifact ID: `8997400153`;
- artifact digest: `sha256:230f1a461612c4210596da6567c5e19dc97f0792a305df393e8ffb5a155b49f5`;
- result: `CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING`;
- one-shot entitlement: consumed;
- rerun/resume/restart/successor: not authorized and not performed.

## Audit and design lineage

- failure audit: `99208dc9bd22da17f29de8cf4a3280089f0f4dc0`;
- repair design: `8612633da618776b735280375e81a084989dea3f`;
- implementation commit on this lane: `5788988c79da6a2889699b4006cee090d9c445d5`.

The audit proved the production discovery seam calls `verifier_transport_factory(mint, signature)`. The proof fixture incorrectly interpreted the second positional argument as the mint, while the prior compatibility helper duplicated the reversed order and therefore masked the defect.

## Exact implementation

Exactly three final implementation/test files differ from the consumed authorization baseline:

1. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
   - two positional arguments now mean `args[0] = mint`, `args[1] = migration signature`;
   - candidate lookup uses the mint;
   - an explicitly supplied signature must match the candidate fixture signature or fail closed with `CHECKPOINT8_PUMPSWAP_FIXTURE_SIGNATURE_MISMATCH`.
2. `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
   - the shared PumpSwap verifier probe now uses the canonical `verifier(first_mint, first_signature)` order.
3. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`
   - adds a production-shaped regression proving canonical `(mint, signature)` succeeds through the real PumpSwap adapter boundary;
   - proves reversed `(signature, mint)` fails closed.

Final proven blob identities:

- harness: `0ca00808f8dcdc7a501cff70806b6cca3ca86518`;
- compatibility helper: `1337f21cc05761ff07a56210a168e0b31a47da54`;
- regression test: `e62ce04b7db9dcdc3e453eef60352a4c00e7c584`.

Production `src/printer_v1/discovery/direct_migration_discovery.py` was not changed.

## Verification

The repaired blobs were exercised by the existing repository-owned offline Checkpoint 8 repair gate, not by a campaign/proof run.

Implementation GREEN job:

- Actions run: `31185418562`;
- job: `92902569062`;
- compatibility tests: `3/3` PASS;
- full focused Checkpoint 8 wildcard suite: `94/94` PASS;
- proof modules compile: PASS;
- offline-only static guard: PASS;
- `git diff --check`: PASS;
- GREEN-only repair commit on the staging lineage: `54025db`.

After removing every temporary bootstrap/hook, the clean final blobs were rechecked by the same offline gate:

- Actions run: `31185418562`;
- clean verification job: `92903042012`;
- compatibility tests: `3/3` PASS;
- full focused Checkpoint 8 wildcard suite: `94/94` PASS;
- proof modules compile: PASS;
- offline-only static guard: PASS;
- `git diff --check`: PASS;
- commit step: `CHECKPOINT8_REAL_CONSUMER_NO_HARNESS_DIFF`.

The three clean proven blobs were then copied byte-for-byte onto this DTW-40 repair branch. The implementation commit changes only those three files relative to its parent.

No `run_operational_campaign()`, `report_only()`, provider/network source execution, memory generation, or controlling proof was performed by this repair verification.

## Temporary tooling cleanup

Temporary implementation helpers and workflows are not part of the final repair state:

- the temporary `sitecustomize.py` hook was removed before clean verification;
- the temporary repair-branch workflow was removed;
- the temporary master-hosted patch workflow was removed;
- disposable trigger PRs were closed without merge.

## Money-usefulness contribution

The repair makes the C8 deterministic PumpSwap fixture obey the same argument contract as the real discovery consumer. That improves the reliability of the eventual proof that Printer can create clean ordinary `WINDOW_15M` memory through its real public campaign composition without weakening source, scheduler, identity, or financial safety boundaries.

## What this lane improves

- closes the exact fixture/production argument-order mismatch;
- prevents the compatibility probe from validating a reversed private convention;
- adds a regression against future coupled fixture/helper drift;
- preserves the failed proof as evidence rather than rewriting it;
- leaves production discovery behavior unchanged.

## What this lane still does not unlock

This PASS does not unlock or authorize:

- another Checkpoint 8 proof attempt;
- public campaign runtime;
- provider/network execution;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallet/private keys/real funds/live execution;
- paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof/test needed before Checkpoint 8 completion

Offline repair evidence cannot complete Checkpoint 8. A later separately authorized one-shot ordinary `WINDOW_15M` controlling proof must still satisfy the full C8 acceptance law and pass independent read-only inspection.

Because the previous explicit authorization was consumed by Actions run `31187598614`, any later controlling proof requires a new explicit operator authorization and a newly pinned exact HEAD/proof identity. The consumed proof may never be rerun, resumed, restarted, or reinterpreted.

## Functionality Risks / Setbacks / Efficiency Blockers

- Two controlling C8 attempts have now exposed proof-fixture/harness defects; another proof must not be treated as a debugging loop or an implicit search for PASS.
- Offline 94/94 coverage materially lowers the known fixture-contract risk but cannot prove full campaign/lifecycle behavior.
- A later proof must pin the exact repaired/readiness lineage; any intervening runtime or source-owner change invalidates readiness.
- The proof remains intentionally `WINDOW_15M` only and cannot be used to infer longer-window readiness.

## Stop condition

Offline repair closeout complete. Stop before any controlling proof. A separate readiness decision may determine whether a new one-shot proof can be proposed for explicit operator authorization.
