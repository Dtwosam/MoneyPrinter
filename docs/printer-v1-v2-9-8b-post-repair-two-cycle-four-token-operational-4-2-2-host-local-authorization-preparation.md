# Printer V1 V2-9.8B Post-Repair Two-Cycle Four-Token Operational 4/2/2 Host-Local Authorization Preparation

Date: 2026-08-18

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_4_2_2_HOST_LOCAL_AUTHORIZATION_PREPARATION_PASS`

## 1. Scope

Prepare exactly one fresh one-use operational authorization for
`four-token-standard-four-hour-run`: one bounded invocation, Cycle 1 two fresh
governed tokens, Cycle 2 two NEW fresh governed tokens, four through-4h token
slots total, each `WINDOW_15M -> eligible WINDOW_1H -> eligible WINDOW_4H`.

Preparation only. The authorization is left UNCONSUMED. No application marker
was created, no Printer runtime started, no provider/RPC/WebSocket call made, no
campaign state mutated, no product code modified and no Migration 059 added.

Reviewed implementation commit: `25daf4fd993fbea4142b16d02820b577fba6e300`

Independent closeout commit: `799cb896955ebe9525d9057f1df408c189244d26`

The local checkout is authoritative for this preparation; the remote branch is
stale and was not consulted as a source of truth.

## 2. Operator decision recorded: abandoned two-token authorization

Preparation was initially blocked. The four-token operational profile requires
the Migration 055/056/057/058 evidence packages to exist under the repository
`operator-runs/` namespace, but they had been isolated into
`~/PrinterOperations/host-isolated-later-lane-working-tree-20260818T183446Z/`
by the earlier Standard-4H preparation lane, whose authorization ID carries the
same `20260818T183446Z` stamp.

Both required enumerations failed closed against the repository:

- `declared historical migration package root is missing: operator-runs/v2-9-8b-migration-055-application`
- `evidence package is unavailable: operator-runs/v2-9-8b-migration-058-application/MIGRATION_058_20260818T082552Z`

Restoring that evidence necessarily invalidates the still-valid two-token
authorization, because the Standard-4H profile declares no historical migration
packages and therefore cannot cover those paths.

The operator decided to proceed and to abandon the two-token authorization.

### 2.1 Abandoned authorization — exact preserved record

- authorization ID: `V2_9_8B_STANDARD_4H_AUTH_20260818T183446Z`
- path: `operator-runs/v2-9-8b-standard-four-hour-final-authorization/V2_9_8B_STANDARD_4H_AUTH_20260818T183446Z/final_authorization.json`
- SHA-256: `a56235b74d7aac7fb75466dc0529307683557725745eae4153bc1128613db645`
- size: `2899` bytes
- authorized mode: `standard-four-hour-run`
- temporal state at abandonment: `VALID` until `2026-08-19T06:34:46.107560+00:00`
- application marker: `ABSENT`
- application namespace directory: absent
- invocation count: `0`

Classification:

`UNCONSUMED_OPERATOR_ABANDONED_WRONG_SCOPE_AUTHORIZATION`

It was not deleted, its bytes were not modified, no consumption marker was
created for it, and it was not falsely classified as consumed or expired. Its
document SHA-256 was re-verified as byte-identical after restoration.

### 2.2 Abandonment demonstrated, not asserted

After restoration the abandoned authorization fails its non-consuming pre-marker
provenance validation on two independent grounds:

1. `manifest repository identity does not match live Git state` — its bound HEAD
   predates the implementation lane.
2. The restored evidence adds 19 visible-untracked and 9 ignored files under
   `operator-runs/` that its manifest allowlist cannot cover, because its profile
   declares no historical migration packages. These would raise
   `unexpected untracked repository file not covered by manifest`.

This is expected and must not be "fixed". The authorization is permanently a
non-candidate for launch after the evidence namespace change.

## 3. Evidence restoration

Only the four exact required packages were restored from the preserved vault
into their canonical `operator-runs/` locations. Nothing else from the 761 MB
vault was copied; in particular `v2-9-8b-four-token-final-authorization` was
deliberately not restored.

Each root was verified to contain exactly one package directory and no symlinks
or non-regular files.

Verification against the committed immutable declarations:

| Package | Execution ID | Files | Inventory SHA-256 | Result |
| --- | --- | --- | --- | --- |
| 050 | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` | 12 | `2bcbfdd3e9…95f8d5` | MATCH |
| 055 | `MIGRATION_055_20260813T220109Z` | 5 | `c004437332…d9e625` | MATCH |
| 056 | `MIGRATION_056_20260815T164802Z` | 6 | `4918774b95…5868f3` | MATCH |
| 057 | `MIGRATION_057_20260816T191558Z` | 6 | `9272f596e7…519535` | MATCH |

