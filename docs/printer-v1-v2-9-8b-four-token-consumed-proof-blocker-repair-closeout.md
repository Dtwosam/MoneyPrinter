# Printer V1 V2-9.8B Four-Token Consumed-Proof Blocker Repair Closeout

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_CONSUMED_PROOF_BLOCKER_REPAIR_CLOSEOUT_PASS_READY_FOR_INDEPENDENT_REREADINESS_REVIEW`

The approved three-part repair is complete and passes its focused contracts.
The sufficiently broad four-token, pre-admission, Scheduler-ownership, and
`AuthoritativeLiveOperationalCampaign` surface has no repair-caused regression:
the current and design-baseline failure-ID sets are exact matches, while current
HEAD adds nine passing repair tests.

This closeout is offline implementation verification only. It did not create or
review a fresh authorization, reuse the consumed authorization, run Printer,
perform discovery or source fetching, mutate the authoritative database,
generate memory, execute a proof, or unlock any retrieval or financial
capability.

## Repository and commit boundary

- repository: `Dtwosam/MoneyPrinter`
- branch: `agent/v2-9-8b-four-token-consumed-proof-blocker-tdd-implementation`
- design baseline: `601731db8c62d9e51675ce335f06907e2fc101a6`
- RED contract commit: `00be41b`
- GREEN repair commit: `303901e`
- authority-drift coverage commit: `a95cced`
- verified final implementation SHA:
  `a95ccedde43365331120e69868c2f3bc478f1eba`

The baseline is an ancestor of the verified final implementation SHA. At task
entry, origin, branch, and HEAD matched the requested identities and the tracked
worktree/index were clean. Existing untracked `operator-runs/` files were not
staged, modified, read as execution authority, moved, or deleted.

## Files changed from design baseline through implementation HEAD

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/four_token_factory_adapter.py`
- `tests/test_v2_9_8b_four_token_consumed_proof_blocker_tdd.py` (new)
- `tests/test_v2_9_8b_pre_admission_later_cycle_callback.py`

This closeout adds:

- `docs/printer-v1-v2-9-8b-four-token-consumed-proof-blocker-repair-closeout.md`

No migration, source adapter, retry owner, Scheduler implementation, capacity
contract, public command, authorization owner, or proof wrapper changed.

## Confirmed repair behavior

### 1. Canonical stage-scoped Scheduler reconciliation

`reconcile_four_token_cycle_terminal()` now reuses the canonical `WORK_SCOPES`
contract and accepts all four exact `V2_STAGE_SCOPED` scopes:

- `DISCOVERY_SELECTION`
- `FIRST_15M_HANDOFF`
- `WINDOW_LIFECYCLE`
- `TERMINAL_CLEANUP`

It still fails closed for an unknown scope, wrong ownership-contract version,
missing Scheduler job identity, missing Scheduler job rows, and invalid active
or orphan ownership state through the existing terminal reconciliation rules.
Non-window campaign work remains visible; it was not filtered out or ignored.

### 2. Durable pre-admission authority before supply

The later-cycle callback now:

1. creates the scheduled pre-admission attempt;
2. claims the Central Scheduler job;
3. marks the attempt `RUNNING`;
4. commits those writes;
5. closes the outer operational connection before invoking candidate supply.

A separate SQLite probe proved that the `RUNNING` attempt, `RUNNING` Scheduler
job, lock timestamp, and lock owner are durably visible when supply begins. The
probe can acquire `BEGIN IMMEDIATE`, proving that the callback holds no outer
write transaction across supply work.

The durable attempt and claimed Scheduler job remain the authority during the
supply phase; releasing the SQLite transaction does not release Scheduler
ownership.

### 3. Phase C authority revalidation

Normal result persistence and exception terminalization both reopen a fresh
operational connection and revalidate the exact attempt/job authority before
writing. The check requires:

- attempt state `RUNNING`;
- the same Scheduler job identity;
- job kind `PRE_ADMISSION_DISCOVERY_SELECTION`;
- job status `RUNNING`;
- a non-null lock timestamp; and
- the exact pre-admission lock owner.

If the Scheduler authority drifts after supply starts, the callback raises
`LATER_CYCLE_PRE_ADMISSION_AUTHORITY_DRIFT`, does not overwrite the newer state,
does not admit a pair, and does not replace the root cause with a generic supply
failure. Both the normal-return and supply-exception drift paths are covered.

### 4. Stable known exception causes

Known approved domain exceptions retain their stable `.code`, normalized to the
bounded safe identifier contract and capped at 128 characters. The same cause
is persisted to the pre-admission attempt and Scheduler `last_error`.

### 5. Bounded unknown exception causes

Unknown exceptions persist only:

`LATER_CYCLE_SUPPLY_EXCEPTION_<SAFE_CLASS_NAME>`

The classifier uses uppercase `A-Z`, digits, and underscore only, caps the
identifier at 128 characters, and never persists `str(exc)`, raw provider
payloads, URLs, query secrets, stack traces, or arbitrary exception detail.

### 6. Unchanged operational contracts

- Normal supply scarcity remains `NO_PAIR` and preserves the canonical supply
  terminal cause, falling back to `NO_EXACT_PAIR`.
- `max_retries=0` remains unchanged; the failed execution increments
  `retry_count` once and transitions directly to `FAILED` without cooldown,
  requeue, retry, restart, resume, or successor.
- Source Governor ownership is unchanged.
- Central Scheduler ownership is unchanged.
- Candidate-supply architecture and eligibility are unchanged.
- Exactly two candidates are still required for later-cycle pair admission.
- Public/default `TOKEN_CAPACITY == 2` and the four-token bounded capacity
  contract are unchanged.
- No migration or schema change was added.
- All V1 safety and financial restrictions remain unchanged.

