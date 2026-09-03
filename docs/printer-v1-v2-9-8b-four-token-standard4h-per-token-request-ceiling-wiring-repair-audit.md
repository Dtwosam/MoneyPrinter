# Printer V1 — Four-Token Standard-4H Per-Token Request-Ceiling Wiring Repair Readiness / Audit

Status: **CLOSED PASS as readiness/audit only**

Lane:

`FOUR-TOKEN STANDARD-4H PER-TOKEN REQUEST-CEILING WIRING REPAIR — READINESS / AUDIT`

Verdict:

`V2_9_8B_FOUR_TOKEN_STANDARD4H_PER_TOKEN_REQUEST_CEILING_WIRING_REPAIR_READINESS_AUDIT_PASS`

Repair classification:

`NARROW_POLICY_WIRING_REPAIR_FEASIBLE`

This audit does not implement the repair. It does not modify `src/`, tests,
migrations, or the authoritative DB. It does not run Printer, prepare an
authorization, or dispose the Sep-3 Cycle-2 finding.

---

## Baseline

- forensic closeout:
  `docs/printer-v1-v2-9-8b-auth-202fbea1-sep3-consumed-4-2-2-standard4h-post-run-forensic-closeout.md`
- forensic verdict:
  `V2_9_8B_SEP3_CONSUMED_4_2_2_STANDARD4H_POST_RUN_FORENSIC_CLOSEOUT_PASS`
- campaign result: `CAMPAIGN_FAILED`
- primary classification: `PROVEN_COMMITTED_BUDGET_ENFORCEMENT_DEFECT`
- consumed authorization:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1`
  (`CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`)
- authorized execution HEAD: `26d7b91bb5f115ad816b3cd632b5036d07b82b0e`
- audit start HEAD: same `26d7b91b...` (no production-code drift)
- untracked at audit start: this forensic closeout plus historical
  `operator-runs/` evidence directories
- post-run / audit DB SHA-256:
  `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`

Production code has not changed since the authorized execution HEAD. The audit
continued on that exact code identity.

---

## Proven failure restated

Authorized 4/2/2 envelope: `476 / 118 / 444`.

Observed Sep-3 factory lifecycle: run `82`, t1 `51`, t2 `31`, Scheduler jobs
`74`.

Failed step: factory `2110` / `t1_continuation_close_context` / Scheduler
`3744` / `SAFE_STOP_BUDGET_CEILING_EXCEEDED`.

The outer selector used `476`. The per-token selector used `50`. Replay of
`_enforce_budgets_before_step` against the post-run DB still raises the same
stop. That chain is reproduced in current committed code.

---

## 1. Outer run ceiling — 476; 102 not reachable for this mode

Producer:

`scaled_standard_four_hour_capacity_contract(4)["lifecycle_request_outer_ceiling"]`
= `2 * standard_four_hour_capacity_contract()["lifecycle_request_outer_ceiling"]`
= `2 * 238` = **476**

Same value on:

- `exact_operational_policy()["lifecycle_request_outer_ceiling"]`
- `FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY.governed_request_ceiling`
- frozen Sep-3 authorization `operational_policy`

Factory consumer:

`one_command_15m_factory._request_ceiling_for_run_config`

When `config["four_token_proof"]` is true it returns the scaled `476` and does
**not** fall through to `_SELECTIVE_1H_MAX_REQUESTS_RUN` (`102`).

`four_token_proof` is set true whenever
`four_token_proof_controller is not None`
(`one_command_15m_factory` config construction). Both operational
`four-token-standard-four-hour-run` and the proof-only four-token mode pass a
controller.

Sep-3 factory config had `four_token_proof = true`. Observed run count `82`
was below both `102` and `476`. The `102` run ceiling was **not** applied and
is **not reachable** for four-token Standard-4H.

Scheduler insert-time ceiling uses the matching helper
`_scheduler_ceiling_for_run_config` → **444** when `four_token_proof` is true.

---

## 2. Per-token ceiling — exact producer → consumer chain

### Approved value source

```text
standard_four_hour_capacity_contract()["lifecycle_requests_per_token"] = 118
scaled_standard_four_hour_capacity_contract(4)["lifecycle_requests_per_token"] = 118
exact_operational_policy()["lifecycle_requests_per_token"] = 118
FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY.governed_requests_per_token = 118
frozen Sep-3 operational_policy.lifecycle_requests_per_token = 118
```

The scaled four-token contract does **not** double the per-token figure. `118`
is the one-token 15m+1h+4h worst-case share after subtracting shared discovery
from the two-token outer envelope: `(238 - 2) / 2 = 118`.

### Stale value source

```text
_CONTEXT_REQUESTS_PER_TOKEN = PRECLOSE_CONTEXT_REQUEST_COUNT = 6
_MAX_GOVERNED_REQUESTS_PER_TOKEN = 16 + 6 = 22          # 15m TRACK_FAST
_CONTINUOUS_MAX_REQUESTS_PER_TOKEN
  = 22 + 24 + FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT(4)
  = 50                                                   # 15m+1h TRACK_FAST
