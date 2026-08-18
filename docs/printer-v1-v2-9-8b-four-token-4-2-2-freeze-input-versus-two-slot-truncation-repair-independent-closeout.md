# Printer V1 V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Independent Closeout

Date: 2026-08-18

Lane: `V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Independent Closeout`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_FOUR_TOKEN_4_2_2_FREEZE_INPUT_VERSUS_TWO_SLOT_TRUNCATION_REPAIR_INDEPENDENT_CLOSEOUT_PASS`

This is an independent review of the implementation/bounded-proof closeout. It does not accept that closeout by citation alone. It reconstructs the repair from current repository evidence. It does not authorize a campaign, create or consume an authorization, or launch Printer.

## 1. Review posture

`CURRENT_HANDOFF.md` at review start still described the **design** lane (`IMPLEMENTATION_REQUIRED`). That handoff is stale and was not used as authority.

Reviewed from:

- active source stack (`AGENTS.md`, Clean Master Spec, Post-RC / Memory Factory / memory-growth v2);
- design: `docs/printer-v1-v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-design.md`;
- implementation closeout: `docs/printer-v1-v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-implementation-closeout.md`;
- current product, tests, diffs, PR/CI state, and independently re-run proofs.

## 2. Exact identities verified

| Item | Independent result |
|---|---|
| Branch | `agent/v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-implementation` |
| Implementation closeout HEAD reviewed | `318c64bd2dcf18ae236d1ca79a4f82cea43c7cb9` |
| Design / consumed-attempt baseline | `2c8caf0b72136cc6eefbb114d4804175abc2097b` |
| Product repair | `083962a5c193d47a9da35d9806f9420d256cc20b` |
| `083962a` is ancestor of `318c64b` | **yes** (`git merge-base --is-ancestor` exit 0) |
| Product file vs `083962a` at reviewed HEAD | **empty diff** — later commits did not rewrite the hunk |

## 3. Exact repair diff

`git show 083962a` touches one production file only:

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` (+6 / −1)

```text
+def _permanent_observation_admission_inputs(supply: Any) -> tuple[Any, ...]:
+    """Return the full lawful reserve used by permanent observation freeze."""
+    return tuple(supply.holder_reserve_supply)

 admission_inputs = (
-    tuple(supply.graduated_supply)
+    _permanent_observation_admission_inputs(supply)
     if permanent_mode and supply is not None
     else ...
 )
```

`git diff --stat 2c8caf0 HEAD -- src/` is that same one-file, seven-line product change. `freeze_eligible_reserve()`, `graduated_supply_front_door.py`, and `later_cycle_graduated_supply.py` are byte-identical to baseline.

## 4. Actual call-path verification

Helper-unit tests are not sufficient by themselves. The live permanent seam is:

1. `permanent_mode` is `supply.diagnostics["permanent_availability"]`.
2. Permanent candidate cap is `HOLDER_ELIGIBILITY_CANDIDATE_MAX` (8), not `ledger.candidate_cap()`.
3. **Real admission seam** (`authoritative_live_operational_campaign.py` ~3888–3897) now calls `_permanent_observation_admission_inputs(supply)` and passes that tuple into `_graduated_admission()`.
4. Observation-row construction (~4221) iterates `graduated_candidates` produced by that admission, not `supply.graduated_supply`.
5. Each surviving row is marked `memory_observation_eligible=True` **before** holder pass/fail is recorded; `fully_eligible` is contextual only.
6. `freeze_eligible_reserve(observation_rows)` is unchanged (`MINIMUM_FREEZE_DEPTH = 4`). Depth `< 4` still returns empty selected/alternates with `coverage_blocker`.
7. Post-freeze handoff (~4634–4661) still takes **only freeze-selected mints** and stops at `len(chosen) == 2`.

Holder I/O remains `selected_slot_holder_candidates(supply)` → `supply.graduated_supply` (the two-slot front-door pair). The repair does not feed the full reserve into holder transports.

This is the designed ownership split: full reserve into freeze; two-slot truncation only after freeze.

## 5. Incident cross-check

Historical consumed attempt `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z` ended `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` with `lifecycle_started=false` after eight lawful `MEMORY_OBSERVATION_ELIGIBLE` rows existed and freeze saw only the two already-selected slots.

The old seam `tuple(supply.graduated_supply)` is exactly that causal mechanism. Replacing it with `holder_reserve_supply` at the live admission call is the matching repair. Freeze depth was not lowered.

## 6. Focused proof (independently re-run)

```text
.venv/bin/python -m pytest -q tests/test_v2_9_8b_four_token_freeze_input_truncation_repair.py
4 passed in 0.16s
```

Those four cases prove:

1. helper returns the 8-member reserve, not the selected pair of 2;
2. eight-candidate incident shape reaches `freeze_eligible_reserve` without two-slot truncation (2 selected, ≥2 alternates, coverage blocker false, depth authority 4, observation count 8);
3. depth 4 still yields exactly 2 selected + 2 alternates;
4. depth 3 still empties selected/alternates and coverage-blocks.

Combined with the live-path trace above, this is sufficient to conclude the causal defect is repaired.

## 7. Bounded nearby regression (independently re-run)

Actual tracked filenames resolved from this checkout:

| Role | File |
|---|---|
| Focused repair | `tests/test_v2_9_8b_four_token_freeze_input_truncation_repair.py` |
| Holder/freeze decoupling | `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py` |
| Four-token operational authority | `tests/test_v2_9_8b_four_token_standard_four_hour_operational_command.py` |
| Bounded four-token offline proof | `tests/test_v2_9_8b_four_token_standard_four_hour_bounded_offline_proof.py` |
| Two-token Standard-4H authority | `tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_authorization.py` |

