# Printer V1 V2-9.8B Post-DTW100 E2Q / WINDOW_1H Current-State Audit Closeout

## Primary classification

`E2Q_WINDOW_1H_REPAIR_ALREADY_SUPERSEDED_WITH_PROOF`

The historical X14 Attempt 3C E2Q blocker is real historical evidence, but it is not the current E2Q implementation state. The exact blocker was repaired by V2-6, retained by current source, protected by focused regression tests, and then crossed successfully by the bounded continuous first-hour V2-7 proof.

This closeout is audit-only. It does not authorize or run another WINDOW_1H proof, create authorization, change production code, apply a migration, call a provider/RPC, run Scheduler work, mutate the authoritative DB, generate memory, activate retrieval, create paper decisions, unlock BUY/SELL/HOLD, create positions/trades/audits/PnL, or activate 4h/12h/24h.

---

## 1. Baseline / repository verification

| Item | Result |
|---|---|
| Repository | `Dtwosam/MoneyPrinter` |
| Audit branch | `agent/v2-9-8b-post-dtw100-e2q-window1h-current-state-audit` |
| Required starting HEAD | `cdc6bd08f59f376d5bc93f0d8859af978f3e0c03` |
| Observed remote branch HEAD before audit write | exact match |
| Required parent DTW100 closeout | `059f4fad26d508b09cc361bc267049adc3cdb9ce` |
| Ancestry | `cdc6bd08...` is exactly one commit ahead of `059f4fad...`; only the audit-plan doc differs |
| Remote alignment | branch vs `cdc6bd08...` was `identical` / 0 ahead / 0 behind before this closeout |
| Repository visibility | currently public; this differs from the earlier handoff's last-observed private state but does not alter this lane |
| Authoritative DB trust anchor | `6ce0e27332427243cffd055c41de58408f46dbcd84d43a764bf1764915a176fb` (DTW100 closeout anchor; DB not opened in this audit) |

The GitHub connector provides repository/ref state, not a local worktree. No local checkout was used or mutated. Therefore there was no local staged/unstaged tree to inspect; the remotely committed branch state was exact and transactional before this documentation-only write.

Active stack reviewed:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- DTW100 closeout
- this lane's audit plan
- current E2Q/E2O/1h runner/selective-1h source and tests
- historical X14 Attempt 3C evidence summarized by the current-state audit
- V2-6 E2Q repair history
- V2-7 bounded continuous first-hour proof closeout
- later V2-9.8B operational selective-1h audit/implementation/proof-command/readiness closeouts

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside this source stack, not the sole source of truth. Later committed implementation/proof closeouts control current implementation facts where older roadmap wording is stale.

---

## 2. Current E2Q owner and exact call chain

Canonical E2Q owner:

- module: `src/printer_v1/operator_cli/e2q_memory_window_audit.py`
- function: `audit_15m_memory_window(connection, window_id)`

The function name is historical. Its current behavior is no longer 15m-only.

Current operational selective-1h ownership is an extension of the existing campaign/factory path, not a parallel production runner:

```text
scripts/Start-PrinterV1-MemoryFactory.ps1
  -> printer_v1.operator_cli.operational_memory_factory_command
  -> AuthoritativeLiveOperationalCampaignOwner.run_operational
  -> OriginToLifecycleCampaignDriver
  -> run_one_command_15m_factory
  -> B.1 authoritative 15m promotion + token-local 4A continuation evaluation
  -> selective WINDOW_1H continuation jobs under the existing factory/Scheduler owner
  -> lane_e2o_1h_window_close.close_1h_memory_window_from_snapshot
  -> e2q_memory_window_audit.audit_15m_memory_window
  -> E2Z per-window clean-memory promotion gate when eligible
  -> terminal reconciliation / report-only replay
```

The historical X12 proof path also remains in source:

```text
run_1h_memory_factory_cycle
  -> _run_x12_token_step(close_window=True)
  -> close_1h_memory_window_from_snapshot
  -> audit_15m_memory_window
```

X12/Lane H are proof-era components, not the V2-9.8B operational front door.

---

## 3. Current conditions that restrict E2Q by window kind

There is **no current blanket condition requiring `WINDOW_15M`**.

Current Gate 2 accepts:

- `WINDOW_15M`
- `WINDOW_1H`
- `WINDOW_4H`

`WINDOW_5M_MICRO_EVENT` is explicitly blocked as support-only. `WINDOW_12H` and `WINDOW_24H` are still unsupported by this E2Q path.

For `WINDOW_1H`, the current additional Gate 8 requires all of the following before shared quality classification:

1. real `window_start_at`;
2. real `window_end_at`;
3. both `snapshot_start_id` and `snapshot_end_id`;
4. parseable elapsed time;
5. elapsed time at least `2700s`;
6. start snapshot exists;
7. start snapshot exact token match;
8. start snapshot exact pair match when both pair IDs are non-null;
9. the common end/audited snapshot exact token/pair gates also pass.

