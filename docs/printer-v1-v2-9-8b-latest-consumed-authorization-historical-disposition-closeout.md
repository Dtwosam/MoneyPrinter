# Printer V1 V2-9.8B — Latest Consumed Authorization Historical-Disposition Closeout

Date: 2026-08-24

## Verdict

`V2_9_8B_LATEST_CONSUMED_AUTHORIZATION_HISTORICAL_DISPOSITION_CLOSEOUT_PASS`

## Authority and scope

- Starting and accepted implementation HEAD:
  `264da32f0746f082d0d22980cbc917ec06af2697`.
- Accepted design HEAD: `4cb2e3e43bd60d144e85b60b67663d4f9f3e88a8`.
- Independent implementation verdict:
  `V2_9_8B_LATEST_CONSUMED_AUTHORIZATION_HISTORICAL_DISPOSITION_IMPLEMENTATION_INDEPENDENTLY_ACCEPTED_READY_FOR_CLOSEOUT`.
- Target authorization:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd`.

This was a closeout and bounded read-only proof. It did not modify production
code, tests, immutable operator evidence, the authoritative database, schema,
migrations, or runtime state. It did not create or execute an authorization,
marker, child, campaign, retry, rerun, resume, restart, or successor.

## Final production diff

The accepted implementation changed production only in
`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`.
Relative to the accepted design, the complete production delta is three added
lines registering one exact policy mapping in the existing canonical
`_POLICY_TERMINAL_DISPOSITIONS` owner:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd -> CONSUMED_CHILD_EXITED_NONZERO`

No classifier, filesystem inference, prefix or regular-expression matching,
generic child-exit derivation, evidence class/root change, enumeration
refactor, or authorization-consumption change is present.

## Bounded proof results

Production enumeration from the real immutable package and the derived
prospective trust root returned exactly one target record:

- terminal disposition: `CONSUMED_CHILD_EXITED_NONZERO`;
- path:
  `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd/final_authorization.json`;
- SHA-256:
  `d76470f33838f4d3d05a3ea865940a2d52e96597b30d61d2ef3c19a99ef50a32`;
- size: `4281` bytes;
- mode: `0444`;
- evidence class: `HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE`.

An equivalent lookalike ID retained `DISPOSITION_NOT_AVAILABLE`. The mapping
therefore remains exact-ID-owned and does not generalize.

The prospective trust root was derived from production evidence and validated
as sorted and unique: count `43`, unique count `43`, duplicate count `0`.
It independently contains the histories ending `512f2436`, `6af1423a`, and
`95dc47dd`. Removing only `95dc47dd` failed closed with
`unapproved historical authorization package`; policy registration did not
create directory-discovery trust.

The three historical dispositions remain distinct:

- `...512f2436`: `DISPOSITION_NOT_AVAILABLE`;
- `...6af1423a`: `BLOCKED_UNCONSUMED_SUPERSEDED`;
- `...95dc47dd`: `CONSUMED_CHILD_EXITED_NONZERO`.

Disposable integrity tests independently rejected a wrong package SHA, wrong
package size, marker/manifest mismatch, and child/marker mismatch. The real
consumed-marker SHA remained
`1ecb94577b08a1ab7cb5546a2f09a65f81373a9b819a9b1d21756f80632993f4`.
The disposition mapping grants no integrity bypass.

The target remains historical-only: it is absent from current authorization
authority, `campaign_authorized`, reuse authority, and current Migration
evidence. Canonical set reconciliation accepted the target in the historical
class with zero class overlap and rejected current/historical overlap. The
directly affected reconciliation/provenance tests also preserved undeclared
path rejection and immutable binding validation.

At a controlled clock one minute after consumption, the original package was
still `TEMPORALLY_VALID` with positive time remaining. The consumed marker
nevertheless retained invocation count `1`; retry, rerun, resume, restart, and
successor flags were all false; and enumeration still returned
`CONSUMED_CHILD_EXITED_NONZERO`. Temporal validity cannot reactivate consumed
history.

Static production search found the exact ID only in the canonical policy
mapping and the disposition vocabulary/mapping only in the provenance owner.
No Scheduler, priority/deadline, provider/source, admission, retry/rerun,
resume/restart/successor, memory, retrieval, decision, position, trade, audit,
or PnL consumer reads this adoption. Provider calls, Source Governor calls,
Scheduler runtime calls, and other runtime calls in this closeout were `0`.

## Database and verification

The authoritative database was opened only through SQLite read-only immutable
mode with query-only enabled.

- before SHA-256:
  `9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`;
- after SHA-256:
  `9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`;
- integrity check: `ok`;
- foreign-key violations: `0`;
- unsafe SQLite sidecars: `0`.

The established focused set passed `106` tests and `4` subtests. It covered
the new latest-consumed module, directly affected historical enumeration,
four-token historical provenance/reconciliation, and nearest pre-marker
trust-root validation. The changed production Python file compiled, the
accepted implementation diff passed `git diff --check`, and final static and
diff inspection passed.

Known unrelated baseline fixture debt was not repaired or pulled into this
lane: four historical Migration-055 recovery fixtures with ledger-identity
drift and 31 legacy Git-provenance fixtures with `migration_execution_id`
drift remain separately documented baseline debt. None failed in the bounded
106-test closeout set.

## Closeout disposition

The `DISPOSITION_NOT_AVAILABLE` rereadiness blocker for the exact target is
closed. This is diagnostic historical adoption only: it does not change the
consumed run, make its nonzero child exit successful, or create any authority.
The authorization remains permanently consumed and non-reusable.

## Functionality Risks / Setbacks / Efficiency Blockers

- The exact-ID entry must remain diagnostic-only; generalization would violate
  the accepted design.
- Trust-root membership and immutable SHA/size/marker/child bindings remain
  mandatory even though a terminal disposition is registered.
- The two unrelated baseline fixture-debt groups remain deferred and must not
  be repaired under this closed lane.
- This PASS does not substitute for the required full rereadiness gate.

## Exact next permitted action

`READ-ONLY POST-HISTORICAL-DISPOSITION-REPAIR EXACT-HEAD / WORKTREE / DB REREADINESS GATE`

The full rereadiness gate must be repeated. No authorization may be prepared
in this closeout run, and any future authorization must bind the later exact
final HEAD produced after all required rereadiness/checkpoint work.
