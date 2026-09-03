# Printer V1 — Next Bounded 4/2/2 Standard-4H Authorization Boundary / Package Design

Date: 2026-09-03

Lane: **DESIGN / SPECIFICATION ONLY — NO AUTHORIZATION CREATION**

Verdict:

`V2_9_8B_NEXT_BOUNDED_4_2_2_STANDARD_4H_AUTHORIZATION_BOUNDARY_PACKAGE_DESIGN_PASS`

Implementation-boundary classification:

`EXISTING_OWNER_ALREADY_SUFFICIENT`

No production-code change is required. No authorization package, ID, hash,
marker, or consumption action is created by this document.

## 1. Purpose and non-authority

Specify the exact future one-shot authorization package for **one** bounded
Printer V1 Standard-4H paper campaign under the already-approved 4/2/2
operational envelope.

This document creates no authority. It does not prepare, hash, apply, consume,
or execute an authorization. It does not run Printer, contact providers, run
Central Scheduler, or mutate the authoritative DB.

The 2026-08-31 boundary design remains historically
`EXISTING_OWNER_ALREADY_SUFFICIENT`. This document is the current package
contract for the post-reconciliation HEAD/DB identity. It does not invent a
second wrapper, profile, validator, or policy owner.

Preserved sequence:

```text
readiness PASS
-> this authorization-boundary design/specification
-> authorization preparation only if separately approved
-> frozen/hash-bound package
-> independent package review
-> separate explicit operator application/execution approval
-> bounded campaign
-> campaign closeout
```

## 2. Design baseline

| Item | Value |
| --- | --- |
| Branch | `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` |
| Design baseline HEAD | `f465e34f702fb80175740a2df3e686d50d914a88` |
| Reviewed production lineage | `6f8a1b6ac7f00fda1f7dca38c7532473b03f1ada` |
| Authoritative DB path | `data/printer_v1.sqlite3` |
| Expected DB SHA-256 | `fb52d8fae2d22c70f6c2c7de7ddf4a18c7d89f01450f12e6c60093ee85e17cff` |
| Readiness verdict | `V2_9_8B_POST_RECONCILIATION_FRESH_EXACT_HEAD_EXACT_DB_NEXT_BOUNDED_CAMPAIGN_READINESS_GOVERNANCE_PASS` |

`f465e34f...` is the **design baseline**, not the future package binding.
Committing this design changes HEAD. The later preparation lane must bind the
**actual final committed design HEAD** via live `git rev-parse HEAD`. Never
invent that future SHA. Never copy `f465e34f...` into a package merely because
it was the design baseline.

If the DB SHA changes before preparation, fail closed and require a fresh
readiness audit. Do not rebind an old package to a new SHA.

Consumed `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` remains
`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`.

## 3. Implementation-boundary classification

`EXISTING_OWNER_ALREADY_SUFFICIENT`

Current committed owners already implement the approved 4/2/2 Standard-4H
one-shot envelope:

| Role | Owner |
| --- | --- |
| Document schema / fixture shape | `four_token_standard_four_hour_one_shot_wrapper.fixture_authorization_document` (fixture only; creates no authority) |
| Document validator | `validate_four_token_standard_four_hour_authorization_document` |
| One-shot application/consumption | `apply_authorization_once` in the same module |
| Operational policy | `exact_operational_policy()` in `four_token_operational_composition.py` |
| Git profile | `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE` |
| Prior non-reuse | `validate_prior_authorizations_non_reusable` / `extract_approved_historical_authorization_ids` |
| Pre-consumption zero-state | `assert_four_token_standard_four_hour_zero_state` |
| Live Git identity | `validate_git_provenance_manifest_pre_marker` |
| DB binding honesty | `assert_migration_ledger_ready(mode="review")` via the zero-state gate |
| Temporal validity | `validate_authorization_temporal_validity` |
| Child command | `build_child_command` → `operational_memory_factory_command` / `four-token-standard-four-hour-run --operator-approved` |

Do not redesign these owners. Do not add a second wrapper, Scheduler, or
Governor. `fixture_authorization_document` is not a preparation owner.

## 4. Exact package schema and bindings

Schema version: `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`

Package path:

```text
operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/{authorization_id}/final_authorization.json
```

Application namespace (outside the repository):

```text
~/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/
```

The object must contain **exactly** these top-level keys:

- `schema_version`
- `authorization_id` (fresh safe identifier; never a consumed ID)
- `migration_execution_id` = `MIGRATION_062_20260828T182504Z`
- `verdict` (PASS-ending string accepted by the validator)
- `authorized_at` / `expires_at` / `validity_seconds` (existing temporal owner)
- `repository` = `{branch, head}`
- `authorized_command` = `{mode: four-token-standard-four-hour-run, operator_approved: true}`
- `one_shot_policy`
- `operational_policy` = exact `exact_operational_policy()` equality
- `authoritative_database` = `{path, sha256, size, inode, mtime_ns, migration_count, migration_head}`
- `prior_authorizations_non_reusable`

