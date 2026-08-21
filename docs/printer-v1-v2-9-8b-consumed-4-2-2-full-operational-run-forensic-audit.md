# Printer V1 V2-9.8B Consumed 4/2/2 Full Operational Run Forensic Audit

Date: 2026-08-21

Lane type: audit / readiness only. No repair implementation.

## 0. Executive verdict

`V2_9_8B_CONSUMED_4_2_2_FULL_OPERATIONAL_RUN_FORENSIC_AUDIT_PASS_READY_FOR_DESIGN`

The consumed one-shot campaign ran exactly once, stayed inside V1 locks, cleaned
to a true zero state, and left durable evidence sufficient to classify the major
abnormal outcomes.

Primary proven defects that must be designed/repaired before another fresh
authorization:

1. **Cycle2 token `token_status` left NULL**, so Lane Q cadence lookup fell back
   to the first `WINDOW_15M` policy (`TRACK_FAST`, `block_at=120s`) instead of the
   actual snapshot lane `TRACK_NORMAL` (`block_at=240s`, dirty band starts at
   `180s`). That false TRACK_FAST evaluation is what dirtied Cycle2 windows
   231/232 despite E2Q clean-candidate classification and TRACK_NORMAL cadence
   PASS under the correct policy.
2. **1H → 4H never materialized** after two Cycle1 `WINDOW_1H` `CLEAN_PROMOTED`
   closes with exact `WINDOW_1H_CLEAN_MEMORY` episodes. Terminal cause collapsed
   to `SAFE_STOP_PREFLIGHT_FAILED` with empty `fault_details` / no preserved
   primary orchestration exception in the final report.
3. **Multi-cycle terminal accounting/reporting is Cycle1-scoped**, producing
   `NO_CAMPAIGN_SLOT_FOR_TOKEN:77/78` and
   `SCHEDULER_PROJECTION_WITHOUT_WINDOW:2475..2492` even though Cycle2 owned
   exact slots/windows and all 18 Cycle2 scheduler jobs succeeded.
4. **Serial close contention** on Cycle2 inflated closing inter-snapshot gaps to
   ~127.7s / ~134.8s. Under correct TRACK_NORMAL policy those gaps alone are
   not dirty; they become decisive only when mis-bound to TRACK_FAST.

Authorization remains permanently consumed. No retry/rerun/resume/restart/
successor is permitted.

## 1. Exact runtime identity

| Item | Value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit` |
| Authorized/runtime branch | `agent/v2-9-8b-pair-ready-parent-terminal-cancellation-repair` |
| Authorized/runtime HEAD | `9a1f0a2eb1cc4f2d179b7d1a4c07a0b69c8b537b` |
| Authorization ID | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436` |
| Authorization SHA-256 | `fbec54fca9fd8ec2e6dd95cf3dd3066d680cc8717b56ef3a0a0e213b0531a100` |
| Application root | `~/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436/` |
| Marker SHA-256 | `2855e6c77805f8973bac49f978469156aa432916563c72980340baa1eae9f7b9` |
| Manifest SHA-256 | `ee782bfcc17b86c5b6a39732bf9120ab84daef61e8de6749254c39299b77e7a0` |
| Child PID | `43640` |
| Child exit | `0` |
| Wrapper classification | `CHILD_EXITED_ZERO` |
| Campaign | `20260821T160842Z-2d39af1663dd-campaign` |
| Campaign run | `20260821T160842Z-2d39af1663dd-campaign-run` |
| Factory run | `23662756-9226-4f50-a89d-457e78d37a68` |
| Supervision | `20260821T160842Z-2d39af1663dd-supervision` |
| Cycle1 | `20260821T160842Z-2d39af1663dd-cycle` |
| Cycle2 | `20260821T160842Z-2d39af1663dd-cycle-2` |
| Started | `2026-08-21T16:08:40.824613+00:00` |
| Ended | `2026-08-21T17:09:54.008973+00:00` |
| First terminal cause | `SAFE_STOP_PREFLIGHT_FAILED` |
| Campaign acceptance | `BLOCKED_UNSAFE` |
| Campaign DB state | `TERMINAL_FAILED` |
| Elapsed (six-unit) | `3669.145s` (~61.2 min) |

