# Printer V1 V2-9.8B Campaign Source-Request Scope Propagation Forensic Audit

Date: 2026-09-01

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`

Authorization state:

`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

Authorized HEAD:

`eefd909fe40b14a6459154c71ba56ace8be08b4f`

Execution:

`20260901T191450Z-520d6a348621`

First terminal cause:

`ValueError:CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`

Failure phase:

`CAMPAIGN_PRE_LIFECYCLE`

Lifecycle started:

`null`

## Verdict

Primary classification:

`COMMITTED_CODE_DEFECT`

Subtype:

`CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_LOSS`

The fail-closed guard is correct. The production defect is that a valid
owner-produced `CampaignSourceRequestScope` is created and used to root real
governed requests, then dropped before the freeze-ready measurement consumer
requires the typed scope.

This audit is read-only. No authorization reuse, retry, rerun, resume, restart,
successor, Printer execution, or authoritative DB mutation occurred during the
investigation.

## 1. Consumed-run state (Phase 1)

Application marker exists and is consumed:

- path: `$HOME/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe/application-marker.json`
- `authorization_consumed_at`: `2026-09-01T19:14:47.648742+00:00`
- `allowed_invocation_count`: `1`
- `automatic_retry_allowed` / `manual_rerun_allowed` / `restart_allowed` / `resume_allowed` / `successor_allowed`: all `false`
- repository HEAD bound: `eefd909fe40b14a6459154c71ba56ace8be08b4f`

Wrapper terminal:

- `child_start_attempted`: true
- `child_pid`: `88419`
- `child_exit_code`: `1`
- `automatic_retries` / `manual_reruns` / `restarts` / `resumes` / `successors`: `0`
- `terminal_classification`: `CHILD_EXITED_NONZERO`

Post-run authoritative DB identity (matches child terminal `database_identity_after`):

- path: `data/printer_v1.sqlite3`
- SHA-256: `ca4c678b6164ad2aad36ed6140a06d96dc409d1cd3b64c40b17bce78a42b01dc`
- size: `146505728`
- inode: `1230526`
- mtime_ns: `1788290102639046545`
- integrity: `ok`
- foreign-key violations: `0`
- migrations: `62` / `062_pre_admission_attempt_evidence.sql`
- sidecars: none (`printer_v1.sqlite3` only)

Ownership zero-state after cleanup:

- campaign/run/cycle: `TERMINAL_FAILED`
- supervision: `TERMINAL`, lease released, cleanup completed
- no non-terminal campaigns/runs/cycles
- no unreleased campaign supervision leases
- candidate-acquisition leases: all historical `TERMINAL` with `released_at` set
- campaign lease lock file absent
- no scheduler work rows for this campaign
- scheduler jobs: `SUCCEEDED` / `FAILED` / `CANCELLED` only
- factory runs: `COMPLETED` / `FAILED` / `SAFE_STOPPED` only
- discovery work: `SUCCEEDED` / `FAILED` only
- no active Printer process; authoritative DB not held open

Do not mutate historical rows from this run.

## 2. Exact traceback / call site (Phase 2)

`child-stderr.txt` is reconstructed local terminal JSON, not a Python traceback.
The envelope is still sufficient when combined with reachable production code:

- `error_type`: `ValueError`
- `error_message`: `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`
- `first_terminal_cause`: `ValueError:CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`

That is not `GraduatedSupplyError`. The front-door missing-scope gate in
`_graduated_supply_front_door_base.py` therefore did not fire. Scope existed at
front-door entry.

Exact raise:

- file: `src/printer_v1/discovery/permanent_discovery_availability.py`
- function: `assemble_and_reconcile_campaign_source_requests`
- line: `5324`
- statement: `raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED)`

Trigger:

```python
scoped_enforcement = (
    scope_input is not None
    or explicit_root_param is not None
    or diagnostic_root is not None
)
if scoped_enforcement:
    if scope_input is None:
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED)
```

Caller:

- file: `src/printer_v1/discovery/eligible_token_supply.py`
- function: `run_persistent_eligible_token_supply._refresh_freeze_ready_depth`
- call site: lines `2138-2146`
- first invocation: line `2246`, after locator / direct-migration / GeckoTerminal
  nomination / liquidity-backup / protocol-confirmation and tracking precheck

Missing argument/state:

- `campaign_source_request_scope` / `scope_input` is `None`
- diagnostics passed to assemble contain only `campaign_source_request_coverage`
- `request_key_root=str(discovery_request_key_prefix)` is supplied, which is the
  authentic current-run root and therefore activates scoped enforcement

Immediately preceding production operations:

1. DexScreener locator request `4265`
2. Solana RPC live-tail request `4266`
3. GeckoTerminal new-pool request `4267`
4. GeckoTerminal liquidity-backup requests `4268-4273`
5. PumpSwap protocol-confirmation request `4274` (response `3878` at
   `2026-09-01T19:15:02.609266+00:00`)
6. freeze-ready measurement; campaign terminal at
   `2026-09-01T19:15:02.631069+00:00`

## 3. Producer → propagation → consumer (Phase 3)

Producer (canonical owner):

`AuthoritativeLiveOperationalCampaignOwner.run_operational` constructs and
validates one `CampaignSourceRequestScope` from the exact execution / campaign /
run / cycle identities, then passes it into `build_graduated_supply`.

Front door:

`build_graduated_supply` validates the typed scope, forces discovery and
front-door prefixes to `scope.request_key_root`, and later writes the scope into
returned `GraduatedSupply.diagnostics`. That return never happens on this run.

