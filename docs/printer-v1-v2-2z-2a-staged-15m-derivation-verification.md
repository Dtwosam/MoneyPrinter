# Printer V1 V2-2Z.2A Staged 15m Derivation Verification

Status: VERIFICATION ONLY

Verification verdict: `VERIFICATION_PASS_WITH_BLOCKERS`

V2-2Z.2A independently verified commit `bf36abb`:

`Implement V2-2Z.2 staged 15m price derivation`

This verification did not implement code, change tests, add migrations, mutate
persistent DB state, run live sources, activate scheduler/runtime, generate
memory, activate retrieval, create paper decisions, unlock BUY/SELL/HOLD,
create positions, create trades, create paper audits, or create PnL.

V2-3, V2-4, PumpPortal live transport, PumpSwap readiness, source expansion,
runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

## Source Stack Read

The verification used the active source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

Recent lane docs inspected:

- `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md`
- `docs/printer-v1-v2-2z-staged-native-15m-evidence-readiness-review.md`
- `docs/printer-v1-v2-2z-1-staged-price-change-15m-derivation-design.md`
- `docs/printer-v1-v2-2z-2-staged-price-change-15m-derivation-implementation-proof.md`
- `docs/printer-v1-v2-2x-3-t2-token-age-evidence-verification.md`
- `docs/printer-v1-v2-2y-bounded-live-t2-token-age-proof.md`

## Target Commit Verified

Target commit:

- `bf36abb Implement V2-2Z.2 staged 15m price derivation`

`git show --name-only --oneline --no-renames bf36abb` confirmed the expected
scope:

- `src/printer_v1/snapshots/staged_derivation.py`
- `src/printer_v1/snapshots/recorder.py`
- `tests/test_v2_2z1_staged_15m_price_derivation.py`
- `docs/printer-v1-v2-2z-2-staged-price-change-15m-derivation-implementation-proof.md`

No source adapters, parser files, selection-batch files, migrations,
memory/retrieval/paper/trading files, scheduler/runtime files,
wallet/private-key files, paid API dependency files, embedding/vector files,
or unrelated files were changed by the target commit.

## Design-Contract Comparison

`src/printer_v1/snapshots/staged_derivation.py` matches the V2-2Z.1 design
contract:

| Requirement | Verification result |
| --- | --- |
| `derive_price_change_15m()` is pure | PASS |
| Formula is `((price_end - price_start) / price_start) * 100` | PASS |
| Result rounded to 6 decimals | PASS |
| Interval band is 720-1080 seconds inclusive | PASS |
| Same non-null `token_id` required | PASS |
| Same non-null `pair_id` required | PASS |
| Same `source_name` required | PASS |
| Both snapshots require `source_status == "COMPLETE"` | PASS |
| Both snapshots require `data_quality_label == "CLEAN_DATA"` | PASS |
| `snapshot_quality_label` is not the main eligibility gate | PASS |
| `PARTIAL_SNAPSHOT` remains allowed | PASS |
| `DIRTY_SNAPSHOT`, `STALE_SNAPSHOT`, `MISSING_CRITICAL_FIELDS`, and `CONFLICTING_SNAPSHOT` rejected | PASS |
| Null price rejected | PASS |
| Zero/negative start price rejected | PASS |
| Invalid/missing timestamps rejected | PASS |
| Reversed/equal timestamps rejected | PASS |
| Extreme positive/negative memecoin moves allowed | PASS |
| Provenance includes required fields plus `derived_at` | PASS |
| Annotation uses `price_change_15m_source_kind = "DERIVED_STAGED_SNAPSHOT"` | PASS |
| Native source protection skips overwrite when source kind is `"NATIVE_SOURCE"` | PASS |

The implementation stores 17 provenance fields. The design listed the required
provenance shape and included `derived_at`; the implementation preserves all of
those fields.

## Recorder Hook Verification

`src/printer_v1/snapshots/recorder.py` has a minimal hook:

- imports `apply_staged_derivation`;
- inserts the snapshot row normally;
- captures `new_id = int(cursor.lastrowid)`;
- calls `apply_staged_derivation(connection, new_id, normalized)`;
- returns the same shape as before: `tuple[bool, int]`.

Verification findings:

- Hook runs after snapshot insert.
- Hook uses the same connection/transaction block as the insert.
- Return type remains unchanged.
- If no eligible pair exists, no update occurs.
- The update targets only the end snapshot row by `WHERE id = ?`.
- The start snapshot is not modified.
- `normalized_snapshot_payload_json` is parsed and merged with derivation keys,
  not replaced with a derivation-only object.
- No memory, retrieval, paper, trading, wallet, signing, or live source path is
  called from this hook.

## Volume/Txn Hard-Block Verification

The implementation derives only `price_change_15m`.

Confirmed:

- `volume_15m` is never derived.
- `txns_15m` is never derived.
- No `volume_5m * 3`.
- No `volume_1h / 4`.
- No `txns_5m * 3`.
- No `txns_1h / 4`.
- No 5m/1h/24h fallback into 15m fields.
- The `UPDATE` statement writes only `price_change_15m` and
  `normalized_snapshot_payload_json`.

## Eligible-Pair Query Verification

