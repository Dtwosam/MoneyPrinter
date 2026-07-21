# V2-9.7D.7B.4D Combined Discovery Execution Owner Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.4D
**Boundary:** fixture-backed combined execution owner only
**Date:** 2026-07-21

PASS means the approved discovery, persistence, selection and tracking-handoff
contracts are bound by one dependency-injected fixture-backed execution owner
compatible with the 7A `execute_campaign` interface. It does not mean live
providers, public commands, operational campaigns, or financial capability.

## Todo / Checklist

- [x] Verify exact starting commit `060177da8e77fe8c3422cb324ac67604af393cd6`.
- [x] Read AGENTS.md, active stack, 7B.2 design, and 4A/4B/4C closeouts.
- [x] Bind Source Governor, Central Scheduler, adapters, and migration 034.
- [x] Implement merge, verification admission, fixed gates, cooldown, selection.
- [x] Implement transactional handoff and first WINDOW_15M job only.
- [x] Return 7A CampaignExecutionResult evidence.
- [x] Prove focused synthetic cases and update 7A migration-head binding.
- [x] Write this closeout and commit only on PASS.

## Exact Files Changed

- `src/printer_v1/discovery/combined_executor.py` (new)
- `tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py` (new)
- `src/printer_v1/operator_cli/abstract_campaign_command.py` (migration-head binding only)
- `tests/test_v2_9_7d_7a_abstract_command_surface.py` (latest_migration expectation)
- `docs/printer-v1-v2-9-7d-7b-4d-combined-discovery-execution-owner-closeout.md` (new)

No new migration was required. Migration 034 ownership is reused as-is.

## Implemented Execution Flow

`CombinedPumpfunCampaignExecutor.execute(command, source_governor, central_scheduler)`:

1. Exact-match campaign/configuration/run/cycle and require non-empty selection seed.
2. Validate provider-contract versions, Git provenance identity, cutoff and ceilings.
3. Create cycle-rooted discovery work through Central Scheduler (`DISCOVERY_REFRESH`).
4. Invoke fixture-backed direct, DexScreener, GeckoTerminal and Solana Tracker lanes only after Source Governor admission.
5. Persist requests/responses/failures, work-source links and normalized observations.
6. Merge by exact mint/market/lifecycle; mint-scoped direct origin is authoritative.
7. Admit secondary-only mints to origin verification with
   `SHA256(cycle_seed|origin|token_identity)` order and 8-mint ceiling.
8. Confirm origin from direct finalized proofs; provider `pumpfun` labels remain unverified alone.
9. Admit PumpSwap proofs with `SHA256(cycle_seed|pumpswap|token_identity)` and 4-mint ceiling.
10. Run fixed eligibility gates in the approved order.
11. Apply token and pair three-batch cooldown checks.
12. Canonical-sort and Fisher-Yates shuffle with immutable cycle seed; select without replacement.
13. Persist merged candidates, verification rows, selection batch and selected-item links.
14. Transactionally hand off selected vacancies into token/pair/tracking-queue/slot ownership.
15. Create only first main `WINDOW_15M` Scheduler jobs (`TRACK_NORMAL_FIRST_15M`).
16. Return `CampaignExecutionResult` with exact 7A usage/owner/terminal evidence.

## Reused Owners and Contracts

- 7A `CampaignExecutionResult` / `OwnerPort` / command identity
- Source Governor `can_request_source`
- Central Scheduler `enqueue_job`
- Direct Pump fixture continuity owner
- GeckoTerminal / Solana Tracker secondary normalizers
- DexScreener active observation fixture path
- Migration 034 discovery persistence repository
- Selection cooldown helpers
- Tracking queue enqueue owner

PumpPortal remains blocked. Pumpdev remains excluded. DexScreener and PumpSwap
authority were not expanded.

## Ceilings and First-Fault Behavior

Enforced maxima: 45 source calls, 45 underlying RPC, 11 scheduler work rows,
96 observations, 64 unique mints, 8 origin admissions, 4 PumpSwap admissions,
2 handoffs, 8 MiB storage, 5 provider-lane failures, zero ordinary retries,
zero endpoint rotation.

Provider lane failures remain isolated. Shared ownership/configuration/policy
faults return `FAILED` with `SHARED_*` causes and optional cancellation reason
for 7A safe-stop. Missing selection seed fails closed before intake work.

## Merge, Verification, Gate and Selection Behavior

- Duplicates collapse by exact candidate identity; provider multiplicity does not
  increase selection probability.
- Direct finalized origin is mint-scoped and may confirm secondary markets for
  the same mint.
- Provider rank/score/risk/promoted/response-order fields are stripped and cannot
  enter factual observation payloads.
- Gates stop at the first failure while retaining the failed gate identity.
- Initial activation requires exactly two eligible candidates or records
  `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` with zero handoff.
