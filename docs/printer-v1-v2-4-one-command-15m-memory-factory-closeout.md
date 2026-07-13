# V2-4 One-Command 15m Memory Factory Closeout

## Status And Verdict

`ONE_COMMAND_15M_FACTORY_SAFE_BLOCK`

V2-4 implemented the approved V2-3 proof-only orchestration surface and ran
exactly one unassisted bounded live proof. The command preserved every lock and
stopped with zero running jobs, but the proof did not produce a valid 900-second
evidence window. V2-5 must not begin.

The live blocker is narrow and measured: close jobs were scheduled 900 seconds
from orchestration start, while governed discovery completed before the opening
snapshots. The resulting exact snapshot intervals were `897.284826` and
`897.948195` seconds. Lane Q correctly rejected both as
`elapsed_seconds_below_900`; neither became clean memory.

No implementation change or second live attempt was made after the proof
started.

## Approved Design Implemented

The implementation adds only the V2-3-approved pieces:

- migration `028_memory_factory_run_ledger.sql` with durable run and step
  ledgers;
- proof-only orchestrator
  `printer_v1.operator_cli.one_command_15m_factory`;
- CLI `printer-run-one-command-15m-memory-factory`;
- Central Scheduler-owned snapshot and window-close dispatch;
- exact selected mint/pair validation at snapshot persistence;
- final DB-backed report generation and report-only replay;
- focused V2-4 tests.

The command accepts no token list or mint. It invokes existing governed
GeckoTerminal discovery, consumes qualified seeded-random selection, permits
at most two selected active tokens, and supports only `WINDOW_15M` in
`PROOF_ONLY` mode. Timed snapshot and close work is represented by Central
Scheduler jobs. Source calls use existing Source Governor execution. No source,
selection, memory-quality, or scheduler architecture was redesigned.

Snapshot persistence now accepts the already-selected exact pair address and
tracking lane. A DexScreener response for the right mint but a different pair
fails closed instead of silently selecting the highest-liquidity pair.

## Deterministic Test Proof

New focused suite:

`python -m pytest tests/test_v2_4_one_command_15m_factory.py -q`

Result: `6 passed`.

It proves:

- unsupported-window and proof-mode rejection;
- empty qualified pool safe stop;
- Source Governor request recording and Central Scheduler dispatch;
- exact token/pair fail-closed behavior;
- bounded duration cleanup and zero running jobs;
- clean/partial gating without forced clean memory;
- terminal report completeness;
- report-only replay with zero new source/evidence rows;
- zero retrieval and financial deltas.

Existing focused regression slice:

`python -m pytest tests/test_post_rc_lane_e2m_snapshot_persistence.py tests/test_post_rc_lane_e2o_memory_window_close.py tests/test_post_lane10_lane_k_e2z_pipeline_wiring.py tests/test_post_rc_controlled_discovery_cycle.py tests/test_phase35_scheduler_single_tick_executor.py -q`

Result: `305 passed` with one pre-existing pytest cache warning.

The active Python environment could not reinstall the editable package because
`setuptools.build_meta` was unavailable and sandboxed pip could not fetch build
dependencies. The newly declared CLI function imported and rendered its help
successfully through the source checkout. The live proof invoked that exact CLI
entry function directly; no dependency or packaging workaround changed Printer
code.

## Live Proof Setup

- Run ID: `344a28c1-36e8-4779-b6e5-13a7fe9b596b`
- Proof DB: `data/printer_v1_v2_4_proof_20260713.sqlite3`
- Backup: `data/printer_v1_v2_4_proof_20260713.backup.sqlite3`
- DB mode: `PROOF_ONLY`
- Window: `WINDOW_15M`
- Started: `2026-07-13T09:28:51.015521+00:00`
- Finished: `2026-07-13T09:43:53.891668+00:00`
- Discovery source plan: GeckoTerminal new pools plus trending pools
- Discovery requests: 2 maximum, 2 attempted, 2 complete, 0 failed
- Automatic retries: 0
- Selected-token maximum: 2
- Total-duration cap: 1,200 seconds
- Selection seed: `343daf45084ec436174043b5d1c2ae68`
- Eligible pool size: 24
- Selection batch: `658277f1-d94c-42c4-a3c9-b75903c75f17`

The command selected autonomously:

| Lane | Token mint | Pair address |
|---|---|---|
| `TRACK_FAST` | `2WpkA1JfHSbxq3hgrnE8PRtPabXgpKDXgKoSxdyHPk2C` | `3hF4XuoNY6Kf87mXi1yPWjkuVNVNsFWNdcRLWeMPBuwy` |
| `TRACK_NORMAL` | `4YpANZ4urF4DW2QtCMP54kZQkhsisypsstJbasQapump` | `6wLSrSbJQdJqYoxQqujVCg2qLKx4HYC6wb3GAh5o3zEb` |

No mint list, manual candidate insertion, fixture, retry, or post-start code
change was used.

## Governed Source And Scheduler Results

