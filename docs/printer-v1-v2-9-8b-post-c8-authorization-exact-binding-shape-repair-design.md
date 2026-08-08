# Printer V1 V2-9.8B Post-C8 Authorization Exact-Binding Shape Repair — Design

Date: 2026-08-08

Linear: `DTW-75`

## Verdict

`V2_9_8B_POST_C8_AUTHORIZATION_EXACT_BINDING_SHAPE_REPAIR_DESIGN_PASS`

The repair should tighten the pre-authorization migration-ledger guard so every review path enforces the same exact `authoritative_database` key set already required by the canonical pre-marker validator.

## Confirmed defect

`PACKAGE_BINDING_FIELDS` is already the canonical field list:

- `path`
- `sha256`
- `size`
- `inode`
- `mtime_ns`
- `migration_count`
- `migration_head`

Current `package_binding_from_document()` checks only that `authoritative_database` is a mapping and returns all keys unchanged. Direct `evaluate_migration_ledger_drift(..., package_binding=...)` / `assert_migration_ledger_ready(..., package_binding=...)` calls can likewise compare the required values while silently ignoring extra keys.

The later Git-provenance pre-marker validator rejects those extras. That disagreement caused DTW-72 review PASS followed by DTW-73 pre-marker BLOCKED.

## Design decision

Add one shared exact-shape validator in `pre_authorization_migration_ledger_guard.py` and use it in both package-extraction and review-mode paths.

Suggested internal/public contract:

`validate_package_binding_shape(binding: Mapping[str, Any]) -> dict[str, Any]`

It must:

1. require a mapping;
2. require `set(binding) == set(PACKAGE_BINDING_FIELDS)`;
3. reject any missing required field;
4. reject any extra field;
5. return a plain dict only after exact-shape PASS;
6. make no DB/network/filesystem mutation.

Error reporting should identify missing and extra keys deterministically.

## Integration points

### 1. `package_binding_from_document()`

After retrieving `document[PACKAGE_DB_BINDING_KEY]`, call the shared validator instead of returning `dict(binding)` directly.

Result: CLI/file-based pre-authorization review cannot accept an invalid binding shape.

### 2. `_review_package_binding()` / direct review path

Direct callers can supply `package_binding` without going through `package_binding_from_document()`. Therefore `_review_package_binding()` must also apply the shared exact-shape law before honesty comparison.

To preserve current `evaluate_migration_ledger_drift()` result semantics, a shape failure should become a deterministic review blocker such as:

`package_binding_shape_invalid`

rather than allowing review PASS.

### 3. Canonical pre-marker validator

Keep the existing exact-key check in `git_provenance_authorization_manifest._validate_authorization_document()` unchanged as defense-in-depth.

Do not weaken or remove it merely because the earlier guard becomes stricter.

## Behavior to preserve

- exact seven-field valid bindings continue through existing DB truth comparison;
- DB path is still compared by resolved identity;
- SHA, size, inode, mtime, migration count and migration head remain exact comparisons;
- migration catalogue/ledger/integrity/FK behavior remains unchanged;
- no authorization schema broadening;
- no source/Scheduler/runtime/memory behavior changes.

## Focused implementation scope

Expected production change:

- `src/printer_v1/operator_cli/pre_authorization_migration_ledger_guard.py`

Expected focused tests only in the existing guard test location(s).

Do not touch discovery, source adapters, Scheduler, wrapper launch logic, DB schema/migrations, memory generation, or trading code.

## Minimum sufficient tests

1. exact seven-field `package_binding_from_document()` PASS;
2. missing one required field BLOCK/raise;
3. one extra field BLOCK/raise;
4. direct `evaluate_migration_ledger_drift(mode="review", package_binding=<truthful + extra>)` returns BLOCKED and includes the shape blocker;
5. valid exact binding still passes the existing honesty/migration review;
6. existing later pre-marker exact-schema defense remains intact.

No broad regression suite is required for implementation. A broader focused closeout may include the existing guard and Git-provenance authorization tests only if needed to prove the shared contract did not drift.

## Bounded zero-runtime proof after implementation

Use a temporary/test DB or existing test fixtures only. Prove:

- valid exact binding PASS;
- missing/extra bindings fail before any authorization application;
- zero provider/source calls;
- zero Scheduler/Printer runtime;
- zero authoritative DB writes;
- zero marker/manifest/application creation in the real operator application root;
- no memory generation.

## Money-usefulness contribution

This repair prevents a structurally invalid authorization package from reaching the one-shot wrapper after already receiving pre-authorization review PASS. That protects scarce operational approval cycles and reduces false readiness without weakening any market or memory safety gate.

## What this improves

- pre-authorization review and pre-marker validation agree on exact DB-binding shape;
- manual/direct review callers can no longer bypass shape enforcement by passing a raw mapping;
- the real wrapper remains a final defense rather than the first place the mismatch is discovered.

## What this still does not unlock

No replacement authorization, wrapper invocation, provider/source access, Scheduler runtime, authoritative DB mutation, memory generation, `WINDOW_1H+`, retrieval, paper decision, BUY/SELL/HOLD, position, trade, paper-trade audit, or PnL action is authorized by this design.

The invalid authorization remains preserved and non-rerunnable.

## Functionality Risks / Setbacks / Efficiency Blockers

- enforcing shape only in `package_binding_from_document()` would leave direct review calls able to bypass the fix;
- removing the later pre-marker check would reduce defense-in-depth and is prohibited;
- error behavior should remain deterministic so blocked package reviews are easy to classify;
- do not expand this narrow repair into authorization-schema redesign.

## Stop condition

DTW-75 stops at design PASS. Proceed to a separate implementation lane for the exact-shape guard plus focused tests only.