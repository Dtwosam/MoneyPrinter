# Printer V1 V2-9.8B Four-Token Fresh Authorization Preparation Design

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_FRESH_AUTHORIZATION_PREPARATION_DESIGN_PASS_READY_FOR_ONE_BOUNDED_CREATION`

## Goal

Prepare exactly one new, unconsumed four-token proof authorization after the fresh post-repair rereadiness PASS. This lane creates authority only; it does not consume authority or run Printer.

## Baseline

- Rereadiness closeout: `c0a77297d2e52aa16ce02a0f2984127c50189bc0`
- Rereadiness verdict: `V2_9_8B_FOUR_TOKEN_POST_ZERO_STATE_REPAIR_REREADINESS_CLOSEOUT_PASS_READY_FOR_FRESH_AUTHORIZATION_CREATION`
- Exact tested/preflight implementation HEAD beneath that closeout: `9d656cf37d6ffdfa139d9be7226a7061a904d551`
- Authoritative schema: migration count 55, head `055_pre_admission_discovery_attempt_ownership.sql`

## Canonical contracts

Use the existing four-token owners only:

- `four_token_proof_one_shot_wrapper.fixture_authorization_document()` for the exact document schema/policy shape;
- `four_token_proof_one_shot_wrapper.validate_four_token_proof_authorization_document()` for fresh-document validation;
- `pre_authorization_migration_ledger_guard.inspect_authoritative_database()` for immutable DB identity;
- `four_token_proof_zero_state_gate.assert_four_token_proof_zero_state()` for the free read-only pre-consumption gate;
- `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` for package roots and migration provenance.

Do not call `apply_authorization_once()`. Do not build a provenance manifest or application marker in this lane.

## Exact authorization policy

The new document must retain the existing exact four-token policy:

- 4 concurrent through-4h tokens;
- 2 active/admitted cycles total;
- exactly 2 tokens per cycle;
- minimum 300-second cycle spacing;
- zero automatic retries;
- endpoint rotation disabled;
- `WINDOW_12H` and `WINDOW_24H` locked.

No six-token authority is permitted.

## Evidence derivation rules

Nothing historical may be guessed from timestamps or branch names.

Before writing the new package, the operator-side preparation must derive and validate:

1. the exact current migration-055 execution directory from `operator-runs/v2-9-8b-migration-055-application`;
2. presence of the profile-required historical migration-050 execution `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` under its exact profile root;
3. prior authorization IDs from existing `final_authorization.json` evidence under the profile-declared historical authorization roots;
4. every prior ID must be safe, unique, lexicographically sorted, and different from the new ID;
5. the authoritative DB identity must be freshly re-derived and unchanged through preparation.

If migration-055 current evidence is absent or ambiguous, historical migration-050 is absent, an existing authorization package is malformed/aliased, or DB identity changes, stop without creating the new authorization.

## Creation boundary

The only new package permitted is:

`operator-runs/v2-9-8b-four-token-final-authorization/<NEW_AUTHORIZATION_ID>/final_authorization.json`

Requirements:

- one new unique safe authorization ID;
- one fresh bounded temporal interval using the existing fixture-document builder defaults/policy;
- repository binding to the exact preparation branch and exact committed HEAD used for creation;
- exact current migration-055 execution ID;
- exact fresh authoritative DB binding;
- exact sorted `prior_authorizations_non_reusable` derived from preserved historical authorization evidence;
- exclusive creation; never overwrite an existing package;
- validate the just-created document and report its SHA-256;
- no other package/file creation.

## Allowed

- Git/read-only repository inspection;
- immutable/read-only DB inspection;
- local filesystem inspection of bounded existing evidence roots;
- exact source-configuration validation with secret-free output;
- one authorization package/document creation;
- SHA-256/reporting.

## Not allowed

- application marker;
- provenance manifest;
- `apply_authorization_once()`;
- Printer/runtime/proof launch;
- source fetching;
- Scheduler work;
- authoritative DB mutation or migration;
- memory generation;
- six-token work;
- 12h/24h activation;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, or PnL.

## Bounded proof required

After creation, report at minimum:

- exact branch/HEAD;
- fresh DB migration/integrity/FK/sidecar state;
- fresh zero-state PASS;
- new authorization ID/path/SHA-256;
- issue/expiry times;
- exact migration-055 execution ID;
- count and IDs of prior authorizations marked non-reusable;
- confirmation of required historical migration-050 presence;
- confirmation no application marker/manifest exists for the new ID;
- tracked/index state remains clean.

A separate independent authorization review/closeout is mandatory before any one-shot consumption or proof execution.

## Money-usefulness contribution

Creates a fresh one-use authority only after current code, DB, process, and provenance readiness are clean, reducing the chance of spending a proof attempt on stale or ambiguous evidence.

## What this lane improves

It converts a clean rereadiness state into one exact, auditable four-token proof authorization while preserving all current/historical provenance boundaries and one-use rules.

## What this lane still does not unlock

It does not unlock proof execution, six-token proof, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions/trades/audits/PnL, wallets/signing/live execution/real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Ambiguous migration-055 packages could bind the wrong schema-transition evidence: fail closed unless exactly one current execution candidate is established.
- Missing historical authorization or migration evidence could make provenance easier by deletion: fail closed rather than silently omit it.
- Authorization time can expire before review: keep the preparation/review sequence bounded and never relax temporal validity.
- Any HEAD or DB identity change after creation invalidates the prepared authority and requires a new review outcome; do not rewrite an existing authorization.

## Next permitted phase after creation

Independent read-only review of the newly created authorization. Proof execution remains locked until that review has its own durable PASS closeout.