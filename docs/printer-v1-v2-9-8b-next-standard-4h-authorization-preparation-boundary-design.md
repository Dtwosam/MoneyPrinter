# Printer V1 V2-9.8B — Next Standard-4H Authorization-Preparation Boundary Design

Date: 2026-08-31

Lane at authoring: **DESIGN / SPECIFICATION ONLY — NO AUTHORIZATION CREATION**

Independent operator review:

`PASS`

Implementation-boundary classification:

`EXISTING_OWNER_ALREADY_SUFFICIENT`

This reviewed design and preparation-lane state becomes active only when the
six-doc source-stack/design package is committed. Until that commit exists, do
not begin authorization preparation. Do not invent the future design-closeout
commit SHA. The later preparation task must inspect the actual resulting HEAD.

## A. Purpose and non-authority

This document specifies the exact preparation boundary for a later separately
approved fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package.

It is design/specification only. Independent design review is `PASS` with
classification `EXISTING_OWNER_ALREADY_SUFFICIENT`. No code change is required.
Existing canonical wrapper/profile/policy/non-reuse/zero-state owners remain
authoritative. The design baseline HEAD is NOT the future package binding after
this docs package is committed.

- No authorization currently exists for the next campaign.
- No authorization package, authorization ID, hash, signature, application
  marker, or consumption action is permitted until the design-closeout package
  is committed and a later preparation task is begun under that committed HEAD.
- No Printer execution, Central Scheduler runtime, provider/RPC/WebSocket call,
  campaign creation, authoritative DB mutation, retrieval unlock, financial
  unlock, or `WINDOW_12H` / `WINDOW_24H` activation is authorized by this
  design.
- After commit, the permitted lane is package preparation only. Preparation
  still may not apply/consume. Execution remains at least one further explicit
  operator approval after independent package review.

Preserved builder sequence:

```text
readiness -> authorization-boundary design/specification -> authorization preparation/implementation only if separately approved -> independent package review -> later explicit execution approval -> bounded execution/proof -> closeout
```

Do not collapse design/specification into package creation.

## Design baseline versus future preparation binding

### Design baseline (this document)

Reviewed against current exact identities:

- repository HEAD: `7d5c3a631091af7e07f941fe56647d6ffc596d46`
- parent: `e79c80d872e6694fce564dbd683567e0c02622f2`
- authoritative DB path: `data/printer_v1.sqlite3`
- authoritative DB SHA-256:
  `859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

These identities establish the design/review baseline only.

### Future authorization-preparation binding

A later separately approved authorization-preparation lane MUST re-read:

- actual Git HEAD at preparation time;
- tracked working-tree cleanliness at preparation time;
- actual authoritative DB path and SHA-256 at preparation time;
- migration count/tip, integrity/FK, and ownership quiescence at preparation
  time.

The authorization package must bind those exact preparation-time identities.

Do **not** hard-code `7d5c3a63...` into a future package merely because that SHA
was the design baseline. Committing this design document (or any later approved
source-stack sync) will change HEAD. Fail closed if preparation-time HEAD/DB
identity differs from the state independently approved for that preparation
task.

No stale cached identity. No hand-entered substitute SHA.

## B. Exact preparation-time identity binding

The later preparation owner must establish, read-only and without mutation, all
of the following before any package bytes are finalized:

1. exact repository HEAD via live `git rev-parse HEAD`;
2. tracked-clean repository state (`git status --short` shows no tracked
   modifications/staged changes; only previously known untracked
   `operator-runs/...` may remain);
3. exact authoritative DB path `data/printer_v1.sqlite3` resolved inside the
   repository;
4. exact DB SHA-256 recomputed at preparation time;
5. expected migration count/tip currently required by committed schema admission
   coherence (`62` / `062_pre_admission_attempt_evidence.sql` at design
   baseline; preparation must reconfirm the live committed requirement, not a
   remembered number);
6. DB integrity `ok`, foreign-key violations `0`, no SQLite WAL/SHM/journal
   sidecars;
7. runtime/ownership quiescence using canonical ownership truth:
   - zero non-terminal campaigns/runs/cycles;
   - zero active/stopping campaign supervision;
   - zero unreleased campaign leases;
   - zero active Scheduler jobs;
   - zero active factory runs/steps;
   - zero active campaign-owned work (`PENDING`/`RUNNING`/`COOLDOWN`);
   - zero active pre-admission attempts outside terminal dispositions;
   - no live Printer / Source Governor / Central Scheduler / wrapper campaign
     process.

If any identity or quiescence check fails, stop without creating or finalizing a
package.

## C. Canonical authorization profile

### Canonical authority family

The next bounded campaign uses the already-approved operational four-token
Standard-4H authority. Do not invent a parallel authorization format.

Current committed owners:

| Role | Owner |
| --- | --- |
| Document schema / fixture shape | `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py` |
| Document validation owner | `validate_four_token_standard_four_hour_authorization_document` |
| One-shot application/consumption owner | `apply_authorization_once` in the same module |
| Exact operational policy owner | `exact_operational_policy()` in `src/printer_v1/operator_cli/four_token_operational_composition.py` |
| Git authorization profile | `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE` in `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` |
| Prior non-reuse field validator | `validate_prior_authorizations_non_reusable` / `extract_approved_historical_authorization_ids` |
| Pre-consumption zero-state gate | `assert_four_token_standard_four_hour_zero_state` in `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` |

Where historical authorization docs disagree with current committed
code/contracts, current committed canonical implementation wins unless the
active source stack explicitly says otherwise.

### Authoritative schema / profile / version

- Final authorization schema version:
  `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`
- Wrapper schema version:
  `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_ONE_SHOT_WRAPPER_V1`
- Git provenance manifest schema version:
  `PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_STANDARD_4H_V1`
- Operational policy version:
  `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- Authorized command mode:
  `four-token-standard-four-hour-run`
