# Printer V1 V2-9.8B Selective-1h Comprehensive Repair Closeout

Date: 2026-07-28
Baseline: `043f9eac4740172e92a4fb4daeb060e31628f9f8`
Lane: V2-9.8B selective-1h comprehensive blocker repair
Execution mode: retained-artifact audit plus mocks, fixtures, temporary SQLite,
and zero-source replay only

## Verdict

`V2_9_8B_SELECTIVE_1H_COMPREHENSIVE_REPAIR_PASS`

All three retained attempts were reconciled, every in-repository owner from
discovery through 1h closeout was audited, every confirmed code,
state-machine, reporting, and efficiency blocker was repaired, and the
coordinated package passed focused offline proof. External provider and genuine
market-supply risks remain explicitly separate. No live proof or operational
runtime was performed.

PASS authorizes only a fresh read-only operator-readiness review. It does not
authorize another live proof.

## Retained attempts reconciled

| Execution | Retained result | Reconciliation |
| --- | --- | --- |
| `20260728T202147Z-3c2735e39266` | `NOT_STARTED`; `BLOCKED_INSUFFICIENT_GRADUATED_POOL`; 30 source calls; zero Scheduler calls | Every exact liquidity request failed at transport (`No route to host`). The fail-close was correct, but historical reporting obscured provider outage as supply shortage. Provider/source lineage and classification were already repaired at the baseline. Provider availability remains external risk. |
| `20260728T212231Z-80579a4adeb8` | `COMPLETED`; 18 source calls; two 15m windows; no 1h continuation | Retained evidence exposed nullable-window safety linkage, final-close ordering, campaign-window flattening, and missing selective reporting. These were already repaired at the baseline through exact safety resolution, close barriers, immutable decisions, terminal state mapping, and report/replay support. |
| `20260728T224158Z-6bf2c4fd8e7e` | `NOT_STARTED`; `COOLDOWN_REOPEN_REQUIRED`; 14 source calls; zero Scheduler calls | Exact queue rows `28` and `29` were `TRACK_NORMAL/COOLDOWN`. Their `next_check_at=2026-07-28T21:22:31.515350+00:00` predates `last_checked_at` (`21:44:17.474089Z` and `21:44:17.474254Z`), proving that no valid cooldown expiry was written. Three reserve candidates were market-eligible, but two were trapped historical identities and only `ApPLzZ...pump` was newly handoff-capable. Exact-pool calls `1452` and `1453` were spent before the known tracking barrier. This package repairs that path. |

The third immutable campaign configuration also confirms
`command_mode=selective-1h-proof`, `selective_1h_continuation=true`, 3900-second
duration, 45 campaign intake source calls, 92 governed selective-lifecycle
requests, and 82 Scheduler rows. Those ceilings were not changed.

## Every blocker found and disposition

