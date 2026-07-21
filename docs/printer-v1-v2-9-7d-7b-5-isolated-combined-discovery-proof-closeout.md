# V2-9.7D.7B.5 Isolated Combined Discovery Proof Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.5
**Boundary:** synthetic end-to-end proof only; no production implementation change
**Date:** 2026-07-21

PASS means the committed combined Pump.fun discovery path was proven on
disposable isolated SQLite databases with synthetic fixtures only. It does not
authorize live providers, public commands, operational activation, V2-9.7D
closeout, or the pilot.

## Todo / Checklist

- [x] Verify exact starting commit `0405191ded2e37b86dce2b13321014bcb99c8368`.
- [x] Read AGENTS.md, active stack, 7B.2 design, and 4A–4D.1 closeouts.
- [x] Build isolated proof harness and mixed synthetic fixtures.
- [x] Execute scenarios A–J with focused assertions.
- [x] Rerun 4D.1, 4D, 4C, and 7A regressions.
- [x] Write this closeout and commit only proof-lane files.

## Exact Commit Proven

`0405191ded2e37b86dce2b13321014bcb99c8368`

No production modules were modified in this lane.

## Exact Fixtures and Disposable Database Strategy

- Each proof case builds a disposable SQLite file under the process temp
  directory via `tempfile.TemporaryDirectory`.
- Migrations are applied with `apply_migrations`.
- Campaign/run/cycle ownership is created through the committed campaign
  persistence helpers in `PROOF_ISOLATED` mode.
- Provider inputs are pure `CombinedDiscoveryFixtures` objects (direct origin
  proofs, DexScreener active pairs, GeckoTerminal trending/active pools, Solana
  Tracker trending/top rows, optional PumpSwap proofs, forced fault injectors).
- No network, WebSocket, credential, or persistent operational DB is used.

Proof suite:

`tests/test_v2_9_7d_7b_5_isolated_combined_discovery_proof.py`

## Scenarios Executed

| ID | Scenario | Result |
|---|---|---|
| A | Successful initial multi-provider campaign | PASS |
| B | Deterministic replay + order/rank mutation invariance | PASS |
| C | Initial two-or-none insufficient eligible pool | PASS |
| D | Atomic rollback on second-handoff failure | PASS |
| E | Replacement healthy-slot preservation and vacancy fill | PASS |
| F | Provider failure isolation (Gecko/Tracker/Dex/PumpSwap/direct) | PASS |
| G | Shared-fault safe stop + ceiling shared fault | PASS |
| H | Ceiling constants and usage-guard enforcement | PASS |
| I | Persistence/replay integrity and locked-table safety | PASS |
| J | Locked-capability zero deltas | PASS |
| + | Windows SQLite clean close | PASS |

Focused suite result: **11 passed** (plus 3 shared-fault subtests).

## Provider Contributions

Successful mixed campaign includes:

- **Direct Pump finalized creates** for mints A/B/C as mint-scoped origin authority;
- **GeckoTerminal** page-1 trending plus one exact active-pool `m5` enrichment;
- **Solana Tracker** trending and top free-REST rows with `market=pumpfun` filter;
- **DexScreener** active-market observations with non-zero `m5` activity;
- **PumpSwap** optional confirmation proof for mint C when graduated claim is present;
- exact-duplicate cross-provider rows retained as provenance, not multiplied authority;
- failing candidate mint D remains origin-unverified without direct evidence.

## Selection Seed and Selected Identities

Cycle selection seed formula (committed contract):

```text
SHA256(
  "PrinterV1|combined-pumpfun-v1|"
  + campaign_selection_seed + "|"
  + campaign_id + "|" + run_id + "|" + cycle_id + "|" + discovery_batch_id
)
```

Proof seed material:

- `campaign_selection_seed = v2-9-7d-7b-5-proof-seed`
- campaign/run/cycle = `campaign-7b5` / `run-7b5` / `cycle-7b5`

Identical logical inputs on two fresh DBs produced identical:

- observation hash sets;
- merged-candidate hashes and origin states;
- selected slot mint identities;
- provider report hash/payload.

Provider rank/score/promoted/order mutation did not change selected mints.

## Atomic Handoff Evidence

- Success path: exactly two slots, two tracking-queue rows, two
  `TRACK_NORMAL_FIRST_15M` jobs, two selected-item links.
- Second-handoff inject (`DURING_SECOND`): zero slots, zero tracking rows, zero
  15m jobs, zero selection activation rows; discovery batch
  `TERMINAL_FAILED` with first cause `HANDOFF_DURING_SECOND`; no retry batch.

## Failure-Isolation Evidence

- GeckoTerminal failure: no Gecko observations; direct/other healthy lanes remain;
  work row `GECKOTERMINAL_FAILED`; campaign can still complete when enough eligible
  candidates remain.
- Solana Tracker failure: tracker observations absent; Gecko/direct remain.
- DexScreener failure: no dexscreener observations; work row `DEXSCREENER_FAILED`.
- PumpSwap ambiguity: confirmation state `AMBIGUOUS` for that mint only; campaign
  still completes two-slot activation from other eligible candidates.
- Direct origin-authority loss: no eligible pool →
  `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`.

## Ceiling Evidence

Committed maxima asserted:

