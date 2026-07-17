# Printer V1 V2-9 Final Closeout

## Verdict

`V2_9_FINAL_CLOSEOUT_PASS`

V2-9 is closed as PASS. Attempt 7 satisfies the active V2-9 contract: one
isolated, supervised, bounded current-run lifecycle produced a real
`WINDOW_4H` result, completed the audit/promotion path, stayed inside source and
scheduler budgets, stopped naturally, preserved proof/persistent DB isolation,
and left retrieval, paper-decision, and financial locks unchanged.

This final closeout is audit-only. It does not begin V2-10, does not authorize
12h/24h, does not activate retrieval, does not create paper decisions, and does
not unlock BUY, SELL, HOLD, positions, trade events, paper trade audits, PnL,
live execution, wallet/private-key/signing logic, paid APIs, scoring, ranking,
confidence percentages, weighted logic, embeddings, vectors, or operational
memory growth.

## Todo / Checklist

- [x] Confirm exact clean preflight at commit `062e546`.
- [x] Review active Printer V1 source stack and V2-9 contract.
- [x] Review Attempt 7 forensic closeout and targeted V2-9 repair closeouts.
- [x] Confirm Attempt 7 satisfies V2-9 final proof requirements.
- [x] Create this final audit-only closeout.

## Preflight

- HEAD: `062e546`.
- Tracked tree: clean before this document was created.
- Runtime/lock state: no active proof runtime or one-proof lock found by
  preflight inspection. Generic local Node/PowerShell processes existed, but no
  active Printer proof lock or runtime artifact was present.
- Unrelated untracked artifacts: present and intentionally untouched.
- Scope followed: documentation-only closeout. No code, tests, migrations,
  databases, runtime, active build order, V2-10, retrieval, financial functions,
  or operational memory-growth path was modified.

## V2-9 Contract Result

The active build order defines V2-9 as a bounded 4h proof whose acceptance gate
is a valid real 4h memory result or an honest block with all locks preserved.
Attempt 7 meets the positive side of that gate.

Completed proof requirements:

- V2-9A final preflight: satisfied by the Attempt 7 preparation and this final
  closeout preflight.
- V2-9B proof DB setup: canonical preparation applied all 30 migrations,
  returned integrity `ok`, found zero foreign-key errors, and made the prepared
  proof DB and backup byte-identical.
- V2-9C bounded 4h run: completed the current-run lifecycle through 15m, 1h,
  and 4h under launcher supervision and approved budgets.
- V2-9D closeout inspection: Attempt 7 forensic audit reconciled identity,
  cadence, continuity, source/scheduler budgets, memory, isolation, cleanup,
  and forbidden deltas.
- V2-9E proof report: this final closeout records the lane-level PASS and stops
  after V2-9.

## Snapshot Results and Continuity

Attempt 7 used one exact token/pair/lane identity for all 102 ledger steps:
token `18`, pair `22`, lane `TRACK_FAST`.

Snapshot results:

| Stage | Ledger snapshots | Result | Maximum gap |
|---|---:|---|---:|
| 15m | `1013-1028` | 16/16, closed, cadence/coverage pass | 67.415s |
| 1h continuation | `1029-1052` | 24/24, closed, continuous | 129.849s |
| 4h continuation | `1053-1113` | 61/61, cadence pass, zero missed | 190.889s |

Exact continuity:

- 15m -> 1h transition: 3.381s, clean; fixed 1h deadline drift was 0s.
- 1h -> 4h transition: 6.912s, clean.
- Window `160` anchored to `2026-07-17T11:52:24.509295Z + 10,800s`;
  deadline drift was 0s.
- The 4h forced close arrived 5.247s after the logical deadline, inside the
  approved 60s closing-freshness allowance.
- Anchored 4h duration was exactly 10,800s; observed first-to-last snapshot
  span was 10,798.335s.
- The 15m resolver kept its distinct zero-second evidence allowance, while 4h
  used the separate approved close allowance.
- Shared contexts reported `non_ledger_snapshot_ids=[]`.

## Launcher Supervision and Cleanup

Attempt 7 launcher supervision passed:

- launcher JSONL: 6,665 valid lines;
- heartbeat renewals: 471 successful;
- maximum heartbeat-event gap: 53.080s against a 90s lease;
- one transient atomic lock-file renewal failure occurred, then the next renewal
  succeeded;
