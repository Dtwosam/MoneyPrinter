# Printer V1 V2-9.8B Fresh Bounded-Operation Authorization Readiness

Date: 2026-08-15

## Verdict

`V2_9_8B_FRESH_BOUNDED_OPERATION_AUTHORIZATION_READINESS_PASS_READY_FOR_FRESH_AUTHORIZATION_CREATION`

## Boundary

Read-only. No authorization created or consumed, no campaign, no discovery, no
source fetch, no Scheduler/runtime, no memory generation, no
retrieval/decisions/trading. Baseline
`fbdfeb4ca96d528402fb62168ee24bd03cae0a47`; reviewed from a temporary worktree.
The user's working branch, HEAD, and untracked evidence were untouched.

One in-memory document was constructed solely to test the temporal contract
(section 5). It was never written to disk, carried the identifier
`READINESS_PROBE_NOT_AN_AUTHORIZATION`, and is not an authorization.

## 1. Authoritative preconditions — 10/10 PASS

| check | observed |
| --- | --- |
| sha256 | `555f9558a4f83ac4639ed5d909768a0c9d4b23871f65c31b251a702efb13273e` (exact) |
| ledger / head | `56` / `056_four_token_pre_lifecycle_terminal_provenance.sql` |
| `integrity_check` / FK / sidecars | `ok` / `0` / none |
| eleven zero-state domains | all `0` |
| active campaign / supervision / non-terminal batch | `0` / `0` / `0` |
| migration-ledger drift review | passes |
| DB holders / campaign lease | `0` / none |

## 2. Exact operation envelope — derived from committed contracts

Read from `four_token_proof_one_shot_wrapper.exact_proof_policy()` and module
constants; nothing assumed or widened.

| field | authorized value |
| --- | --- |
| operation / proof type | `four-token-bounded-capacity-proof-run` |
| policy version | `V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1` |
| token capacity | **4** concurrent through-4h tokens |
| cycle count | **2** active/admitted cycles (`total_cycle_admission_ceiling = 2`) |
| tokens per cycle | **2** |
| minimum cycle admission spacing | 300 s |
| root main window | **`WINDOW_15M`** |
| locked windows | `WINDOW_12H`, `WINDOW_24H` (`long_windows_activated = false`) |
| shared discovery requests | 4 |
| lifecycle requests per token | 117 |
| lifecycle request outer ceiling | 472 |
| lifecycle scheduler outer ceiling | 420 |
| pre-lifecycle acquisition | 900 s |
| post-supply proof duration | 18 000 s |
| max one-shot wall envelope | 18 900 s |
| automatic retries | **0**; endpoint rotation `false` |
| standard four-hour campaign | `true` |

**`WINDOW_15M` remains the only operational memory window.** `WINDOW_12H` and
`WINDOW_24H` are locked in the policy and re-verified by the zero-state gate.

**Forbidden widening:** any token count other than 4; any cycle count other than
2; any per-cycle count other than 2; six-token capacity; shorter cycle spacing;
any retry or successor; endpoint rotation; 1h rerun; 12h/24h activation; any
additional memory window; any ceiling above those listed.

The committed contracts authorize this shape exactly and unambiguously.

## 3. Fresh authorization contract

### Prior authorizations — non-reusable

| authorization | expires_at | status |
| --- | --- | --- |
| `…AUTH_20260814T101513Z` | 2026-08-14T22:15:13Z | **CONSUMED** (marker present) + expired |
| `…AUTH_20260814T143225Z` | 2026-08-15T02:32:25Z | unconsumed but **expired** |
| `…AUTH_20260814T171249Z_0022b4dc` | 2026-08-15T05:12:49Z | **CONSUMED** (marker present) + expired |

Current time 2026-08-15T17:24Z — all three are past expiry, and two carry
application markers. Additionally every one binds the superseded database
identity (`a9c82e97…` or `5e830af4…`), none of which matches `555f9558…`. A
completely fresh authorization identity is therefore required; none of these can
be reused, resumed, restarted, or succeeded (`one_shot_policy`:
`allowed_invocation_count = 1`, resume/restart/successor/manual-rerun/automatic-retry
all `false`).

