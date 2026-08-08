# Printer V1 V2-9.8B Post-C8 Authorization Exact-Binding Shape Repair — Closeout

Date: 2026-08-08

Linear: `DTW-76`

## Verdict

`V2_9_8B_POST_C8_AUTHORIZATION_EXACT_BINDING_SHAPE_REPAIR_PASS`

The pre-authorization migration-ledger guard now enforces the same exact seven-field `authoritative_database` binding shape required later by the Git-provenance pre-marker validator. Missing or extra fields can no longer receive a pre-authorization review PASS.

No replacement authorization was created, no historical authorization was edited or reused, and no wrapper/provider/Scheduler/Printer runtime or authoritative DB mutation occurred.

## Baseline and implementation

Design baseline:

`990db78de2305a4c4019e93246674e8f829d1533`

Production implementation commit:

`edae34af4a4a25334eb16f158c1c27a0f1dd63a0`

Temporary workflow removal head before this closeout document:

`6db8be07e31b624c2ad7314d147e40e2eefddd76`

Final code/test diff from the design baseline contains only:

- `src/printer_v1/operator_cli/pre_authorization_migration_ledger_guard.py`;
- `tests/test_dtw76_authorization_binding_shape.py`.

The temporary `.github/workflows/dtw76-focused.yml` proof workflow was removed after use.

## Exact repair

A shared `validate_package_binding_shape()` owner now requires exact equality with `PACKAGE_BINDING_FIELDS`:

- `path`;
- `sha256`;
- `size`;
- `inode`;
- `mtime_ns`;
- `migration_count`;
- `migration_head`.

`package_binding_from_document()` uses the shared validator, so package/file review rejects missing or extra keys before readiness PASS.

Direct `evaluate_migration_ledger_drift(..., package_binding=...)` review calls also use the same validator. Invalid raw mappings return BLOCKED with blocker code `package_binding_invalid`; they cannot bypass document extraction.

The later Git-provenance pre-marker exact-key check remains unchanged as defense-in-depth. Existing live DB identity and honesty comparison behavior remains in place.

## Bounded zero-runtime proof

TDD RED proof:

- GitHub Actions run `31259099059`;
- job `93106990398`;
- focused command: `python tests/test_dtw76_authorization_binding_shape.py` with `PYTHONPATH=src`;
- result: 4 tests run, 3 expected failures and 1 existing-valid PASS;
- failures proved the pre-fix gap:
  - missing field was accepted;
  - extra field was accepted;
  - truthful binding with an extra field received review PASS.

TDD GREEN proof after the repair:

- GitHub Actions run `31259213475`;
- job `93107268479`;
- same focused command and fixture;
- result: `Ran 4 tests ... OK`.

Covered behavior:

1. exact seven-field binding PASS;
2. missing field BLOCK;
3. extra field BLOCK;
4. truthful binding plus extra field BLOCK in direct review mode.

The temporary proof used only a disposable one-migration SQLite fixture on GitHub Actions. It did not touch the authoritative Mac DB, providers, Source Governor runtime, Central Scheduler runtime, campaign execution, or memory generation.

## Money-usefulness contribution

The repair prevents a scarce future real `WINDOW_15M` opportunity from being wasted by an authorization package that looks factually correct but is structurally incompatible with the canonical wrapper. Invalid authorization DB bindings now fail at the earlier free review boundary rather than at wrapper application time.

## What this improves

- pre-authorization review and pre-marker validation now share the same exact DB-binding shape law;
- missing and extra binding keys fail closed earlier;
- truthful-but-structurally-invalid packages cannot receive review PASS;
- direct raw-mapping review callers cannot bypass the shape check;
- the strict wrapper validator remains unchanged.

## What this still does not unlock

This PASS does not authorize or create a replacement authorization and does not permit a wrapper invocation.

Still locked:

- provider/source fetching;
- Printer or Central Scheduler runtime;
- authoritative DB mutation or memory generation;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`;
- retrieval;
- paper decisions or BUY/SELL/HOLD;
- paper positions, trade events, paper-trade audits, PnL;
- wallets, private keys, signing, real funds, live execution;
- paid API dependencies;
- scoring, ranking, confidence, weighting, embeddings, vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- The invalid authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z` remains historical evidence only. It must not be edited, reused, retried, rerun, resumed, restarted, or treated as current authority.
- A future package must be newly issued and independently reviewed against the repaired guard.
- Any tracked code change or authoritative DB identity change before a future authorization application requires fresh binding/review.
- The repair intentionally does not relax the later pre-marker validator.

## Next gate

A later replacement package requires a **fresh explicit operator authorization**. The previous approval prohibited retry/rerun/resume/restart/successor and therefore cannot be stretched into authority for a new package or new real cycle.

Before a future real `WINDOW_15M` invocation:

1. obtain fresh explicit operator approval;
2. create one new authorization ID/package against the then-current reviewed exact HEAD and authoritative DB identity;
3. require the repaired pre-authorization review to PASS;
4. independently confirm temporal validity, exact package/file set, no competing current authority, and pre-marker readiness;
5. only then permit one manual wrapper invocation.