- supervision never expired;
- child PID `12524` completed naturally;
- forced termination: false;
- one-proof lock: absent after completion;
- Attempt 7 process: absent after completion;
- terminal supervision: `COMPLETED`;
- first terminal reason: `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`;
- cleanup: zero running jobs;
- stdout: complete and parseable;
- stderr: empty.

The transient lock replacement observation is non-blocking under the active
source stack because lease continuity stayed safe and the next renewal
succeeded.

## Memory and Evidence Behavior

Attempt 7 created exactly one clean promoted 4h episode:

- episode `55`;
- memory window `160`;
- `episode_kind=WINDOW_4H_CLEAN_MEMORY`;
- `episode_status=COMPLETE`;
- `memory_status=CLEAN_MEMORY`;
- `data_quality_label=CLEAN_DATA`;
- `do_not_train=0`.

The source window correctly remained the pre-promotion `PARTIAL_MEMORY`
candidate with no rejection reasons.

E2Q returned `E2Q_AUDIT_CLEAN_CANDIDATE`, Lane Q returned `LANE_Q_VALID`, and
Lane K returned `LANE_K_COMPLETED`. E2Z performed the authoritative clean
promotion.

Evidence behavior:

- 4h shared resolver: `clean_memory_context_ready=true`, zero blockers.
- Chart evidence: clean `PATH_ROUND_TRIP` /
  `CHART_CONTEXT_ACCEPTABLE`.
- Flow evidence: honestly partial/caution
  (`TRADING_FLOW_CONTEXT_PARTIAL`, `FLOW_CONTEXT_CAUTION`) and provenance-clean.
- Opening quote `23`: exact-target, fresh, complete Jupiter ENTRY evidence.
- Closing quote `24`: exact-target, fresh, complete Jupiter EXIT evidence.
- Closing safety composite `2`: exact-target, fresh, complete, and
  provenance-complete.
- The negative/round-trip market path was preserved as clean evidence quality;
  unfavorable price behavior was not misclassified as dirty data.

The Attempt 7 forensic audit records four observations. Under the active source
stack, they are non-blocking for V2-9 final closeout:

1. Top-level yield reporting under-reports the clean E2Z promotion, while the
   authoritative episode row records the clean result.
2. Safety label naming still says 15m-only/`BLOCK_CLEAN_MEMORY`, while the
   approved shared 4h gate accepts the exact evidence.
3. One transient heartbeat lock replacement failed, but lease continuity and
   supervision remained safe.
4. Wallet-level flow authenticity remains unknown; the valid claim is partial
   flow, not proven wallet authenticity.

These observations should be carried forward as follow-up risks before any
generalized productionization, but they do not block V2-9 because the active
contract requires a real 4h result or honest block with locks preserved, not
perfect reporting labels, wallet-level flow authenticity, or generalized
campaign readiness.

## Proof DB Isolation and Persistent DB

Attempt 7 used an isolated proof DB. Runtime changed only the isolated proof
copy.

Isolation facts:

- prepared proof DB and backup were byte-identical before runtime:
  `BBF5787A9E1D83D7CDA26F860DAB4DBA46DA0FF7238C873EE9212AD88ACE54D9`;
- final proof DB SHA-256:
  `39CCAAC72CE085E84B3BAC098EE7ECDD0537B48FA0EE78C9B6780D8D730B9F8B`;
