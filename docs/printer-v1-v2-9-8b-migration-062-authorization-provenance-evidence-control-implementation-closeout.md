# Printer V1 V2-9.8B Migration-062 Authorization-Provenance Evidence-Control Implementation Closeout

Date: 2026-08-28

Implementation verdict:

`V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_IMPLEMENTATION_PASS`

Independent closeout verdict:

`V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_IMPLEMENTATION_CLOSEOUT_PASS`

## 1. Authority and boundary

This closeout implements only the explicitly approved design:

`docs/printer-v1-v2-9-8b-migration-062-authorization-provenance-evidence-control-design.md`

The lane changed one production provenance owner and its focused tests. It did
not apply or rerun migration 062, modify migration evidence, mutate the
authoritative database, create/apply/consume an authorization, create an
application marker, run Printer, contact providers/RPC/WebSocket, run Source
Governor or Central Scheduler, start a campaign, or resume remote-host work.

## 2. Implementation

The sole production owner remains:

`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`

It now owns the exact current migration-062 identity once:

- root: `operator-runs/v2-9-8b-migration-062-application`;
- kind: `MIGRATION_062_EVIDENCE`;
- execution: `MIGRATION_062_20260828T182504Z`;
- complete file count: `4`;
- inventory SHA-256:
  `fa617f77f288705e7e8a4d3676f78feee041f098292a59d431a60e66624bcd02`.

Both `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` and
`FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE` consume that same exact
identity. Ordinary and two-token Standard-4H profiles remain unchanged.

Migration 061 is now the seventh immutable historical migration descriptor:

- root: `operator-runs/v2-9-8b-migration-061-application`;
- execution: `MIGRATION_061_20260823T200709Z`;
- class: `HISTORICAL_MIGRATION_061_EVIDENCE`;
- complete file count: `5`;
- historical-class inventory SHA-256:
  `ff8aefa1c0ee3fe4ec2063400a97cd81b8311bc4aa23dd402614bb609659a459`.

Independent path-sorted inventory recomputation produced the exact current-062
members:

| Order | Member below `MIGRATION_062_20260828T182504Z/` | Size | SHA-256 |
| ---: | --- | ---: | --- |
| 1 | `disposable/printer_v1_061_to_062_rehearsal.sqlite3` | 130138112 | `341373e3bea3816b2b5ff86a54b957f2fff96c270d887323f1d53cb4392dcff8` |
| 2 | `migration_062_controlled_application_closeout.md` | 2544 | `14822f8347baab38df9ab308794c25a9336b29b985af36ded24fae860e20a7f9` |
| 3 | `migration_062_controlled_application_evidence.json` | 8648 | `82cbcac85abb63a58a4509b9614613561a78c29ae8e3bccd6ae5e910283b3b20` |
| 4 | `printer_v1_pre_062_verified_backup.sqlite3` | 130117632 | `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1` |

Independent path-sorted, historical-class inventory recomputation produced the
exact migration-061 members:

| Order | Member below `MIGRATION_061_20260823T200709Z/` | Size | SHA-256 |
| ---: | --- | ---: | --- |
| 1 | `apply_migration_060_061.py` | 39030 | `362aa42b8b52f679f0583eedfbbe2c46f0af27c8d059ce843ccda4c20d922997` |
| 2 | `backup_restore_rehearsal.json` | 42034 | `9e4100eb2c4b59afae4f0f3df77719a3567fdd5d680b2a27dfb72a27ef380bc5` |
| 3 | `migration_060_061_application_receipt.json` | 28785 | `fecacf1649cf7e862aac1f4b7e9c057a92c4d4ddc6a351d247a4597b308170d1` |
| 4 | `post_application_snapshot.json` | 29299 | `590ec13b88cf75aba830808b73dd687135aa4573b2a31c7752006eeeb264ff2d` |
| 5 | `pre_application_snapshot.json` | 29600 | `906d3c302794c656dbea438b3758fae7ac0fcc46f0f171f39bfa7f6846ace0af` |

Consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7` has the
diagnostic-only disposition `CONSUMED_CHILD_EXITED_ZERO`. It remains historical
and permanently non-reusable.

No authorization or Git-provenance manifest schema changed. No validator
equality was weakened. `pre_authorization_migration_ledger_guard.py`, schema
admission, wrappers, operational command, migration SQL, and runtime code are
unchanged.

## 3. RED/GREEN proof

The new focused test was run before production code changed. RED was exact:

- missing migration-062 owner constants/profile binding;
- migration 061 absent from the historical chain; and
- consumed `...8e43eae7` missing its diagnostic disposition.

RED result: `3 failed, 1 passed`.

After the minimal owner change, the new focused file passed `4 passed`.

The directly affected bounded regression set initially passed:

`175 passed, 59 subtests passed`

Independent closeout review then adjudicated the adjacent 31-test disposition
and handoff batch, corrected only supported stale test fixtures/expectations,
and ran the combined final gate:

`206 passed, 64 subtests passed`

That set proves:

1. both four-token production profiles require exact current 062 provenance;
2. migration 061 is exact historical provenance and is disjoint from current;
3. an authorization/manifest binding stale 061 or a wrong 062 execution fails;
4. exact 062 current evidence passes canonical pre-marker validation;
5. wrong root, kind, file count, or inventory digest fails;
6. missing, extra, or byte-drifted 062 evidence fails on disposable copies;
7. consumed `...8e43eae7` enumerates only as historical/non-reusable evidence;
8. the ledger/schema guards remain exact at 62/tip 062 and fail closed at stale
   or dishonest bindings; and
9. the real authorization roots and authoritative DB retain exact before/after
   identities.

## 4. Required adjacent 17-failure adjudication

The first independent adjacent run produced `14 passed, 17 failed, 5 subtests
passed`. None was an `ACTUAL_IMPLEMENTATION_REGRESSION` or a
`DIRECTLY_AFFECTED_STALE_TEST_EXPECTATION` requiring production changes.

### 4.1 Historical fixture / synthetic trust-root debt — 11

All 11 failed at the same fail-closed production boundary:

`unapproved historical authorization package contains untracked files not covered by the trust root`

The first omitted exact package was
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T114542Z_d3bc361a`. The fixtures ended
at `...4563a9dd` even though four later immutable packages already existed:
`...d3bc361a`, `...b861fd4c`, `...c3063b7c`, and consumed `...8e43eae7`.
Production correctly rejected the incomplete trust roots. Classification:
`HISTORICAL_TEST_FIXTURE / SYNTHETIC_TRUST_ROOT_DEBT`.

Exact original failing tests:

1. `test_v2_9_8b_07d92adf_historical_disposition_repair.py::Consumed07d92adfHistoricalDispositionTests::test_exact_consumed_package_resolves_to_child_exited_nonzero`
2. `test_v2_9_8b_latest_consumed_authorization_historical_disposition.py::LatestConsumedAuthorizationHistoricalDispositionTests::test_exact_latest_consumed_package_has_approved_historical_disposition`
3. `test_v2_9_8b_latest_consumed_authorization_historical_disposition.py::LatestConsumedAuthorizationHistoricalDispositionTests::test_latest_authorization_remains_historical_only_and_disjoint`
4. `test_v2_9_8b_latest_consumed_authorization_historical_disposition.py::LatestConsumedAuthorizationHistoricalDispositionTests::test_policy_entry_does_not_bypass_package_marker_or_child_bindings`
5. `test_v2_9_8b_latest_consumed_authorization_historical_disposition.py::LatestConsumedAuthorizationHistoricalDispositionTests::test_temporal_validity_never_reactivates_consumed_authorization`
6. `test_v2_9_8b_latest_consumed_authorization_historical_disposition.py::LatestConsumedAuthorizationHistoricalDispositionTests::test_three_historical_authorizations_keep_distinct_dispositions`
7. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_exact_unconsumed_package_has_superseded_historical_disposition`
8. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_four_historical_authorizations_keep_distinct_records`
9. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_policy_entry_does_not_bypass_package_sha_or_size_bindings`
10. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_superseded_authorization_remains_historical_only`
11. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_unconsumed_isolation_does_not_fabricate_marker_child_or_campaign`

The test-only correction added those four exact preserved IDs to each supported
future fixture. It did not derive trust from directory discovery and did not
change production. All SHA, size, marker, child-terminal, disjointness,
supersession, and non-reuse negative assertions remain.

### 4.2 Governance text expectation stale — 6

These tests expected superseded A/B/BLOCK wording from a pre-preparation
handoff. The active handoff had legitimately advanced through migration 062.
Classification: `GOVERNANCE_TEXT_EXPECTATION_STALE`.

Exact original failing tests:

1. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_future_path_requires_no_tracked_handoff_mutation_after_preparation`
2. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_handoff_encodes_fail_closed_block_forbidding_operator_start`
3. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_handoff_encodes_transition_a_without_tracked_mutation`
4. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_handoff_encodes_transition_b_without_tracked_mutation`
5. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_permanent_locks_remain_encoded_in_handoff`
6. `test_v2_9_8b_authorization_handoff_transition_and_supersession.py::AuthorizationHandoffTransitionAndSupersessionTests::test_transitions_do_not_apply_retroactively_to_17181afc`