Migration 057 matches the explicitly required identity exactly: execution
`MIGRATION_057_20260816T191558Z`, 6 files, inventory
`9272f596e7a82c3cfe9d824595be74f34c7203dccab3bd541c187dc236519535`.

Current schema-transition evidence is Migration 058, execution
`MIGRATION_058_20260818T082552Z`, resolved from the real preserved host evidence
and never invented. Its package binds 11 files.

## 4. Readiness checks

All checks were run before anything was created, and all passed.

- **Launch checkout**: the actual local checkout was bound. Tracked index and
  worktree are clean; the only untracked paths are the bound evidence namespaces.
- **Capacity**: re-derived live from
  `scaled_standard_four_hour_capacity_contract(4)` and compared against the
  runtime controller policy from `build_four_token_proof_policy()`.

| Value | Authorization side | Runtime side | Agreement |
| --- | --- | --- | --- |
| through-4h token slots | 4 | 4 | exact |
| active cycles | 2 | 2 | exact |
| tokens per cycle | 2 | — | exact vs canonical |
| total cycle admission ceiling | 2 | 2 | exact |
| lifecycle requests per token | 117 | — | exact vs canonical |
| lifecycle request outer ceiling | 472 | — | exact vs canonical |
| lifecycle Scheduler outer ceiling | 420 | — | exact vs canonical |
| minimum admission spacing | 300s | 300s | exact |
| automatic retries | 0 | — | exact |
| endpoint rotation | false | — | exact |
| long windows activated | false | — | exact |

  The residual risk flagged by the independent closeout is therefore resolved for
  this exact checkout: authorization and runtime capacity agree exactly.

- **Authoritative database**: inspected fresh through both the canonical
  inspector and an independent raw read-only re-read. Migration count 58, head
  `058_direct_pump_migration_cursor.sql`, `integrity_check = ok`, 0 foreign-key
  violations, no 059 ledger row, no SQLite sidecars, 58 migration files on disk.
- **Zero-state gate**: the operational gate passed against the live host with a
  real process probe. Zero live Printer runtime processes and all twelve durable
  ownership domains at zero.
- **Marker absence**: the operational application namespace
  `~/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications`
  did not exist, so no pre-existing marker could apply to the new identity.
- **Historical non-reuse**: 33 distinct prior authorization IDs were enumerated
  across the window-15m and Standard-4H roots. The four-token operational
  authorization root did not exist, so the new identity is necessarily fresh.
  Every prior ID is declared non-reusable in the new document.
- **Authority separation**: `standard-four-hour-run` remains two-token
  operational, `four-token-bounded-capacity-proof-run` remains proof-only, and
  `four-token-standard-four-hour-run` is the operational 4/2/2 authority. No
  proof or two-token authorization can authorize the new child.

## 5. Launch HEAD binding

The provenance validator rejects a detached checkout and requires the manifest
branch and HEAD to equal live Git state. The bound HEAD must therefore be the
final branch tip, not an earlier commit.

This document and the handoff are committed **before** the authorization is
created, so that the resulting commit is the exact launch HEAD the authorization
binds. No further commit is made on this branch afterwards.

Because of that ordering, the authorization's own identity, SHA-256 and validity
window are recorded in the untracked authorization package itself
(`preparation-evidence.json`) and in the lane response, rather than in this
tracked document. The independent review must re-derive them from the package
rather than trusting any summary, exactly as the previous independent review did.

Authorization package root:

`operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization`

## 6. What was NOT done

No authorization consumed. No application marker. No child process. No Printer
launch. No provider, RPC or WebSocket call. No campaign state mutation. No
authoritative database mutation. No retry, rerun, resume, restart or successor.
No product code change. No Migration 059.

## 7. Exact next permitted action

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational 4/2/2 Fresh Authorization Independent Review`

An independent review of this exact fresh authorization must PASS before any
manual Terminal launch. Preparation does not authorize execution.