| Finding | Audit classification | Disposition |
| --- | --- | --- |
| Terminal lifecycle wrote `COOLDOWN` without a future expiry. | Confirmed state-machine defect | Repaired: terminal reconciliation now derives its 1800-second clock from the Resource Governor `BACKUP_SOURCE_CHECK` cadence, writes `next_check_at`, and records exact cooldown payload lineage. |
| Historical rows can have `next_check_at <= last_checked_at`. | Confirmed state-machine defect | Repaired: read-only effective expiry uses a valid later `next_check_at`, otherwise derives `last_checked_at + 1800`; missing/malformed time remains fail-closed. |
| Existing manual reopen appends `WATCH_ONLY`, while operational handoff assesses exact `TRACK_NORMAL`. | Confirmed state-machine defect | Repaired: a separate canonical operational claim appends `REOPEN_REVIVED_TOKEN` in the same exact lane after fresh requalification; manual `WATCH_ONLY` revival is preserved for its original workflow. |
| No final atomic claim existed for an expired cooldown. | Confirmed code/state-machine defect | Repaired: fresh or expired-cooldown claim is rechecked inside the handoff transaction, preserves history, records predecessor queue/expiry/campaign evidence, and refuses duplicates. |
| Expiry could have been mistaken for eligibility. | Confirmed safety/design gap | Repaired: expiry only permits evidence collection. Current holder admission plus explicit requalification lineage is mandatory before claim; stale evidence or an expiry-only claim is refused. |
| Raw eligible-reserve capacity ignored exact tracking feasibility. | Confirmed code defect | Repaired: the operational supply front door performs exact read-only tracking disposition before market evaluation and continues deterministic inventory progression to post-tracking capacity. |
| Active cooldown/ownership/terminal identities consumed exact-pool calls before their unavoidable barrier. | Confirmed efficiency blocker | Repaired: those identities are excluded before exact-pool market source work, retained as audit evidence, and replaced by fresh deterministic inventory when available. |
| An expired cooldown had no deterministic requalification behavior. | Confirmed state-machine defect | Repaired: it remains in inventory, receives wholly fresh market and holder evidence, then may claim the exact lane once. |
| Mixed tracking and provider failures could select the tracking cause first. | Confirmed reporting defect | Repaired: governed holder/provider unavailability precedes tracking in mixed terminals; genuine healthy-source shortage remains separate. |
| Pre-lifecycle candidate/reserve/admission/cooldown evidence was dropped. | Confirmed reporting defect | Repaired: terminal reports persist `pre_lifecycle_admission` with exact identity, tracking disposition, expiry, pre-source exclusion, requalification, holder, capacity, source, Scheduler, and terminal-classification facts. |
| Selective authorization disappeared when no factory run was created. | Confirmed reporting defect | Repaired: reporting falls back to immutable campaign configuration and records `EVALUATION_NOT_REACHED`; zero-source replay preserves it. |
| Downstream safety-link, close-order, immutable-decision, and campaign-window defects from attempt two. | Historical already repaired | Reverified; no new change required. |
| Active ownership, pre-expiry cooldown, terminal/manual-review state, stale/incomplete evidence, insufficient supply, and unsafe memory block progress. | Expected fail-closed policy | Preserved. |
| Free-public provider outage, rate limit, malformed response, or stale response. | External source risk | Not hidden or bypassed; truthfully classified. No unsafe retry/fallback added. |
| Fewer than two genuinely eligible current candidates. | Market supply risk | Not “fixed”; truthfully terminal and bounded. |
| A repaired live campaign reaching actual 15m and selective 1h closeout. | Operationally unproven path | Offline-proven only; requires a later explicitly authorized live lane after read-only readiness review. |

No confirmed in-repository blocker remains unrepaired for a valid bounded
selective-1h proof.

## Complete dependency order delivered

1. Established the lifecycle-owned cooldown clock and historical effective
   expiry rule.
2. Added categorical active, terminal, active-cooldown, and expired-cooldown
   tracking dispositions.
3. Added freshness-required, exact-lane atomic requalification claim.
4. Applied tracking disposition before exact-pool market work and preserved
   deterministic reserve replacement.
5. Propagated requalification state through current holder admission and final
   two-token handoff.
6. Corrected provider-versus-tracking terminal precedence.
7. Persisted pre-lifecycle admission evidence and campaign-config selective
   authorization.
8. Reproved existing 15m, continuation, 1h, cleanup, reporting, replay, ceiling,
   and capability-lock owners.

## Files changed

Documentation:

- `docs/printer-v1-v2-9-8b-selective-1h-comprehensive-blocker-audit.md`
- `docs/printer-v1-v2-9-8b-selective-1h-comprehensive-repair-design.md`
- `docs/printer-v1-v2-9-8b-selective-1h-comprehensive-repair-closeout.md`

Implementation:

