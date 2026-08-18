# Printer V1 V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Implementation Closeout

Date: 2026-08-18

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_AUTHORIZATION_ALIGNMENT_IMPLEMENTATION_PASS`

## 1. Scope

This lane implemented the approved operational 4/2/2 authority boundary and the
post-repair four-token Git-provenance alignment to Migration 058, then proved
both with focused tests and one bounded offline/disposable proof.

Approved design baseline:

`babc8a3b2dfd4ddca1307e140a378e0d3279e113`

Repaired operational product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

Implementation branch:

`agent/v2-9-8b-post-repair-two-cycle-four-token-operational-authorization-alignment-implementation`

No authorization was created or consumed, no campaign ran, no provider/RPC/
WebSocket call was made, no migration was added, and master was not modified.

## 2. TDD sequence actually followed

1. Focused tests expressing the approved design were written first.
2. They were run and failed as expected: all three new modules failed to import
   because no product code existed yet (`ImportError:
   four_token_standard_four_hour_one_shot_wrapper`). That red phase is preserved
   in the lane evidence.
3. Product code was written only to satisfy those tests.
4. Focused tests were re-run to green.
5. Minimum sufficient regression tests for the touched authority seams were run,
   and the stale provenance fixtures the audit anticipated were updated.

## 3. New operational command boundary

New explicit operational mode:

`four-token-standard-four-hour-run`

Existing meanings are preserved exactly:

- `standard-four-hour-run` remains the two-token operational Standard-4H
  authority. Its policy version, duration, and unscaled canonical ceilings are
  unchanged and are asserted by a focused regression test.
- `four-token-bounded-capacity-proof-run` remains proof-only. Its policy version,
  authorization profile, application namespace, wrapper schema, and
  child-terminal schema all remain distinct from the new operational authority.

The new mode is not a capacity selector. It has one immutable shape, no
`--max-tokens`, no cycle-count argument, and no capacity keyword on its public
runner. It is unreachable without its own one-shot wrapper binding and fails
closed on direct child invocation.

### 3.1 Neutral facade

`src/printer_v1/operator_cli/four_token_operational_composition.py`

This is the smallest authority/wiring layer needed to reuse the already-repaired
multi-cycle composition without production code depending on proof-named wrapper
semantics. It:

- owns no numbers (all projected from the canonical capacity contract);
- builds no runtime (`build_operational_multi_cycle_controller()` returns the
  existing repaired `FourTokenProofController.exact()`);
- performs no I/O of any kind;
- declares no Scheduler, Source Governor, factory runner, provider loop, schema
  owner, or selection algorithm.

## 4. Capacity derivation result

Derived live from `scaled_standard_four_hour_capacity_contract(4)`:

| Value | Derived | Expected comparison |
| --- | --- | --- |
| configured through-4h token slots | 4 | 4 |
| configured active cycles | 2 | 2 |
| total cycle admission ceiling | 2 | 2 |
| tokens per cycle | 2 | 2 |
| minimum cycle admission spacing (s) | 300 | at least 300 |
| lifecycle requests per token | 117 | 117 |
| lifecycle request outer ceiling | 472 | 472 |
| lifecycle Scheduler outer ceiling | 420 | 420 |
| automatic retries | 0 | 0 |
| endpoint rotation | false | false |
| long windows activated | false | false |

Result: `EXACT_MATCH_NO_DRIFT`.

No comparison value is hard-coded into the operational authority. A focused test
proves the derivation is live by patching the canonical capacity and observing
the derived policy move with it.

Operational policy version:

`V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`

Bounded clocks reused unchanged from the proven four-token envelope: 2,400s
pre-lifecycle acquisition and 18,000s post-supply lifecycle. Neither raises a
provider rate ceiling nor creates retry authority.

## 5. One-shot wrapper

`src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py`

Distinct identity:

- wrapper schema: `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_ONE_SHOT_WRAPPER_V1`
- authorization schema:
  `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`
- authorization package root:
  `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization`
- package kind: `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE`
- manifest schema:
  `PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_STANDARD_4H_V1`
- application namespace:
  `~/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications`
- child-terminal schema:
  `PRINTER_V1_FOUR_TOKEN_STANDARD_FOUR_HOUR_CHILD_TERMINAL_V1`

Existing one-shot laws are preserved and tested: exact authorization
identity/hash, exact bound repository branch and HEAD, allowed invocation
count 1, operator approval required, fail closed on hash/identity/mode mismatch,
fail closed on second application, no retry/rerun/resume/restart/successor, and
a blocked zero-state gate that runs while the authorization is still unconsumed.

The authorization document binds `operational_policy`, not `proof_policy`, so a
proof authorization cannot authorize the operational mode and vice versa. A
focused test proves that cross-authority rejection directly.

No real authorization was constructed. Only the schema/profile/wrapper
capability a later preparation lane needs now exists.

## 6. Provenance alignment result

Required final hierarchy is now in force for both four-token profiles:

CURRENT: Migration 058.

HISTORICAL: Migrations 050, 055, 056, 057.

- `MIGRATION_058_PACKAGE_ROOT` = `operator-runs/v2-9-8b-migration-058-application`
- `MIGRATION_058_PACKAGE_KIND` = `MIGRATION_058_EVIDENCE`
- Migration 057 ceased to be current four-token schema-transition evidence.
- Migration 058 is current evidence for both the repaired four-token proof
  profile and the new four-token operational profile.
- Ordinary and two-token Standard-4H profile semantics are untouched (both keep
  their Migration-050 defaults and their empty historical-migration tuple).

### 6.1 Migration-057 historical evidence: real, not guessed

The Migration-057 historical package identity was derived from actual preserved
operator evidence on this host, not invented:

- execution ID: `MIGRATION_057_20260816T191558Z`
- evidence class: `HISTORICAL_MIGRATION_057_EVIDENCE`
- expected complete file count: `6`
- expected inventory SHA-256:
  `9272f596e7a82c3cfe9d824595be74f34c7203dccab3bd541c187dc236519535`

The derivation used the committed enumeration and digest primitives themselves
(`_inventory_bound_package_files` and
`compute_historical_migration_inventory_sha256`), read-only, with no file
written, moved, or modified.

The method was validated before it was trusted: running the identical derivation
over the preserved Migration-055 and Migration-056 packages reproduced the
already-committed constants exactly
(`c00443733269993b40353b61390753a49dad184541120916c6e2a400fdd9e625` and
`4918774b95998aab821d69d06854665697347664faf04a3340f2299db95868f3`). That proves
both the derivation method and that the preserved copies are byte-identical to
what was originally bound. `BLOCKED_READINESS` /
`HISTORICAL_PROVENANCE_EVIDENCE_UNAVAILABLE` therefore does not apply.

No provenance validation was weakened, no historical requirement was deleted, no
evidence was fabricated, and no placeholder was substituted for exact evidence.

### 6.2 Migration-058 stays preparation-time bound

Only the Migration-058 package root and kind are committed to source. The exact
execution identity is supplied by the authorization document at preparation time
and hashed through the existing manifest mechanism. Host-specific DB and operator
evidence therefore remains preparation-time binding rather than hard-coded source
truth, as the lane required.

### 6.3 Profile separation

`supported_profiles()` now resolves exactly four distinct authorities with four
distinct command modes, package roots, package kinds, and manifest schemas.
Unknown profiles still fail closed. Historical authorization visibility for the
new operational profile covers the ordinary, Standard-4H, four-token proof and
new operational roots; visibility never creates reuse authority.

`_SUPPORTED_PROFILES` was deliberately implemented as a declared *name* tuple
resolved live by `supported_profiles()`. A frozen object tuple would have
silently broken the long-standing ability of focused tests to scope a disposable
fixture profile over a production name, which is a real fail-closed regression
rather than a test inconvenience.

## 7. Zero-state gate

The existing four-token zero-state gate was generalized, not duplicated. One
private owner `_assert_four_token_zero_state` holds every database identity
check, all ownership SQL, the host-process probe, the migration-ledger guard and
the source-configuration check. Two thin entry points differ only in which
authority validates the document and which exact 4/2/2 policy must match:

- `assert_four_token_proof_zero_state` (unchanged proof authority)
- `assert_four_token_standard_four_hour_zero_state` (new operational authority)

The gate continues to require migration count 58, head
`058_direct_pump_migration_cursor.sql`, integrity `ok`, zero FK violations, no
live Printer runtime, zero conflicting durable ownership in every existing
zero-state domain, valid free/public source configuration, and no pre-existing
application marker. A 059 head fails closed before consumption.

The new operational runtime mode was added to
`PRINTER_OPERATIONAL_RUNTIME_MODES`, so a live operational 4/2/2 child is
correctly recognized as a Printer runtime by the host-process probe.

## 8. Bounded offline proof result

`tests/test_v2_9_8b_four_token_standard_four_hour_bounded_offline_proof.py`

Result: `PASS`.

Conditions: disposable temporary SQLite database (never the authoritative
campaign DB), deterministic frozen time, fake/frozen later-cycle candidate
supply, no provider, no RPC, no WebSocket, no network, no process start, no
authorization.

Proven in one invocation, through the operational authority rather than the
proof command:

- exact derived 4/2/2 capacity and 117 / 472 / 420 ceilings;
- Cycle 1 admits exactly two fresh slots;
- Cycle 2 is admitted in the same campaign/run after the lawful 300s spacing and
  obtains fresh governed later-cycle supply (`admit` → `materialize` → `plan`,
  one supply call);
- four total slots with four distinct token rows, pair rows, mint identities and
  exact pair identities;
- exactly two cycles, exactly two slots per cycle;
- per-cycle Scheduler ownership resolves exactly, and the two cycles' factory
  step sets are disjoint;
- zero new source requests were recorded during the whole proof;
- no 12h/24h planning exists anywhere;
- one terminal closure with exactly one shared cleanup, and afterwards no third
  cycle, no second run, and no non-terminal run remains.

A separate focused test proves the repaired cross-cycle identity guard rejects a
Cycle-2 slot that carries a Cycle-1 mint/pair identity forward.

## 9. Files changed

Product:

- `src/printer_v1/operator_cli/four_token_operational_composition.py` (new)
- `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py` (new)
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py`
- `src/printer_v1/operator_cli/window_15m_child_terminal.py`

