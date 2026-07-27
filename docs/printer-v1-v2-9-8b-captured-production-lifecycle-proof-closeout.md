# Printer V1 V2-9.8B.13 — Captured Production Lifecycle Proof Closeout

## Verdict

```text
V2_9_8B_13_CAPTURED_PRODUCTION_LIFECYCLE_PROOF_PASS
```

The retained first-attempt `PILOT_INPUT_READY` handoff has been exercised
through the repaired post-selection lifecycle on a disposable copy with
fixture-only collection. The existing operational branch created exactly one
`OPERATIONAL_PERSISTENT` factory run, created and completed bounded
`WINDOW_15M` work for both captured mints, closed terminally with no active
work, and preserved every locked capability.

No production command ran. No live source was fetched. No code was changed.
The authoritative database and retained campaign artifacts were read only.

## Baseline and proof inputs

| Item | Value |
|---|---|
| Repository HEAD at starting gate | `91da8238c5b02eb7ab87354ac24f45b36fcf8471` |
| Tracked tree at starting gate | clean |
| Disposable source | retained pre-second-attempt backup from `20260727T010656Z-0a54a31b6f2d` |
| Migration count in source | 44 |
| Retained readiness ID | `20260727T001520Z-d513e21260b5-campaign-run:20260727T001520Z-d513e21260b5-cycle:pilot-input` |
| Retained bundle hash | `1b654626a547712c47bf9863784212c7d1fb8d02eadd567b7d38c6cd13a84212` |
| Captured selection batch | `origin-activated:20260727T001520Z-d513e21260b5-cycle` |
| Collection | injected deterministic fixtures only |
| Clock | injected deterministic clock; preserved 900-second window semantics |
| Mode exercised | `proof_mode=False`, `operational_persistent_mode=True` |

The disposable harness asserted before lifecycle entry that the retained bundle
was `PILOT_INPUT_READY`, contained the exact two mints, and matched the exact
two selected mint/pool identities in the retained origin-activated batch.

The operational canonical-path guard was redirected only to the disposable
copy so the repaired production-mode database branch could be exercised
without writing the authoritative corpus. All source adapter factories were
injected fixtures; the default live builders were not reached.

## Captured identities

| Mint | Exact PumpSwap pool | Tracking lane |
|---|---|---|
| `UUdfUfhkqWEQK9wqADgQTQSbE4qpNkNaeCZdjPPpump` | `7PZL3Fo1bHSkKiSymZsRHjhX4swn1n9WHvupQ4qQcnFR` | `TRACK_NORMAL` |
| `7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump` | `GocsVH4qcQfPsHqgCDiZPWRmq1Q1FBZn2Qv7BVKbgEix` | `TRACK_NORMAL` |

Identity continuity passed from readiness bundle to retained selection batch,
factory selection, work steps, snapshots, and window close.

## Operational factory lifecycle result

| Check | Result |
|---|---|
| Factory run ID | `43c63b49-947c-4dd2-b00c-6cd0aaf64f79` |
| Factory `db_mode` | `OPERATIONAL_PERSISTENT` |
| Factory `window_kind` | `WINDOW_15M` |
| Factory terminal status | `COMPLETED` |
| Stop reason | `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED` |
| Selected tokens | 2 exact retained identities |
| Work steps | 18 total: 16 `SNAPSHOT`, 2 `WINDOW_CLOSE` |
| Step result | all 18 `SUCCEEDED` |
| Fixture snapshot calls | 18; both mints observed |
| Memory windows | 2, both `WINDOW_15M` |
| Longer windows | 0 |
| Pending/running factory steps after close | 0 |
| Active Scheduler jobs attributable to run | 0 |
| SQLite integrity | `ok` |
| Foreign-key violations | 0 |

This proves the repaired migration-044 factory insert and the lifecycle beyond
that insert. It is not merely a schema-insert unit proof: both selected tokens
were scheduled, collected, closed, persisted, reconciled, and terminalized.

## Honest memory outcome

Both fixture-driven 15m windows closed as:

```text
memory_quality_label = DIRTY_MEMORY
data_quality_label = MISSING_CRITICAL_DATA
```

That is a valid proof of lifecycle mechanics and fail-closed memory quality.
The lane did not convert incomplete fixture context into clean memory and did
not claim money usefulness from a synthetic outcome.

## Terminal safety and locked capabilities

The factory's forbidden deltas were all zero:

| Locked table | Delta |
|---|---:|
| `printer_memory_retrieval_queries` | 0 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 0 |

The disposable source contained two historical paper-decision rows from prior
repository history; before/after counts remained exactly 2. Positions, trade
events, and trade audits remained exactly 0. No BUY, SELL, HOLD, position,
trade, audit, PnL, retrieval, wallet, signing, fund movement, paid API, scoring,
ranking, confidence/weighted logic, embedding/vector, retry, restart, successor,
or live-execution capability was activated.

## Failed-selection residue conclusion

The companion read-only audit
`docs/printer-v1-v2-9-8b-failed-selection-residue-audit.md` proves:

1. both captured mints remained graduated and `LIQUIDITY_PROVEN`;
2. neither had market-floor cooldown, selection-rotation state, STNP rejection,
   or lifecycle cooldown/archive state;
3. both explicit token/pair cooldown checks passed; and
4. the second attempt omitted them solely because its seed-specific six-row
   refresh batch filled with two new latest and four other persisted rows.

Therefore no failed-selection residue defect was proven and no code change was
made.

## Focused tests and checks

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_10_post_selection_lifecycle_integrity.py \
  tests/test_v2_9_8b_5_7_discovery_productivity.py \
  -q
```

Result: **22 passed in 12.06s**.

Additional bounded checks:

- clean exact-HEAD starting gate;
- read-only SQLite trace of registry, floor, selection, STNP/rotation,
  cooldown, tracking, campaign, and second-attempt state;
- deterministic read-only replay of the six-candidate refresh composition;
- disposable operational lifecycle proof with fixture adapters;
- post-proof SQLite integrity and foreign-key checks;
- locked-table before/after and factory forbidden-delta checks;
- repository diff/status inspection.

No broad suite was run.

## Files changed

| File | Role |
|---|---|
| `docs/printer-v1-v2-9-8b-failed-selection-residue-audit.md` | read-only residue causality audit |
| `docs/printer-v1-v2-9-8b-captured-production-lifecycle-proof-closeout.md` | this proof closeout |

No Python, migration, runtime, test, configuration, or production-data file was
changed.

## What was not touched

- production execution and authoritative database writes;
- live-source transport;
- Source Governor or Central Scheduler policy;
- source ceiling 45, `$3,000` floor, or two-token rule;
- 5m support and 1h/4h/12h/24h activation policy;
- retrieval or financial capability locks;
- tags, remotes, and pushes.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
|---|---|
| Captured lifecycle proof uses fixture collection | mechanics proven; current live market/source behavior not asserted |
| Both fixture outcomes were dirty | correct fail-closed result; no clean-memory growth claimed |
| Bounded six-row refresh can omit proven persisted rows | efficiency limitation documented; no defect repair authorized |
| Historical failed campaign residue remains in authoritative corpus | harmless to eligibility; intentionally not rewritten |
| Retained bundle is expired | evidence input only; never reused as live production authorization |

## Pass/fail status and next recommendation

```text
PASS — V2-9.8B.13 captured lifecycle proof is complete.
```

Next recommended action: operator review of this closeout against the active
V2-9.8B lane. Do not infer authorization for another production run, V2-10,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