The test-only correction now asserts the exact current lane, post-repair
HEAD/exact-DB/migration-062 binding, separate execution authority, non-execution
boundary, historical supersession, and unchanged permanent locks. It does not
treat handoff text as runtime authority. Rerun result: `31 passed, 5 subtests
passed`.

### 4.3 Non-gating over-broad diagnostics

Two unchanged legacy suites were sampled beyond the approved current owner
set. The old migration-ledger file still pins catalogue 52 and synthetic
pre-schema fixtures (`53 passed, 13 failed, 17 subtests passed`), while the old
ordinary WINDOW_15M manifest fixture omits the authorization document's already
required `migration_execution_id` (`17 passed, 31 failed`). Neither production
path changed in this lane. Current 62/tip-062 guard/coherence tests and the
current four-token validator tests are included in the all-green 206-test gate;
production was not weakened to accommodate obsolete fixtures.

## 5. Database and runtime non-effects

Pre-implementation authoritative DB identity:

- SHA-256:
  `dececa7ce402856978675c66ecbdfd23b88ed97e3ff23f282a2588a436c93836`;
- size: `130138112`;
- inode: `1230526`;
- mtime: `1787941551` seconds in the platform `stat` capture;
- migration state: `62 / 062_pre_admission_attempt_evidence.sql`.

Final verification re-proved the same SHA-256, size, inode, and mtime; integrity
`ok`; zero foreign-key violations; exact 62/tip-062 ledger and migration-062
objects; zero attempt-evidence rows; zero SQLite sidecars; no database holder;
and no Printer/Governor/Scheduler process match.

## 6. Reviewed scope

Parent/pre-repair HEAD:

`45329baafd71f5dba4e2c0e973acc6829fd05e30`

The complete production diff is confined to
`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`. Both
four-token profiles changed atomically. Ordinary and two-token Standard-4H
profiles, authorization/manifest schemas, validator control flow, equality
strength, pre-authorization ledger guard, wrappers, operational command,
migration SQL, evidence bytes, and authoritative DB are unchanged.

Focused tests changed only to promote current 062, preserve historical 061,
exercise exact positive/negative evidence controls, and synchronize the 17
supported adjacent fixture/governance cases above. No meaningful negative
coverage was deleted.

## 7. Exact next permitted action

The current working tree must receive independent review and a normal commit
before any authorization preparation. No authorization may bind the unchanged
pre-repair HEAD because the repair is not part of that commit.

Exact next lane:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

That lane must bind the new committed post-repair HEAD, freshly re-verified
unchanged authoritative DB identity, and exact migration-062 current provenance.
Preparation does not authorize application, consumption, or execution.

All permanent V1 locks remain unchanged.

`V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_IMPLEMENTATION_PASS`

`V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_IMPLEMENTATION_CLOSEOUT_PASS`