This is the intended anti-fabrication boundary: 15m evidence cannot simply be relabelled as 1h.

The historical constant `E2Q_REQUIRED_WINDOW_KIND = "WINDOW_15M"` remains for the original 15m contract/tests, but current Gate 2 does not use it as a blanket admission check. Admission is through `E2Q_VALID_MAIN_WINDOW_KINDS` plus the window-kind-specific validators.

---

## 4. Window-kind-independent clean-memory invariants that remain unchanged

The following common E2Q invariants apply after kind admission and must not be weakened:

- target memory-window row must exist;
- main window must be `WINDOW_CLOSED`;
- `supporting_context_json` must identify the audited snapshot;
- referenced audited snapshot must exist;
- audited snapshot token identity must exactly match the window token;
- pair identity must exactly match when both sides are non-null;
- dirty window quality (`DIRTY_DATA`, `STALE_DATA`, `MISSING_CRITICAL_DATA`, `CONFLICTING_DATA`, `DO_NOT_TRAIN`) cannot become clean;
- dirty snapshot source status (`FAILED`, `STALE`, `CONFLICTING`) cannot become clean;
- dirty snapshot quality cannot become clean;
- acceptable-partial evidence stays audit-only / `do_not_train=1`;
- dirty evidence becomes `DIRTY_MEMORY` / `do_not_train=1`;
- structurally blocked evidence receives no classification write-back;
- clean E2Q classification is only `E2Q_AUDIT_CLEAN_CANDIDATE` / `PARTIAL_MEMORY`, not authoritative clean-memory promotion by itself;
- audit write-back is idempotent;
- E2Q itself creates no episode/fingerprint/retrieval/paper/financial rows;
- 5m cannot become a main outcome window.

These are evidence-quality and identity laws, not 15m-only laws.

---

## 5. Distinct 1h cadence / coverage / identity contract

The current implementation correctly does not reuse 15m timing as if it were a full standalone 1h window.

Key distinct first-hour rules already committed:

| Concern | 15m | 1h continuation |
|---|---|---|
| Main elapsed phase | 900s | 2700s continuation after the 15m close |
| Continuity anchor | opening/closing 15m evidence | exact predecessor 15m close + closing snapshot |
| Deadline | 15m close boundary | fixed at predecessor 15m close + 2700s; delayed first snapshot does not extend it |
| Required E2Q anchors | common closing snapshot contract | explicit start + end snapshot IDs and start/end timestamps |
| TRACK_FAST cadence | separate 15m policy | ~120s continuation cadence; 24 required continuation snapshots in the later proof policy |
| TRACK_NORMAL cadence | separate 15m policy | ~240s continuation cadence; 13 required continuation snapshots in the later proof policy |
| Period identity | evidence-window identity | distinct 1h period identity; duplicate predecessor/period reuse fails closed |
| Transition | n/a | exact run/token/pair/lane continuity; historical/consumed/mismatched/delayed-restart reuse rejected |

This distinct contract is already implemented in cadence/continuity/E2O and was exercised by V2-7.

---

## 6. Existing WINDOW_1H support is not dormant

Current repository evidence shows multiple later layers beyond X14:

1. V2-6 repaired E2Q to admit genuine 1h while preserving 15m and 5m locks.
2. V2-6.2/V2-6.3 added continuous 15m->1h deadline, cadence, exact predecessor, and runtime linkage.
3. V2-7 ran a bounded real first-hour proof and crossed E2Q successfully.
4. Later V2-9.8B operational selective-1h work added campaign/factory lineage, selective 4A continuation, period-aware campaign windows, WINDOW_1H E2Z admission, bounded proof command, and operator-readiness controls.
5. Ordinary production `run` remains intentionally 15m-only/default-off for selective 1h. That is an operational configuration lock, not an E2Q defect.

The current E2Q also contains `WINDOW_4H` structural support from later work. That does not authorize new 4h operation in this lane.

---

## 7. WINDOW_5M_MICRO_EVENT preservation

The support-only rule remains explicit in all controlling layers reviewed.

E2Q Gate 2 blocks `WINDOW_5M_MICRO_EVENT` with a support-only/main-outcome rejection. The active source stack also states that 5m:

- never becomes a main outcome memory;
- never replaces 15m;
- never independently triggers longer-window continuation;
- never independently unlocks retrieval, decisions, positions, trades, audits, or PnL.

No change is required here.

---

## 8. Historical X14 Attempt 3C vs current state

X14 Attempt 3C remains historically `PARTIAL_READY_WITH_BLOCKER`; this audit does not rewrite that historical verdict.

Attempt 3C evidence:

