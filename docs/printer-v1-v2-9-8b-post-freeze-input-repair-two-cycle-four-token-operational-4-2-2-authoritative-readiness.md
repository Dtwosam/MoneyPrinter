# Printer V1 V2-9.8B Post-Freeze-Input-Repair Two-Cycle Four-Token Operational 4/2/2 Authoritative Readiness

Date: 2026-08-18

Lane: `V2-9.8B Post-Freeze-Input-Repair Two-Cycle Four-Token Operational 4/2/2 Authoritative Readiness`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_FREEZE_INPUT_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_4_2_2_AUTHORITATIVE_READINESS_PASS`

This is a read-only / static readiness and baseline-reconciliation closeout. It does **not** authorize Printer execution, create a manifest or application marker, or prepare/consume an authorization.

## 1. Verdict

The exact inspected post-repair repository state is ready for a **separate** fresh 4/2/2 authorization-preparation/review lane bound to this readiness-closeout HEAD.

PASS is not campaign authority.

## 2. Branch / starting HEAD / final HEAD

| Item | Value |
|---|---|
| Branch | `agent/v2-9-8b-four-token-4-2-2-freeze-input-versus-two-slot-truncation-repair-implementation` |
| Required / starting HEAD | `ea6e116faaf140f669b6ec96a9cda63951236210` |
| Product repair | `083962a5c193d47a9da35d9806f9420d256cc20b` (ancestor) |
| Design / incident baseline | `2c8caf0b72136cc6eefbb114d4804175abc2097b` |
| Final HEAD | the commit that records this readiness closeout |

Tracked tree at inspection: clean except historical untracked `operator-runs/` evidence packages. No commits exist after `ea6e116` except this documentation closeout. `git diff --check` clean. `src/` vs `083962a` product hunk is empty.

## 3. Source-stack and handoff reconciliation

`CURRENT_HANDOFF.md` at lane start correctly named this readiness lane after independent closeout PASS. It did not conflict with the source stack.

Independent closeout verdict still holds:

`V2_9_8B_FOUR_TOKEN_4_2_2_FREEZE_INPUT_VERSUS_TWO_SLOT_TRUNCATION_REPAIR_INDEPENDENT_CLOSEOUT_PASS`

This readiness reconstructs the operational path from current code rather than citing that closeout as authority.

## 4. Freeze-input repair reconstruction

Permanent mode:

1. Observation candidate cap remains `HOLDER_ELIGIBILITY_CANDIDATE_MAX` (8).
2. `_permanent_observation_admission_inputs(supply)` returns `tuple(supply.holder_reserve_supply)`.
3. Live seam (~3888–3897) passes that wider input into `_graduated_admission(...)`.
4. Observation-row construction iterates those admitted candidates and can set `memory_observation_eligible=True` without a holder pass.
5. `freeze_eligible_reserve()` is byte-identical to `2c8caf0`.
6. `MINIMUM_FREEZE_DEPTH` remains exactly `4`.
7. Lawful depth ≥ 4 still selects 2 and retains 2 alternates; depth 3 still coverage-blocks.
8. Only after freeze does handoff take freeze-selected mints and stop at 2 active slots.
9. Holder I/O remains `selected_slot_holder_candidates(supply)` → `supply.graduated_supply` (the two-slot pair). Fallback to `graduated_candidates` occurs only if that pair is empty.

The repair fixed **freeze input**, not active capacity.

## 5. Real 4/2/2 call-path verification

Operational mode remains `four-token-standard-four-hour-run`, routed to `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE` and `FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY`.

Derived policy (`exact_operational_policy()` / live import):

- 4 through-4h tokens
- 2 cycles
- 2 tokens per cycle
- 300s minimum cycle spacing
- 0 automatic retries
- no endpoint rotation
- 2400s pre-lifecycle + 18000s post-supply = 20400s finite envelope
- locked `WINDOW_12H`, `WINDOW_24H`
- `WINDOW_15M` root; 1h/4h token-local continuation only

There is no four-token simultaneous active capacity. Cycle 1 activates two slots after freeze. Cycle 2 is a separate ordinal-2 atomic two-slot handoff.

## 6. Two-slot vs four-token authority separation

Distinct modes remain:

| Mode | Authority |
|---|---|
| `standard-four-hour-run` | two-token operational (`V2-9.8-STANDARD-4H-OPERATIONAL-V1`) |
| `four-token-bounded-capacity-proof-run` | proof-only |
| `four-token-standard-four-hour-run` | operational 4/2/2 |

Nearby tests `test_three_distinct_modes`, `test_standard_four_hour_remains_two_token_authority`, and `test_proof_mode_remains_proof_only` passed.

## 7. Later-cycle fresh-acquisition result

`build_later_cycle_graduated_supply()` still:

- requires `proposed_cycle_ordinal == 2`;
- binds a cycle-qualified `execution_id` (`{execution}:c0002`) so Source Governor request-key roots are exclusive;
- runs the canonical permanent supply with `permanent_availability=True` and `required_token_capacity=2`;
- does not recycle Cycle-1 slots as Cycle-2 freshness.

`validate_second_cycle_atomic_activation()` still requires exactly two new slots whose token/pair/mint identities are internally distinct and disjoint from Cycle 1.

Discovery remains Source-Governed; scheduled work remains Scheduler-owned. This readiness lane did not execute either runtime.

## 8. 15m → 1h → 4h continuation result

`token_local_continuation.py` still encodes the post-DTW100 amendment: after hard identity/evidence/safety/continuity gates, 15m→1h and 1h→4h are standard observation transitions. Outcome / learning-need labels cannot stop or promote those two transitions. Automatic continuation stops at `WINDOW_4H`.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot be a main window or independently trigger continuation.

## 9. Operating-constant / budget verification

Independently imported / statically confirmed, unchanged:

- freeze minimum depth 4
- observation surplus target 8
- liquidity floor $3,000
- two active slots after freeze
- 300-second cycle spacing
- finite 4-hour campaign envelope
- exactly 2 cycles
- no 12h/24h
- wrapper one-shot: no retry / rerun / resume / restart / successor
- Source Governor and Central Scheduler ownership not bypassed by this repair

No values were changed in this lane.

## 10. Consumed historical authorization status

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z`