`CURRENT_HANDOFF.md` is stale (still describes final-authorization construction)
and must not override this audit or the persisted runtime evidence.

## 2. Evidence sources used

Read-only only:

- active source stack (`AGENTS.md`, Clean Master Spec, Post-RC / Memory Factory /
  memory-growth build-order docs, stale handoff)
- application package: marker, manifest, wrapper-terminal, child-terminal,
  child-stdout (~884 KiB), empty child-stderr
- execution root:
  `~/PrinterOperations/v2-9-8/20260821T160842Z-2d39af1663dd/`
  (campaign-report, terminal-summary, pre-campaign backup)
- authoritative SQLite read-only:
  `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- static production owners:
  `lane_q_15m_window_integrity_guard.py`,
  `cadence_policy.py`,
  `lane_u2_coverage_audit_persistence.py`,
  `lane_k_e2z_pipeline_wiring.py`,
  `campaign_full_run_accounting.py`,
  `campaign_ownership.py`,
  `operational_selective_1h.py`,
  `one_command_15m_factory.py`,
  four-token wrapper/composition modules

No provider/RPC/WebSocket calls, no DB writes, no campaign, no authorization
mutation, no production/test code changes.

## 3. Authorization / wrapper (Surface A)

| Check | Result | Classification |
| --- | --- | --- |
| Auth ID/hash/size/mode bind | exact match to reviewed package | `NOT_A_DEFECT` |
| Branch/HEAD bind | exact authorized branch/HEAD | `NOT_A_DEFECT` |
| Marker create-once / consumed | consumed at `16:08:40.824562Z` | `NOT_A_DEFECT` |
| One child invocation | single PID `43640`; retries/reruns/restarts/resumes/successors all `0` | `NOT_A_DEFECT` |
| Endpoint rotation | `false` | `NOT_A_DEFECT` |
| Exact 4/2/2 policy | `4/2/2`, spacing `300`, acq `2400`, life `18000`, `118/476/4/420`, storage `67108864`, `15M→1H→4H`, 5m support-only, 12h/24h locked | `NOT_A_DEFECT` |
| Process exit `0` vs objective success | exit 0 with `SAFE_STOP_PREFLIGHT_FAILED` / `BLOCKED_UNSAFE` | `EXPECTED_POLICY_BEHAVIOR` for one-shot consumption; do not equate exit 0 with campaign success |

## 4. Chronological run timeline

| UTC | Event |
| --- | --- |
| 16:08:40.824 | Marker consumption; child start |
| 16:08:43.535 | Campaign/run/cycle1/slots created; discovery begins |
| 16:09:05 | Cycle1 discovery/handoff work sealed; 15M windows planned |
| 16:09:10 / 16:09:15 | Cycle1 slot1/slot2 first snapshots (tokens 75/76) |
| 16:24:24 / 16:24:35 | Cycle1 15M closes; E2Z clean episodes 100/101; both CONTINUE_TO_WINDOW_1H |
| 16:24:35 | Cycle1 WINDOW_1H planned/opened for both slots |
| 16:25:08 | Cycle2 admitted (`…-cycle-2`); slots `…-cycle-2-1/2` (tokens 78/77) |
| 16:25:13 / 16:25:15 | Cycle2 first snapshots |
| 16:40:14 → 16:40:32 | Cycle2 slot1 close job 2484 runs (~18.6s wall) |
| 16:40:32 → 16:40:41 | Cycle2 slot2 close job 2492 runs after waiting on sibling |
| 16:40:32 / 16:40:41 | Cycle2 15M dirtied by Lane Q TRACK_FAST mis-bind; no E2Z; 1H blocked |
| 16:24:35 → 17:09:45/52 | Cycle1 WINDOW_1H collection continues through Cycle2 lifetime |
| 17:09:45 | Cycle1 slot1 1H `CLEAN_PROMOTED` + episode 102 |
| 17:09:52 | Cycle1 slot2 1H `CLEAN_PROMOTED` + episode 103 |
| 17:09:52.64 | Safe-stop terminalization; slots → `MANUAL_REVIEW` / `SAFE_STOP_PREFLIGHT_FAILED` |
| 17:09:52.66 | Cleanup complete; lease released |
| 17:09:54 | Wrapper ends `CHILD_EXITED_ZERO` |

## 5. Per-token lifecycle table

| Slot | Cycle | Token/Pair | 15M campaign | 15M memory | Episode | 1H | 4H | Final slot state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `…-cycle-1` | 1 | 75/79 | `CLEAN_PROMOTED` | window `PARTIAL_MEMORY` + `CLEAN_DATA`; episode/fingerprint `CLEAN_MEMORY` | 100 / 64 | `CLEAN_PROMOTED` (233 / ep 102) | none | `MANUAL_REVIEW` |
| `…-cycle-2` | 1 | 76/80 | `CLEAN_PROMOTED` | same pattern | 101 / 65 | `CLEAN_PROMOTED` (234 / ep 103) | none | `MANUAL_REVIEW` |
| `…-cycle-2-1` | 2 | 78/82 | `DIRTY` | `DIRTY_MEMORY` / `MISSING_CRITICAL_DATA` / `do_not_train=1` | none | blocked | none | `MANUAL_REVIEW` |
| `…-cycle-2-2` | 2 | 77/81 | `DIRTY` | same | none | blocked | none | `MANUAL_REVIEW` |

Notes:

- E2O always creates `PARTIAL_MEMORY` rows; E2Z then creates CLEAN episodes for
  Cycle1. Window-row `PARTIAL_MEMORY` beside episode `CLEAN_MEMORY` is an
  established intermediate/reporting divergence, not by itself the Cycle2 failure.
- Cycle2 was an E2Q clean candidate (`E2Q_AUDIT_CLEAN_CANDIDATE`) before Lane Q
  blocked promotion.

## 6. Discovery / admission (Surface C)

| Cycle | Result | Classification |
| --- | --- | --- |
| Cycle1 | admitted 2 fresh/disjoint tokens; PumpSwap/protocol path present; floor/depth satisfied | `NOT_A_DEFECT` |
| Cycle2 | admitted later at `16:25:08`; fresh/disjoint from Cycle1; exact slots `…-2-1/2` | `NOT_A_DEFECT` |
| Supply | enough eligible supply for both cycles; no scarcity blocker for this run | `NOT_A_DEFECT` |
| Cycle2 `printer_tokens.token_status` | remains `NULL` after admission/tracking | **`PROVEN_CODE_DEFECT`** |

GoPlus/source scarcity did **not** cause Cycle2 dirty. All GoPlus requests in
window were `COMPLETE`; source failures in campaign window: `0`.

## 7. Snapshot cadence and the >120s gaps (Surface F)

### 7.1 Measured closing gaps

| Window | Token | Prev snap → close snap | Gap | Close job wait | Close exec |
| --- | --- | --- | --- | --- | --- |
| 231 | 78 | 16:38:25.019 → 16:40:32.720 | **127.701s** | job 2484 due 16:40:13.5, start 16:40:14.1 (~0.6s) | ~18.6s to capture/finish |
| 232 | 77 | 16:38:27.037 → 16:40:41.811 | **134.774s** | job 2492 due 16:40:15.9, start 16:40:32.8 (**~16.9s** behind sibling) | ~9.0s |

Producer/consumer contract:

1. Cadence planner schedules FIRST_15M snapshots on ~112.5s nominal spacing with
   forced close near +900s.
2. Central Scheduler claims due close jobs.
3. Close work is effectively **serial across sibling tokens** in this run.
4. Closing observation timestamp is the close-path capture time, so sibling wait
   + close/context work inflate the final inter-snapshot gap.

### 7.2 Correct vs incorrect policy evaluation

Authoritative TRACK_NORMAL 15M policy:

- target `120`
- dirty_above / clean_max property `180`
- blocked_at `240`
- minimum snapshots `9`

Independent re-evaluation with TRACK_NORMAL:

- 231/232 → `CADENCE_POLICY_PASS`
- Cycle1 227/228 also PASS with max gaps 123.4 / 126.2

Lane Q at Cycle2 close used `get_policy(WINDOW_15M, None)` because
`printer_tokens.token_status` was NULL, which selects the **first** WINDOW_15M
row = TRACK_FAST (`blocked_at=120`). Reproduced exactly:

`coverage_gap_exceeds_policy: max_gap=127.7s block_at=120s`

| Question | Answer | Classification |
| --- | --- | --- |
| What caused each >120s gap? | Forced close capture delayed by close-path work; token2 also waited on token1 close | scheduling reality |
| Deterministic/systemic? | Yes under serial sibling close while both are due | **`PROVEN_CODE_DEFECT`** for lack of deadline-protecting concurrent close admission; gap magnitude itself is systemic |
| Recur with two tokens? | Yes whenever both closes contend | same |
| Worsen with Cycle3/future work? | Yes if more due work shares the same serial close consumer | future contention risk |
| Did >120s alone correctly dirty under TRACK_NORMAL? | **No** (PASS until >180) | mis-dirty is not justified by TRACK_NORMAL |
| True dirty producer | Lane Q NULL-lane → TRACK_FAST fallback | **`PROVEN_CODE_DEFECT`** |

U2 coverage rows/gap audits were written for Cycle1 (`+1` coverage, `+8` gaps)
and **not** for Cycle2 (`coverage_persisted_count=0`, gap delta `0`), consistent
with Lane K blocking before/without durable U2 persistence for those windows.

## 8. Memory quality / context (Surfaces G–H)

| Window | E2Q | Lane Q / E2Z | Final memory | Campaign window |
| --- | --- | --- | --- | --- |
| 227/228 | clean candidate / PARTIAL audit label | valid → E2Z CLEAN episode | window PARTIAL + CLEAN_DATA; episode CLEAN | CLEAN_PROMOTED |
| 231/232 | clean candidate | blocked: false TRACK_FAST gap policy → downgrade | DIRTY / MISSING_CRITICAL / DNT=1 | DIRTY |
| 233/234 | PARTIAL audit label | 1H path produced CLEAN episodes | window PARTIAL + CLEAN_DATA; episode CLEAN | CLEAN_PROMOTED |

Optional unknowns present on clean and dirty alike and **not** proven causal to
dirty:

- `WALLETS_UNKNOWN`
- `TRADING_FLOW_CONTEXT_PARTIAL`
- safety raw `SAFETY_UNKNOWN` with effective acceptable-for-15m
- `liquidity_lock_or_burn_label` / `known_risk_flag_label` pending

Classification: `EXPECTED_POLICY_BEHAVIOR` / optional unknown — **not** the Cycle2
dirty root cause.

CLEAN candidate → DIRTY transition for 231/232 is explained by Lane K downgrade
after Lane Q TRACK_FAST mis-evaluation, not by missing chart/liquidity/market
context.

No evidence Printer marked dirty/partial evidence as clean for Cycle2.
Cycle1 episodes are CLEAN while window rows remain PARTIAL: reportable
intermediate divergence, not a false-clean of dirty evidence.

## 9. 15M → 1H and WINDOW_1H (Surfaces I–J)

| Item | Result | Classification |
| --- | --- | --- |
| Cycle1 both tokens CONTINUE_TO_WINDOW_1H | yes | `NOT_A_DEFECT` |
| Cycle2 both BLOCK_CONTINUATION | yes, because predecessors dirtied | consequence of defect #1 |
| Cycle1 1H cadence/coverage | 13/13, continuity continuous, CADENCE_POLICY_PASS despite large mid-1h gaps under 1H NORMAL thresholds | `NOT_A_DEFECT` |
| Cycle1 1H terminal | both `CLEAN_PROMOTED` with `window_1h_closed_clean_promoted`; episodes 102/103 `WINDOW_1H_CLEAN_MEMORY` | `NOT_A_DEFECT` |
| Slot state after 1H close | should be `WINDOW_1H_CLOSED`; final durable state is `MANUAL_REVIEW` after safe-stop | see Surface K |

## 10. 1H → 4H failure (Surface K)

Facts:

- `WINDOW_4H` count = 0
- no durable 4H campaign windows
- `continuous_four_hour=true` / standard-four-hour campaign true
- both Cycle1 1H windows and exact clean 1H episodes existed immediately before
  terminalization
- ~17ms after second 1H terminal, slots were safe-stopped to `MANUAL_REVIEW`
  with `first_terminal_cause=SAFE_STOP_PREFLIGHT_FAILED`
- final report `fault_details={}` and no recoverable
  `orchestration_error` / ownership exception string

Required owner for handoff (`campaign_ownership` four-hour path) demands slot
state in `{WINDOW_1H_CLOSED, WINDOW_4H_CONTINUING}` before creating PLANNED 4H
windows. `reconcile_1h_terminal_lifecycle` is the owner that should write
`WINDOW_1H_CLOSED` on successful `CLEAN_PROMOTED`.

Independent conclusion:

1. Second successful 1H close completed.
2. Standard 4H planning/handoff did not persist any WINDOW_4H.
3. Generic exception → `SAFE_STOP_PREFLIGHT_FAILED` path fired.
4. Primary exception text was not preserved in terminal truth
   (`fault_details` empty) — **`PROVEN_CODE_DEFECT`** in failure reporting.
5. Exact first failing 4H contract call is
   **`UNPROVEN_REQUIRES_MORE_EVIDENCE`** without the lost exception string, but
   the missing 4H outcome after eligible Cycle1 1H closes is itself a
   **`PROVEN_CODE_DEFECT`** in the post-1H standard-four-hour progression path.

Do not treat absent durable eligibility manifest alone as root cause after
rollback; absence is consistent with failed/never-committed handoff.

## 11. Cycle2 accounting / terminal reporting (Surface L)

Production lookup in `campaign_full_run_accounting.py`:

```sql
SELECT ... FROM printer_memory_factory_campaign_token_slots
WHERE cycle_id=? AND token_row_id=?
```

with `cycle_id` taken from the Cycle1-scoped accounting context
(`…-cycle`), while tokens 77/78 live on `…-cycle-2`.

| Finding | Runtime truth | Report effect | Classification |
| --- | --- | --- | --- |
| `NO_CAMPAIGN_SLOT_FOR_TOKEN:78/77` | slots exist on Cycle2 | acceptance/compensation blocked | **`REPORTING_ONLY_DEFECT`** |
| `SCHEDULER_PROJECTION_WITHOUT_WINDOW:2475..2492` | all those jobs `SUCCEEDED` with Cycle2 windows/work | same | **`REPORTING_ONLY_DEFECT`** |
| `selective_1h_outcome=EVALUATION_BLOCKED_SYSTEM_DEFECT` | classifier requires exactly 2 token plans; campaign has 4 | misleading multi-cycle report | **`REPORTING_ONLY_DEFECT`** |

These findings are not the cause of Cycle2 dirty memory or missing 4H
collection. They did cause `campaign_acceptance=BLOCKED_UNSAFE`.

## 12. Terminal cause / cleanup / ceilings (Surfaces M–N)

| Item | Result | Classification |
| --- | --- | --- |
| Why `SAFE_STOP_PREFLIGHT_FAILED`? | generic exception handler / later-cycle disposition mapped to `STOP_PREFLIGHT`; primary exception not retained in final fault_details | **`PROVEN_CODE_DEFECT`** (preservation) + unproven exact exception body |
| Exit code 0 | one-shot child completed wrapper protocol after safe-stop | `NOT_A_DEFECT` |
| Cleanup complete / lease released | yes | `NOT_A_DEFECT` |
| Active owned work / campaigns / cycles / jobs / factory / discovery / pre-admission / supervision | all 12 zero-state domains 0 | `NOT_A_DEFECT` |
| integrity_check / FK / sidecars | ok / 0 / none | `NOT_A_DEFECT` |
| Request/Scheduler/storage ceilings | six-unit transport 84, lifecycle reserved 60, scheduler work items 46, wrapper scheduler_runtime_calls 267 << 420; no storage-ceiling breach observed | `NOT_A_DEFECT` |
| Protected capabilities | retrieval/BUY/SELL/HOLD/positions/trades/audits/PnL/12h/24h all remain locked; 5m support-only | `NOT_A_DEFECT` |

## 13. Provider / Source Governor table (Surface E)

Campaign-window durable source requests (approx. 119 in DB time range; envelope
`source_calls=13` is pre-lifecycle-scoped accounting, not full lifecycle
transport):

| Family | Status | Role vs Cycle2 dirty |
| --- | --- | --- |
| DexScreener pair snapshots | COMPLETE (dominant) | not causal |
| GeckoTerminal | COMPLETE | not causal |
| GoPlus safety_reference | COMPLETE (8) | **rejects GoPlus-latency dirty hypothesis** |
| Solana RPC holders/mint/PumpSwap | COMPLETE | not causal |
| Jupiter paper quotes | COMPLETE | paper-sim only |
| CoinGecko broad market | COMPLETE | context only |
| Source failures in window | 0 | no provider-caused memory failure proven |

Hypothesis “GoPlus/source latency caused Cycle2 dirty”: **REJECTED**.

## 14. Finding ledger

| ID | Finding | Classification |
| --- | --- | --- |
| F1 | Cycle2 `printer_tokens.token_status` NULL after admission/tracking | `PROVEN_CODE_DEFECT` |
| F2 | Lane Q resolves NULL lane to first WINDOW_15M policy TRACK_FAST (`block_at=120`) | `PROVEN_CODE_DEFECT` |
| F3 | Cycle2 dirtied / no E2Z because of F2 despite TRACK_NORMAL PASS and E2Q clean candidate | `PROVEN_CODE_DEFECT` |
| F4 | Serial sibling close contention produced 127.7s/134.8s closing gaps | `PROVEN_CODE_DEFECT` (deadline protection gap) and scheduling reality |
| F5 | Under correct TRACK_NORMAL policy those gaps are not dirty | `NOT_A_DEFECT` / corrects false “must raise 120 limit” narrative |
| F6 | No WINDOW_4H after two eligible Cycle1 clean 1H closes | `PROVEN_CODE_DEFECT` |
| F7 | Terminal cause collapsed to `SAFE_STOP_PREFLIGHT_FAILED` with empty fault_details | `PROVEN_CODE_DEFECT` |
| F8 | Exact 4H exception string missing | `MISSING_EVIDENCE` / `UNPROVEN_REQUIRES_MORE_EVIDENCE` for precise contract line |
| F9 | `NO_CAMPAIGN_SLOT_FOR_TOKEN` / `SCHEDULER_PROJECTION_WITHOUT_WINDOW` for Cycle2 | `REPORTING_ONLY_DEFECT` |
| F10 | Multi-cycle `selective_1h_outcome` SYSTEM_DEFECT classifier assumes N=2 plans | `REPORTING_ONLY_DEFECT` |
| F11 | Optional unknowns (wallets/flow/lock-burn) present | `EXPECTED_POLICY_BEHAVIOR` |
| F12 | One-shot consumption, no retry/successor, cleanup zero-state | `NOT_A_DEFECT` |
| F13 | Provider scarcity/GoPlus did not cause dirty | `NOT_A_DEFECT` (hypothesis rejected) |
| F14 | Window PARTIAL vs episode CLEAN on Cycle1 | `REPORTING_ONLY_DEFECT` or established intermediate semantics; not Cycle2 root cause |

## 15. Causal graphs

### Cycle2 dirty

```text
Cycle2 admission
  -> printer_tokens.token_status left NULL                    [F1]
  -> Lane Q _get_token_tracking_lane() returns None
  -> get_policy(WINDOW_15M, None) => TRACK_FAST               [F2]
  -> evaluate_cadence max_gap 127.7/134.8 > block_at 120      [F4 contributes magnitude]
  -> Lane K downgrade DIRTY/MISSING_CRITICAL; no E2Z          [F3]
  -> campaign window DIRTY; 1H blocked