`find_eligible_snapshot_pairs()` verifies as follows:

- filters by same `token_id`;
- filters by same `pair_id` using `COALESCE`;
- filters by `captured_at` within the 720-1080 second range before the end
  snapshot;
- filters by source via
  `json_extract(normalized_snapshot_payload_json, '$.source_name')`;
- filters by `source_status = 'COMPLETE'`;
- filters by `data_quality_label = 'CLEAN_DATA'`;
- returns candidates sorted by closest interval to 900 seconds;
- tie-breaks by later `captured_at`;
- does not mutate DB;
- returns an empty list when the end timestamp is invalid or missing.

Risk notes:

- Source filtering depends on `source_name` being present in
  `normalized_snapshot_payload_json`, because `source_name` is not a dedicated
  `printer_token_snapshots` column.
- Captured-at SQL filtering uses lexicographic ISO timestamp comparison before
  Python-side parsing and sorting. This is safe for the current normalized
  `+00:00` timestamp format, but future mixed timestamp formats should be
  tested before widening the source set.
- Duplicate eligible starts are handled by closest-to-900 ordering and later
  start tie-break.

## Tests and Checks Run

Required focused tests:

- `python -m pytest tests/test_v2_2z1_staged_15m_price_derivation.py -q`
  - `66 passed`
- `python -m pytest tests/test_v2_2h3_field_normalization_fast_events.py -q`
  - `67 passed, 48 subtests passed`
- `python -m pytest tests/test_v2_2c_selection_batch.py -q`
  - `120 passed`
- `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q`
  - `82 passed`
- `python -m pytest tests/test_v2_2p_pair_age_context.py -q`
  - `67 passed`
- `python -m pytest tests/test_post_rc_controlled_discovery_cycle.py -q`
  - `8 passed`

Required focused total:

- `410 passed`
- `48 subtests passed`
- `0 failed`

Optional broader snapshot-related subset:

- `python -m pytest tests -q -k "snapshot or staged or recorder or v2_2z"`
  - `759 passed`
  - `1 failed`
  - `6208 deselected`
  - `175 subtests passed`

Optional subset failure:

- `tests/test_phase27_controlled_token_snapshots.py::Phase27ControlledTokenSnapshotTests::test_readiness_reports_controlled_snapshots`
- Expected `READY_CONTROLLED_SNAPSHOTS`
- Actual `BLOCKED`

This optional failure is an older Phase 27 readiness-label expectation. It was
not part of the required focused V2-2Z.2A gate. It is reported here honestly and
should be triaged separately if the operator wants the broad snapshot subset to
be green.

Warnings observed:

- Pytest emitted cache warnings about `.pytest_cache` already existing.
- The harness printed default local `gltest` configuration messages.

## Safety Confirmations

Confirmed:

- No implementation changes in this verification lane.
- No source code changed.
- No tests changed.
- No migrations added.
- No live source calls.
- No source adapter changes.
- No PumpPortal/PumpSwap activation.
- No Solana RPC / Helius calls.
- No scheduler/runtime execution.
- No memory generation.
- No retrieval activation.
- No paper decision creation.
- No BUY/SELL/HOLD unlock.
- No paper positions.
- No trade events.
- No paper trade audits.
- No PnL.
- No wallet/private-key/signing/live execution logic.
- No paid API dependency.
- No scoring/ranking/confidence/weighted logic.
- No embeddings or vectors.
- No `volume_15m` or `txns_15m` derivation.
- No 5m/1h/24h fallback into 15m fields.
- No pair age used as 15m evidence.

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| `volume_15m` remains unavailable | Intentional; requires native OHLCV source |
| `txns_15m` remains unavailable | Intentional; requires native OHLCV source |
| GeckoTerminal OHLCV 15m native source not wired | Future lane |
| Long-term typed provenance table not implemented | Deferred; JSON annotation is current approved interim |
| Optional broad snapshot subset has one historical Phase 27 readiness failure | Needs separate triage if broad subset is required |
| Memory generation remains paused | Intentional |
| Retrieval remains locked | Intentional |
| Paper decisions remain locked | Intentional |
| BUY/SELL/HOLD remain locked | Intentional |
| Positions/trades/audits/PnL remain locked | Intentional |
| V2-3 remains paused | Intentional |

## Final Verdict

`VERIFICATION_PASS_WITH_BLOCKERS`

V2-2Z.2 correctly implements the approved staged `price_change_15m` derivation
contract. The recorder hook is minimal, transactional with the insert, and
updates only the new end snapshot. The pure derivation uses the approved
formula, interval tolerance, quality gates, provenance annotation, native-source
protection, and hard blocks on `volume_15m` and `txns_15m`.

The required focused tests all pass. The optional broad snapshot subset exposes
one older Phase 27 readiness-label failure that should not be hidden, but it is
separate from the V2-2Z.2A focused verification gate.

## Exact Next Recommended Lane

`V2-2Z.3 - Staged 15m Derivation Coverage Audit`

V2-2Z.3 should measure how often staged derivation fills
`price_change_15m` in existing governed snapshot data, without adding new code,
running live sources, generating memory, activating retrieval, creating paper
decisions, or unlocking any financial path.

V2-3 remains paused.