- Authorization package root:
  `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization`
- Exact package relative path shape:
  `{authorization_package_root}/{authorization_id}/final_authorization.json`
- Application marker namespace (outside repository; consumption-only):
  `~/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/`

### Exact required document fields

The package object must contain exactly these top-level keys and no others:

- `schema_version`
- `authorization_id`
- `migration_execution_id`
- `verdict`
- `authorized_at`
- `expires_at`
- `validity_seconds`
- `repository` (`branch`, `head`)
- `authorized_command` (`mode`, `operator_approved`)
- `one_shot_policy`
- `operational_policy`
- `authoritative_database` (`path`, `sha256`, `size`, `inode`, `mtime_ns`,
  `migration_count`, `migration_head`)
- `prior_authorizations_non_reusable`

Required one-shot policy exact object:

- `allowed_invocation_count`: `1`
- `automatic_retry_allowed`: `false`
- `manual_rerun_allowed`: `false`
- `resume_allowed`: `false`
- `restart_allowed`: `false`
- `successor_allowed`: `false`

Required operational policy must equal `exact_operational_policy()` byte-for-byte
in key set, types, and values. That policy already encodes the Standard-4H 4/2/2
envelope, zero automatic retries, no endpoint rotation, and locked long windows.

`authorized_command.mode` must be exactly `four-token-standard-four-hour-run`.
`authorized_command.operator_approved` must be `true` inside the package as the
operator-approval binding field required by the schema; this still does **not**
authorize consumption by itself. Consumption requires a later separate explicit
operator invocation of `apply_authorization_once(..., operator_approved=True)`
after independent package review PASS and later explicit execution approval.

`verdict` must be a PASS-ending string accepted by the canonical validator.
`migration_execution_id` must bind the profile’s current migration-062 evidence
identity required by
`FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE`.

## D. Permanent non-reuse trust root

The future authorization must carry the complete
`prior_authorizations_non_reusable` trust root.

Minimum required retained IDs that any future package must include:

- `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260830T113652Z_a89ed6bc`
- `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`

Those are not assumed to be the only required IDs.

### Derivation / validation rule

