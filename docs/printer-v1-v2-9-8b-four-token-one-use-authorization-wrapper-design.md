# Printer V1 V2-9.8B Four-Token One-Use Authorization Wrapper Design

Date: 2026-08-13

## Verdict

`V2_9_8B_FOUR_TOKEN_ONE_USE_AUTHORIZATION_WRAPPER_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

This is a design/specification lane only. It creates no authorization, starts no Printer process, performs no source call, mutates no database, and does not run the four-token proof.

## Authority and baseline

Use the active Printer V1 source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

Python implementation also follows `docs/printer-v1-python-builder-guide.md`.

Design baseline:

- Git HEAD: `b351fcee40c5e56267f32a08fe68f3e2c9337e75`
- readiness verdict: `V2_9_8B_POST_MIGRATION_FOUR_TOKEN_PROOF_READINESS_PASS_READY_FOR_AUTHORIZATION_WRAPPER_DESIGN`
- authoritative DB migration count: 55
- authoritative migration head: `055_pre_admission_discovery_attempt_ownership.sql`
- post-migration DB SHA-256: `63a534fca4c6f693c4d4ffa92709ea8c84428b39d0a01ff1a4ca4ab68a47f003`

The existing standard-four-hour one-shot wrapper remains public two-token authority and must not be widened into four-token authority.

## Design decision 1 - dedicated proof-only authority

Add a distinct proof-only authorization surface rather than parameterizing the standard two-token wrapper.

Canonical command mode:

`four-token-bounded-capacity-proof-run`

Recommended implementation identities:

- wrapper module: `src/printer_v1/operator_cli/four_token_proof_one_shot_wrapper.py`
- authorization profile: `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE`
- authorization package root: `operator-runs/v2-9-8b-four-token-final-authorization`
- authorization package kind: `FOUR_TOKEN_PROOF_AUTHORIZATION_EVIDENCE`
- final authorization schema: `PRINTER_V1_FOUR_TOKEN_PROOF_FINAL_AUTHORIZATION_V1`
- manifest schema: `PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_PROOF_V1`
- wrapper schema: `PRINTER_V1_FOUR_TOKEN_PROOF_ONE_SHOT_WRAPPER_V1`
- external application root: `~/PrinterOperations/v2-9-8/four-token-proof-one-shot-applications`

The standard `standard-four-hour-run` mode, its schema, package root, validation, and `token_capacity == 2` contract stay unchanged.

## Design decision 2 - exact proof policy is authorization data, not a widened public setting

The fresh authorization must bind all of these exact values:

- configured through-4h tokens: 4
- configured active cycles: 2
- total cycle admission ceiling: 2
- tokens per cycle: 2
- minimum cycle admission spacing: 300 seconds
- standard four-hour campaign: true
- root main window: `WINDOW_15M`
- pre-lifecycle acquisition duration: 900 seconds
- post-supply/proof duration: 18,000 seconds
- locked long windows: `WINDOW_12H`, `WINDOW_24H`
- automatic retries: 0
- endpoint rotation: false

Capacity values must be validated by calling `scaled_standard_four_hour_capacity_contract(4)`, not by creating a second numeric authority. The currently derived result is:

- shared discovery requests: 4
- lifecycle request outer ceiling: 472
- lifecycle requests per token: 117
- lifecycle Scheduler outer ceiling: 420

The wrapper must reject 6/3, any third cycle, any single-token fresh admission, and any spacing below 300 seconds.

The two bounded clocks remain separate. The wrapper may derive a maximum one-shot wall envelope of 18,900 seconds for supervision/diagnostics, but 18,900 must not replace or obscure the separate 900-second acquisition and 18,000-second proof contracts.

## Design decision 3 - exact current Git and database binding before consumption

The authorization document must carry the same exact repository and authoritative-database identity model used by the hardened one-shot path:

- branch
- exact commit HEAD
- DB canonical path
- SHA-256
- size
- inode
- mtime_ns
- migration count
- migration head

Before an application marker is created, the wrapper must rerun the existing read-only migration-ledger guard and require exact agreement with the authorization binding.

For the first future authorization, the database must therefore be the post-055 authoritative state, not the pre-migration hash. Any DB identity, migration, sidecar, integrity, FK, or Git drift blocks before authorization consumption.

The final operational child preflight remains an additional defence and is not replaced by wrapper checks.

## Design decision 4 - migration-055 evidence is narrowly bound

The controlled migration created current evidence under:

`operator-runs/v2-9-8b-migration-055-application/MIGRATION_055_20260813T220109Z`

The future four-token manifest must bind the exact migration-055 application package by bounded root, execution identity, file paths, sizes, and SHA-256 values.

Do not broaden trust to `operator-runs/` and do not treat arbitrary files under that tree as authorized.

Implementation may minimally extend `GitAuthorizationProfile` so a profile can declare exact additional current evidence package roots/kinds. Existing ordinary and standard-four-hour profiles must retain identical behavior through defaults. If a narrower four-token-only manifest adapter can reuse the generic validator without changing old profile semantics, prefer that.

The historical migration-050 evidence contract must not be misrepresented as the schema transition that produced the current 055 database.

## Design decision 5 - historical authorization visibility does not create reuse authority

The four-token profile must explicitly recognize historical authorization evidence needed for a clean provenance inventory, including prior WINDOW_15M and standard-four-hour authorization roots.

Every historical authorization ID accepted as visible evidence must still be declared through the exact `prior_authorizations_non_reusable` trust root. Directory presence alone never creates trust.

No previous authorization may authorize this proof. The new authorization ID may be consumed once only.

## Design decision 6 - preserve hardened one-shot consumption law

Reuse the existing hardened filesystem/interpreter primitives and one-shot sequence:

1. resolve and hash the final authorization inside its exact package;
2. validate temporal, repository, policy, DB, migration-ledger, source-configuration, and zero-state prerequisites before consumption;
3. construct and validate the exact Git-provenance manifest;
4. publish the immutable manifest outside the repository application root;
5. create one immutable application marker;
6. launch at most one child process;
7. require one exact child-terminal envelope;
8. write one wrapper terminal record.

Once the marker exists, the authorization is consumed even if the child later fails.

All of these remain false:

- automatic retry
- manual rerun
- resume
- restart
- successor

No wrapper path may silently create another authorization or another child.

## Design decision 7 - pre-consumption zero-state gate

Immediately before marker creation, the wrapper must fail closed unless the authoritative state is quiescent for this proof start. Minimum required checks:

- exact authorized tracked HEAD and clean tracked tree;
- no unauthorized untracked/ignored repository evidence;
- no Printer process;
- no authoritative SQLite sidecars;
- migration ledger exact at 55 / `055_pre_admission_discovery_attempt_ownership.sql`;
- integrity `ok` and zero FK violations;
- zero active campaigns;
- zero active campaign runs/cycles;
- zero active campaign Scheduler work;
- zero campaign/proof supervision;
- zero active discovery work;
- zero active factory runs/steps;
- zero pre-admission discovery attempts;
- zero active Scheduler jobs;
- source configuration valid;
- exact 4/2/2 proof policy valid;
- scaled capacity contract valid;
- 12h/24h still locked.

The check is read-only. It creates no campaign, reservation, lease, discovery attempt, Scheduler job, or source request.

## Design decision 8 - child composition activates only the accepted internal controller

`operational_memory_factory_command.py` may gain the new proof-only CLI mode, but the mode must not become a generic capacity argument.

The proof-mode composition must construct the already accepted internal four-token owners, including:

- `FourTokenProofController.exact()` / exact 4/2/2 policy;
- authoritative admission-health projection;
- authoritative later-cycle discovery callback;
- atomic pre-admission attempt consumption/materialization;
- same-factory second-cycle opening planner;
- cycle-aware Scheduler ownership;
- cycle-local continuation/accounting;
- multi-cycle terminal owner.

It then calls the existing canonical operational factory path once.

It must not create:

- a second factory runner;
- a second event loop;
- a discovery polling loop;
- a Scheduler bypass;
- a Source Governor bypass;
- a new public capacity selector.

When this mode is absent, existing public two-token behavior remains identical.

## Design decision 9 - terminal evidence stays bounded and deterministic

The wrapper terminal and child terminal must preserve exact authorization/manifest/marker/Git identities and one-attempt facts.

The child proof report remains responsible for runtime truth: one campaign, one run, one factory, two cycles, four distinct targets, cycle-local accounting, aggregate budget/safety, cleanup, and honest terminal cause.

The wrapper must not convert a blocked/dirty/incomplete child result into proof PASS. Its job is authorization consumption and process/terminal integrity only.

## TDD implementation order

Use focused RED -> GREEN seams and stop on any architecture mismatch:

1. Four-token authorization profile/schema rejects ordinary/standard-four-hour documents and accepts exact 4/2/2 fixture authority.
2. Exact scaled-capacity/timing validation rejects 6/3, widened spacing/timing, copied wrong ceilings, retries, rotation, or long-window activation.
3. Migration-055 package inventory is accepted only by exact root/hash/size; unrelated `operator-runs/` evidence remains rejected.
4. Current DB/migration binding and zero-state pre-consumption gate fail closed on drift/residue.
5. Dedicated one-shot wrapper consumes once and launches only the dedicated proof child mode.
6. Proof child mode constructs the exact internal four-token composition and calls the same canonical factory once.
7. Integrated disposable wrapper proof verifies marker/terminal/non-reuse semantics without live sources or authoritative DB mutation.
8. Regression locks prove ordinary WINDOW_15M and standard-four-hour wrappers remain unchanged.

Use the minimum sufficient focused tests per seam. Run broader wrapper/provenance/factory lock tests only at implementation closeout.

## Implementation boundaries

Allowed after this design closes:

- focused tests and production code needed for the dedicated four-token authorization profile/wrapper and proof-only CLI composition;
- disposable DB/filesystem fixtures;
- read-only checks of the authoritative DB;
- documentation closeout.

Not allowed during implementation:

- creating a real four-token authorization;
- live source fetching;
- authoritative runtime or DB mutation;
- starting the proof;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

## Acceptance gate before authorization preparation

Implementation closeout must prove:

- existing standard two-token wrapper behavior unchanged;
- dedicated four-token authority only;
- exact 4/2/2 and >=300-second spacing;
- two separate bounded clocks 900 / 18,000;
- capacity derived from `scaled_standard_four_hour_capacity_contract(4)`;
- exact post-055 DB/migration binding;
- migration-055 current evidence narrowly bound;
- historical authorizations non-reusable;
- one marker -> at most one child;
- exact controller composition -> one canonical factory run;
- no second runner/loop;
- no retry/restart/resume/successor;
- no 12h/24h or financial/retrieval unlock;
- focused/integrated tests PASS.

After implementation closeout, a separate independent review is required before any real authorization is prepared.

## Money-usefulness contribution

This authority layer allows the smallest approved concurrency increase to be exercised without weakening the existing two-token production boundary. It protects the value of the proof by making the observed four-token corpus growth attributable to one exact code/database/configuration state rather than an ambiguous or reusable launch path.

## What this lane improves

- defines the missing one-use authority around the accepted four-token integration;
- preserves the public two-token wrapper unchanged;
- binds the proof to the post-migration-055 authoritative state;
- makes migration-055 evidence explicit without broadening repository trust;
- preserves exact one-attempt/non-reuse semantics;
- gives implementation a bounded TDD sequence.

## What this lane still does not unlock

- creation of a real proof authorization;
- four-token runtime;
- six-token runtime;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet/private keys/real funds/live execution;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Required mitigation | Stop condition |
|---|---|---|
| Standard wrapper widened to four tokens | Dedicated profile/mode/wrapper | Existing two-token contract changes |
| Four-token mode becomes generic capacity switch | Hard-code exact proof profile; reject 6/3 | Caller can select arbitrary capacity |
| Stale/pre-055 DB authorized | Exact DB binding + migration guard before marker | Any DB/migration drift |
| Migration-055 untracked evidence bypassed | Bind exact package inventory | Broad `operator-runs/` trust required |
| Historical authorization becomes reusable | Explicit non-reusable ID trust root | Old package can launch child |
| Authorization consumed before free checks | Run all possible read-only gates before marker | Known blocker discovered only after marker |
| Separate clocks collapsed incorrectly | Bind 900 and 18,000 separately | One ambiguous duration replaces them |
| Numeric budget authority duplicated | Derive from canonical scaled contract | Independent four-token constants diverge |
| Wrapper starts second runner/loop | Inject accepted controller into canonical factory | >1 factory runner/event loop |
| Wrapper hides child failure | Preserve child terminal truth | Wrapper reports PASS over blocked child |

## Closeout and next permitted lane

This design is ready for focused TDD implementation.

Next permitted lane:

`FOUR_TOKEN_ONE_USE_AUTHORIZATION_WRAPPER_IMPLEMENTATION`

Stop before creating any real authorization or running Printer. After implementation/proof closeout, perform an independent authorization-wrapper review before authorization preparation.