Tests (new):

- `tests/test_v2_9_8b_four_token_standard_four_hour_operational_command.py`
- `tests/test_v2_9_8b_four_token_standard_four_hour_one_shot_wrapper.py`
- `tests/test_v2_9_8b_four_token_operational_provenance_alignment.py`
- `tests/test_v2_9_8b_four_token_standard_four_hour_bounded_offline_proof.py`

Tests (stale provenance fixtures updated to the 058-current truth, as the audit
required):

- `tests/test_v2_9_8b_four_token_proof_migration_057_readiness.py`
- `tests/test_v2_9_8b_four_token_proof_migration_055_evidence.py`
- `tests/test_v2_9_8b_four_token_historical_migration_provenance.py`
- `tests/test_v2_9_8b_historical_migration_package_completeness.py`
- `tests/test_v2_9_8b_pre_lifecycle_schema_gate_coherence.py`

No migration file, provider adapter, source protocol, coordinator, campaign
owner, Scheduler or Source Governor file was changed. No unrelated cleanup or
refactor was performed.

## 10. Locks confirmed

- Migrations on disk: 58. Head: `058_direct_pump_migration_cursor.sql`. No 059.
- Authoritative `data/printer_v1.sqlite3` byte-identical to the recorded
  pre-lane identity: SHA-256
  `a77141bce32468a2685007a276dbac91d1ed68671b5036c7bc24f54f60ad46d7`, size
  `100794368`, inode `1230526`, mtime_ns `1787043184343686970`. No sidecars.