Preparation must derive/validate the complete trust root from authoritative
committed/durable evidence rather than manually dropping historical IDs:

1. Start from the most recent consumed operational four-token Standard-4H
   package’s own `prior_authorizations_non_reusable` list.
2. Add that package’s own `authorization_id` (now permanently consumed).
3. Union any additional IDs required by active governance (`AGENTS.md` /
   `CURRENT_HANDOFF.md` / durable closeouts) that are not already present.
4. Validate the resulting list with
   `validate_prior_authorizations_non_reusable`:
   - array of safe non-empty strings;
   - unique;
   - lexicographically sorted;
   - must not include the new current `authorization_id`.
5. Directory discovery of `operator-runs/...` never creates or broadens trust.
   Discovery may only corroborate evidence for IDs already declared.

No consumed authorization may be revived, reused, replaced, or reinterpreted as
current authority.

## E. Standard-4H bounded envelope

Authorization must preserve exactly:

- Solana-only;
- Solana memecoin-only;
- paper-only;
- two cycles;
- exactly 2 concurrent active token slots;
- up to 4 distinct token identities campaign-wide;
- Cycle 2 fresh slot identities disjoint from prior admitted cycle slots;
- `WINDOW_15M`;
- hard-gated `WINDOW_1H`;
- hard-gated `WINDOW_4H`;
- stop at 4h;
- `WINDOW_12H` locked;
- `WINDOW_24H` locked;
- `WINDOW_5M_MICRO_EVENT` support-only;
- no automatic retry/rerun/resume/restart/successor.

Do not widen the envelope. Envelope drift is a fail-closed preparation blocker.

## F. Source Governor / Central Scheduler ownership

Require:

- Source Governor remains sole governed source authority;
- Central Scheduler remains scheduling authority;
- no independent source loop;
- no Source Governor or Central Scheduler bypass;
- one-shot operational application boundary
  (`apply_authorization_once` + application marker);
- fail-closed behavior;
- no automatic restart.

Provider availability is not an authorization-design fact and is not required to
prepare or review an authorization package. Source scarcity or transport failure
must remain honest operational safe-stop / token-local evidence according to
existing contracts. Do not convert readiness or design PASS into provider
readiness claims.

## G. Active-work preflight truth

Bind the post-repair rule:

```text
Raw historical slot state alone must not establish active execution authority.
Canonical campaign/run/supervision/lease/Scheduler/progression ownership truth governs active-work readiness.
```

Active-work readiness for preparation must be determined through canonical:

- campaign state;
- campaign run state;
- campaign cycle state;
- supervision state;
- lease release / cleanup truth;
- Scheduler job status;
- factory run/step status;
- campaign scheduler work state;
- progression attempt/token disposition where relevant;
- pre-admission attempt state.

The Aug-30 historical Cycle-2 `SELECTED` rows must not be mutated merely to
satisfy preflight. They are accepted historical residue under terminal/drained
canonical ownership.

### Fail-closed preparation-time check (specify only; do not implement here)

Preparation must fail closed unless canonical ownership queries show quiescence
equivalent to the committed operational zero-state domains and the readiness
audit ownership checks. Specifically:

- non-terminal campaign/run/cycle counts are zero;
- active/stopping supervision count is zero;
- unreleased lease count is zero;
- active Scheduler / factory / campaign-work / pre-admission counts are zero.

Finding historical `SELECTED` token-slot rows under an otherwise
`TERMINAL_*` campaign is **not** by itself a preparation blocker and must not
trigger mutation. Treating raw `SELECTED` as active ownership would be a design
defect.

The existing committed pre-consumption gate
`assert_four_token_standard_four_hour_zero_state` already uses canonical
ownership SQL (`campaign_state NOT LIKE 'TERMINAL_%'`, active supervision,
active work/jobs, etc.) and does not treat raw slot `SELECTED` as active
ownership. Preparation-time preflight must preserve that rule.

## H. Authorization lifecycle states

Allowed future sequence, kept distinct:

1. A separately approved preparation task may create a package only after
   preparation-time identity/ownership gates pass.
