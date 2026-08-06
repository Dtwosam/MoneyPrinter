# Printer V1 V2-9.8B WINDOW_15M Source-Request Scope Contamination Audit

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_CONTAMINATION_AUDIT_COMPLETE`

Root-cause classification:

`DURABLE_ATTRIBUTION_DEFECT`

Secondary reporting classification:

`TERMINAL_DETAIL_REPORTING_DEFECT`

This is an audit-only closeout. No production code, tests, database rows,
authorization packages, application evidence, provider calls, discovery,
Scheduler work, lifecycle work, or memory work were changed or executed.

## Baseline

| Item | Value |
| --- | --- |
| Baseline branch | `agent/v2-9-8b-window-15m-fresh-authorization-after-temporal-validation-repair` |
| Baseline full HEAD | `d99f5397d75b2032c2e8f563f3503502d62766d7` |
| Audit branch | `agent/v2-9-8b-window-15m-source-request-scope-contamination-audit` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` |
| Failed execution | `20260806T120233Z-5eb0d3b5f0eb` |
| First terminal cause | `LiveOperationalError:CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` |

## Authorization disposition

`V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` is permanently consumed because its
application marker was successfully created and its child process started.

Disposition:

`CONSUMED_CHILD_EXITED_NONZERO`

It must never be retried, resumed, restarted, rebound, regenerated, or used to
create a successor automatically.

## Failed-run evidence

Application evidence root:

`$HOME/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`

