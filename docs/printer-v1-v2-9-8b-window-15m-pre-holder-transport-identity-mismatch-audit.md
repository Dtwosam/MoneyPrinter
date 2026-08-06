# Printer V1 V2-9.8B WINDOW_15M Pre-Holder Transport-Identity Mismatch Audit

## Verdict

`V2_9_8B_WINDOW_15M_PRE_HOLDER_TRANSPORT_IDENTITY_MISMATCH_AUDIT_COMPLETE`

Root-cause classification:

`PRE_HOLDER_TRANSPORT_IDENTITY_ATTRIBUTION_DEFECT`

Secondary classifications:

- `MANIFEST_IDENTITY_COMPLETENESS_DEFECT`
- `TERMINAL_IDENTITY_DIAGNOSTIC_DEFECT`

This is an audit-only closeout. No production code, tests, database rows,
authorization packages, application evidence, provider calls, discovery,
Scheduler work, lifecycle work, or memory work were changed or executed.

## Baseline

| Item | Value |
| --- | --- |
| Baseline branch | `agent/v2-9-8b-window-15m-fresh-authorization-after-source-request-scope-enforcement` |
| Baseline full HEAD | `7defc2945c42053d9c770ebc66248d27c63ff4a3` |
| Audit branch | `agent/v2-9-8b-window-15m-pre-holder-transport-identity-mismatch-audit` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z` |
| Failed execution | `20260806T131312Z-829382105482` |
| Campaign | `20260806T131312Z-829382105482-campaign` |
| Run | `20260806T131312Z-829382105482-campaign-run` |
| Cycle | `20260806T131312Z-829382105482-cycle` |
| First terminal cause | `HolderBudgetError:PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES:campaign_identity_count=5,manifest_transport_count=9` |

## Authorization disposition

`V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z` is permanently consumed because its
application marker was successfully created and its child process started.

Disposition:

`CONSUMED_CHILD_EXITED_NONZERO`

It must never be retried, resumed, restarted, rebound, regenerated, or used to
create an automatic successor.

## Failed application evidence

Application root:

`$HOME/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`

| File | SHA-256 |
| --- | --- |
| `application-marker.json` | `0895e91e4e554ea9207898ddfd4bcfe469334bf708554c82643fe61426dcd4d5` |
| `git-provenance-manifest.json` | `94e927b697c2e9bd3a0c5a16ed50c991bb0e1acbe2569fa078e9304f93b2f359` |
| `wrapper-terminal.json` | `57cc561d7d339481ec39652fe4cac79d5a81dda28144a69df85f942c9114ae0b` |
| `child-stderr.txt` | `72f7ecd42048307ce903b0f81822bfefb3be9d193f4bb7136ec9524f336dfb62` |
| `child-stdout.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Run progression

The prior temporal and invocation-scoped source-request repairs both worked far
enough for the campaign to complete governed discovery/source execution, exact
market and reserve persistence, and `D = S = M` source-request reconciliation.

The campaign then stopped inside `build_pre_holder_budget_snapshot`, before any
holder I/O, because:

```text
manifest_transport_count = 9
campaign_identity_count = 5
```

The action-local request accounting was complete:

- source requests: `10` (`1969`–`1978`)
- source responses: `8` (`1749`–`1756`)
- source failures: `2` (`220`–`221`)
- response/failure conservation: `10 = 8 + 2`

This is not a missing durable request, response, or failure record. It is an
identity-attribution mismatch after source-request ownership reconciliation.

The campaign did not reach:

- holder evidence attempts;
- holder maturation work;
- Scheduler runtime work;
- lifecycle activation;
- `WINDOW_15M` creation;
- memory generation or closeout.

Cleanup completed, the lease was released, and locked/pending/running Scheduler
counts were zero.

## Authoritative database after the failed attempt

| Field | Value |
| --- | --- |
| path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| size | `69328896` |
| SHA-256 | `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e` |
| inode | `1230526` |
| exact terminal mtime_ns | `1786022001929258221` |
| shell-display mtime_ns | `1786022001000000000` |
| mutation status | `PROVEN_MIXED_INSERT_AND_UPDATE` |

The terminal-captured nanosecond identity is controlling; the shell display was
coarser. The database must not be restored, rewritten, vacuumed, normalized, or
rolled back. Failed-run rows are authoritative evidence.

## Mutation ledger

Net-positive rows from this attempt:

| Table | Delta |
| --- | ---: |
| `printer_source_requests` | `+10` |
| `printer_source_responses` | `+8` |
| `printer_source_failures` | `+2` |
| `printer_discovery_reserve_layers` | `+54` |
| `printer_exact_market_states` | `+34` |
| `printer_memory_factory_campaigns` | `+1` |
| `printer_memory_factory_campaign_runs` | `+1` |
| `printer_memory_factory_campaign_cycles` | `+1` |
| `printer_memory_factory_campaign_supervision` | `+1` |
| `printer_memory_factory_campaign_configurations` | `+1` |