```text
.venv/bin/python -m pytest -q <those five files>
6 failed, 49 passed
```

No live provider campaign, no authorization consumption, no Printer launch.

## 8. Six-failure baseline comparison

The six failures are only in the holder-budget decoupling file, with signatures:

- `MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS` (3 cases)
- `CAMPAIGN_SOURCE_REQUEST_SCOPE_ROOT_MISSING` (3 cases)

They were **not** accepted from the implementation closeout. They were re-run on isolated baseline sources:

```text
git worktree add --detach /tmp/mp-ind-baseline-2c8caf0 2c8caf0
PYTHONPATH=/tmp/mp-ind-baseline-2c8caf0/src pytest tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py
6 failed, 14 passed
```

Failure names and exception types match repaired HEAD. Tracebacks resolve to `/tmp/mp-ind-baseline-2c8caf0/src/...`, not the repaired tree.

Classification: `PRE_EXISTING_HOLDER_BUDGET_TEST_DEBT`. Not a freeze-input regression. Not repaired here.

## 9. Authority-separation result

Independently imported and/or covered by passing nearby tests:

| Authority | Mode string | Result |
|---|---|---|
| Two-token operational | `standard-four-hour-run` | Unchanged policy `V2-9.8-STANDARD-4H-OPERATIONAL-V1` |
| Four-token proof-only | `four-token-bounded-capacity-proof-run` | Unchanged |
| Four-token operational 4/2/2 | `four-token-standard-four-hour-run` | `configured_through_4h_tokens=4`, `configured_active_cycles=2`, `tokens_per_cycle=2` |

Also independently imported:

- `MINIMUM_FREEZE_DEPTH == 4`
- `SELECTION_FLOOR_USD == 3000.0`
- `automatic_retries == 0`, `endpoint_rotation == False`, cycle spacing `300`
- locked windows `WINDOW_12H`, `WINDOW_24H` on both two-token and 4/2/2 operational policies

`test_three_distinct_modes`, `test_standard_four_hour_remains_two_token_authority`, `test_proof_mode_remains_proof_only`, `test_carry_forward_of_cycle_one_identity_is_rejected`, `test_permanent_admission_never_consults_holder_candidate_cap`, and `test_one_operational_invocation_proves_four_two_two` all passed in the nearby run.

## 10. Temporary CI / PR #188

- PR https://github.com/Dtwosam/MoneyPrinter/pull/188 : `state=CLOSED`, `mergedAt=null`.
- `.github/workflows/printer-freeze-input-repair-tdd.yml` is absent from the implementation tip, the design tip, and `master`/`main`.
- Tracked `.github/` files on the implementation branch: **none**.

The earlier GitHub failure (`missing required regression file: test_v2_9_8b_window_15m_holder_budget_decoupling.py`) is independently classified as test-selection plumbing, not a product assertion failure.

## 11. Authorization / DB / migration safety

This independent-closeout lane created:

| Counter | Value |
|---|---:|
| New authorizations | 0 |
| Consumed authorizations | 0 |
| Printer launches | 0 |
| Live provider/RPC/WebSocket campaign calls | 0 |
| Authoritative campaign DB mutations | 0 |

Historical authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z` remains present, SHA-256 `caac717f505bce81f5ce6d1ab8091bac09fe8660342a502bcdd4daeacbb64a12`, one-shot policy forbids retry/rerun/resume/restart/successor, and the application marker still exists. It is **not reusable**.

Read-only DB: 58 migrations, head `058_direct_pump_migration_cursor.sql`, 059 absent, `integrity_check=ok`, no FK violations, sidecar only `printer_v1.sqlite3`.

`git diff --check` clean.

## 12. Permanent locks

Independently confirmed preserved: Solana-only / memecoin-only / paper-only; no live wallet/signing/funds; no paid APIs; no scoring/ranking/confidence/weighted logic; no embeddings/vectors; no Source Governor or Central Scheduler bypass in this diff; no dirty-memory retrieval/decision unlock; no BUY/SELL/HOLD; no positions/trades/PnL; 5m support-only; 12h/24h locked; no migration 059.

## 13. Reporting gaps remain separate

Unchanged classification, not absorbed into this repair:

`NON_CAUSAL_REPORTING_EVIDENCE_GAPS`

- `campaign_activity` six-unit totals reporting gap on the consumed attempt;
- missing 056 / pre-lifecycle provenance row on that historical command path.

## 14. Functionality risks / residual debt

- Pre-existing six holder-budget test failures remain.
- Non-causal reporting gaps remain.
- Independent Closeout does not prove a live 4/2/2 campaign and does not create a fresh authorization.
- A later live attempt can still honest-block if fewer than four lawful observation candidates exist. That is intended.

## 15. Exact next permitted action

`V2-9.8B Post-Freeze-Input-Repair Two-Cycle Four-Token Operational 4/2/2 Authoritative Readiness`

Read-only / static baseline reconciliation and readiness only. Do **not** prepare or create an authorization in that lane unless it later closes PASS and a subsequent explicit authorization-preparation lane is opened.

Required remaining sequence:

Independent Closeout PASS (this document)
→ fresh authoritative readiness / baseline reconciliation
→ fresh authorization preparation only if readiness PASS
→ independent authorization review
→ one operator-approved one-shot campaign

Do not skip fresh readiness. Do not reuse `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z`.
