# Printer V1 V2-9.8B Post-Rollover-2 Frozen Secondary Discovery Contract Exact Proof Root Cause

Date: 2026-08-03

## Verdict

`V2_9_8B_POST_ROLLOVER_2_FROZEN_SECONDARY_CONTRACT_EXACT_PROOF_ROOT_CAUSE_CAPTURED`

The one authorized exact public composition after the frozen-secondary repair did
not complete two `WINDOW_15M` closes and did not reach `CAMPAIGN_PASS`. This
report classifies the immutable first cause only. It does not issue PASS, does
not authorize repair, and does not authorize a rerun.

## Classification

**`TEST_OR_PROOF_HARNESS_DEFECT`**

The immutable first operational cause is:

```text
SAFE_STOP_PREFLIGHT_FAILED
```

Exact preflight blocked reason reconstructed from the production preflight owner
and the exact argument path:

```text
operational persistent mode requires the authoritative corpus
```

| Candidate classification | Decision |
| --- | --- |
| `TEST_OR_PROOF_HARNESS_DEFECT` | **Selected.** Exact offline composition drives the public fifteen-minute operational path (`operational_persistent_mode=True`) against a disposable Migration-050 database. |
| `COMMITTED_CODE_DEFECT` | Rejected. The factory preflight enforces its committed operational-persistent corpus contract. |
| `EXPECTED_SAFETY_STOP` | Secondary description only. The stop is contract-correct given the supplied args, but the composition failed because the offline harness arguments are incompatible with that contract. |
| `CONFIG_OR_ENVIRONMENT_BLOCKER` | Rejected. No missing host config or external service caused the stop. |
| `PRE_EXISTING_UNRELATED_FAILURE` | Rejected. Discovery, secondary contract, and two-slot activation succeeded; failure is at lifecycle factory entry. |
| `INSUFFICIENT_EVIDENCE` | Rejected. JSON, disposable DB, source owners, and exact overrides are sufficient. |

No production code repair is justified by this evidence alone.

## Baseline and identities

| Field | Value |
| --- | --- |
| Repair commit under proof | `ff5f5391c277aec02cac73b146d6242b81c93e9b` — `Repair frozen secondary discovery contract` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked tree at composition | clean (untracked operator evidence only) |
| Comparison worktree | `/private/tmp/mp-preclaim` detached at `8fb4256c70d4e81660c177238253322cb37ae947` — preserved, not modified |
| Exact node | `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::ExactPublicTokenSlotIdCompositionProof::test_exact_public_coordinator_owner_driver_factory_composition` |
| Execution identity | `20260803T194954Z-e58915c59103` |
| Campaign | `20260803T194954Z-e58915c59103-campaign` |
| Campaign run | `20260803T194954Z-e58915c59103-campaign-run` |
| Cycle | `20260803T194954Z-e58915c59103-cycle` |
| Exact invocation count | **one** |
| Focused proof (already completed) | `224 passed, 9 subtests passed` |
| Push | not performed |

## Exact command already run

```bash
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::ExactPublicTokenSlotIdCompositionProof::test_exact_public_coordinator_owner_driver_factory_composition
```

Execution-only bindings used for this composition family:

- `PRINTER_V1_OFFLINE_FAILURE_EVIDENCE_ROOT` → external untracked evidence root under
  `PrinterOperations/v2-9-8/20260803-frozen-secondary-exact-public-composition`
- disposable offline database created by the test via `apply_migrations`
- frozen Pump origin, lawful frozen secondary, fixture snapshot/context transports
- `urllib.request.urlopen` patched for zero-network assertion

This lane did **not** rerun that command.

## What the repair already proved

The frozen secondary producer/consumer repair and focused gate proved:

- lawful Gecko trending/active envelopes and empty lawful responses;
- malformed and missing-pool classification without false empty success;
- provider-local failure isolation with real Scheduler terminal parity;
- claim-at-work-start, SHARED_FAILURE evidence capture, and pre-lifecycle
  propagation regressions still pass;
- exact public-composition success fixture wiring is ready for one composition.

Those proofs are not reopened here.

## Established composition outcome (distinguished surfaces)

