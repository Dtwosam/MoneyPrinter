# Printer V1 V2-9.8B Post-C8 Authorization Schema-Conformance and Review-Path Audit

Date: 2026-08-08

Linear: `DTW-74`

## Verdict

`V2_9_8B_POST_C8_AUTHORIZATION_SCHEMA_CONFORMANCE_REVIEW_PATH_AUDIT_PASS_CODE_GAP_CONFIRMED`

Audit-only inspection confirms a narrow control-plane code gap in the pre-authorization review path. The production wrapper and canonical pre-marker Git-provenance validator are fail-closed and correct; the earlier migration-ledger package-binding review is weaker than the later exact-schema contract.

## Trigger

DTW-73 ended:

`V2_9_8B_POST_C8_AUTHORIZED_WINDOW_15M_ONE_SHOT_BLOCKED_UNCONSUMED_PRE_MARKER_AUTHORIZATION_SCHEMA_MISMATCH`

The wrapper rejected authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z` with:

`GitProvenanceAuthorizationError: authoritative_database must contain the exact required fields`

No marker, child runtime, source fetching, Scheduler runtime, authoritative DB mutation, or memory lifecycle was reached.

## Canonical exact contract

At authorized HEAD `15978c6c54eab0243db8fe07237b6ec354e532a1`, `pre_authorization_migration_ledger_guard.py` defines exactly seven `PACKAGE_BINDING_FIELDS`:

1. `path`
2. `sha256`
3. `size`
4. `inode`
5. `mtime_ns`
6. `migration_count`
7. `migration_head`

`git_provenance_authorization_manifest._validate_authorization_document()` calls `package_binding_from_document()` and then explicitly requires:

`set(database) == set(PACKAGE_BINDING_FIELDS)`

before pre-marker authorization validation can pass.

The DTW-72 package included the seven required values plus extra health/reporting keys, so the canonical pre-marker validator correctly blocked it.

## Confirmed review-path gap

`package_binding_from_document()` documents itself as extracting and shape-validating the package binding, but its implementation currently does only:

- authorization document is a mapping;
- `authoritative_database` exists and is a mapping;
- return `dict(binding)` unchanged.

It does not enforce exact key-set equality.

`evaluate_migration_ledger_drift(..., package_binding=...)` subsequently compares only the named required fields and ignores extra package-binding keys. Therefore a package with truthful required values plus forbidden extras can pass the pre-authorization migration-ledger review even though the canonical pre-marker validator will later reject it.

This mismatch explains exactly how DTW-72's independent review could report PASS before DTW-73 failed.

## Ownership finding

The defect belongs in the pre-authorization package-binding/review boundary, not in the wrapper or Git-provenance validator.

Do not weaken `git_provenance_authorization_manifest.py` to accept extra keys. Its exact-schema gate is the safer and controlling contract.

The smallest repair target is to make the pre-authorization package-binding extraction/review enforce the same exact `PACKAGE_BINDING_FIELDS` set before a package can receive review PASS.

Whether implementation belongs directly in `package_binding_from_document()` or a narrowly shared helper should be decided in the design lane. The audit does not modify code.

## Why a process-only fix is insufficient

A manual checklist could catch the seven-field contract, but the project already has a named pre-authorization guard whose purpose is to stop package defects before authorization application. Leaving the code weaker than the later wrapper contract would preserve a known gap and allow recurrence from any future caller.

A code-level fail-closed check is therefore warranted.

## Money-usefulness contribution

Repairing this boundary prevents scarce real-run approvals from reaching wrapper application with structurally invalid authorization envelopes. It reduces wasted operational attempts while preserving the clean corpus and exact one-shot safety model.

## What this lane improves

This audit identifies the exact owner and smallest repair boundary. It avoids reopening discovery, holder, source, Scheduler, memory, or market logic for a control-plane schema mismatch.

## What this lane still does not unlock

No replacement authorization, wrapper invocation, provider/source call, Scheduler/Printer runtime, DB mutation, memory generation, longer window, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, or PnL action is authorized.

The invalid `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z` package remains preserved and must not be edited or rerun.

## Required design / proof

Next lane should design the smallest shared exact-shape check so the pre-authorization review and pre-marker validator cannot disagree on the `authoritative_database` key set.

Minimum later proof should show:

1. exact seven-field binding passes;
2. missing required field blocks;
3. one extra field blocks;
4. truthful-but-extra package cannot receive pre-authorization review PASS;
5. existing DB honesty/migration checks still pass for a valid binding;
6. no authorization package, marker, runtime, provider call, or authoritative DB write occurs during proof.

No broad regression suite is required until the repair lane closeout unless the implementation changes broader shared behavior.

## Functionality Risks / Setbacks / Efficiency Blockers

- Duplicating the seven-field list in multiple validators could drift; design should prefer one shared canonical definition/helper.
- Tightening the early review must not accidentally reject valid historical package evidence unrelated to current-package DB binding.
- The repair must not broaden package authority or weaken exact schema validation.
- A new real package still requires a new explicit operator authorization after repair proof/closeout; the DTW-72 approval does not authorize a second package.

## Stop condition

DTW-74 stops at audit PASS with a confirmed code gap. Proceed to a design/specification lane only. No implementation or replacement authorization in this audit lane.