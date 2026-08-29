# Printer V1 V2-9.8B — Post-Reconciliation Readiness and Aug-28 Consumed-Authorization Historical-Disposition Design

Date: 2026-08-29

Lane: **READINESS CLOSEOUT + NARROW PROVENANCE AUDIT/DESIGN ONLY**

Baseline governance HEAD:

`aca6218f72e3b97fef3d0a93c98c15dbbc91819a`

Authoritative post-reconciliation DB SHA-256:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`

## 1. Post-reconciliation readiness evidence

The operator ran the required local read-only gate at exact governance HEAD and reported:

- HEAD exactly `aca6218f72e3b97fef3d0a93c98c15dbbc91819a`;
- tracked/index state clean; preserved `operator-runs/` evidence remains untracked;
- authoritative DB SHA exactly `a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`;
- exact interrupted execution inspection returns `RECOVERED`;
- integrity `ok`; foreign-key violations `0`;
- migration ledger exactly 62 rows, tip `062_pre_admission_attempt_evidence.sql`;
- active Scheduler jobs `0`;
- active pre-admission attempts `0`;
- active factory runs `0`;
- exact campaign lease absent;
- Printer/Governor/Scheduler process matches `0`;
- SQLite sidecars `0`;
- consumed application marker SHA remains `9099e5f31949bd9dc219dbe58a301e095df1600cd5698b705841ee33bfd0c76a`;
- all retry/rerun/resume/restart/successor flags remain exactly `false`;
- current migration provenance remains `MIGRATION_062_20260828T182504Z`, file count 4, digest `fa617f77f288705e7e8a4d3676f78feee041f098292a59d431a60e66624bcd02`.

Existing locked-table counts were also re-read. Nonzero historical rows exist in retrieval-query/paper-decision/audit-report tables, but this is not a new capability delta: the active current-state audit already records those historical row counts while retrieval matches, positions, trade events, paper trade audits and PnL-related operational state remain absent/locked. This lane does not activate or consume any retrieval or financial capability.

Operational/database readiness verdict:

`V2_9_8B_POST_RECONCILIATION_LOCAL_STATE_READINESS_PASS`

## 2. Provenance freshness finding

The local audit reported:

`consumed_terminal_disposition_policy: DISPOSITION_NOT_AVAILABLE`

for exact consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`.

This is not an authorization-reuse bug. The marker remains consumed and all non-reuse flags are false. It is a **historical provenance freshness gap**.

The existing provenance owner deliberately separates:

1. trust / non-reuse authority, which comes only from the next authorization document's explicit sorted `prior_authorizations_non_reusable` list; and
2. diagnostic terminal disposition, which comes only from the committed exact-ID policy map.

Directory discovery grants neither trust nor a specific disposition.

The existing historical-disposition proof pattern requires a newly consumed exact authorization to receive its exact diagnostic terminal disposition while proving that:

- a lookalike ID remains at the default `DISPOSITION_NOT_AVAILABLE`;
- the policy entry does not create trust;
- omitting the consumed ID from a future trust root still fails closed;
- package SHA/size, marker, manifest and child/wrapper-terminal evidence remain independent immutable bindings.

The incident evidence for `...5fcb1bf5` proves the one-shot wrapper consumed the authorization and the child exited nonzero. The later exact residue reconciliation repairs only the interrupted database residue; it does not rewrite the historical wrapper/child terminal fact.

Therefore the exact historical diagnostic disposition is:

`CONSUMED_CHILD_EXITED_NONZERO`

## 3. Why fresh authorization preparation is not yet the next lane

A future fresh four-token Standard-4H authorization must explicitly carry `...5fcb1bf5` in `prior_authorizations_non_reusable` because its untracked package remains under the governed authorization root. The validator intentionally fails closed if an untracked historical package exists but is absent from that explicit trust root.