| File | SHA-256 |
| --- | --- |
| `application-marker.json` | `7c39f88e458135cde898fa7b380c0de3b7eb18cb629ef9b5086c6ca9b9c9b48d` |
| `git-provenance-manifest.json` | `bad5ff883e2ab5e604f2ed682dcf3abdb1d2b87c26fd831ae8a7eab7b3b1491e` |
| `wrapper-terminal.json` | `b272523950892466256c241d30bf97caec0bc893353ed825f76e09570e39f3e3` |
| `child-stderr.txt` | `60a6946b0f6b798d1d607a96baba5062d7892628339318cb725392e8fd163f00` |
| `child-stdout.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Run progression

The repaired temporal contract was reached successfully. The campaign progressed
through governed discovery/source execution and exact-market/reserve persistence,
then stopped at the pre-holder source-request reconciliation boundary.

Observed action-local source accounting:

- source requests: `18` (`1951`–`1968`)
- source responses: `11` (`1738`–`1748`)
- source failures: `7` (`213`–`219`)
- response/failure conservation: `18 = 11 + 7`

This proves that the terminal was not caused by a source request disappearing
between durable request creation and response/failure persistence.

The campaign did not reach:

- holder evidence collection;
- holder maturation creation;
- Scheduler lifecycle work;
- lifecycle activation;
- `WINDOW_15M` creation;
- memory generation or closeout.

Cleanup completed, the lease was released, and locked/pending/running Scheduler
counts were zero.

## Authoritative database after the failed attempt

| Field | Value |
| --- | --- |
| path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| size | `69046272` |
| SHA-256 | `0b4b2b40c817bfd09a796686a898ef1c788d438b412ef6aa789ce6596c2c7b80` |
| inode | `1230526` |
| mtime_ns | `1786017804315875344` |
| mutation status | `PROVEN_MIXED_INSERT_AND_UPDATE` |

The database must not be restored, rewritten, vacuumed, normalized, or rolled
back. The failed-run rows are authoritative evidence.

## Mutation ledger

Net-positive rows recorded by the failed attempt include:

| Table | Delta |
| --- | ---: |
| `printer_source_requests` | `+18` |
| `printer_source_responses` | `+11` |
| `printer_source_failures` | `+7` |
| `printer_discovery_reserve_layers` | `+41` |
| `printer_exact_market_states` | `+31` |
| `printer_discovery_exhaustion_certificates` | `+1` |
| `printer_memory_factory_campaigns` | `+1` |
| `printer_memory_factory_campaign_runs` | `+1` |
| `printer_memory_factory_campaign_cycles` | `+1` |
| `printer_memory_factory_campaign_supervision` | `+1` |
| `printer_memory_factory_campaign_configurations` | `+1` |

No holder, Scheduler, lifecycle-window, memory-window, retrieval, decision,
position, trade, audit, or PnL row count increased.

## Reconciliation contract

`assemble_and_reconcile_campaign_source_requests` enforces:

`D = S = M`

where:

- `D` = database-proven durable source-request IDs;
- `S` = source-request IDs reported by the current campaign stages;
- `M` = source-request IDs represented by current stage coverage-manifest rows.

The durable loader constructs `D` from both:

1. current stage-reported IDs proven to exist in `printer_source_requests`; and
2. every durable row whose `request_key` equals or begins with each supplied
   request-key prefix.

Prefix lookup is therefore safe only when the supplied prefix is unique to one
campaign invocation.

## Proven root cause

The permanent operational path does not supply invocation-scoped request-key
prefixes.

`AuthoritativeLiveOperationalCampaignOwner.run_operational` passes only
`OPERATIONAL_GRADUATED_SUPPLY_KWARGS` into `build_graduated_supply`, plus campaign,
execution, run, and cycle identities. The kwargs constant does not contain
`discovery_request_key_prefix` or `front_door_request_key_prefix`.

`build_graduated_supply` therefore falls back to these legacy defaults:

```python
discovery_request_key_prefix = "v2-9-7e-44"
front_door_request_key_prefix = "v2-9-7e-44"
```

The persistent supply service derives locator, direct-migration, market-batch,
liquidity-backup, protocol-confirmation, and reconciliation request keys from
those prefixes.

At pre-holder reconciliation, the campaign supplies the same static discovery
prefix to `load_durable_campaign_source_request_ids`, whose SQL includes:

```sql
WHERE request_key = ? OR request_key LIKE ?
```

with the second argument equal to `v2-9-7e-44%`.

Because the operational database is persistent and earlier authorized attempts
used the same defaults, that prefix query admits historical source-request rows
from earlier campaigns into `D`.

Current stage diagnostics and coverage rows are invocation-local, so `S` and `M`
represent the current attempt while `D` contains current plus historical rows.
The resulting primary failed relation is:

`D - S != empty`

and, because historical rows are not in the current coverage manifest:

`D - M != empty`

The immediately preceding consumed attempt created requests `1940`–`1950` on the
same unchanged static-prefix path. They are a concrete minimum historical
contamination population for the new run's prefix scan; older matching rows may
also exist. The exact complete historical contaminant set remains a read-only DB
enumeration detail, but it is not needed to establish the production defect.

## Why the public terminal was generic

`reconcile_campaign_source_requests` records `durable_only_not_stage` and
`missing_from_manifest`, but these branches do not assign a
`categorical_detail` value.

The caller raises:

```python
LiveOperationalError(
    "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH",
    categorical_detail or blocker,
)
```

For this defect, `categorical_detail` is absent and `blocker` is the same generic
constant. The public terminal therefore reports only:

`CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`

instead of the exact category and contaminating request IDs.

This is a secondary terminal-detail reporting defect. It did not cause the
safe-stop, but it made the safe-stop materially harder to diagnose.

## Ruled-out alternatives

The evidence rules out these as the primary blocker:

- temporal carrier failure: the campaign passed the repaired temporal boundary;
- missing durable source execution: all 18 requests have exactly one response or
  failure at the aggregate level;
- holder provider failure: holder work did not begin;
- Scheduler ownership failure: Scheduler runtime calls were zero;
- DB lock or cleanup failure: cleanup completed and lease released;
- memory closeout failure: no lifecycle or memory window was created;
- provider failure alone: seven source failures were durably recorded, but the
  terminal was the accounting-set invariant, not a provider-status terminal.

## Money-usefulness contribution

The audit protects future memory quality by keeping source evidence scoped to the
campaign that actually produced it. Without invocation-local request ownership,
historical source work can be misrepresented as current evidence, distort budget
accounting, or block otherwise valid current candidates.

## What the repair must improve

The repair must:

- give every operational campaign a deterministic, unique request-key root;
- bind every discovery/front-door child stage to that root;
- preserve prefix lookup as a detector of current-stage reporting omissions;
- prevent historical rows from entering the current durable set;
- fail before provider work if the proposed root already exists;
- expose exact reconciliation categories and bounded request-ID differences in
  terminal evidence.

## What remains locked

This audit does not unlock:

- another authorization or campaign run;
- automatic retry, resume, restart, or successor;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, signing, real funds, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Proof required before completion of a repair

A later implementation must prove, on disposable databases only:

1. two sequential campaigns using different invocation roots remain isolated;
2. historical `v2-9-7e-44%` rows do not enter a new campaign's `D` set;
3. a current stage-reporting omission is still discovered by the unique prefix;
4. every current request appears exactly once in `D`, `S`, and `M`;
5. request-prefix collision blocks before any provider call;
6. the terminal reports exact mismatch category and bounded IDs;
7. no Source Governor, Scheduler, selection, window, memory, retrieval, or
   financial behavior changes.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Audit finding / control |
| --- | --- |
| Historical rows charged to current campaign | Confirmed static-prefix contamination |
| Removing prefix lookup hides stage omissions | Do not remove it; make the prefix invocation-unique |
| Prefix collision silently reuses evidence | Require zero pre-existing rows for the new root |
| Request keys become nondeterministic | Derive from stable campaign/run/cycle identity |
| Generic safe-stop repeats | Persist and surface exact category plus bounded IDs |
| Failed evidence is lost during repair | Preserve DB and application evidence unchanged |
| Scope drifts into provider or selection behavior | Restrict repair to request-scope construction, reconciliation detail, and focused tests |

## Exact next lane

Design an invocation-scoped campaign request-key contract and exact reconciliation
terminal-detail repair.

Do not implement, authorize, or run anything from this audit branch.