# Printer V1 V2-9.8B — Aug28 Consumed Authorization Historical Disposition Implementation Closeout

Date: 2026-08-29

Lane: **NARROW PROVENANCE IMPLEMENTATION / BOUNDED PROOF**

## Authority

Governing audit/design:

`docs/printer-v1-v2-9-8b-post-reconciliation-readiness-and-aug28-consumed-auth-historical-disposition-design.md`

Design commit:

`dc4d5cafe5f142bd959ab5b3bf6d681d8f00776d`

Operator implementation approval was explicit.

## Exact repair

Production change is confined to `_POLICY_TERMINAL_DISPOSITIONS` in
`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`.

Exact consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`

now has diagnostic historical disposition:

`CONSUMED_CHILD_EXITED_NONZERO`

This records the original consumed wrapper/child outcome. The later successful exact-residue reconciliation does not rewrite that historical execution result.

No inference fallback, wildcard, directory-discovery trust, reuse authority, authorization schema, migration contract, database logic, runtime owner, recovery owner, provider path, or Scheduler path changed.

## TDD proof

RED was executed before the production mapping existed in GitHub Actions run `33251818225`.
The focused test produced `2 failed, 3 passed`; both failures were the same intended missing-policy root cause:
`DISPOSITION_NOT_AVAILABLE` versus `CONSUMED_CHILD_EXITED_NONZERO`.

After the one exact mapping was added, the bounded directly affected proof result was:

`35 passed, 8 subtests passed in 1.35s`

The gating set covers exact-ID disposition, lookalike default behavior, explicit-trust-only admission, marker non-reuse flags, temporal-validity non-reactivation, distinct historical IDs, migration-062 current provenance, the existing exact consumed-disposition owner, and four-token operational provenance alignment.

`py_compile` and `git diff --check` also passed in the same bounded proof.

## Adjacent stale-suite adjudication

An earlier GREEN attempt (GitHub Actions run `33252013744`) also sampled
`tests/test_v2_9_8b_authorization_handoff_transition_and_supersession.py` and returned
`7 failed, 44 passed, 8 subtests passed` across the combined batch. All seven failures came from that older handoff-transition suite, not from the new test or the current provenance owners. Six assert superseded pre-reconciliation/current-authorization-preparation wording against the intentionally newer `POST-RECONCILIATION FRESH NEXT-BOUNDED-CAMPAIGN READINESS / GOVERNANCE AUDIT` handoff. The seventh fails earlier in synthetic Git tracked-operator-runs discovery (`Git tracked operator-runs status could not be verified`) instead of reaching its expected trust-root exception. These are `GOVERNANCE_TEXT_EXPECTATION_STALE / SYNTHETIC_FIXTURE_ENVIRONMENT_DEBT`, not implementation regressions. Current governance was not rolled backward and production was not weakened to satisfy them.

## Database / runtime boundary

GitHub-hosted implementation and proof did not open or mutate the authoritative Mac database and did not access the live PrinterOperations marker tree. No Printer, Source Governor, Central Scheduler runtime, provider/RPC/WebSocket, authorization preparation/application, campaign, retry, resume, restart, successor, retrieval, decision, position, trade, audit, or PnL capability was executed or unlocked.

The latest operator read-only baseline immediately before this implementation was:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

A final local read-only SHA recheck is still required before closing the post-reconciliation readiness gate because GitHub cannot independently read the Mac authoritative DB.

## Verdict

`V2_9_8B_AUG28_CONSUMED_AUTH_HISTORICAL_DISPOSITION_IMPLEMENTATION_PASS`

## Next permitted action

`INDEPENDENT AUG28 CONSUMED AUTH HISTORICAL DISPOSITION IMPLEMENTATION REVIEW / LOCAL DB IDENTITY RECHECK`

This closeout does not authorize preparation, application, or consumption of a new authorization and does not authorize another campaign.