- persistent DB SHA-256 remained
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`;
- persistent DB critical counts were unchanged before/after preparation;
- no persistent WAL/SHM sidecars existed before immutable read-only audit;
- recovery/report deltas were zero;
- no duplicate run snapshot attachment;
- no duplicate stage window;
- exactly one episode for window `160`.

Full-run proof deltas reconciled to:

- 101 snapshots;
- four windows: 5m support, 15m, 1h, and 4h;
- 102 run steps/jobs;
- 113 source requests;
- 112 source responses;
- one source failure;
- four quote rows;
- two safety composites;
- one clean promoted 4h episode.

## Retrieval and Financial Deltas

Forbidden deltas stayed zero:

- retrieval queries: 0;
- retrieval matches: 0;
- paper decisions: 0;
- BUY/SELL/HOLD: 0;
- paper positions: 0;
- trade events: 0;
- paper trade audits: 0;
- paper audit reports: 0;
- PnL: 0.

The final report also preserved retrieval, paper decision, and financial locks.

## Money-Usefulness Contribution

V2-9 improves Printer's money-usefulness without unlocking money actions. It
proves the medium-term evidence machine can carry one exact Solana memecoin
token/pair through a real 15m -> 1h -> 4h lifecycle, preserve realistic entry
and exit evidence, retain safety/provenance context, and promote an unfavorable
round-trip/low-volatility lesson as clean memory when the evidence is clean.

That matters because money-useful memory is not winner-only memory. Attempt 7
adds a clean 4h lesson that can later help Printer understand avoid/loss/
round-trip behavior, realistic exits, and medium-term continuation failure,
while still keeping retrieval and all paper/financial paths locked.

## What V2-9 Improved

- Proved real 4h evidence confidence after V2-8 approval.
- Proved exact current-run identity across 15m, 1h, and 4h.
- Proved cadence and continuity through 16/16, 24/24, and 61/61 snapshot sets.
- Proved launcher supervision and natural cleanup over a multi-hour proof.
- Proved canonical proof DB setup and persistent DB isolation.
- Proved source/scheduler budget ceilings stayed intact.
- Proved clean 4h promotion can happen through E2Q -> Lane Q -> Lane K -> E2Z.
- Proved unfavorable price outcomes do not become dirty merely because they are
  unfavorable.
- Preserved free/public source governance, Central Scheduler control, and all
  downstream locks.

## What Remains Locked

- V2-10.
- 12h and 24h lifecycle work.
- Generalized 4h production or operational memory-growth campaigns.
- Retrieval activation.
- Paper decisions, including WAIT/AVOID/NO_ACTION creation.
- BUY, SELL, HOLD.
- Paper positions.
- Trade events.
- Paper trade audits.
- PnL.
- Live execution.
- Wallet, private-key, signing, or transaction logic.
- Paid APIs.
- Scoring, ranking, confidence percentages, weighted logic.
- Embeddings and vectors.
- Dirty-memory retrieval or dirty-memory decision support.
- `WINDOW_5M_MICRO_EVENT` as a main outcome window.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Top-level report under-counts clean promotion.** The run-level yield
   surfaces still read the source window label and classify the run as
   zero-clean/`BLOCKED_QUALITY`, while the authoritative E2Z promotion row is
   clean. This is non-blocking for V2-9 closeout, but should be repaired before
   operational campaigns.
2. **Safety label naming is timeframe-confusing.** The exact 4h shared gate
   accepted the evidence, while a legacy label still says
   `SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY` / `BLOCK_CLEAN_MEMORY`. This should
   be clarified before generalized 4h production.
3. **Long-run supervision had one transient lock-file replacement failure.**
   Lease continuity held and supervision did not expire, but repeated Windows
   atomic-replace contention could threaten later longer runs.
4. **Wallet-level flow authenticity remains unavailable.** Flow is validly
   partial/caution, not fabricated. Future money-usefulness would improve with
   stronger wallet/flow evidence, but V2-9 does not require it.
5. **Attempt 7 is one-token evidence.** It closes the bounded V2-9 proof lane,
   not corpus diversity, generalized 4h yield, or operational campaign
   readiness.
6. **Git provenance was reconstructed, not embedded in launcher artifacts.**
   Future launch artifacts should embed HEAD and tracked-tree status directly.
7. **No live report-only replay was separately executed after Attempt 7.**
   Idempotency rests on duplicate-free artifacts and focused fixture contracts,
   not on a second live close.

## Files Changed

- `docs/printer-v1-v2-9-final-closeout.md`

## What Was Built

- Final audit-only V2-9 lane closeout.
- PASS verdict tying Attempt 7 evidence to the active V2-9 contract.
- Explicit lock-preservation, isolation, memory/evidence, cadence/continuity,
  supervision, money-usefulness, and risk/setback record.

## What Was Not Touched

- Code.
- Tests.
- Migrations.
- Databases.
- Runtime/proof execution.
- Source fetching.
- Active build order.
- V2-10.
- Retrieval.
- Financial functions.
- Operational memory growth.
- Unrelated untracked artifacts.

## Tests / Checks Run

Static checks and `git diff --check` only are required for this audit-only
closeout. Results are recorded in the task closeout response after the checks
run.

## Pass / Fail Status

PASS: `V2_9_FINAL_CLOSEOUT_PASS`.

## Risks or Concerns

The four Attempt 7 forensic observations are non-blocking for V2-9, but should
not be ignored before generalized 4h production or operational campaigns:
report-yield under-counting, timeframe-confusing safety label naming, transient
lock-file renewal contention, and partial-only flow authenticity.

## Next Recommended Phase

Stop after this commit, per operator instruction. The next active work should
not begin in this task. Any V2-10 or longer-lifecycle review requires a separate
explicit operator-approved lane.