- SHA-256 `caac717f505bce81f5ce6d1ab8091bac09fe8660342a502bcdd4daeacbb64a12`
- one-shot policy forbids retry/rerun/resume/restart/successor
- application marker present; `authorization_consumed_at=2026-08-18T21:02:02.204930+00:00`
- bound HEAD was `2c8caf0` (pre-repair)
- durable campaign `20260818T210203Z-ad5006b1a65e-campaign` remains `TERMINAL_FAILED` / `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

That failure was the now-repaired freeze-input truncation (eight lawful observation candidates existed; freeze saw only the two-slot pair). The consumed package and marker grant **no** permission for another run.

No second application directory exists.

## 11. Focused tests / checks and exact results

Independently re-run on `ea6e116`:

| Command | Result |
|---|---|
| `pytest -q tests/test_v2_9_8b_four_token_freeze_input_truncation_repair.py` | **4 passed** |
| `pytest -q` operational command + bounded offline proof + Standard-4H activation authorization + four-token provenance alignment | **50 passed, 8 subtests passed** |

No providers contacted. No Printer command invoked. No authorization consumed.

## 12. Baseline classification of any failures

No failures in the readiness-required set.

The six holder-budget decoupling cases remain `PRE_EXISTING_HOLDER_BUDGET_TEST_DEBT` (same signatures previously reproduced on isolated `2c8caf0`). They fail because those fixtures omit `campaign_request_key_root` / full transport-identity keys. Production permanent holder evaluation supplies `supply.diagnostics["request_key_root"]` and fail-closes if it is missing.

Classification for authorization-preparation: **not a causal blocker**. A live 4/2/2 campaign that lacked a campaign source-request root would fail closed, which is the intended safety behavior.

`NON_CAUSAL_REPORTING_EVIDENCE_GAPS` (consumed-attempt `campaign_activity` six-unit zeros; missing 056 provenance row on that historical path) remain historical reporting gaps. They do not govern a fresh authorization’s admission, freeze, or lifecycle law.

Neither item is a real blocker to opening a **separate** fresh authorization-preparation/review lane.

## 13. Migration / DB / repository safety

- 58 migrations; head `058_direct_pump_migration_cursor.sql`
- Migration 059 absent
- `integrity_check=ok`; no FK violations
- no WAL/SHM/journal sidecars
- inode `1230526` (same file as the consumed attempt; that attempt’s terminal residue is preserved, not deleted)
- no active campaigns/runs/cycles/supervision/factory/discovery/pre-admission/jobs
- no live Printer process
- this lane performed no authoritative DB writes

## 14. Permanent-lock verification

Preserved: Solana-only, memecoin-only, paper-only; no live wallet/signing/funds; no paid APIs; no scoring/ranking/confidence/weighted logic; no embeddings/vectors; no Source Governor or Central Scheduler bypass; no dirty-memory retrieval/decision unlock; no BUY/SELL/HOLD; no positions/trades/audits/PnL; 5m support-only; 12h/24h locked; no Migration 059.

This lane: 0 new authorizations, 0 consumptions, 0 Printer launches, 0 live campaign source calls, 0 DB mutations.

## 15. Residual risks / setbacks / efficiency blockers

- A later live attempt can still honest-block if fewer than four lawful observation candidates exist. That is intended.
- Cycle 2 still requires a real fresh governed acquisition; readiness does not prove market supply at launch time.
- Holder-budget test fixtures remain stale relative to later identity-key / scope-root contracts. Separate from this readiness verdict.
- Historical reporting gaps remain. Separate.
- Fresh authorization, if later prepared, must bind **this readiness-closeout HEAD**, not `2c8caf0` and not the consumed authorization.

## 16. Exact next permitted lane

`V2-9.8B Post-Freeze-Input-Repair Two-Cycle Four-Token Operational 4/2/2 Fresh Authorization Preparation`

Must bind the exact readiness-closeout HEAD. Must not reuse `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z`.

This readiness closeout does **not** create that authorization and does **not** authorize execution.