_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN
  = _CONTINUOUS_MAX_REQUESTS_PER_TOKEN
  = 50
```

These are factory-local 15m / continuous-1h / selective-1h integrity constants.
They do not include `WINDOW_4H`. They are the correct selective-1h per-token
envelope.

### Defective consumer

`one_command_15m_factory._enforce_budgets_before_step`, pre-4h branch
(everything that is not `LONG_CONTINUATION_*`):

```text
run_ceiling = _request_ceiling_for_run_config(config)     # 476 when four_token_proof
token_ceiling = (
    _CONTINUOUS_MAX_REQUESTS_PER_TOKEN                   # 50
    if continuous_first_hour
    else _MAX_GOVERNED_REQUESTS_PER_TOKEN                # 22
)
if run_count + projected > run_ceiling: _GlobalStop
if token_count + projected > token_ceiling: _GlobalStop
```

There is **no** `_token_ceiling_for_run_config`. The 102-repair helper covers
only the **run** ceiling. Per-token still keys solely off
`continuous_first_hour`. Four-token Standard-4H sets
`continuous_first_hour = true` because `selective_1h_continuation = true`
reuses the 1h collection machinery. Therefore token ceiling **50**.

`CONTINUATION_CLOSE_CONTEXT` is not a `LONG_CONTINUATION_*` step, so the 4h
subset owner (`_standard_four_hour_cumulative_budget_for_run` /
`standard_campaign_lifecycle_budget`) is never consulted for this stop.

### Command policy is not wired into factory enforcement

`FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY.governed_requests_per_token = 118` exists
on the operational command. Factory config records `hard_ceilings` catalog
values (`selective_1h_governed_requests_per_token = 50`,
`selective_1h_governed_requests_run = 102`) and does **not** copy `118` into
the live per-token check. `max_source_requests = 2` on the Sep-3 config is the
discovery budget, not the lifecycle per-token ceiling.

### Propagation chain

```text
cadence policy (15m FAST 16, 1h FAST 24, 4h FAST 61)
  -> standard_campaign_lifecycle_budget / standard_four_hour_capacity_contract
  -> scaled_standard_four_hour_capacity_contract(4)
  -> exact_operational_policy() / FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY
  -> authorization document validator (requires exact 118)
  -> factory live enforcement DOES NOT READ THIS for pre-4h per-token
       instead:
         continuous_first_hour
           -> _CONTINUOUS_MAX_REQUESTS_PER_TOKEN (50)
           -> _enforce_budgets_before_step token check
           -> _GlobalStop
