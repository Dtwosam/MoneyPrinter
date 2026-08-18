# Printer V1 V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Implementation Closeout

Date: 2026-08-18

Lane: `V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Implementation`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_FOUR_TOKEN_4_2_2_FREEZE_INPUT_VERSUS_TWO_SLOT_TRUNCATION_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`

This is the implementation / bounded-proof closeout. It is not Independent Closeout. It does not authorize a campaign, create or consume an authorization, or launch Printer.

## 1. Authority and baselines

Governing artifacts:

- `docs/printer-v1-v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-design.md`
- forensic reconstruction of consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z`

| Item | Value |
|---|---|
| Design baseline | `2c8caf0b72136cc6eefbb114d4804175abc2097b` |
| Design close | `308f769` |
| Product repair commit | `083962a5c193d47a9da35d9806f9420d256cc20b` |
| Implementation branch | `agent/v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-implementation` |
| Design branch | `agent/v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-design` |
| Temporary verification PR | `#188` closed without merge |

`CURRENT_HANDOFF.md` on the earlier authorization-alignment branch is stale. The current lane is this freeze-input repair, not a new authorization.

The product repair remains exactly `083962a`. Later commits on the implementation branch add focused tests, then add and later remove temporary CI scaffolding. No later commit supersedes or rewrites the product repair.

## 2. Proven defect repaired

The consumed 4/2/2 attempt terminalized `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` after Printer had already written eight lawful `MEMORY_OBSERVATION_ELIGIBLE` / `MARKET_READY` candidates.

Permanent admission was reading `supply.graduated_supply` (the already-selected two-slot pair). `freeze_eligible_reserve()` correctly requires depth `>= 4`, so it saw `2 < 4` and blocked.

The freeze-depth rule was not the defect. The pre-freeze input carrier was.

Repair in `authoritative_live_operational_campaign.py`:

- add `_permanent_observation_admission_inputs(supply)` returning `tuple(supply.holder_reserve_supply)`;
- in permanent mode only, pass that full reserve into `_graduated_admission()` instead of `supply.graduated_supply`.

Two-slot truncation remains at the existing post-freeze Cycle-1 handoff. Holder I/O remains `selected_slot_holder_candidates`. `MINIMUM_FREEZE_DEPTH` remains 4.

## 3. Files changed by the repair

Product (commit `083962a`):

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` (+6 / −1)

Focused tests (commits `4de4921`, `3b6ec8a`, `d00861e`):

- `tests/test_v2_9_8b_four_token_freeze_input_truncation_repair.py`

Temporary CI (later removed):

- `.github/workflows/printer-freeze-input-repair-tdd.yml` added then deleted on both implementation and design branches

This closeout:

- `docs/printer-v1-v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-implementation-closeout.md`

No production code was changed to accommodate the stale CI filename.

## 4. Expanded-regression interruption classification

GitHub Actions run `32191750112` on PR #188 failed in 11 seconds with:

```text
missing required regression file: test_v2_9_8b_window_15m_holder_budget_decoupling.py
```

That filename does not exist in the current checkout. The actual holder/freeze decoupling file is:

`tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py`

The same temporary workflow also named two other non-existent files:

- `test_v2_9_8b_four_token_standard_four_hour_operational_authority.py`
- `test_v2_9_8b_standard_four_hour_production_authority.py`

Classification: `TEST-SELECTION / CI PLUMBING FAILURE`, not a product assertion failure and not a repair regression.

## 5. Focused proof

Already observed green: 4/4.

Independently re-verified on this checkout after `083962a`:

```text
.venv/bin/python -m pytest -q tests/test_v2_9_8b_four_token_freeze_input_truncation_repair.py
4 passed in 0.10s
```

Cases:

1. Permanent admission uses `holder_reserve_supply` (8), not `graduated_supply` (2).
2. Eight-candidate incident shape reaches freeze without two-slot truncation; freeze returns 2 selected + >=2 alternates; coverage blocker false.
3. Depth 4 still yields exactly 2 selected + 2 alternates.
4. Depth 3 still coverage-blocks truthfully.

## 6. Bounded nearby regression

Current tracked filenames were resolved with `git ls-files` and `pytest --collect-only`. No historical/guessed names were reused.

| Role | Actual file | Why in scope |
|---|---|---|
| A. Focused incident/repair | `tests/test_v2_9_8b_four_token_freeze_input_truncation_repair.py` | Direct RED/GREEN contract for this repair |
| B. Holder/freeze decoupling | `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py` | Holder remains context-only; permanent admission must not consult holder candidate-cap |
| C. Four-token operational authority | `tests/test_v2_9_8b_four_token_standard_four_hour_operational_command.py` | `four-token-standard-four-hour-run` stays distinct from two-token and proof-only modes |
| D. Bounded four-token offline proof | `tests/test_v2_9_8b_four_token_standard_four_hour_bounded_offline_proof.py` | Offline 4/2/2 composition proof; no authorization or live campaign |
| E. Two-token Standard-4H authority | `tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_authorization.py` | Existing `standard-four-hour-run` production authority non-regression |

Full collection of those five files: 55 tests.

Command including the six pre-existing holder-file cases:

```text
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_four_token_freeze_input_truncation_repair.py \
  tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py \
  tests/test_v2_9_8b_four_token_standard_four_hour_operational_command.py \
  tests/test_v2_9_8b_four_token_standard_four_hour_bounded_offline_proof.py \
  tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_authorization.py