Dropped seam:

`build_graduated_supply` calls `run_persistent_eligible_token_supply` with the
canonical prefixes but does **not** forward `campaign_source_request_scope`.
`run_persistent_eligible_token_supply` has no parameter for the typed scope.

Consumer:

`_refresh_freeze_ready_depth` calls `assemble_and_reconcile_campaign_source_requests`
with `request_key_root=str(discovery_request_key_prefix)` and no typed scope.

This is not a later `supply = ...` object replacement that overwrites
diagnostics. The persistent-supply function never received the scope object, so
the freeze-ready consumer cannot recover it. Reconstructing a scope from
request-key strings is forbidden.

`run_persistent_eligible_token_supply` is the only production assemble caller
that supplies a root/prefix without the typed scope.

## 4. Requests `4265..4274` (Phase 4)

Expected root:

`v2-9-8b-window15m-20260901T191450Z-520d6a348621`

All ten request keys belong to that exact root.

| ID | Source | Kind | Key suffix | Outcome |
| --- | --- | --- | --- | --- |
| 4265 | dexscreener | dexscreener_fresh_profiles | `-locator` | response 3870, HTTP 200, CLEAN_DATA |
| 4266 | solana_rpc | restored_pump_migration_signature_page | `-migration-page-live-tail` | response 3871, HTTP 200, CLEAN_DATA |
| 4267 | geckoterminal | geckoterminal_new_pool_discovery | `-gt-new-pools` | response 3872, HTTP 200, CLEAN_DATA |
| 4268 | geckoterminal | candidate_market_batch | `-liq-backup-...` | response 3873, HTTP 200, CLEAN_DATA |
| 4269 | geckoterminal | candidate_market_batch | `-liq-backup-...` | response 3874, HTTP 200, CLEAN_DATA |
| 4270 | geckoterminal | candidate_market_batch | `-liq-backup-...` | response 3875, HTTP 200, CLEAN_DATA |
| 4271 | geckoterminal | candidate_market_batch | `-liq-backup-...` | response 3876, HTTP 200, CLEAN_DATA |
| 4272 | geckoterminal | candidate_market_batch | `-liq-backup-...` | failure 395, `geckoterminal_rate_limited` |
| 4273 | geckoterminal | candidate_market_batch | `-liq-backup-...` | response 3877, HTTP 200, CLEAN_DATA |
| 4274 | solana_rpc | pumpswap_pool_account_batch | `-protocol-1` | response 3878, HTTP 200, CLEAN_DATA |

Durable evidence and in-memory scope diverged: durable rows prove the upstream
root existed and was used; the in-memory typed scope was not forwarded into the
freeze-ready assemble call.

Source Governor continued after the provider event: request `4273` and `4274`
executed successfully after `4272`. Cleanup completed. Lease released. No
retry/restart/successor.

## 5. Provider-rate-limit relevance

Not the root cause.

Request `4272` is an honest GeckoTerminal rate-limit failure. It did not stop
Source Governor, did not prevent later governed requests, and is not the
`ValueError` raised 22ms after the later protocol response.

Classification is not `PROVIDER_LIMITATION`.

## 6. Existing tests (Phase 5)

Existing scope tests prove the initial composition path and the assemble guard:

- `tests/test_v2_9_8b_window_15m_source_request_scope_repair.py` patches
  `run_persistent_eligible_token_supply`, so freeze-ready measurement never runs.
- `tests/test_v2_9_8b_window_15m_source_request_scope_enforcement_followup.py`
  proves assemble fail-closed when a root is supplied without a typed scope, but
  not that production freeze-ready does exactly that.
- `tests/test_v2_9_8b_freeze_ready_wiring_completion.py` only inspects source
  text for `assemble_and_reconcile_campaign_source_requests`; it does not assert
  that the authentic scope is passed.
- Many `run_persistent_eligible_token_supply(..., permanent_availability=True)`
  tests omit `run_id` and/or `cycle_id`, so `_refresh_freeze_ready_depth`
  returns `RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE` before assemble.

The missing production path is: valid scope at the front door, prefixes forced
to the current-run root, real governed requests under that root, then freeze-ready
measurement with root and no typed scope.

## 7. Classification (Phase 6)

| Candidate | Result |
| --- | --- |
| `COMMITTED_CODE_DEFECT` / `CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_LOSS` | **Primary. Proven.** |
| `EXPECTED_FAIL_CLOSED_GUARD` | Rejected as primary. The guard is correct, but the unscoped state is caused by a production propagation drop of a valid owner-produced scope. |
| `SOURCE_OR_EVIDENCE_BLOCK` | Rejected. Durable requests exist under the exact current-run root. |
| `PROVIDER_LIMITATION` | Rejected. Rate limit is incidental. |
| `ENVIRONMENT_OR_RUNTIME_BLOCK` | Rejected. |
| `INSUFFICIENT_EVIDENCE_TO_CLASSIFY` | Rejected. |

## 8. Repair boundary

Repair the upstream forwarding seam only:

- `build_graduated_supply` must forward the authentic `CampaignSourceRequestScope`
  into `run_persistent_eligible_token_supply`
- `_refresh_freeze_ready_depth` must pass that same object into
  `assemble_and_reconcile_campaign_source_requests`

Do not:

- weaken or remove `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`
- reconstruct a scope from request-key strings
- bypass Source Governor or Central Scheduler
- change budgets, 4/2/2, freeze-ready depth 4, windows, or financial locks
- reuse the consumed authorization
- run Printer again