Zero row-count deltas were reported for holder evidence, holder maturation,
Scheduler jobs, lifecycle events, campaign windows, memory windows, retrieval,
decisions, positions, trades, audits, and PnL.

## Static contract audit

### Pre-holder owner compares a count claim, not an exact manifest set

`build_pre_holder_budget_snapshot` currently:

1. sums every manifest row's `transport_identity_count`;
2. constructs exact campaign and action-local identity keys;
3. compares the summed manifest count with `len(campaign_keys)`;
4. compares campaign and action-local key sets.

It does not reconstruct and compare an exact manifest identity-key set. The
first failing relation therefore reports only `9 != 5`, not which requests,
stages, or identities are missing or extra.

### Manifest accepts positive counts without matching keys

`build_campaign_source_request_manifest` and
`_normalize_stage_coverage_entry` preserve `transport_identity_count` and an
optional `transport_identity_keys` list independently. They do not require:

```text
transport_identity_count == len(transport_identity_keys)
```

A positive count with an absent or incomplete key list is accepted into an
otherwise source-request-reconciled manifest.

### Production coverage is not uniformly identity-bearing

The GeckoTerminal reconciliation fallback inside
`run_dexscreener_batch_market_resolution` records
`transport_identity_count=gt_transport_count` but does not include the exact
`transport_identity_keys` delta on its coverage entry.

This proves the production manifest contract is not uniformly identity-bearing,
even though stage ledgers can carry measured identities.

### Current terminal is insufficient for exact stage attribution

The failed terminal records only:

```text
campaign_identity_count=5
manifest_transport_count=9
```

It does not persist or report:

- exact manifest identity keys by source request;
- exact campaign-owner keys;
- exact action-local keys;
- manifest-minus-campaign keys;
- campaign-minus-manifest keys;
- campaign-minus-action keys;
- action-minus-campaign keys;
- request IDs and logical stages owning each difference.

Therefore the exact four missing or extra identities cannot be named honestly
from the preserved terminal alone. This audit does not invent them.

## Root-cause conclusion

The immediate safe-stop was correctly enforced: holder work must not start when
manifest transport claims exceed exact campaign identities.

The repairable defect is the pre-holder evidence contract:

- source-request ownership can reconcile while transport evidence remains
  count-only or key-incomplete;
- manifest, campaign-owner, and action-local transport truth are not compared as
  three exact identity-bearing sets;
- terminal evidence cannot localize the mismatch.

This is not a provider, source-request scope, temporal, holder-policy, Scheduler,
lifecycle, or memory-policy defect.

## Money-usefulness contribution

The safe-stop prevented holder eligibility and eventual memory from being built
on transport counts that could not be tied exactly to measured source operations.
The audit identifies the evidence contract needed to preserve trustworthy source
cost, provenance, and campaign budget truth.

## What the next repair improves

- exact per-request transport identities in the campaign manifest;
- count/key parity before source reconciliation can PASS;
- exact manifest = campaign = action-local identity reconciliation;
- stage/request-local terminal diagnostics;
- no lowering of counts or fabrication of missing identities.

## What remains locked

- no authorization or campaign rerun;
- no automatic retry/resume/restart/successor;
- no holder, Scheduler, lifecycle, or memory execution;
- no `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- no retrieval, dirty-memory use, paper decisions, BUY/SELL/HOLD, positions,
  trades, audits, or PnL;
- no wallets, keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

## Proof required before completion

A later implementation must prove on disposable migrated databases that every
positive manifest count has exact keys, all three identity sets are equal on
PASS, every mismatch is categorized with bounded request/stage/key detail, and
no provider/runtime or authoritative DB mutation occurs.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
| --- | --- |
| Fix lowers `9` to `5` without evidence | Forbidden; exact identities must drive counts |
| Manifest keys use a different key shape | One canonical measured-transport key owner |
| Count/key enforcement breaks lawful zero-transport failures | Require `0 == len([])` and retain BLOCKED terminal status |
| Same transport appears under two requests/stages | Duplicate identity fails closed with both owners reported |
| Terminal leaks provider payloads | Report only bounded canonical keys, request IDs, and logical stages |
| Scope expands into holder/provider policy | Restrict repair to accounting/coverage/pre-holder surfaces |

## Exact next lane

Design the exact identity-bearing source-request manifest and pre-holder
three-set reconciliation repair.

Do not implement, authorize, or run anything from this audit lane.
