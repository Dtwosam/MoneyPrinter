# Printer V1 V2-9.8B C12-C14 Durable Cleanup Timestamp and Replay Reconstruction Repair

Date: 2026-08-01

Lane: `V2-9.8B C12-C14 Durable Cleanup Timestamp and Replay Reconstruction Repair`

Repository: `MoneyPrinter`
Branch: `agent/v2-9-8b-c12-c14-durable-cleanup-replay-reconstruction-repair`

This is a narrow implementation and disposable-test lane. No bounded proof was
run. It repairs only the three blockers raised by the repeat independent
read-only C1-C15 conformance review
(`docs/printer-v1-v2-9-8b-c1-c15-repeat-independent-read-only-conformance-review.md`,
findings F1, F2, F3).

## Commit boundary

- Required and confirmed starting HEAD:
  `780fabfc815026243bc5ad9ab3e0f13e86ae05d8`.
- The branch and starting HEAD were confirmed before any edit. On first attempt
  the working copy was on the predecessor branch at
  `780496423926f70d9904196bfe391327e09b8370` and the required HEAD did not exist;
  the lane stopped and the operator fetched the correct baseline before this
  repair began.
- Ending HEAD: the single lane commit containing this report; its exact pushed
  commit ID is recorded by `git rev-parse HEAD` in the final handoff. A Git
  commit cannot embed its own resulting object ID.

## No schema change or new owner required

The repair is implementable on the accepted schema baseline with the existing
owners. No migration, evidence owner, report owner, runner, Scheduler, or source
path was added. Therefore
`V2_9_8B_C12_C14_DURABLE_CLEANUP_REPLAY_REPAIR_BLOCKED_DESIGN_AMENDMENT_REQUIRED`
does not apply.

## Files changed

- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/campaign_supervision.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_8b_c12_c14_durable_cleanup_timestamp_and_replay_reconstruction_repair.py` (new)
- `tests/test_v2_9_8b_full_run_wiring_integration.py` (overridable lease-lock hook only)
- `docs/printer-v1-v2-9-8b-c12-c14-durable-cleanup-timestamp-and-replay-reconstruction-repair.md` (new)
- `docs/printer-v1-v2-9-8b-c12-c14-authorization-marker-and-lease-evidence-conformance-repair.md` (factual addendum + corrected `ensure_ascii` statement)

No schema or migration file changed. Neither independent review file was
rewritten or erased.

## 1. Durable cleanup timestamp flow (F1)

The cleanup evidence, report, and gate now explicitly carry and require the
durable cleanup completion timestamp, not only a caller-carried
`cleanup_completed=True`.

Flow:

1. `cleanup_campaign_supervision()` terminalizes owned work, releases the exact
   lease-lock, persists `cleanup_completed_at` and `lease_released_at`, then
   performs a durable read-back of the exact supervision row and returns those
   durable persisted timestamps. It never trusts the local timestamp variable;
   the durable row (with `COALESCE` preserving a prior idempotent release) owns
   the truth.
2. `load_cleanup_lease_evidence()` reads `durable_cleanup_completed_at` and
   `lease_released_at` from the exact durable supervision row keyed by
   `(supervision_id, campaign_id, configuration_id, run_id)`.
3. `build_full_run_terminal_report()` exposes `durable_cleanup_completed_at` as
   an explicit `terminal_safety` field beside `lease_released_at`. It invents no
   timestamps.
4. `evaluate_campaign_acceptance_gate()` adds three checks — all fail-closed:
   - `durable_cleanup_completion_timestamp_present` — non-empty durable
     `cleanup_completed_at`;
   - `durable_lease_release_timestamp_present` (already present) — non-empty
     `lease_released_at`;
   - `durable_cleanup_and_release_timestamps_valid` — both parse as timezone-aware
     ISO-8601 and the release time is never before cleanup completion.
   The field is also added to the `canonical_report_complete` presence list.
5. The single canonical owner of the timestamp law is
   `parse_durable_timestamp()` / `durable_cleanup_release_timestamps_valid()` in
   `campaign_full_run_accounting.py`. A non-string, empty, malformed, or
   timezone-naive value returns `None`; a lease released before cleanup
   completion is rejected.

Because the timestamp source is the durable supervision row (not a
caller-supplied value), the gate requires actual durable cleanup completion. A
schema `CHECK` additionally guarantees a `TERMINAL` supervision row can never
durably hold a null `cleanup_completed_at`, so the gate law is defense-in-depth
above an already-durable invariant.

Initial acceptance and public replay apply the identical requirement: replay runs
the same `evaluate_campaign_acceptance_gate()` on the reconstructed report and,
in addition, requires the exact durable supervision row to satisfy
`durable_cleanup_release_timestamps_valid()` and to equal the report-carried
`durable_cleanup_completed_at` and `lease_released_at`.

## 2. Shared canonical marker-hash owner (F2)

The authoritative marker hashing contract is preserved and unchanged:

- `canonical_campaign_evidence_json()` — sorted keys, compact separators,
  `ensure_ascii=True`;
- `campaign_evidence_sha256()` — SHA-256 of those bytes.

Creation (`operational_memory_factory_command._create_campaign_command`
and `campaign_supervision.build_invocation_marker_payload`), acceptance
(`evaluate_campaign_acceptance_gate`), and the finalizer all already computed
authorization and invocation marker digests through `campaign_evidence_sha256()`.
Only the public `report_only()` replay path recomputed marker digests with a
local `json.dumps(..., ensure_ascii=False)` serializer. That replay-local marker
hashing is removed: replay now computes `expected_authorization_hash` and
`expected_invocation_hash` through `campaign_evidence_sha256()`. The owner /
action-local / report-body digests keep their own local `ensure_ascii=False`
canonical form because the finalizer hashes them the same way — only the two
marker digests moved to the canonical owner.

The canonical format was not changed to match replay; replay was changed to use
the canonical owner. A valid non-ASCII lease-lock path (carried inside the
invocation marker's `lease_lock_path`) now hashes identically at creation,
acceptance, and replay. The predecessor report's inaccurate `ensure_ascii=False`
statement is corrected and annotated in its addendum.

## 3. Independent factory-config reconstruction flow (F3)

Public replay no longer assigns durable evidence from
`full_identity["factory_config_hash"]`. It queries the exact factory-run owner:

```sql
SELECT run_id, config_hash FROM printer_memory_factory_runs WHERE run_id = ?
```

using the exact `factory_run_id`. Replay requires:

- exactly one matching factory-run row;
- non-empty durable `config_hash`;
- exact factory-run identity (`row.run_id == factory_run_id`);
- durable `config_hash` equals the report identity's `factory_config_hash`;
- durable `config_hash` equals the separate factory-config field in the marker /
  report evidence (`authorization_and_invocation.factory_config_hash`);
- authorization and invocation marker digests remain distinct from it.

The durable value is assigned into the reconstruction (`durable_markers`) only
after validation, from the durable owner — never copied from report JSON before
comparison. Replay blocks on a missing factory row, multiple or wrong factory
identity, null/empty config hash, report/durable mismatch, or marker/factory hash
mismatch, all as `FULL_RUN_DURABLE_RECONSTRUCTION_MISMATCH`.

## C12-C14 completion law

| ID | Required repaired law | Positive evidence | Fail-closed evidence | Status |
| --- | --- | --- | --- | --- |
| C12 | One canonical report is backed by durable owners, including durable cleanup completion and the durable factory configuration hash | Real disposable coordinator path reaches `CAMPAIGN_PASS` only with a non-empty tz-aware durable `cleanup_completed_at`, `lease_released_at` no earlier than it, and a factory-config field backed by the exact factory-run row | Null/malformed/naive/inverted durable timestamps, or a report-carried factory-config hash diverging from `printer_memory_factory_runs.config_hash`, block | PASS |
| C13 | Lease truth is actual and durable; the durable cleanup timestamp is mandatory at PASS | Literal cleanup/release truth plus a durable, parseable, tz-aware `cleanup_completed_at` and an ordered `lease_released_at`, with absent lock and zero active/locked residue | Missing/`None`/false/non-boolean lease truth, or an invalid durable cleanup/release timestamp, block | PASS |
| C14 | Public exact replay reconstructs persisted marker, cleanup, and factory-config truth read-only through one canonical hash owner | Replay returns `REPLAYED` with zero source/Scheduler/write counters and unchanged disposable DB mtime; a valid non-ASCII lease-lock path replays identically | Replay-local marker canonicalization drift, a report-carried factory-config hash, missing/empty durable factory config, or an invalid durable cleanup/release timestamp block | PASS |

## Exact commands and results

All databases were disposable temporary SQLite databases created by the wiring
fixture (`tempfile.TemporaryDirectory`). Transports were injected fixtures. No
provider, RPC, WebSocket, network discovery, operational campaign, authoritative
memory operation, migration application, or public runtime campaign ran. The
authoritative database `data/printer_v1.sqlite3` was never opened.

```text
.venv/bin/python -m py_compile \
  src/printer_v1/operator_cli/campaign_full_run_accounting.py \
  src/printer_v1/operator_cli/campaign_supervision.py \
  src/printer_v1/operator_cli/operational_memory_factory_command.py \
  tests/test_v2_9_8b_c12_c14_durable_cleanup_timestamp_and_replay_reconstruction_repair.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py