2. The package receives a unique fresh `authorization_id`.
3. Exact package bytes are frozen and hashed (SHA-256 of
   `final_authorization.json`).
4. Independent package review occurs against those exact bytes/hash.
5. The package remains unusable during review: review must not call
   `apply_authorization_once`, must not create an application marker, and must
   not launch Printer.
6. Later explicit operator approval is required before application/consumption.
7. Application is one-shot through `apply_authorization_once`.
8. Once the application marker exists, the authorization is permanently consumed
   and non-reusable regardless of child success/failure.
9. No automatic retry/reuse/restart/resume/successor path exists.

Do not collapse preparation, review, application, and execution into one action.

### Immutable after preparation

Once package bytes are frozen for independent review, the entire
`final_authorization.json` object is immutable, including:

- `authorization_id`;
- repository HEAD/branch bindings;
- authoritative DB identity fields;
- `one_shot_policy` / `operational_policy`;
- `prior_authorizations_non_reusable`;
- temporal fields and verdict;
- `migration_execution_id` and command mode.

Any change requires a new authorization ID and a new preparation lane. Editing a
reviewed package in place is prohibited.

## I. Fail-closed preparation blockers

Future preparation must stop without creating/finalizing a package if any
required condition fails, including:

- wrong / unapproved preparation-time HEAD;
- tracked dirty tree;
- unexplained DB SHA mismatch versus independently approved preparation-time
  DB identity;
- DB integrity/FK/migration mismatch;
- SQLite sidecars present;
- active runtime/ownership;
- missing/incomplete prior-authorization non-reuse trust;
- source-stack / `CURRENT_HANDOFF.md` contradiction about current lane or locks;
- Standard-4H envelope drift;
- missing/mismatched canonical authorization schema/profile/command mode;
- ambiguous campaign ownership truth;
- accidental retrieval/financial/`WINDOW_12H`/`WINDOW_24H` unlock;
- attempt to revive a consumed authorization ID.

Classification rule:

- structural/governance/identity/ownership failures are preparation blockers;
- source scarcity / provider transport uncertainty is an execution-time
  operational fact under Source Governor honest safe-stop / token-local
  contracts, not a code defect and not a substitute for structural readiness.

## J. Package-review contract

Before an authorization can become eligible for later application, an
independent operator must verify:

- exact package bytes and SHA-256;
- authorization ID uniqueness and safe-identifier shape;
- exact preparation-time HEAD/DB bindings inside the package;
- canonical schema/profile/version/command mode;
- complete prior non-reuse trust root, including at least Aug-30 `a89ed6bc` and
  Aug-28 `5fcb1bf5`, sorted/unique/valid;
- Standard-4H envelope via exact `operational_policy` equality;
- one-shot / no-retry / no-resume / no-restart / no-successor rules;
- Source Governor / Central Scheduler authority preserved by command mode and
  policy;
- permanent V1 locks unchanged;
- no hidden runtime action occurred during preparation or review;
- no stale preparation evidence reused from a different HEAD/DB;
- package path is exactly under the canonical authorization package root;
- review itself did not create an application marker or invoke
  `apply_authorization_once`.

Independent review PASS must still not execute Printer and must still not
consume the authorization.

## K. Minimum sufficient future proof

For future authorization preparation/review, require only bounded checks:

- read-only Git identity and status;
- read-only DB SHA / integrity / FK / migration / sidecar checks;
- canonical ownership quiescence queries;
- `validate_four_token_standard_four_hour_authorization_document`;
- `validate_prior_authorizations_non_reusable`;
- exact `operational_policy` / `one_shot_policy` equality;
- package path/profile binding checks;
- package SHA-256 verification;
- `git diff --check` / `git status --short` for documentation/package staging
  hygiene.

No provider/RPC/WebSocket call is required to prepare or review authorization.
No broad regression suite is required by default.

## Explicit design decisions

1. **Canonical authorization validation owner:**
   `validate_four_token_standard_four_hour_authorization_document` in
   `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py`.

