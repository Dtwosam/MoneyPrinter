# Printer V1 V2-9.8B Four-Token Zero-State Fixture Expiry Audit and Design

Date: 2026-08-14

## Audit verdict

`V2_9_8B_FOUR_TOKEN_ZERO_STATE_FIXTURE_EXPIRY_AUDIT_PASS_TEST_MAINTENANCE_REQUIRED`

The fresh operator rereadiness command reached the focused zero-state tests and stopped before authoritative-DB preflight because `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py` builds fixture authorization documents with a fixed issue time of `2026-08-13T22:00:00+00:00` and a fixed 12-hour expiry. On 2026-08-14 those fixture documents are expired, so production temporal validation correctly raises `AUTHORIZATION_EXPIRED` before the individual zero-state assertions can execute.

The failing test file has the same blob SHA (`f801058c52fecf5a058112bd33c5ef9ea1821e34`) at the pre-zero-state-repair rereadiness commit `e149a5d95bc090cd711e7dc7abbe1f13fada7a53` and at repaired HEAD `1f714ec7264fdbd3c8029999de0eeb27eeb13e02`. This is therefore pre-existing test-fixture drift, not a regression caused by the pre-admission zero-state repair.

No production temporal rule should be weakened. Expired real authorizations must continue to fail closed.

## Design

Canonical repair owner: `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py` only.

Minimal repair:

1. Keep the fixed `NOW` constant for deterministic database/supervision row timestamps.
2. Stop passing fixed `authorized_at` and `expires_at` values from `_document()`.
3. Let existing `fixture_authorization_document()` create a fresh timezone-aware issue time and derived expiry using its established fixture-only default behavior.
4. Remove the now-unused `timedelta` import.

No production source, migration, authorization validator, zero-state predicate, Scheduler, Source Governor, runtime, database, or operator artifact changes are permitted.

## Required bounded proof

Re-run only:

- `tests/test_v2_9_8b_four_token_pre_admission_zero_state_semantics.py`
- `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py`

Then, only if those pass, continue the same fresh read-only authoritative-DB/process/source-configuration preflight. No authorization may be created during this proof.

## Money-usefulness contribution

Restores trustworthy rereadiness verification so a one-use proof is not consumed because of stale test data while preserving real authorization expiry safety.

## What improves

The focused zero-state suite can test the intended gate conditions rather than failing first on an obsolete fixture timestamp.

## What remains locked

Fresh authorization creation and proof execution remain locked until the repaired-head focused tests and fresh operator zero-state/preflight pass and are closed separately. Six-token proof, 12h/24h, retrieval, decisions, BUY/SELL/HOLD, positions, trades, PnL, wallets, signing, live execution, real funds, paid APIs, scores/ranks/confidence/weighted logic, embeddings, and vectors remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Weakening production expiry checks would hide a real safety property; prohibited.
- Replacing all deterministic fixture timestamps is unnecessary and could broaden scope; keep fixed row timestamps.
- A passing repaired test suite alone does not establish current host/DB quiescence; fresh read-only operator preflight is still required.

## Design verdict

`V2_9_8B_FOUR_TOKEN_ZERO_STATE_FIXTURE_EXPIRY_DESIGN_PASS_READY_FOR_TEST_ONLY_IMPLEMENTATION`