- proof DB: `data/proof_runs/printer_v1_x14_attempt3_20260708-123214.sqlite3`;
- selected token row `7`, pair row `7`;
- mint `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`;
- pair `6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp`;
- command `printer-run-lane-x12-fast-1h-cycle`;
- runner status `LANE_X12_COMPLETED`;
- actual duration `3620.032s`;
- cadence cycles `15`;
- snapshots/source requests/source responses `15/15/15`;
- source failures `1`;
- pair drift `false`, events `0`;
- freshness `FRESH_WITHIN_PREFERRED_LIMIT`;
- one `WINDOW_1H` row created as memory-window id `157`;
- 15 `TRACK_FAST_1H` Scheduler jobs succeeded and 1 failed;
- no retrieval/paper/position/trade/audit/PnL unlock.

The historical blocking result was:

```text
E2Q_BLOCKED: window_kind must be 'WINDOW_15M'; got 'WINDOW_1H'; 5m is not a valid main outcome window
```

The runner therefore reported zero successful 1h window closes / clean-memory rows and one dirty-or-blocked memory outcome.

What X14 did **not** prove at that time:

- E2Q acceptance of genuine 1h;
- valid audited 1h closeout;
- clean 1h memory creation/promotion;
- 1h fingerprint readiness;
- retrieval eligibility;
- paper-decision readiness.

Historical X14 remains an important failure artifact; it is simply no longer a current-code blocker.

---

## 9. Exact superseding evidence

### V2-6 repair

Commit:

`8f42e2f3ea39f311888117f418435ec8ee897bb9` — `Repair E2Q 1h audit gate (V2-6)`

The commit is an ancestor of the current audit baseline. It replaced the blanket 15m Gate 2 with window-kind-specific admission while preserving all existing 15m regression behavior and explicit 5m rejection.

Committed verification recorded:

- 97 existing E2Q tests green;
- 19 new 1h gate tests green;
- E2Z, Lane Q, Lane H and X12 regressions green;
- 394 tests passed in the repair verification set;
- no source calls, Scheduler runtime, persistent DB mutation, or 1h proof in that repair lane.

### V2-7 bounded continuous first-hour proof

Closeout verdict:

`V2_7_BOUNDED_1H_PROOF_PASS`

Proof facts relevant to E2Q:

- one autonomous same-run token completed a continuous 15m + immediate 2700s continuation;
- `WINDOW_1H` memory-window id `159` was created;
- exact predecessor was 15m window `157` / closing snapshot `1028`;
- fixed continuation deadline drift was `0.0s`;
- 24 continuation snapshots were collected at the required TRACK_FAST shape;
- exact run/token/pair/lane continuity remained continuous;
- E2Q returned `E2Q_AUDIT_CLEAN_CANDIDATE` for the 1h window;
- the 1h row remained `PARTIAL_MEMORY`; no clean row/fingerprint was promoted;
- downstream locked deltas were zero.

That proof is sufficient to establish that the historical `WINDOW_15M`-only E2Q blocker was crossed by real bounded 1h evidence after repair.

### Later operational selective-1h lineage

The V2-9.8B selective-1h readiness/implementation lineage independently classifies E2Q genuine-1h support as already resolved, then builds its later operational campaign/factory path around that existing gate. Its bounded non-live implementation proof and command/readiness suites preserve E2Q, E2Z, 5m, Scheduler, Source Governor, and downstream locks.

---

## 10. Minimum safe design surface

No new E2Q repair design is required for the historical blocker.

The already-landed minimum safe design was the correct narrow surface:

- preserve shared E2Q structural/quality/idempotency gates;
- admit 1h only through a window-kind-specific genuine-1h validator;
- require real elapsed time and governed start/end anchors;
- require exact token/pair identity;
- preserve dirty/stale/partial fail-closed behavior;
- preserve explicit 5m support-only rejection;
- prove existing 15m behavior unchanged.

This audit therefore stops before any new design or implementation.

Legacy naming/comments (`audit_15m_memory_window`, and some comments that still describe 4h as not enabled even though current valid-kind code contains 4h) are documentation/code-comment drift, not a reason to reopen functional E2Q repair inside this audit lane.

---

## 11. Regression protection / tests

Existing focused protection includes:

- `tests/test_post_rc_lane_e2q_memory_window_audit.py` — original 15m structural, quality, idempotency, no-memory/no-financial, and 5m rejection coverage;
- `tests/test_v2_6_1h_audit_gate.py` — 15m unchanged, genuine 1h admitted, 2700s minimum, relabelled/short/missing-anchor/mismatched/open 1h blocked, dirty/stale 1h dirty, 5m blocked, longer-kind behavior, zero downstream deltas;
- lifecycle/cadence/E2O/X12 suites from V2-6.2/V2-6.3;
- focused V2-7 proof-readiness checks plus the real bounded V2-7 run;
- later operational selective-1h suites proving zero/one/two continuation, exact lineage, idempotency, distinct periods, clean/dirty/5m promotion boundaries, reporting linkage, and production default locks.