`authorized_command.operator_approved: true` is a schema field only. It does
not consume the package. Consumption requires a later separate
`apply_authorization_once(..., operator_approved=True)` after independent
package review and explicit execution approval.

### Repository identity (preparation-time)

Bind live:

- `git rev-parse HEAD` (the design-closeout HEAD, not `f465e34f...` after that
  commit exists);
- branch `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` if still the
  live branch;
- clean tracked worktree/index (known untracked `operator-runs/...` only).

Application re-checks live Git via `validate_git_provenance_manifest_pre_marker`.
Stale HEAD fails closed.

### Authoritative DB identity (preparation-time)

Bind live `inspect_authoritative_database` fields. Expected SHA-256 remains
`fb52d8fae2d22c70f6c2c7de7ddf4a18c7d89f01450f12e6c60093ee85e17cff` unless a
later lawful lane changes it. Also bind:

- path resolving to `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- migration count/head `62` / `062_pre_admission_attempt_evidence.sql`
- integrity `ok`, foreign keys `0`, no sidecars

Application re-derives those claims. SHA/size/inode/mtime_ns mismatch fails
closed. A rewritten file with the same bytes still fails inode/mtime honesty.

### One-shot policy (exact object)

```text
allowed_invocation_count = 1
automatic_retry_allowed = false
manual_rerun_allowed = false
resume_allowed = false
restart_allowed = false
successor_allowed = false
```

### Prior non-reuse trust root

Preparation must:

1. take `prior_authorizations_non_reusable` from consumed `59fdefe7` (58 IDs);
2. add `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7`;
3. union any additional IDs required by `AGENTS.md` / `CURRENT_HANDOFF.md`;
4. validate unique, lexicographically sorted, excluding the new current ID.

The complete future root is 59 IDs. Directory discovery must not broaden it.
Do not revive `59fdefe7`, `12a7ea61`, `ab6c68fe`, stale `b6d7ab46`, or any
older consumed ID.

Do not invent the future `authorization_id` in this design.

## 5. One-shot / non-reuse semantics

- Valid for one application only.
- Marker existence = consumed = permanently non-reusable.
- Child failure does not restore the authorization.
- No retry, rerun, resume, restart, successor, or automatic second campaign.
- No reuse of historical markers.
- No rebinding an old authorization to a new HEAD/DB.
- Editing a frozen reviewed package in place is prohibited; any change needs a
  new ID and a new preparation lane.

## 6. Application / consumption ordering

Canonical owner: `apply_authorization_once`.

Required order:

```text
fresh package exists and passed independent package review
-> separate explicit operator execution approval
-> apply_authorization_once(..., operator_approved=True)
   1. resolve package + SHA-256
   2. temporal validity
   3. refuse if application directory already exists
   4. official zero-state gate (still unconsumed)
   5. staging git-provenance manifest + pre-marker live HEAD/DB validation
   6. exclusive write of application-marker.json (consumption)
   7. full git-provenance validation of marker+manifest
   8. bind exact immutable paths/hashes into one child environment
   9. launch at most one child
```

Child command:

```text
python -m printer_v1.operator_cli.operational_memory_factory_command
  four-token-standard-four-hour-run --operator-approved
