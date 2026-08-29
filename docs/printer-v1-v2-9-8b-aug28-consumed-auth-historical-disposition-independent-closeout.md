# Printer V1 V2-9.8B — Aug28 Consumed Authorization Historical Disposition Independent Closeout

Date: 2026-08-29

Lane: **INDEPENDENT IMPLEMENTATION REVIEW / CLOSEOUT**

Reviewed implementation head:

`784d4afd1e2cb479e6773e588b5d62ebea53f71e`

Reviewed design commit:

`dc4d5cafe5f142bd959ab5b3bf6d681d8f00776d`

Reviewed test-first commit:

`cef8c119b12010f979c81c6a4624c460114c1a9c`

## Authority and sequencing

The operator explicitly approved only the narrow Aug28 consumed-authorization historical-disposition implementation after the post-reconciliation readiness audit isolated that provenance blocker. This review does not authorize a fresh authorization, application/consumption, Printer/provider/Scheduler execution, another campaign, recovery, remote/VPS work, retrieval, decisions, positions, trades, audits, PnL, or longer-window activation.

## Scope review

Independent compare from design commit `dc4d5cafe5f142bd959ab5b3bf6d681d8f00776d` to implementation head `784d4afd1e2cb479e6773e588b5d62ebea53f71e` is exactly two commits ahead and exactly three files:

1. `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
2. `tests/test_v2_9_8b_aug28_consumed_authorization_historical_disposition.py`
3. `docs/printer-v1-v2-9-8b-aug28-consumed-auth-historical-disposition-implementation-closeout.md`

No CI helper/workflow entered the implementation branch.

The final implementation commit `784d4afd1e2cb479e6773e588b5d62ebea53f71e` has parent `cef8c119b12010f979c81c6a4624c460114c1a9c`; that test-first commit has parent design commit `dc4d5cafe5f142bd959ab5b3bf6d681d8f00776d`, whose parent is post-reconciliation governance commit `aca6218f72e3b97fef3d0a93c98c15dbbc91819a`.

## Production-code review

The complete production delta is exactly three added lines inside `_POLICY_TERMINAL_DISPOSITIONS`:

```python
"V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5": (
    "CONSUMED_CHILD_EXITED_NONZERO"
),
```

This is the exact historical wrapper/child outcome from the consumed campaign. The later successful residue reconciliation does not rewrite the original execution result.

No default disposition changed. No wildcard or inference was added. No authorization root or profile changed. No historical trust-root enumerator changed. No temporal-validity logic changed. No current migration-062 identity changed. No authorization/manifest schema or marker rule changed. No database, runtime, recovery, provider, Source Governor, or Central Scheduler owner changed.

Therefore the mapping is diagnostic-only and cannot itself create authorization trust or reuse authority. A future authorization must still explicitly include the consumed ID in its `prior_authorizations_non_reusable` trust root; omission still fails closed.

## RED / GREEN verification review

RED ran before the production mapping existed. GitHub Actions run `33251818225` produced `2 failed, 3 passed`; both failures were the intended exact mismatch `DISPOSITION_NOT_AVAILABLE` versus `CONSUMED_CHILD_EXITED_NONZERO`.

Final GREEN GitHub Actions run `33252065482`, job `99099335731`, checked out exact test-first head `cef8c119b12010f979c81c6a4624c460114c1a9c`, applied only the exact three-line production mapping, and ran the directly affected bounded suite:

- `tests/test_v2_9_8b_aug28_consumed_authorization_historical_disposition.py`
- `tests/test_v2_9_8b_latest_consumed_authorization_historical_disposition.py`
- `tests/test_v2_9_8b_four_token_operational_provenance_alignment.py`

Result:

`35 passed, 8 subtests passed in 1.35s`

The same run passed `py_compile` on the changed production module and `git diff --check`.

The new tests prove exact-ID disposition, lookalike default behavior, explicit-trust-only admission, unchanged consumed-marker non-reuse flags, temporal-validity non-reactivation, distinct historical identities, and unchanged migration-062 current provenance.

## Adjacent stale-suite adjudication

An earlier diagnostic run `33252013744` included the older authorization-handoff transition suite and returned `7 failed, 44 passed, 8 subtests passed`. All seven failures were isolated to that older suite: six asserted superseded pre-reconciliation/current-authorization-preparation `CURRENT_HANDOFF.md` wording, while one synthetic fixture failed at its Git tracked-operator-runs environment probe before reaching the expected trust-root exception.

Those failures do not exercise the three-line mapping as a regression. They are `GOVERNANCE_TEXT_EXPECTATION_STALE / SYNTHETIC_FIXTURE_ENVIRONMENT_DEBT`. Current post-reconciliation governance was correctly not rolled backward, and production trust/reuse behavior was not weakened to satisfy stale fixtures.

## Authoritative DB boundary

The latest operator-produced read-only readiness audit immediately before implementation proved authoritative DB SHA-256:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

with recovered residue, integrity `ok`, zero FK violations, migration 62/tip 062, zero active Scheduler/pre-admission/factory work, no lease, zero matching Printer/Governor/Scheduler processes, and no SQLite sidecars.

The GitHub implementation/proof could not access or mutate that Mac database. Therefore one final local read-only SHA recheck is required after this code-only implementation before the broader post-reconciliation readiness gate may close.

## Independent verdict

`V2_9_8B_AUG28_CONSUMED_AUTH_HISTORICAL_DISPOSITION_IMPLEMENTATION_INDEPENDENT_REVIEW_PASS`

## Next permitted action

`FINAL LOCAL READ-ONLY AUTHORITATIVE DB IDENTITY RECHECK`

Required SHA-256 remains:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

If and only if that exact identity is unchanged, the post-reconciliation readiness/governance lane may be closed PASS and may identify `FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW` as the later next lane. Such a closeout still does not authorize applying or consuming an authorization or running another campaign.
