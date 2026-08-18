# Printer V1 V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Independent Closeout

Date: 2026-08-18

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_AUTHORIZATION_ALIGNMENT_INDEPENDENT_CLOSEOUT_PASS`

## 1. Scope and method

This is an independent review of the implementation lane. Every claim was
re-derived from the repository rather than accepted from the implementation
closeout. Where a claim could be tested adversarially, it was.

Reviewed implementation branch:

`agent/v2-9-8b-post-repair-two-cycle-four-token-operational-authorization-alignment-implementation`

Reviewed implementation commit:

`25daf4fd993fbea4142b16d02820b577fba6e300`

Approved design baseline:

`babc8a3b2dfd4ddca1307e140a378e0d3279e113`

This review modified no product code, no tests, created and consumed no
authorization, started no Printer runtime, made no provider/RPC/WebSocket call,
and did not mutate the authoritative database.

## 2. Branch, HEAD, ancestry and diff scope

- Local HEAD equals the expected implementation commit exactly.
- The approved design baseline and the repaired product-code baseline
  `df1aced4` are both ancestors of HEAD.
- Exactly one commit exists between the design baseline and HEAD.
- Working tree carries one untracked path, analysed in section 12.

Diff from the design baseline is exactly the approved scope: 6 product files
(2 new, 4 modified), 4 new test files, 5 updated test files, 2 documents.

Independently confirmed absent from the diff: any `migrations/` file, any
provider adapter, anything under `sources/`, and every Source Governor, Central
Scheduler, discovery, multi-cycle coordinator, factory-runner, later-cycle
supply or four-token adapter/controller/integration owner file.

## 3. Authority separation

Three authorities remain three distinct authorities:

| Authority | Mode | Policy version |
| --- | --- | --- |
| two-token Standard-4H | `standard-four-hour-run` | `V2-9.8-STANDARD-4H-OPERATIONAL-V1` |
| four-token proof | `four-token-bounded-capacity-proof-run` | `V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1` |
| four-token operational | `four-token-standard-four-hour-run` | `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1` |

All four Git authorization profiles are distinct in every identity field:
command mode, authorization package root, package kind and manifest schema. The
three wrapper authorities carry distinct authorization schemas and distinct
application namespaces. All child-terminal schemas are distinct.

### 3.1 Cross-authority reuse was attacked, not assumed

Fourteen adversarial attempts were executed against the document validators.
Every one was rejected:

- proof document into the operational validator — rejected;
- operational document into the proof validator — rejected;
- operational document into the two-token Standard-4H validator — rejected;
- two-token Standard-4H document into the operational validator — rejected;
- operational document with its mode swapped to `standard-four-hour-run`,
  `four-token-bounded-capacity-proof-run` and `run` — all rejected;
- operational document carrying the proof schema version — rejected;
- all six one-shot policy fields loosened individually (invocation count raised,
  retry / rerun / resume / restart / successor enabled) — all rejected.

No authorization of any other authority can authorize the operational 4/2/2
mode, in either direction.

### 3.2 Direct child invocation

The new mode is a member of `wrapper_bound_modes`. Three independent guards fire
before any campaign work: absent bindings, partial bindings (all-or-none), and
absent/invalid provenance authorization. The one-shot wrapper is therefore the
only operational application boundary. This was verified statically and by the
sandboxed focused test; the live command was deliberately not executed against
the authoritative database.

## 4. Proof-semantics leakage review

The neutral facade returns `FourTokenProofController.exact()`. The required
question is whether reusing it imports proof-only authorization, application,
terminal, retry or execution behaviour into production operation. It does not.

Evidence:

- `FourTokenProofController` carries exactly one field, `policy`, and two
  methods, `exact` and `evaluate_factory_wake`. It holds no authorization
  identity, no application/marker path, no retry counter and no execution
  authority. It is a read-side multi-cycle wake evaluator.
- The `four_token_proof_controller` parameter is orthogonal to database mode.
  `standard_four_hour_campaign=True` — which the operational policy sets — hard
  *requires* operational-persistent mode and explicitly rejects `proof_mode` and
  `four_hour_proof_mode`. Proof database isolation cannot reach the operational
  path.
- `four_token_proof_owned` affects exactly one thing in accounting: threading
  the exact cycle-scoped factory step identities so the bare `WINDOW_15M` root
  stage is accepted for cycle-owned steps. That is multi-cycle step-identity
  handling required by any multi-cycle run. It relaxes no accounting rule.
- `aggregate_four_token_cycle_acceptance`, which emits the
  `FOUR_TOKEN_CAPACITY_PROOF_STRUCTURAL_PASS` verdict, is referenced only by
  tests and is never called from `src/`. Proof acceptance cannot be reported as
  operational memory acceptance.
- The facade contains no loop, thread or subprocess, and performs no I/O.
- The Cycle-2 identity guard exposed by the facade is the *same function object*
  as the repaired adapter guard (verified by identity, not by name), so it is
  reuse rather than reimplementation.

Result: reusable runtime composition only. No proof authorization, application,
terminal, retry or execution semantics leak. `NO_PROOF_SEMANTIC_LEAKAGE`.

## 5. Independent capacity derivation

Re-derived live from `scaled_standard_four_hour_capacity_contract(4)`:

| Value | Required | Derived |
| --- | --- | --- |
| through-4h token slots | 4 | 4 |
| active cycles | 2 | 2 |
| tokens per cycle | 2 | 2 |
| total cycle admission ceiling | 2 | 2 |
| lifecycle requests per token | 117 | 117 |
| lifecycle request outer ceiling | 472 | 472 |
| lifecycle Scheduler outer ceiling | 420 | 420 |
| cycle admission spacing | >= 300s | 300s |
| automatic retries | 0 | 0 |
| endpoint rotation | false | false |
| long windows activated | false | false |
| locked windows | 12h, 24h | 12h, 24h |

Hard-coding was excluded two ways. A source scan found no literal `472`, `117`
or `420` in any changed product file. More decisively, the facade was reloaded
against a deliberately perturbed canonical contract and every derived value
moved with it (117→999, 472→8888, 420→7777, tokens-per-cycle 2→5) and restored
cleanly afterwards. The derivation is live, not a literal.

### 5.1 Residual finding (non-blocking)

The authorization-binding policy derives from the canonical contract, but the
runtime controller's structural policy is built by `build_four_token_proof_policy()`
from separate literals in `four_token_proof_integration.py`
(`FOUR_TOKEN_PROOF_THROUGH_4H_TOKENS = 4`, etc.; only the spacing constant is
shared with `multi_cycle_memory_growth`).

Today the two agree exactly — independently verified at 4 / 2 / 2 with 300s
spacing — and a focused test pins the agreement, so drift would fail loudly
rather than silently. Reusing that repaired policy builder was also mandated by
this lane's scope, which forbade a new selection algorithm.

This is therefore recorded as a residual risk, not a defect: **the host-local
preparation lane should re-derive both the canonical contract and the controller
policy on the exact launch checkout and stop on any disagreement**, rather than
assuming today's agreement holds.

## 6. Multi-cycle and Cycle-2 semantics

Verified against the repository, and independently re-executed in section 10:

- Cycle 2 is admitted inside the same campaign/run ownership graph — one
  campaign run row exists at terminal, not a successor.
- Cycle 2 obtains supply through the repaired governed later-cycle acquisition
  callback; exactly one supply call occurred.
- Four slots exist with four distinct token rows, pair rows, canonical mint
  identities and exact pair identities.
- Cycle-1 carry-forward is rejected by the repaired guard, which the facade
  reuses by object identity.
- Source Governor and Central Scheduler remain the owners; no owner file was
  changed by this lane.
- `MARKET_PRESENT_POOL` modules are untouched by the diff.
- No second runner, event loop, or independent source/scheduling loop exists.

## 7. Provenance hierarchy

Both four-token profiles now resolve to:

CURRENT: `operator-runs/v2-9-8b-migration-058-application` / `MIGRATION_058_EVIDENCE`

HISTORICAL: 050 (12 files), 055 (5), 056 (6), 057 (6) — four distinct roots,
evidence classes and execution identities.

Ordinary and two-token Standard-4H profiles are unchanged: both keep the
Migration-050 root and kind and an empty historical-migration tuple.

### 7.1 Migration-057 evidence reproduced independently

Using the committed enumeration and digest primitives, read-only, against the
preserved host evidence, this review recomputed all three historical digests:

| Package | Execution ID | Files | Inventory SHA-256 | Result |
| --- | --- | --- | --- | --- |
| 055 | `MIGRATION_055_20260813T220109Z` | 5 | `c004437332…d9e625` | MATCH |
| 056 | `MIGRATION_056_20260815T164802Z` | 6 | `4918774b95…5868f3` | MATCH |
| 057 | `MIGRATION_057_20260816T191558Z` | 6 | `9272f596e7…519535` | MATCH |

Reproducing the two previously-committed constants (055, 056) — which this lane
did not author — validates both the derivation method and the integrity of the
preserved packages. The 057 identity is therefore real preserved evidence, not
fabrication. No `BLOCKED_READINESS` condition exists.

### 7.2 No weakened validation

Every removed line in the provenance module was inside the replaced profile
declaration, except the inline profile allowlist tuple, which became
`supported_profiles()` with the fail-closed `raise` preserved. No validation
check was deleted or relaxed. The immutable completeness law still fires on file
count, digest, missing root and empty package.

### 7.3 Migration-058 stays preparation-time bound

Only the 058 package root and kind are committed. A repository-wide scan found
no hard-coded Migration-058 execution identity. The execution identity is
supplied by the authorization document at preparation time.

## 8. Zero-state ownership

One shared implementation, not a duplicate: each ownership domain query appears
exactly once in the module; `_assert_four_token_zero_state` is the single body;
`assert_four_token_proof_zero_state` and
`assert_four_token_standard_four_hour_zero_state` are thin mode-specific entry
points.

Pins: migration count 58, head `058_direct_pump_migration_cursor.sql`, 12
required zero-state domains, no occurrence of `059` in the module, and 58
migrations on disk with no 059 file.

Behavioural probes (offline, no DB mutation) confirmed the operational gate
fails closed on: migration count/head 59/059, count/head 57/057, a live Printer
runtime process, an unreadable authoritative database, and a proof-authority
document submitted to the operational gate.

## 9. One-shot wrapper

Distinct across every identity dimension: wrapper schema
`PRINTER_V1_FOUR_TOKEN_STANDARD_4H_ONE_SHOT_WRAPPER_V1`, authorization schema
`PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`, package root
`operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization`, kind
`FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE`, manifest schema
`PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_STANDARD_4H_V1`, and application
namespace `four-token-standard-four-hour-one-shot-applications`.

Confirmed by test and by the adversarial probe in section 3.1: exact branch and
HEAD binding, exact authorization hash and identity, operator approval required,
allowed invocation count exactly 1, second application refused with no second
child, hash/mode/profile mismatch refused, zero-state block leaves the
authorization unconsumed, marker written at most once, and retry/rerun/resume/
restart/successor all fixed false. HEAD drift after binding fails closed.

## 10. Independent test and proof results

All runs offline. The bounded proof and the full new-authority set were also run
under a hard outbound-network block (`socket.connect`, `create_connection` and
`getaddrinfo` denied); everything still passed, which independently establishes
zero live provider/RPC/WebSocket activity.

| Set | Result |
| --- | --- |
| new 4/2/2 operational tests (network blocked) | 57 passed |
| affected authority / provenance / multi-cycle / capacity set | 230 passed, 6 failed |
| compilation of all changed product modules | OK |
| import of 11 changed and sibling authority modules | OK |

All 6 failures in the affected set were reproduced identically on the untouched
design baseline in an isolated extracted tree (section 11).

### 10.1 Bounded proof re-executed with an independent audit

Rather than trust the proof test's own assertions, this review re-executed the
same composition against a disposable database with frozen time and fake supply,
then audited the resulting state with its own raw SQL. All 20 independent checks
passed:

one invocation admitted Cycle 2; Cycle 1 held exactly 2 slots beforehand;
exactly 1 fresh supply call; 4 total slots; 4 distinct token rows; 4 distinct
pair rows; 4 distinct mint identities; 4 distinct exact pair identities; exactly
2 cycles; 2 slots per cycle; exactly 1 campaign run; zero new source requests;
zero 12h/24h steps; disjoint per-cycle factory step sets; 300s admission
spacing; every Scheduler job correctly owned by its cycle (both cycles); exactly
one shared terminal cleanup; no non-terminal run remaining; still exactly two
cycles after terminal, so no third cycle and no successor.

## 11. Disposition of the baseline failures

This was investigated, neither auto-repaired nor auto-dismissed.

A read-only copy of the design baseline was extracted with `git archive` into an
isolated scratch tree and the same tests were run against it.

`tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`:

- baseline: 31 failed / 17 passed; implementation: 31 failed / 17 passed;
- **failing test identities: identical** (diff empty);
- **failure signatures: identical** — 35 × `final authorization
  migration_execution_id mismatch`, 2 × `manifest repository identity does not
  match live Git state`.

Intersection analysis with the new authority:

- every failing test in that file exercises `mode: "run"` — the ordinary profile
  only; the file contains no reference to the new 4/2/2 authority;
- the ordinary profile was independently confirmed unchanged by this lane;
- the only shared-helper change was the profile allowlist becoming
  `supported_profiles()`, which cannot produce a `migration_execution_id`
  mismatch.

Safety direction: **every failure is a validator rejection**, not a wrongful
acceptance. The `assertRaisesRegex` failures are cases where the validator did
raise, merely with an earlier, broader message than the test expected. There is
no fail-open condition anywhere in the set — including
`test_valid_manifest_and_marker_pass`, which fails because a valid fixture is
*refused*. A fail-closed validator cannot authorize anything unsafely.

The other affected-set failures were likewise reproduced byte-identically on the
baseline, with signatures naming Migration-050 (`expected 12, found 1`) — a
declaration this lane did not change:

- `test_v2_9_8b_four_token_proof_one_shot_wrapper.py` ×3
- `test_v2_9_8b_four_token_proof_authorization_profile.py` ×2
- `test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py` ×1

Classification: `PRESERVED_SEPARATE_PRE_EXISTING_DEBT`.

Zero new relevant regressions. These failures do not intersect the operational
4/2/2 authority and do not block authorization preparation. They are not
repaired here and require their own lane. The dominant root cause is fixture
drift between an ordinary-profile authorization document and its manifest
`migration_execution_id`.

## 12. Authoritative state, authorization state and locks

- Authoritative `data/printer_v1.sqlite3` matches its recorded pre-lane identity
  exactly: SHA-256 `a77141bce32468a2685007a276dbac91d1ed68671b5036c7bc24f54f60ad46d7`,
  size `100794368`, inode `1230526`, mtime_ns `1787043184343686970`. No sidecars.
- No operational authorization package exists; no operational application
  namespace exists; no application marker was created; nothing was consumed.
- The single untracked path,
  `operator-runs/v2-9-8b-standard-four-hour-final-authorization/`, is
  pre-existing host evidence whose directory mtime precedes the lane commit. All
  eight packages are two-token `standard-four-hour-run` authorizations; none can
  authorize the 4/2/2 mode, and none carries an application marker. Correctly
  left uncommitted.
- Migrations: 58 on disk, head `058_direct_pump_migration_cursor.sql`, no 059.
- The two new product modules are clean of scoring, ranking, confidence,
  weighting, embeddings, vectors, wallet/private-key/signing, real funds,
  BUY/SELL/HOLD, positions, trade events, PnL, paper decisions, retrieval and
  `059`. 12h/24h appear only as locked-window declarations; 5m is support-only
  and absent from the main lifecycle windows.

## 13. Git reconciliation

| Ref | Value |
| --- | --- |
| local branch | `agent/v2-9-8b-post-repair-two-cycle-four-token-operational-authorization-alignment-implementation` |
| local HEAD | `25daf4fd993fbea4142b16d02820b577fba6e300` |
| origin branch of the same name | `babc8a3b2dfd4ddca1307e140a378e0d3279e113` (the design baseline) |
| local master | `19bcd23da1608e406e25f675532df193b65d038a` |
| origin/master | `a98e2da6e133146026949a47e522d625fba59fff` |

The implementation commit is **not** reachable from local master or
origin/master; master is untouched by this lane in both places. Local master is
an ancestor of origin/master — 21 behind, 0 ahead — which is a stale local
pointer, not a divergence and not a lane modification.

The implementation commit is local-only; the remote branch still exposes the
design handoff. Per the review instruction this is classified as
`LOCAL_ONLY_VISIBILITY_STATE`, not a product defect. The governing source does
not require publishing, so nothing was pushed. A later launch lane that binds a
HEAD must bind the actual local launch checkout, since remote visibility does
not currently reflect it.

## 14. Verdict

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_AUTHORIZATION_ALIGNMENT_INDEPENDENT_CLOSEOUT_PASS`

The implementation, its evidence and its bounded proof independently satisfy the
approved design.

## 15. Exact next permitted lane

Derived from the approved design's own sequence
(`implementation -> bounded proof/test -> closeout -> host-local authorization
preparation -> independent authorization review -> operator-approved one-use
run`), the next lawful lane is the host-local operational 4/2/2 authorization
preparation:

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational 4/2/2 Host-Local Authorization Preparation`

That lane must bind the actual launch checkout and the actual
`data/printer_v1.sqlite3` filesystem identity (path, SHA-256, size, inode,
mtime_ns); GitHub-only evidence cannot substitute. It must stop without
consuming the authorization, and it should re-derive both the canonical capacity
contract and the controller policy on the exact launch checkout per section 5.1.

Only after an independent authorization review PASS may the operator-approved
wrapper consume it exactly once.

This closeout does not prepare or create that authorization.