```

---

## 3. Minimum repair surface

Required behavior is **A**: four-token mode must enforce
`lifecycle_requests_per_token = 118`.

Matching existing factory shape is **B**: a config selector helper, the same
pattern as `_request_ceiling_for_run_config` / `_scheduler_ceiling_for_run_config`.

Canonical numeric owner is **C**:
`scaled_standard_four_hour_capacity_contract(4)["lifecycle_requests_per_token"]`
(same `118` as `exact_operational_policy()`). The 102 repair already used this
scaled contract, not a copied literal.

**D is not required.** No new budget owner, no cadence rewrite, no 4h subset
change, no global constant mutation.

Recommended minimum production change, later design/implementation only:

1. Add `_token_ceiling_for_run_config(config)`:
   - `four_token_proof` → scaled contract `lifecycle_requests_per_token` (`118`)
   - else `continuous_first_hour` → `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN` (`50`)
   - else `_MAX_GOVERNED_REQUESTS_PER_TOKEN` (`22`)
2. In `_enforce_budgets_before_step` pre-4h branch, replace the inline
   `token_ceiling = 50/22` assignment with that helper.

Do **not** change `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN` or
`_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN`. Those remain correct for selective-1h.

Exact production file expected to change:

`src/printer_v1/operator_cli/one_command_15m_factory.py`

Exact tests expected to change/extend:

`tests/test_v2_9_8b_standard4h_pre4h_request_ceiling_wiring.py`

That file already proves four-token **run** `476` vs selective-1h **run** `102`,
but it stubs `_token_request_count = 0`, so it never sees the `50` per-token
stop.

No wrapper, authorization profile, validator, or `exact_operational_policy()`
change is required. Those already bind `118`.

---

## 4. Callers and mode isolation

Production callers of `_enforce_budgets_before_step`:

| Caller | Role |
|---|---|
| factory loop after Scheduler claim | live enforcement (Sep-3 stop) |
| `authoritative_admission_health.project_lifecycle_budget_reserve` | read-only forecast; inherits the same token ceiling |

Modes:

| Mode | `four_token_proof` | Must keep | After repair |
|---|---|---|---|
| selective-1h | false | per-token **50**, run **102** | unchanged |
| 15m-only V2-5 | false, not continuous | per-token **22** | unchanged |
| four-token Standard-4H | true | run **476**, Scheduler **444**, per-token **118** | per-token becomes 118 |
| four-token proof-only | true | same scaled `118` | same helper; in family |
| two-token Standard-4H | false | policy `238 / 118 / 222` | **unchanged by this repair** |

Isolating to `four_token_proof` / `four-token-standard-four-hour-run` is
possible and is the minimum safe boundary. Proof-only four-token shares the
same flag and the same scaled `118`; including it is not a broadening.

Residual, **out of this repair**: two-token Standard-4H factory pre-4h
enforcement still selects run `102` and per-token `50` despite
`STANDARD_FOUR_HOUR_POLICY` `238 / 118`. Do not silently “fix” that here.

`_run_budgets` non-4h reporting still inlines per-token `50`. Four-token
Standard-4H sets `continuous_four_hour = true`, so Sep-3 reporting used the 4h
reporting branch (`token_ceiling = None` for standard campaigns) and did not
apply that `50` as a report ceiling. Do not expand the repair into reporting
unless the later design proves a four-token consumer still reads that field.

---

## 5. Global-stop semantics

Classification:

`GLOBAL_STOP_SEMANTICS_ALREADY_CORRECT`

`_enforce_budgets_before_step` documents a projected ceiling breach as a
**global integrity safe-stop**. The factory loop treats `_GlobalStop` as
run-wide (`stop_reason = gstop.reason`, fail the current step, then drain).
`TOKEN_LOCAL_*` is reserved for source/token-local failures, not budget
integrity.

Current authority does not say a genuine per-token `118` exhaustion should
become token-local. After wiring `118`, a real `current + projected > 118`
must still raise `_GlobalStop`. Do not redesign that in this repair.

---

## 6. Projected-count semantics

Owner: `_projected_requests_for_step`. Comparison in both
`_enforce_budgets_before_step` and `require_projected_capacity`:

```text
if current + projected > ceiling: reject
```

Exactly at the ceiling is lawful. Overshoot is not.

Sep-3 failing step `CONTINUATION_CLOSE_CONTEXT`:

- reserved operations for that kind: **0**
- projected: **0**
- t1 current: **51** already persisted (last key
  `t1_continuation_close_evidence:geckoterminal_fallback` at `13:43:58Z`)
- `51 + 0 > 50` → reject
- no new request on the failed step

Boundary matrix the later proof must use:

| current | projected | ceiling | `current + projected > ceiling` | required result |
|---|---|---|---|---|
| 50 | 0 | 118 | false | allow |
| 50 | 1 | 118 | false | allow |
| 51 | 0 | 118 | false | allow |
| 51 | 1 | 118 | false | allow |
| 117 | 1 | 118 | false | allow (exactly 118) |
| 118 | 0 | 118 | false | allow (no additional request) |
| 118 | 1 | 118 | true | reject |
| 119 | 0 | 118 | true | reject |
| 50 | 1 | 50 (selective-1h) | true | reject (mode preserved) |
| 49 | 1 | 50 (selective-1h) | false | allow |

---

## 7. Policy consistency

Authoritative 4/2/2 surfaces agree:

| Surface | outer | per-token | Scheduler | retries | rotation |
|---|---|---|---|---|---|
| `exact_operational_policy()` | 476 | 118 | 444 | 0 | false |
| scaled contract(4) | 476 | 118 | 444 | 0 | false |
| command `FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY` | 476 | 118 | 444 | 0 | n/a (factory hard-codes 0) |
| wrapper validator vs `exact_operational_policy()` | exact match required | 118 | 444 | 0 | false |
| Sep-3 frozen authorization | 476 | 118 | 444 | 0 | false |
| factory `_request_ceiling_for_run_config` (four_token_proof) | **476** | — | — | — | — |
| factory `_scheduler_ceiling_for_run_config` (four_token_proof) | — | — | **444** | — | — |
| factory `_enforce_budgets_before_step` per-token (four_token_proof) | — | **50 stale** | — | 0 | — |

Stale values still **reachable from four-token Standard-4H live enforcement**:

- per-token **50** via `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN` (this defect)

Stale values **catalogued but not selected** for this mode:

- `hard_ceilings.selective_1h_governed_requests_run = 102`
- `hard_ceilings.selective_1h_governed_requests_per_token = 50`

Stale values **not reachable** for four-token outer run: `102`.

---

## 8. Bounded-proof requirements (later implementation)

Focused unit/integration tests only. No live Standard-4H campaign as
implementation proof.

1. four-token config, t1 current `50`, projected `1` → no `_GlobalStop`
2. four-token config, t1 current `51`, projected `0` → no `_GlobalStop`
3. four-token config, t1 current `117`, projected `1` → no `_GlobalStop`
4. four-token config, t1 current `118`, projected `1` → `_GlobalStop`
5. selective-1h config, current `50`, projected `1` → `_GlobalStop` (50 retained)
6. four-token `_request_ceiling_for_run_config` remains `476`
7. four-token `_scheduler_ceiling_for_run_config` remains `444`
8. `automatic_retries` remains `0`; endpoint rotation remains false
9. genuine per-token `118` overshoot still `_GlobalStop` / `CUMULATIVE_LIFECYCLE`
10. no Source Governor or Scheduler bypass (existing claim/enforce/request order)

Prefer extending
`tests/test_v2_9_8b_standard4h_pre4h_request_ceiling_wiring.py` rather than a
new suite.

---

## 9. Cycle-2 finding

Classification:

`CYCLE2_FINDING_INDEPENDENT`

Sep-3 Cycle-2 pre-admission terminalized at `13:01:12Z` as `NO_PAIR` /
`DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`, with refresh wait `FAILED` on
`DUPLICATE_TRANSPORT_IDENTITY`. The budget stop was at `13:44:00Z` on Cycle-1
1h close. Duplicate-transport owners
(`measured_transport.DUPLICATE_TRANSPORT_IDENTITY`,
campaign six-unit accounting) do not share the per-token ceiling selector.

Admission-health `project_lifecycle_budget_reserve` *does* call
`_enforce_budgets_before_step`, so a later Cycle-2 attempt could be
false-blocked by the same `50` once Cycle-1 is above 50. That is a consequence
of this defect, not proof that the Sep-3 Cycle-2 finding is the same owner.
Keep a separate Cycle-2 disposition before another live 4/2/2 authorization.

---

## 10. DB / cleanup

Read-only at audit time:

- DB SHA-256 `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`
- official zero-state: all 13 required domains `0`
- `PRAGMA integrity_check` = `ok`
- `PRAGMA foreign_key_check` empty
- no non-terminal campaign rows
- authorization `...202fbea1` remains consumed; marker unchanged

---

## 11. Conclusion

```text
defective function:     _enforce_budgets_before_step (pre-4h token_ceiling)
                        missing _token_ceiling_for_run_config
