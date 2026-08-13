# Printer V1 V2-9.8B Four-Token One-Use Authorization Wrapper Implementation Closeout

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_ONE_USE_AUTHORIZATION_WRAPPER_IMPLEMENTATION_PASS_READY_FOR_INDEPENDENT_REVIEW`

This is an implementation closeout only. It created no authorization, started no
Printer process, performed no live source or RPC call, mutated no authoritative
database, applied no migration, and did not run the four-token proof.

## Authority and baseline

Implemented exactly from the committed design
`docs/printer-v1-v2-9-8b-four-token-one-use-authorization-wrapper-design.md`,
inside the active Printer V1 source stack (`AGENTS.md`, clean master spec,
post-RC build order, memory factory guide, current-state memory-growth audit,
memory-growth build order v2) and `docs/printer-v1-python-builder-guide.md`.

- Implementation baseline: `0b1454667067c42bdf3244388c1bf04eec90a351`
- Local branch synchronized to the remote baseline by fast-forward only
  (`7683b88..0b14546`). No reset, no clean, no discarded work.
- The local migration-055 operator artifact
  `operator-runs/v2-9-8b-migration-055-application/MIGRATION_055_20260813T220109Z`
  and the historical standard-four-hour authorization artifacts were preserved
  untouched and remain untracked.

## RED/GREEN sequence

Each seam ran focused RED, confirmed the expected failure, committed RED, then
made the smallest production change and committed GREEN.

| Seam | RED | GREEN |
|---|---|---|
| 1. Dedicated proof profile/schema | `2eb8d55` | `67a144c` |
| 2. Exact 4/2/2 capacity and timing | `748cb80` | `d00970e` |
| 3. Exact migration-055 evidence binding | `4c9d328` | `fae791e` |
| 4. Read-only pre-consumption zero-state gate | `254a56f` | `5967f53` |
| 5. One-use wrapper and exact one-child law | `8bdad44` | `7be320b` |
| 6. Proof-only CLI mode composition | `1c74a57` | `0f24773` |
| 7. Integrated disposable wrapper proof | — | `95df861` (lock) |
| 8. Existing-wrapper regression locks | — | `b402493` (lock) |

Seams 7 and 8 are recorded honestly as locks rather than as REDs that drove new
code: the lane was implemented additively, so both passed at the HEAD produced by
seams 1–6. Nothing was weakened to make them pass.

## What was implemented

### Dedicated proof-only authority

- `src/printer_v1/operator_cli/four_token_proof_one_shot_wrapper.py`
- `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` in
  `git_provenance_authorization_manifest.py`
- authorization package root `operator-runs/v2-9-8b-four-token-final-authorization`
- package kind `FOUR_TOKEN_PROOF_AUTHORIZATION_EVIDENCE`
- final authorization schema `PRINTER_V1_FOUR_TOKEN_PROOF_FINAL_AUTHORIZATION_V1`
- manifest schema `PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_PROOF_V1`
- wrapper schema `PRINTER_V1_FOUR_TOKEN_PROOF_ONE_SHOT_WRAPPER_V1`
- child terminal schema `PRINTER_V1_FOUR_TOKEN_PROOF_CHILD_TERMINAL_V1`
- application root `~/PrinterOperations/v2-9-8/four-token-proof-one-shot-applications`
- command mode `four-token-bounded-capacity-proof-run`

### Exact policy as authorization data

`exact_proof_policy()` is the single bound policy and is compared for exact
type/value equality during document validation. Capacity comes only from
`scaled_standard_four_hour_capacity_contract(4)`:

- through-4h tokens 4, active cycles 2, total cycle admissions 2, tokens per cycle 2
- minimum admission spacing 300 seconds
- shared discovery requests 4
- lifecycle request outer ceiling 472
- lifecycle requests per token 117
- lifecycle Scheduler outer ceiling 420
- automatic retries 0, endpoint rotation false, long windows not activated
- locked windows `WINDOW_12H`, `WINDOW_24H`

The two bounded clocks stay separate: 900-second pre-lifecycle acquisition and
18,000-second post-supply proof. `MAX_ONE_SHOT_WALL_ENVELOPE_SECONDS` is 18,900
and is supervision/diagnostic only; the validator rejects any attempt to put
18,900 in place of either contract.

6/3, a third cycle admission, single-token cycles, sub-300-second spacing,
widened or collapsed clocks, copied two-token ceilings, retries, rotation, and
long-window activation are all rejected.

### Narrowly bound migration-055 evidence

`GitAuthorizationProfile` gained `migration_package_root` and
`migration_package_kind`, defaulting to the migration-050 identities so the
ordinary and standard-four-hour profiles keep byte-identical behavior. The
four-token profile declares
`operator-runs/v2-9-8b-migration-055-application` / `MIGRATION_055_EVIDENCE`.
Trust was not broadened to `operator-runs/`: unrelated evidence under that tree
still fails reconciliation, and the migration-050 root cannot supply four-token
current evidence.

### Read-only pre-consumption gate

`src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` re-runs the
existing migration-ledger guard against the authorization's database binding and
independently proves migration count 55, head
`055_pre_admission_discovery_attempt_ownership.sql`, integrity `ok`, zero
foreign-key violations, no sidecars, no Printer process, valid source
configuration, exact 4/2/2 policy, still-locked 12h/24h, and zero residue across
every required domain: active campaigns, campaign runs, campaign cycles, campaign
Scheduler work, campaign supervision, proof supervision, discovery work, factory
runs, factory steps, pre-admission discovery attempts, and Scheduler jobs.

The database is opened immutable, so the gate cannot write or create a sidecar.
The gate runs while the authorization is still unconsumed; a blocked gate leaves
no marker.

### One-use consumption and one-child law

`apply_authorization_once` reuses the hardened primitives and the same eight-step
sequence: resolve/hash the authorization inside its exact package, validate
temporal/repository/policy/DB/ledger/source/zero-state prerequisites, build and
validate the manifest, publish it outside the repository, create one immutable
marker, launch at most one child, require one exact child-terminal envelope, and
write one wrapper terminal record. Once the marker exists the authorization is
consumed even if the child later fails. Retry, rerun, resume, restart, and
successor remain false and are recorded as zero in the terminal.

### Proof-only child composition

`run_four_token_bounded_capacity_proof_campaign` constructs
`FourTokenProofController.exact()` and calls the existing canonical
`_run_operational_campaign` path once with `FOUR_TOKEN_PROOF_POLICY`. It creates
no second factory runner, no second event loop, no discovery polling loop, and no
Scheduler or Source Governor bypass. The mode is wrapper-bound and carries no
capacity argument; `TOKEN_CAPACITY` remains 2 and the three existing public
runners still have no proof-controller parameter.

## Verification

Focused per-seam tests plus the closeout regression set were run with the
repository virtual environment.

Four-token lane (7 files):

```
45 passed, 4 subtests passed
```

Minimum integrated wrapper/provenance/factory regression set (9 files):

```
101 passed, 11 subtests passed
```

Files: standard-four-hour activation authorization, standard-four-hour
operational activation, WINDOW_15M one-shot wrapper, four-token canonical factory
wiring, four-token proof controller, four-token Gate H integrated disposable,
four-token factory terminal integration, four-token factory wake ordering, and
second standard-four-hour public budget authority repair.

`py_compile` passed for every touched production and test module.
`git diff --check` is clean. The tracked worktree is clean; only the two
protected operator-runs artifact directories remain untracked.

### Pre-existing failures, not caused by this lane

Two test files fail identically at the baseline commit `0b14546` and at this
HEAD, verified by running them in a detached worktree at the baseline:

- `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py` —
  31 failed, 17 passed at both revisions.
- `tests/test_v2_9_8b_pre_authorization_migration_ledger_drift_guard.py` —
  21 failed, 50 passed at both revisions.

They are reported here rather than repaired, because repairing them is outside
this lane's authority.

## Acceptance gate

- existing standard two-token wrapper behavior unchanged — locked by seam 8
- dedicated four-token authority only — separate profile, schema, mode, package
  root, application namespace, child terminal schema
- exact 4/2/2 and >= 300-second spacing — locked by seam 2
- two separate bounded clocks 900 / 18,000 — locked by seam 2
- capacity derived from `scaled_standard_four_hour_capacity_contract(4)` — locked
  by seams 2 and 6
- exact post-055 DB/migration binding — locked by seam 4
- migration-055 current evidence narrowly bound — locked by seam 3
- historical authorizations non-reusable — locked by seam 7
- one marker -> at most one child — locked by seams 5 and 7
- exact controller composition -> one canonical factory run — locked by seam 6
- no second runner/loop — locked by seam 6
- no retry/restart/resume/successor — locked by seams 5 and 7
- no 12h/24h, retrieval, decision, or financial unlock — locked by seams 2 and 4
- focused/integrated tests PASS

## What this lane still does not unlock

- creation of a real four-token proof authorization
- four-token runtime or six-token runtime
- 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD
- paper positions, trade events, paper trade audits, PnL
- live wallet, private keys, real funds, live execution, paid APIs
- scoring/ranking/confidence/weighted logic, embeddings/vectors

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Stop boundary and next lane

Stop here for independent review. No authorization may be prepared or created
until an independent authorization-wrapper review passes.
