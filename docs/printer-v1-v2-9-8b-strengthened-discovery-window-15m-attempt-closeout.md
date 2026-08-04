# Printer V1 V2-9.8B Strengthened Discovery WINDOW_15M Attempt Closeout

Date: 2026-08-03 (local) / 2026-08-04 (UTC evidence)

Lane:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

## Live result classification

```text
PRE_LIFECYCLE_OPERATION_BUDGET_EXHAUSTED
```

Honest pre-lifecycle terminal. Lifecycle did not start. No factory run. No
`WINDOW_15M` rows and no clean-memory episodes were created by this attempt.
Authorization was consumed exactly once. Cleanup and lease release completed.
No retry, restart, resume, or successor.

Child exit `0` is not a memory PASS. Memory PASS would require authoritative DB
evidence of completed `WINDOW_15M` clean-memory rows — not present.

## Implementation and authorization bindings

| Item | Value |
| --- | --- |
| Implementation commit SHA | `0ab3fa33e580cbe1c55e3a6bfd2b318edd93aa6c` |
| Implementation subject | `Strengthen discovery and selection funnel` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Fresh authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z` |
| Authorization SHA-256 | `8bb922e4450a81ee42e160a638f93175723f128bc05c058664aa211c008c70e7` |
| Independent review verdict | `V2_9_8B_STRENGTHENED_DISCOVERY_SELECTION_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS` |
| Readiness artifact | Not required; not created |
| Execution identity | `20260804T014608Z-ee2e19ddcf60` |
| Campaign ID | `20260804T014608Z-ee2e19ddcf60-campaign` |
| Run ID | `20260804T014608Z-ee2e19ddcf60-campaign-run` |
| Wrapper started (UTC) | `2026-08-04T01:46:08.418983+00:00` |
| Wrapper ended (UTC) | `2026-08-04T01:46:31.749210+00:00` |
| Campaign started (UTC) | `2026-08-04T01:46:08.977508+00:00` |
| Campaign ended (UTC) | `2026-08-04T01:46:31.733198+00:00` |
| Elapsed seconds | `22.76` |

## External evidence surfaces

| Surface | Path |
| --- | --- |
| Application directory | `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z/` |
| Application marker | `…/application-marker.json` |
| Git provenance manifest | `…/git-provenance-manifest.json` |
| Child stdout | `…/child-stdout.txt` (123512 bytes) |
| Child stderr | `…/child-stderr.txt` (empty) |
| Wrapper terminal | `…/wrapper-terminal.json` |
| Execution directory | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260804T014608Z-ee2e19ddcf60/` |
| Campaign report | `…/reports/20260804T014608Z-ee2e19ddcf60-report.campaign-report.json` |
| Terminal summary | `…/terminal-summary.json` |
| Repo authorization package | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z/` |

## Funnel accounting (authoritative report)

| Metric | Value |
| --- | --- |
| Nominations / channels attempted | `dexscreener_fresh_profiles_locator`, `direct_pump_finalized_live_tail`, `exact_pump_pumpswap_graduation_verify`, `dexscreener_exact_pool_market` |
| Channels unavailable | `[]` (none) |
| Unique candidates observed | 37 |
| Pre-source local tracking exclusions | 7 (2 `DUPLICATE_ACTIVE_TRACKING`, 5 `TERMINAL_TRACKING_STATE`) |
| Fresh market checks | 28 |
| Discovery rounds | 6 |
| Calls / source operations used | 30 (remaining 0) |
| Campaign source calls | 30 |
| Campaign scheduler calls | 0 |
| Provider failures | **0** |
| Liquidity-stage provider failures | **0** |
| Temporary exclusions | 2 below-floor cooldown skips; 22 exact-pair no-match (recheckable market absence) |
| Permanent / hard exclusions this cycle | 5 terminal tracking; 2 active duplicate (state-based, not permanent market ban) |
| Rejection reasons | `LIQUIDITY_NO_EXACT_PAIR` 22; `LIQUIDITY_BELOW_SELECTION_FLOOR` 6; `LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN` 2; `TERMINAL_TRACKING_STATE` 5; `DUPLICATE_ACTIVE_TRACKING` 2 |
| Liquidity outcome counts | `LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH` 22; `LIQUIDITY_EXACT_BELOW_FLOOR` 6; `LIQUIDITY_HISTORICAL_BELOW_FLOOR_COOLDOWN` 2 |
| Unexplored reserve remaining | yes (`unexplored_work_prevented_by_hard_ceiling=true`) |
| Eligible-set size | 0 |
| Selected mints / pools | none |
| Lifecycle started | false |
| Factory-run identity | not_found / null |
| `WINDOW_15M` rows created (this attempt) | 0 |
| Clean-memory episodes created (this attempt) | 0 |
| First terminal cause | `BUDGET_EXHAUSTION` |
| Stop classification | `PRE_LIFECYCLE_OPERATION_BUDGET_EXHAUSTED` |
| Last reason discovery could not continue | `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` |

### Six-unit totals

| Unit | Value |
| --- | --- |
| `SOURCE_TRANSPORT_OPERATION` | 31 |
| `SOURCE_RESPONSE_BYTES` | 73896 |
| `NORMALIZED_SOURCE_ROWS` | 58 |
| `LOCAL_VALIDATION_STEP` | 0 |
| `SCHEDULER_WORK_ITEM` | 0 |
| `LIFECYCLE_RESERVED_TRANSPORT_OPERATION` | 0 |

Accounting status: `SIX_UNIT_ACCOUNTING_COMPLETE`. Six-unit evidence match: true.

## Source and Scheduler ownership

* Source Governor owned every provider call (no direct adapter bypass).
* Central Scheduler ownership path active for campaign; zero lifecycle scheduler work items because lifecycle never started.
* No separate readiness run.
* No discovery-only qualification run.
* No retry / rerun / restart / resume / successor.
* No manual candidate injection.

## Cleanup and residue

| Check | Result |
| --- | --- |
| Cleanup completed | true at `2026-08-04T01:46:31.722…Z` (terminal summary) |
| Lease released | true |
| Active owned work after | 0 |
| Automatic retries | 0 |
| Restart / resume / successor created | false |
| New child work allowed | false |
| Downstream unlocks (retrieval/decisions/trades/PnL) | all false |

## Before → after effect of strengthening

Compared with immediately prior live attempt `20260804T005054Z-b7e4d39744aa` on HEAD `b26e9aa` (pre-strengthening):

| Metric | Prior attempt | This attempt |
| --- | --- | --- |
| Malformed liquidity (`LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL`) | 21 | **0** |
| Exact-pair no-match (`LIQUIDITY_NO_EXACT_PAIR` / unavailable) | 0 (misclassified as malformed) | **22** |
| Provider failures | 22 | **0** |
| Terminal shortage label | `SOURCE_VISIBILITY_SHORTAGE` | `BUDGET_EXHAUSTION` |
| Channels unavailable | included `dexscreener_exact_pool_market` | none |
| Eligible count | 0 | 0 |

DexScreener exact-pair HTTP 200 `pairs:null` responses are now lawful no-match
PARTIAL outcomes, not `dexscreener_malformed_fixture` failures. Terminal truth
no longer labels that pattern as source-visibility malformation.

## DB identity

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size after | 66600960 |
| SHA-256 after | `ad7b72a86cb4d3345a722ba519b6abd68a977a9cdc04a66316fbb9129449aa9e` |
| Pre-campaign backup | `…/20260804T014608Z-ee2e19ddcf60/printer_v1.pre-campaign.backup.sqlite3` |

## Whether another code repair is proven necessary

**Not proven necessary for the repaired malformation path.** The defect that
turned lawful exact-pair no-match into provider malformation is fixed and live-
confirmed (0 provider failures; 22 honest no-match outcomes).

Remaining live blockers to a memory PASS are market/supply under declared
ceilings:

* 22 graduated pools currently invisible on DexScreener exact-pair;
* 6 below the $3,000 floor (+ 2 still in below-floor cooldown);
* 7 state-blocked (active duplicate / terminal tracking);
* operation budget exhausted with unexplored inventory remaining.

Improving yield further would require a **separate approved** design (for
example broader nomination efficiency, temporary no-match cooldown accounting,
or budget policy) — not an emergency re-open of the null-pairs defect, and not
a floor/holder/safety bypass.

## Locked surfaces (unchanged)

* No retrieval, paper decision, BUY/SELL/HOLD, positions, trades, audits, PnL
* No wallets / private keys / real funds
* No 1h/4h/12h/24h continuation
* No second attempt under this authorization
* No push

## Final verdict of this closeout

```text
PRE_LIFECYCLE_OPERATION_BUDGET_EXHAUSTED
```

Implementation remains:

```text
V2_9_8B_DISCOVERY_SELECTION_STRENGTHENING_IMPLEMENTATION_PASS
```

Live memory outcome is not PASS. Authorization is consumed and non-reusable.