## Verification evidence

### Focused and directly affected repair surface

The focused set covered the new blocker contracts plus pre-admission
persistence/Scheduler behavior, four-token factory terminal integration,
two-phase terminal behavior, and canonical Scheduler ownership migration
contracts.

Result:

```text
83 passed, 1 skipped in 18.16s
```

The skipped test is inherited and was not converted into a pass or hidden.

### Broad closeout surface and exact baseline comparison

The broad file set was selected from all Python tests whose paths contain
`four_token`, `pre_admission`, `scheduler_ownership`, or
`authoritative_live_operational_campaign`. Host process inspection was allowed
for the final comparison so `ps` sandbox denial did not distort the result.

Current implementation HEAD:

```text
17 failed, 283 passed, 1 skipped, 29 subtests passed in 68.73s
```

Isolated design baseline archive, with `PYTHONPATH` pinned to baseline source:

```text
17 failed, 274 passed, 1 skipped, 29 subtests passed in 57.88s
```

The failing test/subtest IDs and causes are identical. Current HEAD adds nine
passing repair tests and adds no failure.

The inherited broad-surface failures are:

- five legacy `AuthoritativeLiveOperationalCampaign` tests that already fail at
  baseline because a historical fixture path dereferences
  `None.holder_reserve_candidates`; and
- twelve authorization-profile/zero-state failure or subtest outcomes caused by
  their fixture authorization now being expired.

Those files and causes are outside this repair diff. They were not fixed,
suppressed, or used to widen scope.

### Known unrelated SQLite heartbeat concurrency failure

The specifically named node was run independently at both exact design baseline
and current HEAD:

`tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestMigrationDiscoverySleepDoesNotHoldLock::test_settle_sleep_releases_write_transaction`

Both runs produced exactly:

```text
AttributeError: module 'printer_v1.discovery.direct_migration_discovery'
has no attribute 'release_write_transaction'
1 failed
```

The failure is therefore a confirmed unrelated baseline defect. This repair
does not touch `direct_migration_discovery` or that test, and no fix was made.

Blocker classification:

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT (PRE-EXISTING, UNRELATED)
CODE CHANGE JUSTIFIED IN THIS LANE: NO
MINIMUM SAFE RESPONSE: preserve and report the baseline fact
AUTHORIZATION STATUS: no authorization created, reused, or consumed
```

### Compile and static checks

- `py_compile`: PASS for both changed production modules and both changed test
  files.
- `git diff --check 601731d..a95cced`: PASS.
- tracked worktree/index after verification: clean before this closeout document.
- baseline-to-implementation changed-file audit: exactly the four files listed
  above.

## Money-usefulness contribution

The repair makes a future separately authorized four-token capacity proof test
real multi-cycle collection behavior instead of failing on a false scope
validator or a self-created SQLite write lock. Stable bounded terminal causes
also make a future one-shot failure actionable without leaking secrets or
wasting operator time on opaque reruns. This improves the reliability and
diagnostic value of paper-only memory growth; it does not claim profit or prove
four-token capacity.

## What improved

- truthful reconciliation across every canonical campaign Scheduler scope;
- durable Scheduler/pre-admission authority before later-cycle supply;
- no outer SQLite write transaction across supply I/O or lengthy work;
- fresh-boundary authority validation before admission or terminal overwrite;
- safe, bounded, machine-readable exception provenance;
- explicit regression proof for no retry and honest `NO_PAIR` behavior.

## What was not touched

- no fresh or reused four-token authorization;
- no application marker;
- no four-token proof, rerun, resume, retry, restart, or successor;
- no Printer runtime, discovery, provider, RPC, or source fetching;
- no authoritative database mutation or memory generation;
- no source architecture or Scheduler ownership change;
- no exact-two or capacity-contract change;
- no migration;
- no 12h/24h work;
- no retrieval activation;
- no paper decisions or BUY/SELL/HOLD;
- no positions, trades, paper audits, or PnL;
- no wallet, private key, signing, live execution, real funds, paid API,
  scoring, ranking, confidence, weighted logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- The consumed proof did not preserve its original exception class or detail;
  this repair correctly does not invent that historical root cause.
- The durable `RUNNING` attempt/job intentionally remains authoritative while
  supply executes. Independent rereadiness review must verify that the new
  close/reopen boundary is acceptable for the exact future proof composition.
- Authority drift deliberately leaves the already-drifted durable state
  untouched and raises fail-closed. It does not try to repair or reinterpret
  concurrent ownership changes.
- The exception classifier preserves stable codes only from the approved domain
  exception classes; all other exceptions are intentionally reduced to a safe
  class identifier.
- The 17 inherited broad-surface failures and the separately named heartbeat
  concurrency failure remain open outside this lane. Baseline comparison proves
  this repair did not cause them.
- Broad verification is slower because current time-sensitive authorization
  fixtures fail before their intended assertions; this is a pre-existing test
  maintenance blocker, not evidence against this repair.

## What remains locked

Four-token capacity remains unproven. A fresh authorization, authorization
review, application marker, or proof remains forbidden until a separate
independent rereadiness review closes PASS and the operator explicitly approves
the later authorization sequence.

Retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade
audits, PnL, live execution, wallets, private keys, signing, real funds, paid
APIs, scoring, ranking, confidence percentages, weighted logic, embeddings,
vectors, 12h/24h operation, unbounded runtime, and automatic restart remain
locked.

## Next recommended phase

`V2-9.8B FOUR-TOKEN CONSUMED-PROOF BLOCKER REPAIR INDEPENDENT REREADINESS REVIEW`

That next phase is review only. It must not create or review a fresh four-token
authorization, reuse the consumed authorization, run a proof, fetch sources,
run Printer, generate memory, or unlock any retrieval or financial capability.
