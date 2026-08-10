# Printer V1 — Post-DTW100 Standard Four-Hour Rereadiness Historical-Evidence Provenance Design

## Status

`APPROVED_FOR_HELPER_ONLY_IMPLEMENTATION`

Baseline: `aeea656727f06a172595ca21af81b42f70a4699f`

## Decision

Keep all production Git-provenance and standard-four-hour authorization code unchanged. Replace only the post-staging-repair rereadiness wrapper with an evidence-aware, audit-only host checker.

The checker must not create or imitate `ValidatedGitProvenanceAuthorization`. It must independently establish pre-authorization evidence readiness, then invoke the existing non-Git preflight owners directly.

## Exact retained-evidence contract

### Authoritative migration package

Root:
`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Require the complete 12-file package byte-for-byte, including the two Git-ignored SQLite evidence files. No extra package entry, symlink, directory, device, or changed byte is allowed.

### Historical ordinary authorization evidence

Require the exact 16 visible untracked `final_authorization.json` paths captured in the host audit:

- `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260809T011312Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260809T130306Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z`
- `V2_9_8B_WINDOW_15M_AUTH_20260809T180257Z`

Every file must match the audited SHA-256 and size. The live visible-untracked set must equal the 10 visible migration-package files plus these 16 files exactly. Zero sidecars are expected at rereadiness.

The 16 IDs are a readiness input for the future authorization-preparation audit; this design does not itself declare them reusable or create `prior_authorizations_non_reusable` authority.

## Host safety gates before non-Git preflight

Fail closed unless all are true:

1. exact expected branch and tracked-clean index/worktree;
2. repository `.venv` Python is >=3.11;
3. no stale wrapper environment;
4. no active Printer process;
5. no authoritative DB open handle;
6. no campaign lease lock;
7. no ordinary or standard wrapper staging residue;
8. no standard-four-hour application marker;
9. authoritative DB exact SHA/size, no sidecars;
10. exact retained-evidence package/inventory as above.

## Non-Git readiness composition

Do not call raw `build_standard_four_hour_preflight()` before authorization exists.

Instead call the same canonical non-Git owners used by activation preflight:

- readiness source-contract preflight;
- concrete WINDOW_15M composition preflight;
- runtime dependency preflight;
- operational holder-budget preflight;
- canonical migration-ledger validation;
- read-only DB integrity and foreign-key checks;
- active operational counts;
- locked-capability baseline validation;
- historical null-position paper-audit count;
- standard-four-hour policy and ceiling constants, including exact WINDOW_12H/WINDOW_24H locks.

The helper may use existing internal read-only owners but must not add a public command, production bypass parameter, or production allowlist.

## Post-check invariants

Re-fingerprint DB and host quiescence after all checks. Require exact before/after equality. Re-read visible untracked inventory and retained migration package; require exact equality. Require no new staging or marker.

## PASS result

PASS only if all checks succeed. Report:

- exact branch/HEAD;
- interpreter identity;
- DB fingerprint/integrity/FK/migrations;
- active and locked counts;
- evidence inventory count/hash truth;
- migration package 12/12 truth;
- non-Git source/dependency/composition/budget readiness;
- standard 4h policy/ceilings;
- zero source calls, Scheduler runtime calls, DB writes, authorization creation, Printer runtime, and standard-4h start;
- next step `REREADINESS_CLOSEOUT_BEFORE_ANY_FRESH_AUTHORIZATION`.

## Money-usefulness contribution

Proves the host can safely progress to authorization preparation without discarding evidence the one-use trust chain needs, moving Printer toward reliable 4h memory growth rather than weakening provenance for convenience.

## What improves

- Removes a false pre-auth provenance deadlock.
- Proves retained historical evidence is exact rather than merely tolerated.
- Keeps actual launch-time provenance stricter than rereadiness.

## Still not unlocked

No authorization, provider/source use, Scheduler runtime, DB mutation, memory generation, retrieval, paper decision, BUY/SELL/HOLD, paper position, trade event, audit, PnL, WINDOW_12H, or WINDOW_24H.

## Minimum proof

- compile helper;
- static AST/text proof: no production source modification, no authorization construction/application, no source transport, no DB write connection, no deletion/move/rename;
- test exact inventory comparison logic with synthetic temporary paths if practical;
- exact branch delta limited to audit/design/helper;
- fresh host execution under `.venv/bin/python`;
- independent review of PASS evidence before authorization preparation.

## Functionality Risks / Setbacks / Efficiency Blockers

- A newly retained authorization after this design must cause a fail-closed inventory mismatch and a fresh audit, not automatic trust growth.
- Internal preflight owner signatures can drift in future lanes; helper closeout is tied to its exact HEAD.
- Ignored migration evidence would be missed by visible-untracked Git inventory alone; complete migration-package enumeration is mandatory.