2. **One-shot application/consumption owner:**
   `apply_authorization_once` in
   `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py`,
   with permanent consumption established by creation of the application marker
   under the out-of-repo application namespace.

3. **Authoritative schema/profile/version:**
   document schema
   `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`;
   profile
   `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE`;
   policy
   `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`;
   command mode
   `four-token-standard-four-hour-run`.

4. **Immutable after preparation:**
   the entire frozen `final_authorization.json` byte content and its SHA-256.

5. **Re-read at preparation time:**
   Git HEAD, branch, tracked-tree cleanliness, authoritative DB path/SHA/size/
   inode/mtime_ns, migration count/head, integrity/FK/sidecars, and canonical
   ownership/runtime quiescence.

6. **Prior non-reuse derivation/validation:**
   derive from prior consumed package trust root + that package’s own ID + any
   additional active-governance-required IDs; validate with
   `validate_prior_authorizations_non_reusable`. Directory discovery never
   creates trust.

7. **What prevents stale authorization reuse after HEAD or DB changes:**
   the package binds exact `repository.head` and
   `authoritative_database.sha256` (plus full DB identity fields). Application
   resolves the exact package path/hash, revalidates the document, and
   pre-consumption gates re-inspect live DB/migration/ownership state. A changed
   HEAD/DB fails closed against the frozen package binding / live gates rather
   than being silently re-bound.

8. **What prevents package review from accidentally consuming authorization:**
   review is read-only validation of package bytes/hash and schema/profile/
   trust/envelope. Review must not invoke `apply_authorization_once`, must not
   write under the application marker namespace, and must not launch the
   operational child command.

9. **Exact later operator action required before consumption:**
   after independent package review PASS, a later separate explicit operator
   approval must invoke
   `apply_authorization_once(..., operator_approved=True, authorization_file=..., authorization_sha256=...)`
   for the exact reviewed package. Package presence alone is not consumption
   authority.

10. **Historical `SELECTED` rows under an otherwise terminal/drained campaign:**
    not an active-ownership blocker; do not mutate them; determine readiness from
    canonical campaign/run/supervision/lease/Scheduler/factory/progression/
    pre-admission truth only.

11. **Structural blockers versus execution-time provider facts:**
    structural blockers = HEAD/tree/DB identity, integrity/migrations,
    ownership/runtime quiescence, schema/profile/envelope/trust-root,
    source-stack contradictions, accidental capability unlocks.
    Execution-time provider facts = live DexScreener/GeckoTerminal/RPC
    availability and transport outcomes under Source Governor. Provider facts
    are not authorization-design blockers and are not committed-code defects by
    themselves.

12. **Existing committed implementation sufficiency:**

`EXISTING_OWNER_ALREADY_SUFFICIENT`

The committed operational four-token Standard-4H wrapper, composition policy,
Git authorization profile, prior-non-reuse validators, and operational zero-state
gate already define and enforce this preparation/application boundary. This
design does not propose code. A later preparation lane may construct a package
that conforms to the existing schema and must validate it with the existing
owners; it must not invent a parallel format or bypass `apply_authorization_once`.

## Next-lane rule

Independent design review is `PASS`. After the six-doc source-stack/design
package is committed, the exact active lane is:

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION
```

Exact next permitted action after that commit:

```text
Prepare one fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package using the existing canonical authorization owners, freeze/hash the exact package bytes, and stop unconsumed for independent package review.
```

That lane may create/freeze/hash a package but still may not apply/consume it.
Independent package review remains mandatory. A further explicit operator
approval remains mandatory before `apply_authorization_once`.

Until the six-doc package is committed, authorization preparation remains
blocked and no package may be created. No authorization currently exists for
the next campaign.

## Non-creation confirmation for this design / docs-transition task

This design and its post-review source-stack transition create documentation
only.

They do not create:

- JSON/YAML/TOML authorization files;
- candidate authorization IDs;
- package hashes;
- signed/frozen authorization bytes;
- application/consumption markers;
- files under an authorization `operator-runs/...` directory;
- code/tests/migrations;
- DB/runtime/provider activity.