```

Result on this repair HEAD: **49 passed, 6 failed**.

The same six failures reproduce on design baseline `2c8caf0` with the same four nearby files (no focused repair file on that commit): **45 passed, 6 failed**.

Therefore the six failures are **pre-existing debt**, not a repair regression. They were not repaired.

Deselected re-run of the in-scope green subset:

```text
.venv/bin/python -m pytest -q <same five files> --deselect <six pre-existing holder cases>
49 passed, 6 deselected in 1.28s
```

No outbound live-provider campaign work. No authorization consumption. No Printer launch. Nearby tests use disposable/fake/frozen fixtures.

## 7. Authority-separation / non-regression evidence

- `test_three_distinct_modes` and `test_standard_four_hour_remains_two_token_authority` still pass.
- `test_proof_mode_remains_proof_only` still passes.
- `test_new_mode_is_not_a_capacity_selector` still passes.
- Two-token Standard-4H wrapper/authorization tests still pass.
- `test_permanent_admission_never_consults_holder_candidate_cap` still passes.
- `test_one_operational_invocation_proves_four_two_two` still passes offline.
- Window law tests still lock 12h/24h and keep 5m support-only.

## 8. Temporary CI cleanup

Before:

| Branch | Temporary file |
|---|---|
| implementation | `.github/workflows/printer-freeze-input-repair-tdd.yml` |
| design | `.github/workflows/printer-freeze-input-repair-tdd.yml` |

No other GitHub workflows existed on `master`/`main` or on the design baseline `2c8caf0`.

After:

| Branch | Temporary file |
|---|---|
| implementation `4076df1` | absent |
| design `1814387` | absent |

Remote `git ls-tree` on both branch tips contains no `.github/` files.

## 9. PR #188

- URL: https://github.com/Dtwosam/MoneyPrinter/pull/188
- Title: `TDD: repair four-token freeze input truncation`
- Final state: `CLOSED`
- `mergedAt`: `null`
- Product change in the PR that is not already on the repair branch: none. The only product hunk is commit `083962a`, already on the implementation branch.

## 10. Migration / DB / lock safety

- Tracked migration head: `migrations/058_direct_pump_migration_cursor.sql`
- Migration 059: **absent**
- Authoritative schema table: 58 rows, head `058_direct_pump_migration_cursor.sql`
- No schema or migration change in this lane
- No authoritative campaign DB mutation by this closeout
- Consumed-attempt evidence remains preserved and unused

## 11. Authorization / campaign counters for this lane

| Counter | Value |
|---|---:|
| Authorizations created | 0 |
| Authorizations consumed | 0 |
| Printer campaign launches | 0 |
| Provider / RPC / WebSocket campaign calls | 0 |
| Authoritative campaign DB mutations | 0 |
| Retrieval / BUY / SELL / HOLD / positions / trades / PnL unlocks | 0 |

The earlier consumed authorization remains historical-only and was not reused.

## 12. Permanent locks preserved

Solana-only, Solana memecoin-only, paper-trading only, no live wallet/private keys/signing/real funds/live execution, no paid APIs, no scoring/ranking/confidence/weighted logic, no embeddings/vectors, no Source Governor or Central Scheduler bypass, no dirty-memory retrieval/decision use, no BUY/SELL/HOLD, no positions/trades/audits/PnL, 5m support-only, 12h/24h locked, no migration 059.

## 13. Separate pre-existing debt (not repaired)

The following six cases in `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py` fail identically on `2c8caf0` and on this repair:

1. `test_pre_holder_snapshot_reconciles_request_and_transport_identities_exactly` — `MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS`
2. `test_pre_holder_snapshot_fails_closed_on_inconsistent_accounting[transport_count_without_identity-...]`
3. `test_pre_holder_snapshot_fails_closed_on_inconsistent_accounting[stage_campaign_mismatch-...]`
4. `test_low_cost_holder_context_evaluates_all_four_when_budget_permits` — `CAMPAIGN_SOURCE_REQUEST_SCOPE_ROOT_MISSING`
5. `test_higher_cost_holder_context_stops_without_request_or_exception[transport_costs0-3]` — same
6. `test_higher_cost_holder_context_stops_without_request_or_exception[transport_costs1-2]` — same

Classification: `PRE_EXISTING_HOLDER_BUDGET_TEST_DEBT`. Out of this repair scope. Not a freeze-input regression.

Secondary forensic reporting gaps (`campaign_activity` six-unit zeros; missing 056 provenance on this command path) remain `NON_CAUSAL_REPORTING_EVIDENCE_GAPS` and were not repaired.

## 14. Functionality risks / setbacks / efficiency blockers

- The repair is integration-correct for freeze input. It does not by itself create a fresh lawful 4/2/2 authorization or prove a live campaign.
- A later live attempt can still honest-block if fewer than four lawful observation candidates exist, or if later-cycle discovery fails. That is intended.
- Re-authorization remains a later operator-approved lane after Independent Closeout and any required rereadiness.

## 15. Exact next permitted action

`V2-9.8B CURRENT REPAIR — INDEPENDENT CLOSEOUT`

Do not prepare a fresh 4/2/2 authorization in that independent closeout unless that later lane explicitly authorizes it. This implementation closeout does not authorize execution.
