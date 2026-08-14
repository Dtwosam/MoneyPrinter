# Printer V1 V2-9.8B Four-Token Historical Migration Provenance Repair Design

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_HISTORICAL_MIGRATION_PROVENANCE_REPAIR_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

This repair is authorization-preparation safety work only. It creates no authorization, application marker, Printer runtime, source call, Scheduler work, memory, or authoritative DB mutation.

## Trigger

The first four-token authorization preparation reached pre-marker Git-provenance reconciliation and correctly failed because preserved untracked/ignored migration-050 evidence is outside the current four-token evidence model.

Current preserved historical package:

- root: `operator-runs/v2-9-8b-authoritative-mig050`
- execution ID: `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Current authoritative schema-transition evidence remains:

- root: `operator-runs/v2-9-8b-migration-055-application`
- execution ID: `MIGRATION_055_20260813T220109Z`
- migration head: `055_pre_admission_discovery_attempt_ownership.sql`
- DB SHA-256: `63a534fca4c6f693c4d4ffa92709ea8c84428b39d0a01ff1a4ca4ab68a47f003`

The failed preparation was pre-marker and unconsumed. No proof authorization may be prepared again until this repair closes and is independently reviewed.

## Design decision

Add an explicit historical-migration evidence class to the four-token Git-provenance model.

Use four disjoint evidence sets:

- `T`: tracked operator-run history
- `M`: current manifest evidence — migration 055 plus the current four-token authorization only
- `Ha`: explicitly approved historical authorization evidence
- `Hm`: explicitly profile-bound historical migration evidence

The exact untracked allowlist is `U = M ∪ Ha ∪ Hm`.

Current-package equality remains `C == M` only. Historical evidence must never satisfy current-package identity.

Complete filesystem reconciliation becomes `F == T ∪ M ∪ Ha ∪ Hm`.

## Exact historical migration binding

Only the four-token profile gains one exact historical migration package binding:

- root: `operator-runs/v2-9-8b-authoritative-mig050`
- execution ID: `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`
- package kind/evidence class must remain explicitly migration-050 historical evidence

Directory presence alone creates no trust. The manifest must bind every regular file in that exact package by normalized path, size, and SHA-256. Missing, extra, mutated, symlinked, aliased, or non-regular entries fail closed.

No other package under the migration-050 root is implicitly trusted.

Migration 050 must never be treated as the transition that produced the current 055 DB. Migration 055 remains the sole current migration package and the authorization still binds migration count 55/head 055/current DB identity.

## Implementation shape

Prefer a minimal additive extension to `GitAuthorizationProfile` with a default-empty historical-migration package declaration. Ordinary and standard-four-hour profiles must retain byte-for-byte behavior through defaults.

Represent historical migration evidence separately from `historical_authorization_evidence`; do not overload authorization IDs, terminal dispositions, sidecar allowlists, or current migration fields.

If the manifest needs a new profile-specific field such as `historical_migration_evidence`, update only the four-token manifest schema/version as necessary. No live four-token authorization exists yet, so no consumed contract needs migration.

The allowed-file-set digest must cover `Hm` records so historical migration bytes are cryptographically bound before marker creation.

## Required TDD

RED must reproduce the real blocker: migration 055 current evidence + exact four-token authorization + preserved untracked migration-050 package fails as unexplained ignored evidence.

GREEN must prove:

1. exact migration-050 historical package is accepted only by the four-token profile;
2. all of its files are path/size/SHA-bound;
3. mutation, deletion, extra file, symlink/alias, or extra migration-050 package fails closed;
4. `Hm` is disjoint from current `M`, historical authorization `Ha`, and tracked `T`;
5. current-package equality remains migration055 + current four-token authorization only;
6. migration055 remains the sole current schema-transition evidence;
7. final allowed untracked set/digest includes exact `Hm` evidence;
8. arbitrary `operator-runs/` files remain rejected;
9. WINDOW_15M and standard-four-hour provenance behavior remains unchanged;
10. no sidecar or broad-root bypass is introduced.

Use focused tests only, then the directly affected provenance/wrapper regression locks, `py_compile`, and `git diff --check`.

## Hard locks

- no real authorization creation or preparation during implementation
- no application marker
- no Printer runtime or source/RPC fetching
- no authoritative DB mutation or migration
- no broad `operator-runs/` trust
- do not delete, move, rewrite, or commit historical operator artifacts
- no retry/rerun/resume/restart/successor
- no 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL
- preserve Source Governor and Central Scheduler ownership

## Money-usefulness contribution

This repair preserves the exact historical evidence needed to prove how the current database evolved while keeping the four-token proof attributable to one current 055 DB/code state. It prevents provenance cleanup shortcuts from weakening launch safety.

## What this improves

It gives the four-token pre-marker validator a truthful semantic place for preserved migration-050 evidence instead of forcing deletion, broad trust, or misclassification.

## What this still does not unlock

It does not create or approve a four-token authorization and does not permit runtime. After implementation closeout, one focused independent review is required; only PASS may return to fresh authorization preparation against the new exact HEAD.

## Functionality Risks / Setbacks / Efficiency Blockers

- Risk: historical migration evidence becomes current migration authority. Mitigation: separate `Hm`; current equality remains `M` only.
- Risk: whole migration root becomes trusted. Mitigation: exact root + execution ID + file inventory/hash binding.
- Risk: old wrappers drift. Mitigation: default-empty profile field and focused regression locks.
- Risk: authorization retry before repair review. Mitigation: stop preparation until implementation closeout and independent review PASS.

## Next permitted lane

`FOUR_TOKEN_HISTORICAL_MIGRATION_PROVENANCE_REPAIR_TDD_IMPLEMENTATION`