### Evidence binding

All required roots exist in the operator working tree:

| role | root | status |
| --- | --- | --- |
| current migration evidence | `operator-runs/v2-9-8b-migration-056-application` | **4 tracked JSON files, 0 untracked/ignored residue, BINDABLE** |
| current authorization evidence | `operator-runs/v2-9-8b-four-token-final-authorization` | exists (3 prior packages) |
| historical migration 050 | `…/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` | exists, 12 files |
| historical authorization roots | window-15m (72 files), standard-4h (7), four-token (3) | exist |

### Required fields for the fresh authorization

`schema_version` `PRINTER_V1_FOUR_TOKEN_PROOF_FINAL_AUTHORIZATION_V1` ·
new unique safe `authorization_id` · `migration_execution_id`
**`MIGRATION_056_20260815T164802Z`** · `verdict` ending `_PASS` ·
`authorized_at` / `expires_at` / `validity_seconds` (default TTL **43 200 s = 12 h**) ·
`repository` {branch, head} bound to the exact creation commit ·
`authorized_command` {`four-token-bounded-capacity-proof-run`, `operator_approved: true`} ·
`one_shot_policy` exactly as above · `proof_policy` exactly equal to
`exact_proof_policy()` · `authoritative_database` pinning
**sha256 `555f9558a4f83ac4639ed5d909768a0c9d4b23871f65c31b251a702efb13273e`**,
`migration_count 56`, `migration_head 056_…sql`, plus path/size/inode/mtime_ns ·
`prior_authorizations_non_reusable` sorted, unique, excluding the new id.

### Drift semantics

No authorization survives relevant drift: the document pins exact DB sha,
size, inode, mtime_ns, migration count and head, plus exact branch and HEAD. Any
change to database identity, schema, or repository HEAD invalidates it, and the
zero-state gate independently re-checks migration count/head and the eleven
domains before consumption. The TTL is 12 h, so creation and independent review
must stay inside one bounded window.

## 4. `AUTHORIZATION_EXPIRED` — classified from evidence

**Classification: test-fixture-only; NON-BLOCKING to fresh production
authorization creation.**

This was not accepted on the basis of it being previously known; it was traced to
root cause and both branches were tested.

Root cause: `tests/test_v2_9_8b_four_token_proof_authorization_profile.py:27`
hard-codes `NOW = datetime(2026, 8, 13, 22, 0, tzinfo=utc)`, and `_document()`
passes `authorized_at=NOW`, `expires_at=NOW + 12h`. That document expired
2026-08-14T10:00Z and is now ~2 days 7 hours stale, so
`validate_authorization_temporal_validity` correctly rejects it.

Decisive discriminating evidence, both run against the same production validator:

- **Production shape** — `fixture_authorization_document(...)` with
  `authorized_at` omitted, so issue time is `datetime.now(timezone.utc)`:
  `authorized_at 2026-08-15T17:23:55Z`, `expires_at 2026-08-16T05:23:55Z`,
  `validity_seconds 43200`. `validate_four_token_proof_authorization_document`
  → **PASS**, returning mode `four-token-bounded-capacity-proof-run` and policy
  4 tokens / 2 cycles / 2 per cycle.
- **Frozen-timestamp shape** — same builder with the fixture's literal
  timestamps → **FAIL: `authorization temporal validity failed:
  AUTHORIZATION_EXPIRED`**, reproducing the test failure exactly.

The defect is therefore isolated to a stale constant in one test fixture. The
production creation path is issue-time-relative and validates cleanly today. It
does not block fresh authorization creation.

It remains a genuine test-hygiene defect: it will keep failing until repaired,
and while failing it masks any real regression in that same test. That is
recorded as a risk, not waived.

## 5. Focused regression

The clearance lane's focused set ran **77 passed, 10 subtests passed, 1 failed** —
the failure being exactly the fixture defect classified above. Properties
re-proven there and relied on here: schema 56 canonical; zero-state gate admits
it; `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` non-stranding with counterfactual;
`TWO_CYCLE_COMPLETION` valid; migration-evidence binding works. No broad suite was
run.