Source request IDs `1119-1135` and response IDs `1072-1088` were created in
the isolated proof DB only:

- request `1119` / response `1072`: GeckoTerminal new-pool discovery;
- request `1120` / response `1073`: GeckoTerminal trending-pool reference;
- requests `1121-1135` / responses `1074-1088`: exact-mint DexScreener pair
  market snapshots.

All 17 requests and responses were `COMPLETE / CLEAN_DATA`; source failures
were zero.

The orchestrator created 15 run steps: ten total attempts for the TRACK_FAST
token and five total attempts for the TRACK_NORMAL token, with each close job
owning the final governed snapshot attempt. All 15 run-step scheduler jobs
succeeded. The two original discovery handoff jobs were cancelled rather than
executed; no scheduler job remained running or locked.

## Window And Memory Result

| Window | Token/pair | Measured elapsed | Lane Q result | Stored state |
|---|---|---:|---|---|
| `157` | token `19`, pair `23` | `897.284826s` | blocked below 900s | `PARTIAL_MEMORY`, `DIRTY_MEMORY`, `do_not_train=1` |
| `158` | token `18`, pair `22` | `897.948195s` | blocked below 900s | `PARTIAL_MEMORY`, `DIRTY_MEMORY`, `do_not_train=1` |

The live result was therefore:

- clean memory: 0;
- blocked/partial windows: 2;
- new memory fingerprints: 0;
- new memories: 0;
- retrieval rows: 0 delta;
- paper and financial rows: 0 delta.

This is an honest safety outcome, but it does not satisfy the required real
900-second proof. The command's stored terminal stop reason was
`COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`; the V2-4 lane verdict is stricter
and remains `ONE_COMMAND_15M_FACTORY_SAFE_BLOCK`.

## Proof DB Deltas

| Table | Delta |
|---|---:|
| source requests | +17 |
| source responses | +17 |
| source failures | 0 |
| discovery candidates | +2 |
| selection batches | +1 |
| selection batch items | +24 |
| tracking queue | +2 |
| scheduler jobs | +17 |
| token snapshots | +15 |
| memory windows | +2 |
| run ledger | +1 |
| run-step ledger | +15 |
| memory fingerprints | 0 |
| retrieval queries/matches | 0 |
| paper decisions | 0 |
| paper positions | 0 |
| paper trade events/audits/reports | 0 |

## Report-Only Replay

The completed run was replayed once using the report-only path.

- proof DB SHA-256 before and after:
  `4139c941643feaff206918d581b7233a0aa63ed90e9820d29bdd8230693c8233`;
- all inspected row counts unchanged;
- new source calls: 0;
- new evidence rows: 0.

This proves report replay idempotency for the completed run.

## Persistent DB And Lock Proof

Persistent DB: `data/printer_v1.sqlite3`.

SHA-256 before and after:
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.

The hash and inspected source, snapshot, memory, retrieval, decision, position,
trade, and audit counts were unchanged. Pre-existing persistent rows were not
treated as proof deltas.

No `WINDOW_1H`, 4h, 12h, or 24h path ran. No retrieval, paper decision,
BUY/SELL/HOLD, position, trade, audit, PnL, wallet, key, paid API, score, rank,
confidence, weight, embedding, or vector capability was added or activated.

## Remaining Blocker And Required Next Work

The next work must remain inside V2-4 as a narrow timing-origin repair and
second explicitly approved proof lane. It must schedule each token's close from
that token's durable first successful snapshot time, not orchestration start,
and must ensure the close snapshot is captured at or after the 900-second
boundary while retaining the 1,200-second total cap. It must add a deterministic
test proving discovery latency cannot shorten the measured evidence window.

No threshold may be weakened, no timestamp may be fabricated, and the existing
blocked windows must remain unchanged.

V2-5 remains blocked.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Current evidence | Required treatment |
|---|---|---|
| Window timer starts too early | Both live windows were about 897s | Anchor close scheduling to first durable snapshot |
| Terminal command status is broader than proof acceptance | Command reported completed while Lane Q blocked both windows | Keep honest per-window result and add proof-level acceptance reporting |
| Lane K scans historical proof-copy windows | Close reports are large and include prior windows | Preserve correctness; later narrow reporting to run-linked windows without changing memory rules |
| Editable CLI packaging unavailable in active Python | Local build backend missing | Repair environment separately; do not add runtime dependencies to Printer |
| Zero clean yield | Correct for this blocked proof | Never force clean memory; rerun only after explicit repair/proof approval |

## Final Conclusion

The V2-4 command, ledger, governed source path, scheduler dispatch, exact
identity protection, safe stop, final report, and replay boundary are
implemented and deterministically tested. The one live run preserved all locks
and persistent data. It did not prove a real 900-second window, so V2-4 is not
closed as pass.

Verdict: `ONE_COMMAND_15M_FACTORY_SAFE_BLOCK`.

Next recommended lane:

`V2-4.1 - Repair first-snapshot-anchored 15m close timing and run one new bounded proof`.