- No operational authorization package was created; no application marker
  namespace exists; no authorization was consumed.
- Zero provider, RPC or WebSocket calls occurred.
- Master untouched at `19bcd23da1608e406e25f675532df193b65d038a`.
- Solana-only, memecoin-only, paper-only. No wallet, private key, signing, real
  funds or live execution. No paid API. No scoring, ranking, confidence or
  weighted logic. No embeddings or vectors. No retrieval. No BUY/SELL/HOLD,
  positions, trades, paper audits or PnL. 5m remains support-only. 12h/24h remain
  locked and appear only as declared locked windows.

## 11. Regression result and pre-existing conditions

### 11.1 Controlled before/after comparison

Because the touched seam is broad, the regression set was measured against the
untouched baseline rather than asserted. The identical selection was run twice:
once on this lane's tree and once with every change in this lane stashed.

| | Baseline (stashed) | This lane |
| --- | --- | --- |
| passed | 1037 | 1093 |
| failed | 89 | 90 |

Failure-set difference: exactly **one** test moved from pass to fail, and none
moved from fail to pass:

`tests/test_v2_9_8b_pre_lifecycle_schema_gate_coherence.py::test_profile_current_migration_evidence_is_057`

That was a stale 057-as-current assertion of exactly the class the audit
authorized updating, and it was updated. Two sibling assertions in the same file
asserted the old three-package historical set; they were missed by the keyword
selection and were found and updated by re-running every affected file in full.

### 11.2 Directly affected files, run in full

Every test file referencing a changed symbol was then run complete (not keyword
filtered): 182 passed, 3 failed.

Those 3 remaining failures were confirmed **pre-existing on the untouched
baseline** by stashing this lane's changes and re-running the same two files,
which produced the identical failure set:

- `test_v2_9_8b_four_token_proof_authorization_profile.py::FourTokenProofAuthorizationProfileTests::test_exact_four_token_fixture_document_validates`
- `test_v2_9_8b_four_token_proof_authorization_profile.py::FourTokenProofExactCapacityAndTimingTests::test_two_bounded_clocks_stay_separate`
- `test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py::StandardFourHourOperationalActivationContracts::test_public_standard_four_hour_policy_is_explicit_and_bounded`

### 11.3 Pre-existing conditions outside this lane

The baseline carries 89 pre-existing failures across roughly 26 files, the
largest cluster being 31 in
`tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py` (first
error: `final authorization migration_execution_id mismatch` under the *ordinary*
profile, which this lane does not modify).

Per the lane's scope rule these are documented rather than silently repaired:
they are separate genuine conditions outside the approved change scope, and the
lane was not widened to fix them. They should be classified by their own lane.

## 12. Exact next permitted action

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Independent Closeout`

Do not proceed automatically into independent closeout. Do not prepare or create
the final operational authorization. Do not run Printer.
