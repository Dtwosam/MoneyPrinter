# Authorization Report — V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z

## Verdict

`V2_9_8B_STRENGTHENED_DISCOVERY_SELECTION_WINDOW_15M_ONE_USE_AUTHORIZATION_PASS`

## Bindings

| Item | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| HEAD | `0ab3fa33e580cbe1c55e3a6bfd2b318edd93aa6c` |
| Subject | `Strengthen discovery and selection funnel` |
| Main window | `WINDOW_15M` only |
| Token capacity | 2 |
| DB path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| DB sha256 | `841ccb18485355d4a1f1a574d53e3b62ee7c038f412495ebce62b5da09de2326` |
| DB size | `66355200` |
| final_authorization.sha256 | `8bb922e4450a81ee42e160a638f93175723f128bc05c058664aa211c008c70e7` |
| Readiness artifact required | No |
| Wrapper entry | `scripts/Start-PrinterV1-Window15M-OneShot.ps1` |

## Law

One-use only. Consumed when wrapper execution begins. No retry/rerun/resume/restart/successor.
No 1h/4h/12h/24h continuation. No direct operational child. No separate readiness run.
Source Governor and Central Scheduler remain mandatory owners at runtime.