| Surface | Result |
| --- | --- |
| Public wrapper reached | yes |
| Malformed secondary-response failure recurred? | **no** |
| Discovery | **succeeded** — 10 discovery work rows `SUCCEEDED`; 0 source failures |
| Two-slot activation | **succeeded** — two token slots created with `PUMPSWAP_GRADUATED_CONFIRMED` |
| Lifecycle factory preflight | **failed** — `SAFE_STOP_PREFLIGHT_FAILED` |
| Lifecycle terminal / run status | `SAFE_STOPPED` |
| Immutable first terminal cause | `SAFE_STOP_PREFLIGHT_FAILED` |
| Campaign / run / cycle states | `TERMINAL_COMPLETED` with first cause `SAFE_STOP_PREFLIGHT_FAILED` |
| Campaign acceptance | `BLOCKED_UNSAFE` |
| Factory run row | **none** (`reconciliation.factory_run = not_found`) |
| `WINDOW_15M` rows | **zero** |
| Retry / rerun / restart / resume / successor | all **zero** in failure evidence |

## Required answers

### 1. Which exact preflight condition returned `SAFE_STOP_PREFLIGHT_FAILED`?

Production owner:

`src/printer_v1/operator_cli/one_command_15m_factory.py` →
`run_one_command_15m_factory` preflight gate returning
`stop_reason = SAFE_STOP_PREFLIGHT_FAILED` when `reasons` is non-empty.

For this composition, the determining condition is:

```text
if operational_persistent_mode:
    if path != CANONICAL_PERSISTENT_DB:
        reasons.append(
            "operational persistent mode requires the authoritative corpus"
        )
```

`CANONICAL_PERSISTENT_DB` resolves to:

```text
/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3
```

The composition database was a disposable temp Migration-050 file, not that
corpus.

### 2. What values were expected and observed?

| Argument / check | Expected by factory preflight for this path | Observed in exact composition |
| --- | --- | --- |
| `fifteen_minute_only` (public owner) | `True` for normal public campaign | `True` |
| `proof_mode` | `False` when `fifteen_minute_only` | `False` |
| `operational_persistent_mode` | `True` when `fifteen_minute_only` | `True` |
| `operational_natural_disposition` | `True` at live owner boundary | `True` |
| `continuous_first_hour` / `continuous_four_hour` / `four_hour_proof_mode` | all `False` for 15m-only | all `False` |
| `max_selected_tokens` | 2 | 2 |
| `total_duration_seconds` (public policy default) | `1200` | overridden by exact owner to `3.0` |
| `_window_seconds` (factory default) | `900.0` | overridden by exact owner to `0.05` |
| Duration gate `total > required` | required = `0.05` with 15m-only compressed windows | `3.0 > 0.05` — **would pass** |
| DB path under `operational_persistent_mode` | must equal `CANONICAL_PERSISTENT_DB` | disposable temp DB — **fails** |
| Public `AUTHORITATIVE_DB` patch | public coordinator accepts patched disposable path | factory corpus check still uses unpatched `CANONICAL_PERSISTENT_DB` |

Duration compression is therefore **not** the first failure. The corpus identity
check is.

### 3. Did the production owner behave according to its committed contract?

**Yes.**

- Non-proof execution with `operational_persistent_mode=True` is the public
  fifteen-minute operational contract.
- That mode may not target a disposable proof DB; it requires the authoritative
  corpus.
- The factory returns `SAFE_STOPPED` / `SAFE_STOP_PREFLIGHT_FAILED` without
  creating a factory run, without scheduling window steps, and without weakening
  six-unit accounting.

### 4. Did the exact test supply incompatible lifecycle/proof-mode arguments?

**Yes.**

The exact owner injects lifecycle overrides suitable for offline compressed
timing (`_window_seconds=0.05`, `total_duration_seconds=3.0`, fixture adapters)
while still invoking the **public** operational campaign path:

- `fifteen_minute_only=True`
- therefore `operational_persistent_mode=True` and `proof_mode=False`
- disposable Migration-050 DB under a temp root
- `AUTHORITATIVE_DB` patched for the public command only

That combination is incompatible with the factory's operational-persistent corpus
preflight. Focused tests of `run_one_command_15m_factory` itself use
`proof_mode=True` on disposable DBs; the exact public composition does not.

