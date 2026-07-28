# Printer V1 V2-9.8B Selective-1h Comprehensive Blocker Audit

Date: 2026-07-28
Lane: V2-9.8B active bounded memory-growth operations
Audit mode: committed-code review, retained-artifact reconciliation, and offline tests only
Baseline commit: `043f9eac4740172e92a4fb4daeb060e31628f9f8`
Authoritative database before-work SHA-256: `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872`

## Verdict of this audit stage

The complete selective-1h path is not ready for another operator proof at the
audited baseline. The most recent `COOLDOWN_REOPEN_REQUIRED` terminal is caused
by a confirmed state-machine defect, accompanied by confirmed code,
reporting, and efficiency defects. The two earlier retained attempts also
identify historical defects that are already repaired at the baseline. No live
runtime was invoked and the authoritative database was not opened for writes.

This document is the required audit stage only. It does not authorize runtime,
implementation outside the coordinated design, or another live proof.

## Sources and owners reviewed

The active source stack was read and applied:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-python-builder-guide.md`

Relevant committed V2-9.8B architecture, eligible-supply, discovery,
admission, tracking-handoff, liquidity, lifecycle-rotation, continuation,
reporting, replay, readiness, proof, repair, and closeout documents were
reconciled with their owning code and focused tests. The principal owners
reviewed were:

- graduated discovery and persistent eligible reserve;
- campaign admission and holder/safety evidence;
- exact tracking handoff and two-token activation;
- lifecycle terminal reconciliation and cooldown disposition;
- Scheduler barriers, leases, deadlines, and close-step reservations;
- 15m lifecycle close, memory quality, promotion, and exact safety linkage;
- immutable selective-continuation evaluation;
- 1h window scheduling, collection, terminalization, and cleanup;
- terminal reporting and zero-source read-only replay.

## Mandatory source-grounded blocker investigation

The Python Builder Guide investigation was completed before proposing code.

| Question | Finding |
| --- | --- |
| Failing operation | The third retained campaign stopped before two-token handoff with `COOLDOWN_REOPEN_REQUIRED`. |
| Owner | Tracking lifecycle reconciliation writes cooldown state; exact tracking handoff enforces it; eligible-supply ordering determines whether source work is spent first. |
| Inputs/state | Two exact `TRACK_NORMAL` identities were in `COOLDOWN`; one new reserve candidate was otherwise eligible; two slots were required. |
| Timestamps | Both cooldown rows retained `next_check_at=2026-07-28T21:22:31.515350+00:00` even though `last_checked_at` was approximately `2026-07-28T21:44:17.474Z`. |
| Transaction boundary | Terminal reconciliation updated the existing row to `COOLDOWN` but did not establish cooldown expiry. Later handoff assessed the latest exact lane row and refused it. |
| Retry/phase behavior | No automatic retry is permitted. The campaign correctly stopped before lifecycle and Scheduler activation. |
| Test evidence | The baseline focused suite passed, but it had no historical-row expiry, exact-lane requalification, reserve replacement, or pre-lifecycle report-preservation case. |
| Classification | `COMMITTED_CODE_DEFECT`, `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`, and `DESIGN_GAP`; mapped below to the operator-requested audit categories. |

The issue is not a provider-capacity fact, CLI invocation error, or safe
configuration change. Code is justified because the active lane requires
cooldown/reopen/expiry/requalification semantics that the committed owners do
not represent.

## Retained execution reconciliation

### `20260728T202147Z-3c2735e39266`

- Terminal: `NOT_STARTED`, first cause
  `BLOCKED_INSUFFICIENT_GRADUATED_POOL`.
- Work: 30 Source Governor calls, zero Scheduler calls, 24 candidates, zero
  eligible candidates.
- Retained request evidence shows every Dex liquidity operation failed at the
  transport boundary with `No route to host`.
- The campaign failed closed, but its terminal classification collapsed a
  provider outage into apparent supply/budget shortage.
- Classification: **historical already repaired** for provider/source lineage
  and terminal classification at the current baseline; **external source
  risk** remains because a real provider can still be unavailable.

### `20260728T212231Z-80579a4adeb8`

- Terminal: `COMPLETED`; 18 Source Governor calls. Two 15m lifecycles started
  for token/pair `25/29` and `26/30`, producing memory windows `159` and `160`.
- Window `159` closed `PARTIAL_MEMORY` / `CLEAN_DATA` /
  `SHORT_TERM_PUMP`; window `160` closed `PARTIAL_MEMORY` / `CLEAN_DATA` /
  `DEAD`.
- Both selective continuations were blocked. One had an eligible predecessor
  episode but could not resolve exact safety because the accepted safety
  composite carried no `memory_window_id`; evaluation could also race a final
  close step still marked running. Campaign-window rows were subsequently
  flattened to `CANCELLED`, and reporting omitted the selective detail.
- Classification: **historical already repaired** at the required baseline.
  Current owners resolve safety through exact run/token/pair linkage, enforce
  the close barrier, preserve immutable continuation results, map terminal
  window state, and report/replay the selective outcome.
- The repaired downstream route remains **operationally unproven** because no
  retained live campaign has completed actual selective 1h collection and
  closeout on the repaired baseline.

### `20260728T224158Z-6bf2c4fd8e7e`

- Terminal: `NOT_STARTED`, first cause `COOLDOWN_REOPEN_REQUIRED`.
- Work: 14 Source Governor calls, zero Scheduler calls, no lifecycle, no
  continuation.
- Three reserve rows ended `ELIGIBLE_FRESH`:
  - mint `2Xz...pump`, pool `4XC...`, liquidity `9867.12`;
  - mint `AkYn...pump`, pool `Cod...`, liquidity `3260.44`;
  - mint `ApPL...pump`, pool `2Jz...`, liquidity `16020.66`.
- Exact tracking rows for the first two identities were queue rows `28` and
  `29`, both `TRACK_NORMAL` / `COOLDOWN`. Their `next_check_at` predates the
  cooldown transition recorded by `last_checked_at`, so it cannot be the
  cooldown expiry.
- The third mint had no token, pair, or tracking row and passed the retained
  holder path. Its Solana RPC holder check was rate-limited, while Helius
  returned complete healthy evidence; the aggregate remained eligible under
  the approved provider policy.
- Holder maturation was correctly skipped for the two known cooldown
  candidates, but their exact pools were revalidated first, consuming two
  avoidable Dex market calls. Only one handoff-admissible candidate remained
  for two required slots.
- The report omitted the candidate-level admission/cooldown facts and omitted
  the selective-1h `EVALUATION_NOT_REACHED` projection, even though immutable
  campaign configuration selected the selective-1h mode.

## Full-path trace and finding classification

| Path owner | Audited behavior | Classification |
| --- | --- | --- |
| Discovery | Governed migration/profile discovery is bounded and fail-closed. A provider outage must not be presented as market scarcity. | External source risk; historical already repaired |
| Source evidence | Exact pool, origin, graduation, liquidity, quote, token age, pair age, holder, and safety evidence remain source-attributed and freshness-bound. No stale fallback was found. | Expected fail-closed policy |
| Admission | Admission checks are conservative. Candidate-level facts are not fully preserved in a pre-lifecycle terminal report. | Confirmed reporting defect |
| Eligible reserve | Durable reserve can report two cooldown-blocked identities plus one fresh identity as sufficient eligible capacity before exact handoff feasibility is applied. | Confirmed code defect |
| Cooldown/reopen | Terminal reconciliation writes `COOLDOWN` without a valid expiry. Existing manual reopen appends `WATCH_ONLY`, while handoff inspects the latest exact `TRACK_NORMAL` lane, so it cannot clear this barrier. | Confirmed state-machine defect; missing approved implementation boundary |
| Replacement/requalification | No canonical path distinguishes active cooldown from expired cooldown, demands fresh evidence after expiry, then atomically claims the exact operational lane. | Confirmed state-machine defect; design gap |
| Two-token handoff | Atomic handoff correctly prevents one-token partial activation, but it can receive a reserve set that was never capable of satisfying both exact tracking claims. | Confirmed code defect; expected fail-closed policy at final barrier |
| Scheduler ownership | No Scheduler work was created in attempts one or three. Once handoff succeeds, creation/lease/deadline/barrier owners remain centralized and bounded. | Operationally unproven path for the repaired end-to-end route |
| 15m lifecycle | Both close orders, terminal close reservations, memory quality, and zero-orphan cleanup have focused offline coverage. | Historical already repaired; operationally unproven live route |
| 15m promotion/safety | Exact predecessor and accepted-safety linkage are enforced without relaxing freshness or quality. Dirty/non-trainable memory stays excluded. | Historical already repaired; expected fail-closed policy |
| Continuation | Decisions are immutable; zero, one, or two tokens can continue independently; no duplicate decisions/windows/jobs are allowed. | Historical already repaired; operationally unproven live route |
| 1h scheduling/collection | The approved path is bounded by campaign duration, source, Scheduler, lease, and close-step reservations. It does not schedule 4h. | Operationally unproven path |
| 1h closeout/cleanup | Focused code tests exercise collection, closeout, state mapping, and cleanup. No retained live proof reached it. | Operationally unproven path |
| Reporting | Mixed tracking and provider failures can select the tracking cause first; pre-lifecycle admission evidence is dropped; selective authorization is inferred only from an authoritative factory run that does not exist before lifecycle. | Confirmed reporting defect |
| Replay | Replay is zero-source and preserves stored reports, but it cannot restore fields that the original terminal report never persisted. | Confirmed reporting defect upstream; replay mechanism expected |
| Ceilings | Source, Scheduler, duration, and selective continuation ceilings remain explicit and fail closed. | Expected fail-closed policy |

## Confirmed blockers requiring coordinated repair

### Confirmed code defects

1. Eligible-reserve capacity is evaluated before exact tracking feasibility, so
   a historically blocked reserve can trap a fresh campaign.
2. Exact market revalidation can be spent on identities already known to be in
   an unavoidable active cooldown or another non-claimable tracking state.
3. The final handoff owner has no canonical claim operation for a freshly
   requalified, expired-cooldown identity.

### Confirmed state-machine defects

1. Lifecycle terminalization does not persist a future cooldown expiry.
2. Historical cooldown rows with a pre-transition `next_check_at` have no
   defined effective expiry.
3. The manual `WATCH_ONLY` reopen transition is not a valid reopen for the exact
   `TRACK_NORMAL` handoff lane.
4. Active cooldown, expired cooldown requiring requalification, active
   ownership, terminal/manual-review state, and fresh claimability are not
   modeled as distinct handoff dispositions.

### Confirmed reporting defects

1. Provider failure can be hidden by an earlier tracking blocker in mixed
   pre-lifecycle failures.
2. Candidate-level reserve, admission, handoff, cooldown, replacement, and
   requalification facts are not retained in the terminal report.
3. A selective-1h campaign that stops before factory-run creation loses its
   immutable campaign-mode authorization and therefore omits
   `EVALUATION_NOT_REACHED`.

### Confirmed efficiency blockers

1. The latest retained campaign spent two exact-pool market calls on identities
   whose active tracking state made immediate handoff impossible.
2. Reserve selection can stop after reaching raw eligible capacity rather than
   continuing to deterministic post-tracking-admissible capacity.
3. The absence of candidate-level terminal evidence makes a safe next operator
   review more expensive and less conclusive.

## Non-repair classifications

### Expected fail-closed policy

- Active cooldown before its expiry, active tracking ownership, unsupported or
  manual-review terminal states, incomplete/stale evidence, invalid safety, and
  insufficient genuinely eligible supply must continue to block.
- A provider failure may reduce usable supply. It must not trigger unsafe stale
  reuse, an ungoverned fallback, or automatic retry.
- Atomic two-token handoff must continue to prevent partial campaign start.
- Dirty/partial/ineligible memory must not unlock continuation.

### External source risks

- Dex, PumpPortal, GoPlus, Solana RPC, or Helius can be unavailable, malformed,
  delayed, or rate-limited.
- The first attempt demonstrates a real transport outage. The repair can make
  it truthful and efficient; it cannot manufacture source evidence.

### Market supply risks

- A bounded campaign may genuinely find fewer than two candidates satisfying
  origin, graduation, age, liquidity, quote, holder, safety, freshness, and
  tracking requirements.
- Repairing reserve progression does not guarantee that the live market
  contains eligible supply.

### Operationally unproven paths

- A fresh campaign passing the repaired reserve/requalification handoff.
- Both tokens completing repaired 15m lifecycle under live source conditions.
- Zero, one, and two actual 1h continuations in operator runtime.
- Actual bounded 1h collection, closeout, terminal reporting, replay, and
  cleanup on the repaired commit.

These paths may be offline-proven in this lane, but another live proof is
explicitly outside scope.

### Historical already repaired

- Provider-failure lineage and first-attempt shortage misclassification.
- Exact safety linkage that does not depend on a nullable memory-window foreign
  key.
- The final-close barrier and both token close orders.
- Immutable continuation decisions and idempotent continuation artifacts.
- Campaign-window terminal state mapping and selective report/replay support
  after a factory run exists.

### Inconclusive

- Whether a fresh live market would currently supply two eligible candidates.
- Which free provider would be available during a future operator-approved
  proof.
- Which of zero, one, or two candidates would qualify for live 1h continuation.

## Required repair boundary

The coordinated design must establish one lifecycle-owned cooldown clock,
tracking-aware reserve progression, freshness-preserving expired-cooldown
requalification, atomic exact-lane claim, truthful pre-lifecycle reporting, and
selective-mode reporting before factory-run creation. It must retain all
admission and safety gates, deterministic selection, Source Governor and
Central Scheduler ownership, immutable continuation decisions, and every
campaign ceiling.

No live source, Scheduler, campaign, lifecycle, memory runtime, authoritative
database mutation, proof restart, 4h+ capability, retrieval, or financial
capability is authorized by this audit.