- Healthy occupied slots cannot be overwritten by replacement selection.

## Transactional Handoff Behavior

For each selected vacancy the owner:

- creates exact token/pair rows only at handoff time;
- enqueues tracking-queue work;
- enqueues first WINDOW_15M Scheduler job only;
- creates/links campaign token slots and selected-item links;
- refuses duplicate active tracking and forbidden 1h/4h/5m discovery jobs.

## Exact 7A Result Evidence Returned

`CampaignExecutionResult` fields:

- `terminal_status`, `first_terminal_cause`, optional `cancellation_reason`
- `cycles`, `duration_seconds`, `source_calls`, `scheduler_work`,
  `storage_bytes`, `failures`
- `source_governor_used=True`
- `central_scheduler_used=True`
- `selective_continuation_preserved=True`
- `support_5m_only=True`
- `successor_created=False`
- `restart_created=False`

7A preflight now accepts the repository migration head dynamically so 034 is
not a false blocker.

## Money-Usefulness Contribution

The owner turns approved discovery contracts into one auditable, deterministic
cycle that can fill two tracking slots only from clean-memory-path eligibility
inputs: exact origin, exact markets, fixed gates, cooldown and seed-uniform
selection. This improves future corpus intake quality without inventing profit
or enabling trade actions.

## What the Lane Improves

- One injectable execution owner binds adapters, persistence, gates and handoff.
- Fixture-proven two-or-none activation and healthy-slot preservation.
- Provider marketing fields cannot steer selection.
- First WINDOW_15M work is created without 1h/4h/5m discovery activation.

## What It Still Does Not Unlock

- real RPC/provider calls or secret setup;
- public command publication;
- operational persistent-target mutation;
- live-source proof, V2-9.7D closeout, pilot;
- memory generation, retrieval, paper decisions;
- BUY/SELL/HOLD/WAIT/AVOID/NO_ACTION;
- positions, trades, audits, PnL;
- wallets, signing, live execution, paid APIs, scoring/ranking/embeddings.

## Focused Proof Results

| Check | Result |
|---|---|
| Exact identity/config preflight and seed requirement | PASS |
| Provider work only via Central Scheduler | PASS |
| Transport only after Source Governor admission | PASS |
| Direct/DexScreener/GeckoTerminal/Solana Tracker contributions | PASS |
| Provider Pump labels unverified without direct proof | PASS |
| Merge + duplicate collapse | PASS |
| Origin verification admission / direct proof | PASS |
| Fixed gates + cooldown + uniform selection | PASS |
| Rank/score/promoted/order mutation invariance | PASS |
| Initial two-or-none / no partial handoff | PASS |
| First WINDOW_15M only; no 1h/4h/5m | PASS |
| Independent provider failure isolation | PASS |
| Shared-fault safe stop | PASS |
| Ceiling accounting and zero retries | PASS |
| Locked financial tables remain zero | PASS |
| Windows SQLite close | PASS |
| 7A owner-port result contract | PASS |

Focused suites:

- `tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py` — 7 passed
- `tests/test_v2_9_7d_7a_abstract_command_surface.py` — passed after migration-head binding
- `tests/test_v2_9_7d_7b_4c_discovery_persistence.py` — passed

## Remaining Blockers

No blocker remains for this fixture-backed execution-owner lane.

Live providers, durable operational activation, combined disposable end-to-end
proof beyond these focused cases, and public command publication remain later
explicit lanes.

## Functionality Risks / Setbacks / Efficiency Blockers

- Fixture direct origin uses simplified proofs when full RPC continuity fixtures
  are not supplied; live decode still depends on 4A continuity under real RPC.
- INITIAL two-slot handoffs are sequential; a later failure after the first
  successful handoff can leave one slot filled unless the caller rolls back the
  outer transaction. The executor returns FAILED and 7A cleanup owns lease stop.
- Cycle may start with zero slots; this is intentional for discovery-before-
  selection and differs from older factory graphs that pre-create two slots.
- Scheduler intake uses all 11 work-type rows in a full multi-provider cycle,
  leaving no headroom for extra unplanned work.
- 7A backup `latest_migration` configuration values must track the repository
  head; tests were updated accordingly.
- Idempotent full-cycle re-execution on a filled DB may terminal-fail on unique
  constraints; identical content paths are safe, conflicting replays fail closed.

## Stop Boundary

V2-9.7D.7B.4D stops at the fixture-backed combined execution owner, focused
proofs, 7A migration-head binding, and this closeout. `V2-9.7D.7B.5`,
live-source proof, V2-9.7D closeout and the pilot have not begun.

## Final Lane Result

`V2_9_7D_7B_4D_COMBINED_DISCOVERY_EXECUTION_OWNER_PASS`