Result: exit 0, no output.

.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_c12_c14_durable_cleanup_timestamp_and_replay_reconstruction_repair.py
Result: 10 passed in 4.81s.

.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_c12_c14_durable_cleanup_timestamp_and_replay_reconstruction_repair.py \
  tests/test_v2_9_8b_c12_c14_authorization_marker_lease_evidence_conformance_repair.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py \
  tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py \
  tests/test_v2_9_7d_6b_5_operational_lease_safe_stop.py \
  tests/test_v2_9_7d_7a_abstract_command_surface.py
Result: 163 passed, 33 subtests passed in 44.47s.

.venv/bin/python -m pytest -q --disable-warnings \
  tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py \
  tests/test_v2_4_one_command_15m_factory.py \
  tests/test_v2_9_8b_operational_factory_active_path_restoration.py \
  tests/test_v2_9_8b_post_handoff_terminal_compensation.py \
  tests/test_v2_9_8b_restored_factory_source_compatibility_reset.py \
  tests/test_v2_9_7e_46b_2_source_accounting.py \
  tests/test_v2_9_8b_2_holder_budget_supervision_repair.py
Result: 72 passed in 22.77s.
```

### Focused proof matrix (new module)

| # | Test | Proves |
| --- | --- | --- |
| 1 | `test_null_durable_cleanup_completed_at_blocks` | Null durable `cleanup_completed_at` cannot reach Campaign PASS (gate law) |
| 2a | `test_malformed_cleanup_timestamp_blocks` | Malformed durable cleanup timestamp blocks via full finalize path |
| 2b | `test_timezone_naive_cleanup_timestamp_blocks` | Timezone-naive durable cleanup timestamp blocks |
| 3 | `test_release_before_cleanup_completion_blocks` | `lease_released_at` earlier than cleanup completion blocks |
| 4 | `test_valid_durable_cleanup_and_release_timestamps_pass` | Valid durable cleanup + release timestamps pass |
| 5 | `test_non_ascii_lease_lock_path_replays_with_identical_digest` | A valid non-ASCII lease-lock path yields an identical invocation digest at creation, acceptance, and replay; replay returns `REPLAYED` with zero side effects; the rejected `ensure_ascii=False` serializer would have diverged |
| 6 | `test_tampered_report_factory_config_hash_blocks_replay` | Replay blocks when only the report-carried factory config hash is changed and all report/body hashes are recomputed |
| 7 | `test_missing_factory_run_row_blocks_replay` | Missing factory-run row blocks replay |
| 8 | `test_empty_durable_factory_config_hash_blocks_replay` | Missing/empty durable factory `config_hash` blocks replay (`config_hash` is `NOT NULL`, so the missing case is the empty owner value) |
| 9 | `test_exact_replay_zero_side_effects_and_unchanged_mtime` | Exact replay returns `source_calls=0`, `scheduler_runtime_calls=0`, `database_writes=0`, and unchanged disposable DB mtime |

The pre-existing, unrelated failure
`tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestMigrationDiscoverySleepDoesNotHoldLock::test_settle_sleep_releases_write_transaction`
(`AttributeError: module 'printer_v1.discovery.direct_migration_discovery' has no
attribute 'release_write_transaction'`) was confirmed to fail identically on the
starting HEAD via `git stash`; it is outside this lane's scope (discovery, not
campaign supervision/accounting) and was not touched.

## Money-usefulness contribution

This repair prevents a memory-production run from being certified before durable
cleanup completion is proven, prevents a platform/path-dependent false replay
failure for valid non-ASCII lease-lock paths, and prevents public replay from
silently trusting a report-carried factory-configuration field. It strengthens
the trustworthiness of evidence that may later inform paper-only analysis. It
adds no retrieval, decision, trade, money movement, or profitability capability.

## What improved

- Initial Campaign PASS now requires a non-empty, parseable, timezone-aware
  durable `cleanup_completed_at` and a `lease_released_at` that never precedes it,
  read from the exact durable supervision row.
- Unified cleanup returns the exact persisted `cleanup_completed_at` and
  `lease_released_at` after a durable read-back.
- Creation, acceptance, and replay share exactly one marker canonicalization
  owner (`campaign_evidence_sha256`); the replay-local `ensure_ascii=False` marker
  serializer is gone.
- Public replay independently reconstructs `factory_config_hash` from
  `printer_memory_factory_runs.config_hash` for the exact `factory_run_id`.
- The predecessor report's inaccurate `ensure_ascii=False` statement is corrected.

## What remains locked

`data/printer_v1.sqlite3`; migration 050 application to that database; bounded or
live proof; provider/RPC/WebSocket/source execution; discovery or an operational
campaign; authoritative memory generation or promotion; WINDOW_1H/4H/12H/24H;
retrieval; paper decisions; BUY/SELL/HOLD; positions, trades, audits, PnL;
wallets, signing, private keys, real funds, live execution; paid APIs; scoring,
ranking, confidence, weighting, embeddings, and vectors.

## Proof still required

This lane is implementation plus disposable verification only. A repeat
independent read-only C1-C15 conformance review is still required. This PASS does
not authorize bounded proof or a campaign.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Impact | Disposition |
| --- | --- | --- |
| Durable-null cleanup timestamp is unreachable for a TERMINAL row | The null-timestamp negative cannot be constructed by mutating a real terminal row (a schema `CHECK` forbids it). | The gate law is proven directly against `evaluate_campaign_acceptance_gate()` on a real PASS report with the durable field nulled; the malformed/naive/inverted negatives are proven end-to-end. |
| Final commit self-reference | The report cannot contain the object ID of the commit that contains it. | Exact ending HEAD is recorded after commit and push in the final handoff. |
| Missing-factory and empty-config negatives copy the disposable DB | FK references and the `NOT NULL config_hash` column prevent in-place deletion/nulling on the live disposable DB. | Negatives operate on a `shutil.copy2` of the disposable DB, with FK enforcement off, and use an empty durable `config_hash` for the missing case. |
| Wiring fixture gained an overridable lease-lock hook | A shared test fixture changed. | The hook keeps the exact prior ASCII default; only the new non-ASCII subclass overrides it, and the full wiring suite still passes. |
| Pre-existing unrelated discovery test failure | One repository test fails independently of this lane. | Confirmed failing on the starting HEAD; out of scope; not modified. |
| Full repository suite not run | Unrelated repository behavior was not surveyed. | The requested focused and nearest affected matrices passed with no shared architectural regression, so scope was not expanded. |

## Verdict

`V2_9_8B_C12_C14_DURABLE_CLEANUP_TIMESTAMP_AND_REPLAY_RECONSTRUCTION_REPAIR_PASS`

This PASS authorizes only another independent read-only C1-C15 conformance
review. It does not authorize bounded proof, a campaign lane, merge, or tag.