```

Forbidden:

```text
child start -> marker later
```

Once the marker exists the authorization is spent, even if the child never
starts or later exits nonzero.

## 7. Zero-state law

Preparation-time readiness is not enough.

`apply_authorization_once` must re-run
`assert_four_token_standard_four_hour_zero_state` **before** marker creation.

Require every official domain = 0, including
`active_pre_lifecycle_discovery_refresh_waits` counted as
`wait_state IN ('WAITING','CLAIMED')`.

Historical terminal rows are allowed. Any `WAITING` or `CLAIMED` wait blocks
application. The wrapper must not drain, abandon, or otherwise manufacture
zero-state. Existing `apply_authorization_once` does not do that cleanup; do
not add it.

## 8. 4/2/2 campaign profile

`operational_policy` must equal `exact_operational_policy()`:

| Field | Required |
| --- | --- |
| policy_version | `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1` |
| configured_through_4h_tokens | 4 |
| configured_active_cycles | 2 |
| tokens_per_cycle | 2 |
| total_cycle_admission_ceiling | 2 |
| standard_four_hour_campaign | true |
| root_main_window | `WINDOW_15M` |
| locked_windows | `WINDOW_12H`, `WINDOW_24H` |
| long_windows_activated | false |

Envelope:

```text
one campaign
one campaign-run
one authoritative factory
two overlapping cycles
two token slots per cycle
maximum four concurrent through-4h tokens
no third cycle
no fifth token
compiled 6/3 unused
WINDOW_15M -> hard-gated WINDOW_1H -> hard-gated WINDOW_4H -> stop
```

Where four tokens exist through the campaign, freeze/report remains existing
evidence-based selection:

```text
4 freeze-ready -> 2 selected + 2 report-only alternates
```

`MINIMUM_FREEZE_DEPTH = 4`. Sets must stay disjoint and stable. Authorization
must not add scoring/ranking/confidence/weighted selection.

Cycle-2 fresh slots remain campaign-history disjoint from earlier admitted
cycles.

## 9. Budgets and Cycle-2 timing

Must remain exact:

```text
lifecycle request outer ceiling = 476
per-token lifecycle ceiling = 118
Scheduler outer ceiling = 444
automatic retries = 0
endpoint rotation = false
pre_lifecycle_acquisition_duration_seconds = 2400
```

Refresh ordinals remain `DISCOVERY_REFRESH` interval 600s:

```text
+600 / +1200 / +1800
acquisition deadline +2400
```

Cycle-2 acquisition exhaustion must remain Cycle-2 / pre-lifecycle local. It
must not become factory `PROOF_DEADLINE` and must not terminate lawful Cycle-1
lifecycle work early. That is committed factory/wake law
(`next_four_token_factory_wake` prefers `LIFECYCLE_WORK` over equal-time
admission; lifecycle wins). The authorization package has no field that may
retune this.

## 10. Failure matrix

| Condition | Owner | Effect |
| --- | --- | --- |
| Stale HEAD vs live Git | `validate_git_provenance_manifest_pre_marker` | fail closed, unconsumed |
| Stale DB SHA / size / inode / mtime | zero-state + migration-ledger review | fail closed, unconsumed |
| Nonzero official zero-state, including `WAITING`/`CLAIMED` waits | `assert_four_token_standard_four_hour_zero_state` | fail closed, unconsumed |
| Migration count/head drift | schema-admission + ledger guard | fail closed, unconsumed |
| Missing/extra package field | document validator | fail closed |
| Package SHA-256 mismatch | `_resolve_authorization` | fail closed |
| Pre-existing application directory/marker | `apply_authorization_once` | fail closed |
| Already-consumed authorization ID reused | marker directory exists / non-reuse list | fail closed |
| Wrong command mode / profile | document validator + Git profile | fail closed |
| Policy/budget mismatch vs `exact_operational_policy()` | document validator + zero-state gate | fail closed |
| Temporal expiry / over-age | `validate_authorization_temporal_validity` | fail closed |
| `operator_approved` not true at apply | `apply_authorization_once` | fail closed |
| Child start without marker | forbidden by wrapper order | cannot occur |
| Child later fails | marker already written | authorization remains consumed |

The wrapper must not auto-repair any of these.

## 11. Later preparation proof (minimum, no Printer)

If separately approved, preparation must prove without running Printer:

- exact live HEAD and branch;
- clean tracked worktree/index;
- exact DB SHA (expected `fb52d8fa...` unless a later lawful identity exists);
- `inspect_authoritative_database` identity fields;
- schema/migration coherence PASS (`62` / `062_...`);
- integrity `ok`, FK 0, no sidecars;
- official zero-state all zeros;
- `exact_operational_policy()` 4/2/2, 476/118/444, retries 0, rotation false;
- `+600/+1200/+1800/+2400`;
- complete 59-ID prior-non-reuse root including `59fdefe7`;
- canonical JSON bytes frozen under the exact package path;
- deterministic SHA-256 of those bytes;
- `validate_four_token_standard_four_hour_authorization_document` PASS;
- no application marker / directory for the new ID;
- authorization remains unconsumed;
- zero provider/RPC/WebSocket calls;
- zero Printer execution.

No broad implementation regression suite is required unless a later lane
proves a production-code change. This design does not.

## 12. Independent package review

Package creation is not execution approval.

Review must inspect the actual frozen `final_authorization.json` bytes and
SHA-256, plus exact preparation-time HEAD/DB inside those bytes — not the
preparation agent's summary.

Review must confirm:

- schema/profile/mode/policy exactness;
- one-shot flags;
- 59-ID non-reuse root;
- no application marker;
- no `apply_authorization_once` call during review.

After review PASS, a **separate** explicit operator execution approval is
still required before application.

## 13. Permanent V1 locks

The package/policy must preserve:

- Solana-only; Solana memecoin-only; paper-trading only;
- no live wallet / private keys / signing / real funds / live execution;
- no paid API dependency;
- no scoring / ranking / confidence percentages / weighted decision logic;
- no embeddings / vectors;
- no Source Governor bypass; no Central Scheduler bypass;
- no dirty-memory retrieval or decisions;
- `WINDOW_5M_MICRO_EVENT` support-only;
- `WINDOW_12H` / `WINDOW_24H` locked;
- retrieval, BUY/SELL/HOLD, positions, trade events, paper audits, PnL locked.

Authorization may permit only the existing Source Governor, Central Scheduler,
and four-token factory. No second Scheduler/Governor. No authorization-layer
thread/process worker. No provider-limit increase. No hidden cycle-local
source-budget reset.

## 14. Confirmations

- no `final_authorization.json` created by this lane;
- no authorization ID invented;
- no package hash;
- no application marker;
- no DB mutation;
- no providers / RPC / WebSockets;
- no Printer run;
- no production-code change.

## 15. Exact next permitted action

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT 4/2/2 STANDARD-4H AUTHORIZATION PACKAGE PREPARATION
```

That later lane may create/freeze/hash **one** authorization package only after
separate operator approval. It may not apply or consume it. Do not begin that
lane from this design PASS.