## 6. Next-lane contract

**Creation and execution are separable.** The document is written by an operator
step; consumption happens only when `apply_authorization_once()` creates the
application marker under
`~/PrinterOperations/v2-9-8/four-token-proof-one-shot-applications/<id>/`. The
programme has previously created authorizations without executing them. No
committed contract makes creation and execution inseparable, so **no block is
required** on that ground.

The next lane may create **exactly one** authorization package:

`operator-runs/v2-9-8b-four-token-final-authorization/<NEW_ID>/final_authorization.json`

with the section 3 fields, then STOP. It must not call
`apply_authorization_once()`, must not build a provenance manifest or application
marker, must not start Printer, and must be followed by an independent
authorization review before any consumption.

**Sequencing requirement.** The creation lane must run from a checkout whose
lineage contains the migration commit `0948d09`, because the committed
migration-056 JSON evidence exists only there. The user's current working branch
(`agent/v2-9-8b-post-repair-zero-state-residue-audit`, HEAD `8fbfb088`) predates
it and carries only the two gitignored `.sqlite3` blobs in that root. Creating
from the stale branch would fail evidence binding.

## Preserved constraints

Solana memecoin-only · paper-only · no live wallet, private keys, or real funds ·
no scoring/ranking/confidence/weighted logic · no retrieval · no paper decisions ·
no BUY/SELL/HOLD · no positions, trades, audits, or PnL · no 1h rerun · no 12h/24h
activation.

## Money-usefulness contribution

Establishes that the one remaining path to measuring real four-token concurrent
memory throughput is open, with the exact envelope derived from committed code
rather than assumed. Classifying `AUTHORIZATION_EXPIRED` from evidence — rather
than by reputation — removes the last credible doubt that the authorization path
itself is broken, which would otherwise have been discovered only by spending a
fresh authorization.

## What improves

- The authorized shape is derived and pinned: 4 tokens / 2 cycles / 2 per cycle,
  `WINDOW_15M` only, with every forbidden widening enumerated.
- All three prior authorizations are proven non-reusable on three independent
  grounds: expiry, consumption markers, and superseded DB identity.
- Every required evidence root is confirmed present and the migration-056 package
  confirmed bindable with zero residue.
- The `AUTHORIZATION_EXPIRED` defect is precisely bounded to a stale test constant
  with both branches empirically tested.
- The creation/execution separability question is answered from the contract, and
  a concrete checkout-lineage requirement is surfaced before it can bite.

## What remains locked

Four-token proof execution, authorization consumption, six-token proof and
capacity widening, 12h/24h activation, 1h rerun, source fetching and discovery,
memory generation, Scheduler work creation, campaign start, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets,
private keys, signing, live execution, real funds, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings, and vectors.

The tracking-queue readiness limitation and the migration-055 historical-package
promotion remain deferred.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authorization TTL is 12 h. Creation and independent review must complete
  inside one window or the authorization expires unused — the same wall-clock
  pressure that produced two of the three dead prior authorizations.
- The creation lane must run from a checkout containing commit `0948d09`.
  Creating from the user's current branch would fail migration-056 evidence
  binding.
- The `AUTHORIZATION_EXPIRED` fixture defect is unrepaired. While failing it
  masks genuine regressions in the authorization-profile test; it should be fixed
  before that test is relied on as a gate.
- Any change to the authoritative DB or repository HEAD after creation
  invalidates the authorization; it cannot be edited, only re-created.
- Migration-056's triggers have still never been exercised by a live campaign.
  The eventual proof is their first runtime test on real data.
- The `.sqlite3` evidence blobs are gitignored and machine-local; the JSON
  evidence binds without them, but the byte-level pre-migration copy is not
  reproducible if pruned.
- This review ran no new tests beyond the temporal-contract probe and relies on
  the clearance lane's focused set.

## Next permitted lane

`V2-9.8B Fresh Four-Token Authorization Creation` — create exactly one
authorization package per section 3 and section 6, from a checkout containing
`0948d09`, then STOP. Do not consume it, do not start a campaign, and require an
independent authorization review before any proof execution.