### 5. Fixture/test configuration issue or production defect?

**Fixture / exact-proof harness configuration issue.**

Not a production preflight defect. Not a recurrence of the repaired secondary
discovery contract defect.

### 6. Why were both token slots moved to `MANUAL_REVIEW`?

Activation had already created two campaign token slots and tracking-queue rows.
After the lifecycle factory returned `SAFE_STOP_PREFLIGHT_FAILED`, campaign
terminal reconciliation applied pre-lifecycle dispositions:

| token_slot_id | slot disposition | tracking queue | priority_reason |
| --- | --- | --- | --- |
| `slot-...-cycle-1` | `MANUAL_REVIEW` | `SKIPPED` / `MANUAL_REVIEW` | `campaign_terminal:SAFE_STOP_PREFLIGHT_FAILED` |
| `slot-...-cycle-2` | `MANUAL_REVIEW` | `SKIPPED` / `MANUAL_REVIEW` | `campaign_terminal:SAFE_STOP_PREFLIGHT_FAILED` |

This is the committed terminal-reconciliation behavior for a campaign terminal
after activation and before completed windows, not an independent slot fault.

### 7. Why were no `WINDOW_15M` rows created?

The one-command factory never passed preflight, so:

- `printer_memory_factory_runs` count = **0**
- `printer_memory_factory_run_steps` count = **0**
- `printer_memory_factory_campaign_windows` count = **0**
- `printer_memory_windows` count = **0**

Two `TRACK_NORMAL_FIRST_15M` Scheduler jobs were present from handoff and were
terminalized `CANCELLED` during campaign cleanup. No window-close evidence was
produced.

### 8. Were all Scheduler jobs terminal with zero active residue?

**Yes.**

| Status | Count |
| --- | --- |
| `SUCCEEDED` | 10 (discovery family) |
| `CANCELLED` | 2 (first-15m tracking handoff jobs) |
| Active / non-terminal | 0 |
| Rows with lock owner | 0 |

Discovery work: 10 rows, all `SUCCEEDED`. Source failures: 0.

### 9. Did strict accounting and campaign acceptance behave correctly?

**Yes, for a failed incomplete campaign.**

- Campaign acceptance verdict: `BLOCKED_UNSAFE` (`pass: false`).
- Failing checks include missing factory binding, missing two terminal
  `WINDOW_15M` lifecycles, incomplete mandatory stages, and non-pass slot
  dispositions — consistent with preflight stop after activation.
- Cleanup completed; lease released; zero active owned work; zero locked
  Scheduler work.
- Downstream unlocks remain false for retrieval, decisions, positions, trades,
  audits, BUY/SELL/HOLD, and PnL.
- Six-unit evidence sealed discovery-selection and terminal-reconciliation
  stages; lifecycle transport reservations remained zero.

Acceptance correctly refused `CAMPAIGN_PASS`.

### 10. Is any code repair justified?

**No production repair is justified from this evidence.**

A future separately authorized lane may adjust the **exact offline public
composition harness / proof-mode boundary** so disposable offline composition
either:

- exercises a lawful proof-mode lifecycle entry that still proves the public
  coordinator chain, or
- otherwise satisfies the operational-persistent corpus contract without
  touching live authoritative data,

without weakening preflight, accounting, Scheduler, Source Governor, schema, or
migrations. That is out of scope for this report.

## Argument / configuration table (source-grounded)