No tests were run during this documentation-only audit because static current source plus committed focused verification and the later bounded proof were sufficient. This follows the risk-based rule for audit/documentation work.

If E2Q is modified in a future approved lane, minimum sufficient regression should include the original 15m E2Q suite, V2-6 1h gate suite, nearest E2O/continuity tests, 5m support-only rejection, E2Z promotion boundary, and zero downstream-delta assertions. No broad suite is justified merely by this audit.

---

## 12. Blocker classification

The historical blocker is **superseded implementation history**, not a current E2Q blocker.

Current facts:

- no blanket 15m-only E2Q gate remains;
- genuine 1h has a distinct anti-fabrication contract;
- current focused tests protect 15m and 1h behavior;
- a later bounded real first-hour proof crossed E2Q;
- later operational selective-1h implementation builds on that resolved E2Q boundary;
- normal production still being 15m-only is an intentional activation/configuration restriction, not evidence that E2Q needs repair.

A fresh post-DTW100 WINDOW_1H runtime proof is **not** authorized by this classification. This audit only retires the premise that E2Q still needs the historical 15m-only repair.

---

## 13. Money-usefulness contribution

This audit avoids spending another long-window proof cycle or engineering lane on an already-repaired gate. It preserves the successful DTW100 15m foundation while confirming that Printer already has a bounded, identity-safe first-hour audit contract capable of learning continuation/failure evidence without fabricating 1h from 15m.

That is useful because longer-horizon survival, collapse, continuation, and transition memory can improve future comparison quality while keeping evidence quality separate from token performance.

---

## 14. What this audit improves

- reconciles stale X14/current-state wording against current implementation;
- identifies the actual current E2Q owner and 1h call chain;
- separates shared clean-memory invariants from 1h-specific timing/identity rules;
- confirms 5m remains support-only;
- prevents an unnecessary duplicate E2Q repair/design lane;
- preserves historical X14 truth without treating it as current code truth.

---

## 15. What this still does not unlock

This closeout does not unlock or authorize:

- another WINDOW_1H runtime/proof;
- normal-production selective 1h activation;
- WINDOW_4H / WINDOW_12H / WINDOW_24H operation;
- retrieval;
- paper decisions;
- BUY / SELL / HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live execution, wallets, private keys, signing, or real funds;
- paid APIs;
- scoring, ranking, confidence, weighted logic, embeddings, or vectors;
- dirty-memory use for retrieval/decisions;
- Source Governor or Central Scheduler bypass.

---

## 16. Proof / review needed before any future operational 1h action

Because the historical E2Q repair is already proven, the next review must not redesign that gate from scratch. Before any new post-DTW100 operational 1h action, the roadmap/current operational state should be reconciled against the later V2-9.8B selective-1h implementation, current migrations/campaign ownership, current authoritative DB trust anchor, one-use authorization rules, Scheduler/Source Governor ceilings, and current post-DTW100 lineage.

Any future operational proof still requires its own approved readiness/authorization sequence and exact current bindings. The V2-7/X14 proof identities are evidence, not reusable execution authority.

---

## 17. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current interpretation | Control |
|---|---|---|
| Old build-order text still says E2Q is 15m-only | stale historical/current-state wording | this closeout records current code/proof truth; do not repair from stale prose |
| `audit_15m_memory_window` legacy name | naming drift only | do not rename in audit lane; preserve API until separately justified |
| E2Q clean candidate confused with clean memory | material semantic risk | E2Q outputs PARTIAL candidate; authoritative promotion is separate |
| 1h fabricated from short/relabelled 15m | blocked by 2700s + anchored identity contract | preserve Gate 8 |
| 5m accidentally promoted | blocked explicitly in E2Q and source-stack law | keep support-only invariant |
| Current normal production is 15m-only | intentional activation lock | do not treat as E2Q defect or silently enable 1h |
| V2-7 proof predates DTW100 | does not prove a new post-DTW100 operational campaign | use it only to prove the E2Q blocker was superseded; require fresh authorization for future runtime |
| Stale E2Q comments around 4h | documentation drift | no functional change in this lane |
| Re-running broad tests in audit | unnecessary cost/side effects | static evidence + committed proof sufficient |

---

## 18. Audit closeout

Audit/readiness step: complete.

No production code, migration, source, runtime, Scheduler, authoritative DB, memory, authorization, retrieval, decision, position, trade, audit, or PnL action was performed.

The correct current-state conclusion is that the X14 E2Q blocker has already been repaired and proven crossed by bounded real WINDOW_1H evidence. Stop here; do not open a duplicate E2Q repair design from the historical blocker.