```

### Missing WINDOW_4H

```text
Cycle1 both WINDOW_1H CLEAN_PROMOTED + CLEAN episodes
  -> post-1H standard-four-hour progression attempted
  -> no WINDOW_4H persisted                                  [F6]
  -> exception mapped to SAFE_STOP_PREFLIGHT_FAILED          [F7]
  -> slots terminalized MANUAL_REVIEW; cleanup zero-state
```

### Acceptance BLOCKED_UNSAFE (reporting)

```text
Cycle1-scoped accounting context.cycle_id
  -> Cycle2 token_row lookup misses
  -> NO_CAMPAIGN_SLOT + SCHEDULER_PROJECTION_WITHOUT_WINDOW  [F9]
  -> campaign_acceptance fail checks
```

## 16. Cross-cutting answers

1. **Cycle2 >120s gaps:** closing observation delayed by close-path work; token2
   also waited on token1 close.
2. **Deterministic/systemic:** yes under serial sibling closes.
3. **Recur with two tokens:** yes.
4. **Worsen with Cycle3/future workloads:** yes without protected close/snapshot
   admission.
5. **1H→4H safe stop:** post-1H standard-four-hour progression failed; exact
   exception text missing; outcome is proven no-4H + SAFE_STOP_PREFLIGHT_FAILED.
6. **Cycle2 accounting errors:** reporting-only, not runtime-causal.
7. **Provider/source failure cause memory/lifecycle failure?** No.
8. **Incorrectly mark clean dirty?** Yes for Cycle2 via F1/F2/F3.
9. **Incorrectly mark dirty clean?** No proven case.
10. **Required evidence missed?** Cycle2 lost clean promotion through false
    policy bind; 4H never collected.
11. **Optional evidence missed:** wallets/flow/lock-burn unknowns — optional.
12. **Scheduler deadline protection adequate?** Insufficient for sibling close
    contention under multi-token due-close clustering.
13. **Source Governor correct?** No bypass/provider-causal failure proven.
14. **Inside ceilings?** Yes.
15. **Protected capability activation?** None.
16. **True safe zero state?** Yes.
17. **Defects before next fresh auth:** F1–F4, F6–F7, and reporting F9–F10 at
    least to design/repair; do not merely raise the 120s limit.
18. **Not defects / honest unknowns:** optional context unknowns; one-shot
    consumption; exit-code-0 wrapper completion; TRACK_NORMAL PASS of ~127s
    gaps; provider completeness on this run.

## 17. Future contention / capacity (Surface O)

Resource classes that already competed or will compete with evidence deadlines:

- sibling token close/context work (observed)
- cross-cycle overlap (Cycle1 1H concurrent with Cycle2 15M — observed)
- future Cycle3 admission/discovery quanta
- later retrieval / paper monitor / paper decision-audit lanes when unlocked

Recommendation for design (not implementation here): explicit protected
scheduling/admission priority for active evidence-window snapshot and close
deadlines before adding Cycle3 or future locked workloads.

## 18. Minimum repair scope and sequencing

Design-only next lanes (do not implement in this task):

1. **Design: Cycle-scoped token status / Lane Q lane authority**
   - ensure later-cycle tokens persist cadence lane (`TRACK_NORMAL`)
   - Lane Q must not fall back NULL→TRACK_FAST; prefer snapshot/supporting_context
     lane; fail closed or UNKNOWN rather than wrong tight policy
   - bounded proof: disposable two-cycle close with NULL-status negative test and
     correct-status positive test
2. **Design: evidence-deadline protected scheduling for multi-token closes**
   - concurrent or priority close admission for due sibling closes
   - bounded proof: two due closes no longer serialize into >dirty-band gaps
3. **Design: post-1H standard-four-hour progression + fault preservation**
   - ensure WINDOW_1H_CLOSED → 4H handoff path runs and persists or fails with
     exact recoverable exception in terminal truth
   - bounded proof: two clean 1H closes produce WINDOW_4H PLANNED/CONTINUING or
     explicit typed blocker
4. **Design: multi-cycle terminal accounting/reporting**
   - stop Cycle1-only slot projection; classify 4-plan selective outcomes without
     false SYSTEM_DEFECT
   - bounded proof: Cycle2 jobs/slots attribute exactly

Do **not** “fix” Cycle2 by raising the TRACK_FAST 120s limit. The source stack
shows TRACK_NORMAL already permits these gaps; the defect is wrong policy bind.

## 19. Schema / migration implications

Possibly needed after design approval:

- stronger invariant that admitted/tracked tokens always carry cadence
  `token_status` in `{TRACK_FAST, TRACK_NORMAL}`
- no mandatory schema change identified for reporting-only cycle-scoped
  accounting if fixed in projection code
- no BUY/retrieval/12h/24h schema unlocks

## 20. Affected production owners/files

- `src/printer_v1/operator_cli/lane_q_15m_window_integrity_guard.py`
- `src/printer_v1/snapshots/cadence_policy.py` (`get_policy(None)` fallback)
- later-cycle admission / token status writers (factory/discovery/tracking path)
- `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py`
- scheduler/close execution path (serial sibling closes)
- `src/printer_v1/operator_cli/campaign_ownership.py` / standard-4h progression
- `src/printer_v1/operator_cli/operational_selective_1h.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py` (STOP_PREFLIGHT mapping)
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`