| Layer | Setting | Value |
| --- | --- | --- |
| Public policy | `_NORMAL_CAMPAIGN_POLICY.duration_seconds` | `1200` |
| Public run path | `fifteen_minute_only` | `True` |
| Authoritative owner → driver | `proof_mode` | `not fifteen_minute_only` → `False` |
| Authoritative owner → driver | `continuous_first_hour` | `False` |
| Authoritative owner → driver | `continuous_four_hour` | `False` |
| Authoritative owner → driver | `four_hour_proof_mode` | `False` |
| Authoritative owner → driver | `operational_persistent_mode` | `True` |
| Live owner | `operational_natural_disposition` | forced `True` |
| Exact composition owner | `total_duration_seconds` | `3.0` |
| Exact composition owner | `_window_seconds` | `0.05` |
| Exact composition owner | snapshot/context factories | frozen fixtures |
| Exact composition owner | `migration_transport` | `None` |
| Exact test patches | `AUTHORITATIVE_DB` | disposable temp DB |
| Exact test patches | `urllib.request.urlopen` | call count 0 |
| Factory preflight constant | `CANONICAL_PERSISTENT_DB` | repo `data/printer_v1.sqlite3` (unpatched) |
| Campaign configuration JSON | `db_mode` surface | `OPERATIONAL_PERSISTENT` |
| Campaign configuration JSON | `duration_seconds` ceiling | `1200` |
| Campaign configuration JSON | `continuous_first_hour` / `continuous_four_hour` | `false` / `false` |

## Scheduler and discovery results

Discovery work types (all `SUCCEEDED`):

1. `DISCOVERY_PUMPFUN_LATEST`
2. `DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`
3. `DISCOVERY_DEXSCREENER_ACTIVE`
4. `DISCOVERY_IDENTITY_MERGE`
5. `DISCOVERY_ORIGIN_VERIFICATION`
6. `DISCOVERY_PUMPSWAP_CONFIRMATION`
7. `DISCOVERY_FIXED_ELIGIBILITY_GATES`
8. `DISCOVERY_UNIFORM_SELECTION`
9. `DISCOVERY_TRACKING_HANDOFF_SLOT_1`
10. `DISCOVERY_TRACKING_HANDOFF_SLOT_2`

Tracking jobs 11–12: `TRACK_NORMAL_FIRST_15M` → `CANCELLED` after terminal cause
`SAFE_STOP_PREFLIGHT_FAILED`.

## Token-slot results

| Slot | Mint | Lifecycle identity | Final state | First cause |
| --- | --- | --- | --- | --- |
| slot-…-cycle-1 | `GvBfTT3o8Gr9FC5x8mm3JtPitDRsp7mAqnQrutt1c65z` | `PUMPSWAP_GRADUATED_CONFIRMED` | `MANUAL_REVIEW` | `SAFE_STOP_PREFLIGHT_FAILED` |
| slot-…-cycle-2 | `25E1oYYcgMRDK1QiB2ns8e3hEZkFyLW5pqa68T3JGEpi` | `PUMPSWAP_GRADUATED_CONFIRMED` | `MANUAL_REVIEW` | `SAFE_STOP_PREFLIGHT_FAILED` |

Tokens: 2. Pairs: 2. Lifecycle events: 0.

## Window and campaign-acceptance results

| Check | Result |
| --- | --- |
| Campaign windows | 0 |
| Memory windows | 0 |
| Exactly two terminal `WINDOW_15M` lifecycles | false |
| Campaign acceptance verdict | `BLOCKED_UNSAFE` |
| `CAMPAIGN_PASS` | false |
| Runtime terminal status | `SAFE_STOPPED` |
| Runtime first terminal cause | `SAFE_STOP_PREFLIGHT_FAILED` |
| Terminal status wrapper | `COMPLETED` (supervision/cleanup completed; not campaign pass) |

## Preserved evidence artifacts