Technically the validator can represent an approved historical package with the default diagnostic disposition. However the active Printer evidence-control pattern has already adopted exact terminal dispositions for newly consumed four-token packages, including the immediately preceding consumed authorization. Advancing to fresh authorization preparation while the latest consumed package is diagnostically stale would leave the provenance chain knowingly behind the authoritative incident/recovery history.

This is therefore classified as:

`PROVENANCE_FRESHNESS_BLOCKER`

not:

- a database defect;
- a source/provider limitation;
- an authorization-reuse weakness;
- a recovery defect; or
- an operational residue defect.

Readiness verdict:

`V2_9_8B_POST_RECONCILIATION_FRESH_NEXT_BOUNDED_CAMPAIGN_READINESS_GOVERNANCE_BLOCKED_ON_LATEST_CONSUMED_AUTH_HISTORICAL_DISPOSITION`

## 4. Narrow repair design

### Goal

Promote exact consumed authorization `...5fcb1bf5` into the committed diagnostic historical-disposition policy without granting it any trust/reuse authority and without changing database/runtime behavior.

### Production change

Only the provenance owner may change:

`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`

Add exactly:

`"V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5": "CONSUMED_CHILD_EXITED_NONZERO"`

to `_POLICY_TERMINAL_DISPOSITIONS`.

No vocabulary expansion is required. Do not add a recovered-specific terminal disposition: authoritative residue recovery is separate evidence and must not overwrite the consumed wrapper/child terminal classification.

### Focused tests

Add a new exact-ID historical-disposition proof modeled on the existing latest-consumed-authorization test. It must prove at minimum:

1. exact `...5fcb1bf5` enumerates with `CONSUMED_CHILD_EXITED_NONZERO`;
2. equivalent/lookalike ID retains `DISPOSITION_NOT_AVAILABLE`;
3. policy registration alone never creates historical trust;
4. omitting `...5fcb1bf5` from the future `prior_authorizations_non_reusable` trust root fails closed when its untracked package is present;
5. including it explicitly permits enumeration only as historical/non-reusable evidence;
6. its marker remains allowed-invocation-count 1 with all retry/rerun/resume/restart/successor flags false;
7. no temporal-validity path can reactivate it;
8. existing historical authorization IDs remain distinct and disjoint.

Update only directly affected future-history test fixtures that enumerate the complete four-token authorization root so they explicitly include `...5fcb1bf5`. Do not derive trust from directory scanning.

### Proof boundary

Minimum sufficient proof:

- new focused exact-ID disposition test;
- directly affected historical authorization / transition / supersession suites;
- current migration-062 provenance owner tests;
- `py_compile` for the changed production owner;
- `git diff --check`.

No broad runtime regression suite is justified because the change is diagnostic provenance policy only.

### Database/runtime effects

Forbidden:

- authoritative DB writes;
- Printer execution;
- Source Governor or Central Scheduler runtime;
- provider/RPC/WebSocket contact;
- authorization preparation/application/consumption;
- new application marker;
- campaign execution;
- recovery/reconciliation;
- remote/VPS work;
- retrieval or financial activation.

The authoritative DB must remain byte-identical at:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

for any local proof that can see it.

## 5. Acceptance gate

Implementation may close PASS only if:

- the exact ID maps to `CONSUMED_CHILD_EXITED_NONZERO`;
- lookalike/default behavior is unchanged;
- historical trust still comes solely from explicit `prior_authorizations_non_reusable`;
- `...5fcb1bf5` remains permanently consumed/non-reusable;
- migration-062 current provenance remains unchanged;
- no DB/runtime/provider/campaign effect occurs;
- focused tests pass.

## 6. Sequencing

The exact next permitted lane is:

`AUG-28 CONSUMED AUTHORIZATION HISTORICAL-DISPOSITION ADOPTION IMPLEMENTATION / BOUNDED PROOF`

**Implementation requires explicit operator approval.**

Only after that implementation and closeout PASS may Printer return to:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

That later lane still does not authorize consumption or campaign execution.

Permanent V1 locks remain unchanged.