## 21. Preserved V1 locks

Solana-only; memecoin-only; paper-only; no wallet/private keys/signing/real funds/
live execution; no paid APIs; no scoring/ranking/confidence/weighted logic; no
embeddings/vectors; no Source Governor/Central Scheduler bypass; no retrieval;
no BUY/SELL/HOLD; no positions/trades/audits/PnL; 5m support-only; 12h/24h locked.

## 22. CURRENT_HANDOFF.md reconciliation required

Handoff still claims construction-precommit lane and unconsumed authorization.
Required future docs-only handoff update (separate lane) must record:

- authorization `…512f2436` permanently consumed
- campaign `…2d39af1663dd` terminal `SAFE_STOP_PREFLIGHT_FAILED` /
  `BLOCKED_UNSAFE`
- this forensic audit PASS_READY_FOR_DESIGN
- next design lanes above
- no automatic fresh authorization

## 23. Exact next permitted DESIGN lane(s)

Minimum lawful order:

1. `V2-9.8B Cycle2 Token-Status / Lane-Q Cadence Authority Design`
2. `V2-9.8B Multi-Token Evidence-Deadline Scheduling Design`
3. `V2-9.8B Post-1H Standard-Four-Hour Progression + Fault-Preservation Design`
4. `V2-9.8B Multi-Cycle Terminal Accounting/Reporting Design`

Then: implementation → bounded disposable proof → closeout → fresh readiness →
new exact-HEAD authorization (never reuse `…512f2436`).

Do not start those designs in this audit task unless separately authorized.