- `src/printer_v1/lifecycle/tracking_queue.py`
- `src/printer_v1/operator_cli/tracking_lifecycle_reconciliation.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/operator_cli/operational_selective_1h.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Tests:

- `tests/test_v2_9_7b_3_tracking_lifecycle_reconciliation.py`
- `tests/test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff.py`
- `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py`
- `tests/test_v2_9_8b_4_blocked_supply_source_reporting.py`
- `tests/test_v2_9_8b_operational_selective_1h.py`
- `tests/test_v2_9_8b_selective_1h_tracking_handoff_contract.py`

No schema migration was required.

## Offline proof and checks

The final focused cross-owner regression command covered 12 test modules and
passed:

- **170 passed, 28 subtests passed** in 112.19 seconds.

It proves:

- active cooldown reserve exclusion before market I/O and fresh replacement;
- valid future cooldown, historical derived expiry, pre-expiry refusal, and
  expired-cooldown fresh requalification;
- no stale-evidence or expiry-only claim;
- atomic two-slot handoff with one exact reopen event, two Scheduler jobs, and
  no duplicate queue;
- provider failure distinct from true market shortage, including mixed failure
  precedence;
- either token 15m close order and the final-close barrier;
- exact safety and predecessor linkage;
- immutable zero/one/two continuation cases with no duplicate decisions,
  windows, or Scheduler jobs;
- bounded 1h scheduling, collection, memory binding, terminal campaign-window
  state, closeout, and cleanup;
- truthful terminal report persistence and zero-source replay;
- zero active/orphan work at terminal;
- source, duration, Scheduler, and close-step ceilings;
- 4h+, retrieval, paper, and financial locks.

Additional checks:

- Python compilation: PASS.
- `git diff --check`: PASS.
- Retained artifact/report and SQLite reconciliation: read-only PASS.
- Authoritative database runtime sidecars: none.
- No network, live source, campaign, Scheduler, lifecycle, or memory runtime was
  invoked.

## Authoritative database integrity

- Before SHA-256:
  `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872`
- After SHA-256:
  `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872`
- Equality: PASS.
- Authoritative cleanup/mutation: none.

## Rollback

Revert the single commit titled `Repair complete selective 1h blocker path`.
There is no migration and no authoritative data rollback. Retained artifacts
and database rows were not changed. Reverting restores the historical cooldown
trap and reporting omissions, so an operator proof must not run on the reverted
state without another readiness review.

## Money-usefulness contribution

The repair increases useful clean-memory throughput without manufacturing
profit or relaxing evidence. A fresh campaign can now rotate past genuinely
unavailable reserve identities, reconsider a legitimately expired cooldown
only with current evidence, and reach Scheduler-owned 15m/1h learning work when
two candidates truly qualify. Provider outage and market shortage remain
visible, so corpus growth is not misreported as trading opportunity or fake
success.

## What remains locked

- Any additional live proof, retry, restart, resume, or successor.
- 4h, 12h, and 24h production work.
- Retrieval activation.
- Paper decisions and `BUY`, `SELL`, or `HOLD`.
- Paper positions, trade events, paper audits, and PnL.
- Live execution, wallets, signing, private keys, and real funds.
- Paid APIs.
- Scoring, ranking, confidence percentages, weighted logic, embeddings, and
  vectors.
- Any source fetching outside Source Governor or work outside Central
  Scheduler.

## Proof still required

Only a future operator-authorized live proof could establish current external
provider availability, current two-token market supply, actual repaired 15m
completion, the live zero/one/two continuation outcome, and actual bounded 1h
collection/closeout. This PASS does not authorize that proof.

The exact next permitted lane is a **fresh read-only V2-9.8B operator-readiness
review for the repaired selective-1h path**.

## Functionality Risks / Setbacks / Efficiency Blockers

- Free-public providers can still fail, rate-limit, delay, or return malformed
  evidence; the machine will stop truthfully.
- Current Solana memecoin supply may contain fewer than two candidates that pass
  every graduation, liquidity, age, quote, holder, safety, freshness, and
  tracking gate.
- Historical cooldown expiry is derived from `last_checked_at` only when the
  old `next_check_at` is unusable. Missing or malformed historical timing still
  requires fail-closed operator review.
- A cooldown that expires after the campaign's fixed admission instant remains
  blocked for that campaign, preserving deterministic evidence timing; no
  automatic retry is created.
- The repaired full live route remains operationally unproven because this lane
  correctly prohibited runtime.
- Discovery/migration work may still be necessary before known identities are
  filtered because that governed work is what can supply safe replacements;
  exact-pool calls for already unavoidable tracking blockers are now avoided.