| Ceiling | Value | Proof method |
|---|---:|---|
| Governed source calls | 45 | constant + usage guard raises `SOURCE_CEILING` |
| Direct underlying RPC | 45 | constant present |
| Scheduler intake work | 11 | constant + usage guard raises `SCHEDULER_WORK_CEILING` |
| Normalized observations | 96 | constant |
| Unique merged mints | 64 | constant |
| Origin-verification admissions | 8 | constant + slice-bound assertion |
| PumpSwap confirmations | 4 | constant + slice-bound assertion |
| Tracking handoffs | 2 | constant + success path slot count |
| Persisted intake growth | 8 MiB | constant + storage guard raises `STORAGE_CEILING` |
| Intake deadline | 360 s | constant + work `deadline_at` bound to cycle cutoff |
| Provider-lane failures | 5 | constant + failure guard raises `PROVIDER_LANE_FAILURE_CEILING` |
| Ordinary retries | 0 | unique `(batch, work_type)` rows; no second attempt |

Wall-clock preemption of a long-running cycle is not a separate runtime kill
switch in the fixture executor; deadline is carried as immutable work
`deadline_at` equal to the cycle cutoff.

## Persistence and Replay Evidence

- Observations and candidates are campaign/run/cycle/discovery-batch owned.
- Discovery work has no pre-selection `token_slot_id` / `window_id` fabrication.
- Work-to-source links are one-to-many.
- Observation hashes are 64-char digests.
- Provider report reconstructs with discarded non-authoritative field list.
- Identical re-execution on a filled DB remains locked-capability safe.
- Conflicting shared fault fails closed without discovery batch activation.

## 7A Result / Report Evidence

Successful result includes:

- `source_governor_used=True`
- `central_scheduler_used=True`
- `selective_continuation_preserved=True`
- `support_5m_only=True`
- `successor_created=False`
- `restart_created=False`
- finite usage fields within campaign ceilings

Provider contribution report link persists factual diagnostics only.

## Locked-Capability Baseline and Final Deltas

Baseline and final counts for:

- `printer_memory_retrieval_queries`
- `printer_memory_retrieval_matches`
- `printer_paper_decisions`
- `printer_paper_positions`
- `printer_paper_trade_events`
- `printer_paper_trade_audits`
- `printer_paper_audit_reports`

were all **0 / 0**. No BUY/SELL/HOLD/WAIT/AVOID/NO_ACTION activation tables were
written. No `TRACK_FAST_MICRO_EVENT`, 1h, or 4h discovery jobs were created.

## Money-Usefulness Contribution

This proof shows the machine can, under fixture conditions, convert multi-source
Pump.fun observations into exactly two tracking handoffs only after:

- governed source/scheduler ownership;
- exact origin confirmation;
- fixed gates and cooldown;
- seed-uniform selection;
- atomic two-or-none activation.

That protects later memory growth from partial activation, provider marketing
bias, and unverified origin labels, without claiming profit.

## What the Proof Establishes

- The committed 7B.4A–4D.1 stack is coherently bindable end-to-end on disposable
  DBs.
- Initial activation is two-or-none and rollback-safe.
- Provider isolation and shared-fault stop behave as designed under fixtures.
- Locked financial/retrieval surfaces remain zero throughout.

## What Remains Unproved

- real provider/RPC schema drift, auth, quota, latency, and disconnect behavior;
- measured free-plan monthly capacity under multi-cycle campaigns;
- durable operational-target supervision under concurrent operators;
- public command publication and operator runbooks;
- multi-cycle continuous campaign wall-clock deadline preemption;
- live-source proof (`7B.6`) and activation/pilot review.

## Next Permissible Lane

`V2-9.7D.7B.6 — Bounded live-source proof` only after explicit operator approval,
provider by provider, still without pilot activation.

Do not start V2-9.7D closeout or the pilot from this proof alone.

## Functionality Risks / Setbacks / Efficiency Blockers

- Fixture origin proofs can complete without exercising full RPC continuity
  decode under live retention limits.
- Full multi-provider cycles consume the entire 11-work intake ceiling, leaving
  no spare unplanned work room.
- Deadline enforcement is contract/deadline_at based; a runaway fixture loop is
  not process-killed at 360 seconds by this owner.
- Replacement success depends on vacant-slot state reconciliation; failed prior
  slot identity remains until a later lifecycle policy rewrites it.
- Report hash reconstruction is validated for presence and shape; byte identity
  across runs was proven for identical logical campaigns, not for wall-clock
  fields outside canonical payloads.
- Windows temp-directory cleanup can race if a DB handle is left open; proof
  cases close connections explicitly.

## Exact Files Changed

- `tests/test_v2_9_7d_7b_5_isolated_combined_discovery_proof.py` (new)
- `docs/printer-v1-v2-9-7d-7b-5-isolated-combined-discovery-proof-closeout.md` (new)

No production implementation files changed.

## Regressions Run

- `tests/test_v2_9_7d_7b_5_isolated_combined_discovery_proof.py`
- `tests/test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff.py`
- `tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py`
- `tests/test_v2_9_7d_7b_4c_discovery_persistence.py`
- `tests/test_v2_9_7d_7a_abstract_command_surface.py`

All passed. `git diff --check` passed for lane files.

## Stop Boundary

V2-9.7D.7B.5 stops at isolated combined discovery proof artifacts and this
closeout. `V2-9.7D.7B.6`, activation review, V2-9.7D closeout, and the pilot
have not begun.

## Final Lane Result

`V2_9_7D_7B_5_ISOLATED_COMBINED_DISCOVERY_PROOF_PASS`
