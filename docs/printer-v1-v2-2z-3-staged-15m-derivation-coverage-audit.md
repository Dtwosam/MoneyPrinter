# Printer V1 V2-2Z.3 Staged 15m Derivation Coverage Audit

Status: AUDIT ONLY

Audit verdict: `AUDIT_COMPLETE_WITH_BLOCKERS`

This lane measured whether staged `price_change_15m` derivation is currently
useful on the existing operator DB. It did not implement code, edit tests, add
migrations, run source fetching, call `apply_staged_derivation`, create temp
tables in the operator DB, mutate the DB, generate memory, activate retrieval,
create paper decisions, unlock BUY/SELL/HOLD, create positions, create trades,
create paper audits, or create PnL.

V2-3, V2-4, PumpPortal/PumpSwap, source expansion, runtime/scheduler, memory
generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, and PnL remain paused.

## Source Stack Read

Required source documents checked:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2z-2a-staged-15m-derivation-verification.md`
- `docs/printer-v1-v2-2z-2-staged-price-change-15m-derivation-implementation-proof.md`
- `docs/printer-v1-v2-2z-1-staged-price-change-15m-derivation-design.md`

Current anchors:

- V2-2Z.1 design: `5a47ca6`
- V2-2Z.2 implementation: `bf36abb`
- V2-2Z.2A verification: `c238ad4`

## DB Path Inspected

Operator DB inspected:

`C:\Users\dtwof\Desktop\MoneyPrinter\data\printer_v1.sqlite3`

The DB was opened through SQLite read-only mode and `PRAGMA query_only = ON`.
Only `SELECT`/read-only inspection was used. No temp tables were created inside
the operator DB.

DB hash before audit:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

DB hash after audit:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

Hash unchanged: YES.

## Snapshot Coverage Summary

`printer_token_snapshots` row count:

| Metric | Count |
| --- | ---: |
| Total snapshot rows | 1,012 |
| Rows with `price_change_15m IS NOT NULL` | 0 |
| Rows with `price_change_15m IS NULL` | 1,012 |

Current actual `price_change_15m` coverage:

| Coverage metric | Value |
| --- | ---: |
| Filled rows | 0 / 1,012 |
| Filled percent | 0.00% |
| Missing rows | 1,012 / 1,012 |
| Missing percent | 100.00% |

## Derived/Native Annotation Counts

All rows currently lack `price_change_15m_source_kind` annotation.

| Annotation | All rows | Rows with `price_change_15m` |
| --- | ---: | ---: |
| `DERIVED_STAGED_SNAPSHOT` | 0 | 0 |
| `NATIVE_SOURCE` | 0 | 0 |
| Missing source-kind annotation | 1,012 | 0 |

This means the existing operator DB has not yet recorded either native 15m
evidence or staged derived 15m evidence.

## Source and Quality Context

| Field | Counts |
| --- | --- |
| Source name | `dexscreener`: 924; missing source name: 88 |
| Source status | `COMPLETE`: 1,012 |
| Data quality | `CLEAN_DATA`: 1,012 |
| Snapshot quality | `NULL`: 924; `PARTIAL_SNAPSHOT`: 88 |

The operator DB is mostly clean and complete at the stored source/data-quality
level. The main missing fields are not caused by failed source status or dirty
data quality in this audit.

## Potential Eligible-Pair Coverage

Eligibility contract used:

- same non-null `token_id`
- same non-null `pair_id`
- same `source_name` from `normalized_snapshot_payload_json`
- both `source_status = COMPLETE`
- both `data_quality_label = CLEAN_DATA`
- `PARTIAL_SNAPSHOT` allowed
- `DIRTY_SNAPSHOT`, `STALE_SNAPSHOT`, `MISSING_CRITICAL_FIELDS`, and
  `CONFLICTING_SNAPSHOT` rejected
- both `price_usd` values non-null
- start `price_usd > 0`
- end timestamp after start timestamp
- interval 720-1080 seconds inclusive

Potential coverage:

| Metric | Count |
| --- | ---: |
| Clean complete same-token/pair/source eligible snapshot pairs in 720-1080s | 1,918 |
| End snapshot rows with at least one eligible prior pair | 762 |
| Rows with `price_change_15m` and eligible prior pair | 0 |
| Rows that could potentially receive staged `price_change_15m` | 762 |
| Eligible rows still NULL | 762 |

Interpretation:

- Existing operator DB history already contains enough same-token/pair/source
  spacing to make staged derivation useful.
- Staged derivation has not been applied to existing rows.
- That is expected because this lane was read-only and because V2-2Z.2 added a
  post-insert hook, not a historical backfill.

## Missing-Reason Buckets

Rows with `price_change_15m IS NULL`: 1,012.

| Missing reason | Count | Example snapshot ids |
| --- | ---: | --- |
| Eligible prior exists but `price_change_15m` is still NULL | 762 | 106, 107, 108, 109, 110 |
| Prior snapshot too soon | 126 | 93, 95, 101, 102, 103 |
| Missing token/pair/source identity | 88 | 1, 2, 3, 4, 5 |
| Prior snapshot too late | 25 | 90, 91, 92, 94, 412 |
| No prior same token/pair/source snapshot | 11 | 89, 96, 97, 98, 99 |
| Not `CLEAN_DATA` / not `COMPLETE` | 0 | none |
| Missing price | 0 | none |
| Disqualifying snapshot quality | 0 | none |
| Timestamp problem | 0 | none |
| Unknown/other | 0 | none |

Main missing reason:

`Eligible prior exists but price_change_15m is still NULL`.

This is not a data-quality failure. It is a lifecycle/timing result: the
operator DB snapshot rows predate the V2-2Z.2 post-insert staged derivation
hook, and this audit was not allowed to backfill or mutate existing rows.

## Cadence Usefulness Result

Adjacent same-token/pair/source interval buckets:

| Adjacent interval bucket | Count |
| --- | ---: |
| Under 720s | 960 |
| 720-1080s | 6 |
| 1081-1800s | 0 |
| 1801-3600s | 3 |
| Over 3600s | 23 |
| Total adjacent intervals | 992 |

Although most adjacent intervals are under 720 seconds, the dense cadence still
creates many non-adjacent pairs inside the approved 720-1080 second band. The
audit found 1,918 eligible clean same-token/pair/source pairs and 762 end rows
that could potentially receive staged `price_change_15m`.

Cadence verdict:

`CADENCE_USEFUL_FOR_STAGED_15M_PRICE_DERIVATION`

The current snapshot cadence appears useful for staged point-to-point 15m price
change derivation, provided new snapshots are recorded after the V2-2Z.2 hook or
a future operator-approved backfill/audit lane is explicitly created.

## Timing Context

Latest snapshot in operator DB:

- Snapshot id: 1012
- Captured at: `2026-07-07T22:46:25.199279+00:00`
- Source: `dexscreener`
- `price_change_15m`: NULL

V2-2Z.2 implementation commit timestamp:

- `2026-07-09T21:53:39+01:00`

The inspected operator DB snapshot history ends before the staged derivation
implementation commit. This supports the conclusion that current NULL coverage
is expected for existing historical rows and does not prove the post-insert hook
is ineffective.

## Audit Question Answers

| Question | Answer |
| --- | --- |
| How many `printer_token_snapshots` rows exist? | 1,012 |
| How many rows have `price_change_15m IS NOT NULL`? | 0 |
| How many rows have `price_change_15m IS NULL`? | 1,012 |
| How many are `DERIVED_STAGED_SNAPSHOT`? | 0 |
| How many are `NATIVE_SOURCE`? | 0 |
| How many have missing source-kind annotation? | 1,012 |
| How many clean complete same-token/pair/source pairs exist within 720-1080s? | 1,918 |
| How many rows could potentially receive staged `price_change_15m`? | 762 |
| How many eligible rows still have NULL? | 762 |
| Main reason rows are still missing `price_change_15m`? | Existing operator DB rows predate the V2-2Z.2 post-insert hook; no backfill was allowed. |
| Is current cadence useful? | Yes, dense cadence creates many non-adjacent 720-1080s pairs. |
| Does this unlock A3 or V2-3? | No. |

## Safety Confirmations

Confirmed:

- Audit-only lane.
- Read-only operator DB inspection only.
- DB hash unchanged before/after.
- No DB writes.
- No temp tables created in the operator DB.
- No derivation/backfill call.
- No source fetching.
- No source adapter work.
- No runtime/scheduler work.
- No memory generation.
- No retrieval activation.
- No paper decisions.
- No BUY/SELL/HOLD unlock.
- No paper positions.
- No trades.
- No paper audits.
- No PnL.
- No wallet/private-key/signing/live execution logic.
- No paid API dependency.
- No scoring/ranking/confidence/weighted logic.
- No embeddings or vectors.
- No `volume_15m` derivation.
- No `txns_15m` derivation.

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| Current operator DB actual `price_change_15m` coverage is 0% | BLOCKING for live coverage claim |
| 762 existing rows appear eligible but remain NULL | Expected because no backfill was allowed and rows predate hook |
| Need post-Z.2 snapshot insert proof on operator/proof DB | Recommended next measurement |
| Native `volume_15m` unavailable | Still requires native OHLCV source |
| Native `txns_15m` unavailable | Still requires native OHLCV source |
| Native `price_change_15m` unavailable | Future OHLCV lane if needed |
| A3 remains blocked where token age is absent | Staged price change does not solve token-age evidence |
| V2-3 remains paused | Intentional |

## Does This Unlock A3 or V2-3?

No.

Staged `price_change_15m` can improve fast-event context and field
completeness when populated, but it does not unlock A3 by itself. A3 still
requires real `token_age_seconds` evidence. This audit also does not authorize
V2-3, memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, or PnL.

## Final Verdict

`AUDIT_COMPLETE_WITH_BLOCKERS`

The existing operator DB contains 1,012 token snapshots and 0 populated
`price_change_15m` values. It also contains strong evidence that staged
derivation is practically useful: 1,918 eligible clean same-token/pair/source
snapshot pairs and 762 end rows that could potentially receive staged
`price_change_15m`.

The main blocker is not cadence. The main blocker is that existing operator DB
rows predate the V2-2Z.2 post-insert hook, and this audit was not allowed to
backfill historical rows. Future value should be proven either by a fresh
post-Z.2 snapshot insert/coverage audit or by a separate explicitly approved
historical backfill design/proof lane.

## Exact Next Recommended Lane

`V2-2Z.4 - Fresh Post-Hook Staged 15m Insert Proof`

Recommended purpose:

- Use a proof DB or explicitly approved bounded operator flow.
- Insert or collect fresh governed snapshots after the V2-2Z.2 hook.
- Prove that new end snapshots receive `price_change_15m` automatically when an
  eligible 720-1080s prior snapshot exists.
- Preserve all locks: no memory generation, no retrieval, no paper decisions,
  no BUY/SELL/HOLD, no positions, no trades, no audits, no PnL.

V2-3 remains paused.