Artifact directory:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/20260803-frozen-secondary-exact-public-composition/20260803T194954Z-e58915c59103
```

| Artifact | SHA-256 |
| --- | --- |
| `shared-failure-evidence.json` | `d53e998c1049a630163ee3898146f5515566feed7fbcd120ad434845eadd8f6d` |
| `shared-failure-disposable-migration-050.sqlite3` | `3d6c785b5158e6b96377571077042dd1e8849587cc6deefdccb16eb0243534c5` |

Evidence JSON records:

- `first_failure.classification = SAFE_STOP_PREFLIGHT_FAILED`
- `authoritative_terminal.run_status = SAFE_STOPPED`
- `authoritative_terminal.first_terminal_cause = SAFE_STOP_PREFLIGHT_FAILED`
- `baseline_git_head = ff5f5391c277aec02cac73b146d6242b81c93e9b`
- `test_node_id` exact public composition node above
- retries/reruns/restarts/resumes/successors all 0

Note: the early factory return carries `blocked_reasons` in the in-memory
lifecycle result; the durable campaign report stores the terminal cause as
`SAFE_STOP_PREFLIGHT_FAILED` without re-embedding the reasons array. The exact
reason string above is reconstructed from the production preflight owner plus the
observed argument path and is consistent with zero factory-run rows.

## Migration-050, integrity, and foreign keys

| Check | Result |
| --- | --- |
| Migration count | 50 |
| Migration head | `050_campaign_scheduler_ownership_scope.sql` |
| Migration-050 applied | yes |
| Copy method | SQLite backup API after owner connections closed |
| Journal mode | `delete` |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | empty |
| Evidence-only disposable DB | yes |
| Authoritative production DB used | no |

## Zero-network result

| Boundary | Result |
| --- | --- |
| Frozen transports | yes (Pump, secondary, snapshot/context fixtures) |
| `urllib.request.urlopen` patched call count | 0 |
| Packet-level capture | not claimed |
| Live provider / RPC / WebSocket | not used |

## Retry / restart / successor result

From preserved failure evidence and terminal safety:

| Action | Count |
| --- | --- |
| Automatic retries | 0 |
| Reruns | 0 |
| Restarts | 0 |
| Resumes | 0 |
| Successors | 0 |

## Locked-capability counts

| Surface | Count |
| --- | --- |
| Memory retrieval queries | 0 |
| Memory retrieval matches | 0 |
| Paper decisions | 0 |
| Paper positions | 0 |
| Paper trade events | 0 |
| Paper trade audits | 0 |
| Episode outcomes | 0 |
| Episodes | 0 |
| Memory windows | 0 |
| Token lifecycle events | 0 |
| Source failures | 0 |
| Active Scheduler jobs | 0 |
| Locked Scheduler jobs | 0 |

Longer windows, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits,
PnL, wallets, signing, funds, live providers, and paid APIs remain locked.

## Money-usefulness contribution

This composition is money-useful as a **negative proof with preserved evidence**:

- The secondary-discovery repair removed the previous false
  `MALFORMED_RESPONSE` / pre-lifecycle masking path; discovery and activation
  now succeed under the lawful frozen secondary contract.
- The next real blocker is isolated at the public operational lifecycle entry
  boundary: offline disposable composition cannot satisfy the operational
  persistent corpus preflight.
- Campaign acceptance still refuses unsafe incomplete memory growth, so no false
  `CAMPAIGN_PASS` was emitted and no downstream money-bearing capability unlocked.

## What remains blocked

- Exact public composition pass (two owned `WINDOW_15M` closes + `CAMPAIGN_PASS`)
- Any production repair inferred from this report
- Rerun of the exact composition without new authorization
- Authoritative live campaign authorization reuse
- Downstream locked capabilities listed above

## Functionality Risks / Setbacks / Efficiency Blockers

- Exact offline public composition currently collides with the operational
  persistent corpus preflight even after discovery/activation success.
- Public-command `AUTHORITATIVE_DB` patching does not rewrite the factory's
  `CANONICAL_PERSISTENT_DB` identity check, which can surprise harness authors.
- Compressed timing overrides (`3.0s` / `0.05s`) are compatible with the 15m-only
  duration gate but irrelevant until the corpus check is lawfully satisfied or
  the harness uses a committed proof-mode entry.
- Application-level urllib patching is not packet capture.
- No closeout or PASS is permitted while windows remain zero.

## Next permitted lane

A **separately authorized** lane may design and prove an exact offline public
composition lifecycle-entry contract that:

1. preserves the frozen secondary success path and disposable Migration-050
   boundary;
2. does not weaken factory preflight, six-unit accounting, Scheduler, Source
   Governor, schema, or migrations;
3. either uses a lawful proof-mode lifecycle entry for offline composition or
   another explicitly authorized corpus identity strategy that never writes the
   live authoritative database;
4. requires a new explicit authorization before any second exact composition.

This lane grants no repair, no rerun, no closeout, and no capability unlock.

## Stop condition

This document is the sole deliverable of the post-composition classification
lane. Source, tests, fixtures, Scheduler, accounting, Source Governor, schema,
migrations, runtime behavior, comparison worktree, and preserved evidence were
not modified. The exact composition was not rerun.