stale value source:     _CONTINUOUS_MAX_REQUESTS_PER_TOKEN = 50
approved value source:  scaled_standard_four_hour_capacity_contract(4)
                        ["lifecycle_requests_per_token"] = 118
minimal production:     src/printer_v1/operator_cli/one_command_15m_factory.py
callers affected:       factory loop; admission-health forecast (inherits)
modes unchanged:        selective-1h 50; 15m 22; two-token Standard-4H leftover
global-stop:            GLOBAL_STOP_SEMANTICS_ALREADY_CORRECT
Cycle-2:                CYCLE2_FINDING_INDEPENDENT
```

Repair classification: `NARROW_POLICY_WIRING_REPAIR_FEASIBLE`

---

## Functionality risks / setbacks / efficiency blockers

- Two-token Standard-4H factory pre-4h path still uses `102 / 50` despite
  public policy `238 / 118`. Out of scope; do not silently widen this repair.
- Selective-1h command policy currently prints `92 / 45` while factory
  constants are `102 / 50`. Unrelated catalog mismatch; do not “align” by
  changing `50`.
- `_run_budgets` non-4h reporting still inlines `50`; four-token reporting
  currently takes the 4h branch. Confirm in design whether that field needs
  the new helper.
- Fallbacks can push a token over a tight envelope (Sep-3 t1 51 vs 50). `118`
  has headroom for 15m+1h+4h plus some fallbacks; the later design must not
  treat fallback extras as a reason to raise `118`.
- Cycle-2 duplicate-transport remains a separate live-authorization blocker.
- Consumed `...202fbea1` is permanently non-reusable. Future prior-non-reuse
  root is 60 IDs.

---

## Next permitted lane

```text
FOUR-TOKEN STANDARD-4H PER-TOKEN REQUEST-CEILING WIRING REPAIR — DESIGN / SPECIFICATION
```

Do not implement automatically. Do not run Printer. Do not create or prepare
another authorization.
