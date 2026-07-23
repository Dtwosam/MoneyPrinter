# Printer V1 V2-9.7E.40 Continuous Full-Pilot Repair, Restart, and Clean-Pass Session Closeout

## Verdict

`V2_9_7E_40_ATTEMPT_CEILING_REACHED`

Three authorized live `FULL_PILOT` attempts were completed without a full clean
lifecycle PASS. Every discovered blocker was repaired and proved offline; the
final blockers (BL-40-03/04) are fixed and committed but not yet live-verified
because the three-attempt ceiling is reached. Per the operator's direction, the
session applies the E.40 stop conditions after Attempt 3.

## Starting commit

`6d8472ba8dd816ca816fc663a9b07bc5bc48f892` (`Close full pilot blocker investigation`).

## Repair commits (in order)

1. `68274a9` — `Repair full-pilot admission and candidate supply`
   (BL-39-01 full-pilot 900s maturity + fail-closed admission; BL-39-03 admission
   mechanism).
2. `47e76e8` — `Repair full-pilot pre-lifecycle block terminal`
   (BL-40-01, found by Attempt 1).
3. `7dc0f62` — `Repair full-pilot candidate supply with persistent pool`
   (BL-39-03 operator-approved discovery-only persistent pool).
4. `61fe119` — `Apply full-pilot maturity before candidate cap`
   (BL-40-02, static).
5. `3ab4bc2` — `Preserve create layout for pool-seeded origin activation`
   (BL-40-03 create_layout propagation; BL-40-04 pilot-runner no-activation
   robustness — both found by Attempt 3).

## Final commit

This closeout + blocker register (`<final commit>`).

## Number of live attempts

3 (ceiling).

## Attempt identities and verdicts

| Attempt | Commit | Execution id | Verdict | First terminal cause |
|---|---|---|---|---|
| 1 | `68274a9` | `e40-attempt1-20260723T170534Z` | blocked, not clean → repaired | `attach_run` FK failure (BL-40-01) |
| 2 | `47e76e8` | `e40-attempt2-20260723T171456Z` | **clean** `GOVERNED_SAFE_STOP` | `BLOCKED_INSUFFICIENT_MATURE_POOL` (honest cold-start supply) |
| 3 | `61fe119` | `e40-attempt3-20260723T174343Z` | blocked, not clean → repaired | `ACTIVATION_FAILED`/`ORIGIN_REGISTRY_CONFLICT` (BL-40-03); runner raised on no run_id (BL-40-04) |

## What was fixed

- **BL-39-01** (`FIXED`, live-proven at Attempt 2): FULL_PILOT applies the frozen
  900s categorical maturity boundary and fails closed with
  `BLOCKED_INSUFFICIENT_MATURE_POOL` before any holder/lifecycle/memory work; the
  historical admission evidence is distinguished from the forward WINDOW_15M (the
  readiness-mode completed-15m gate is intentionally not copied).
- **BL-39-03** (`PARTIAL`, supply mechanism + persistent pool proven; live
  delivery proven at Attempt 3): the active pool is no longer solely the newest
  creates; a discovery-only persistent pool (reusing the durable
  `printer_pumpfun_finalized_origin_registry`, no new table) retains confirmed
  origins across bounded acquisition cycles, matures them categorically outside
  FULL_PILOT, and copies a bounded immutable DUE export into a fresh isolated
  attempt. Attempt 3 confirmed mature pool candidates are admitted past the 900s
  gate — a cold start never could.
- **BL-40-01** (`FIXED`): the live pilot runner finalizes a pre-lifecycle
  admission block cleanly without attaching a nonexistent factory run.
- **BL-40-02** (`FIXED`): maturity is classified over the whole universe before
  the candidate cap, so immature candidates cannot displace mature ones.
- **BL-40-03** (`FIXED`, offline): `create_layout` is carried through the origin
  proof, staged reload and executor reconstruction, so a pool-seeded
  `PUMP_CREATE_V2` origin no longer conflicts with a default `PUMP_CREATE_V1`
  re-record.
- **BL-40-04** (`FIXED`, offline): the pilot runner requires a run identity only
  when the lifecycle actually started; a no-atomic-activation terminal finalizes
  as a clean governed safe stop.

## What remains unfixed / limitations

- **No full clean lifecycle PASS** within the 3 authorized attempts. Attempts 1
  and 3 were consumed largely by discovering and fixing harness/integration
  defects; Attempt 2 was the honest cold-start supply block.
- **BL-40-03/04 not yet live-verified:** the fixes are proved offline but the
  ceiling is reached, so no live attempt has yet run through pool-seeded
  activation with the fix in place.
- **Possible next-stage blocker (not yet observed):** pool-seeded pre-graduation
  Pump bonding-curve tokens carry `lifecycle_identity = PUMP_CREATED_UNPAIRED`
  and `market_identity = pumpfun:<bonding_curve>`. The combined-discovery design
  records that unpaired launches may remain ineligible for a tracking-eligible
  AMM market identity. A 4th attempt could therefore still block at the
  market/eligibility gate; this is a known design limitation, not a proven defect.
- **BL-39-03 discovery-channel diversity (explicit):** the persistent pool
  supplies mixed-age *direct-origin* (`LATEST_PUMPFUN`) candidates only.
  Trending / top / active secondary-channel candidate coverage is NOT proved and
  remains a separate future operator decision.

## Repeated-after-repair

No repaired blocker recurred. Each repair advanced the live flow to the next
honest stage: A1 (runner attach) → A2 (honest supply block) → A3 (supply
delivered; activation conflict) → fixed.

## Candidate-pool channel and age composition per attempt

- **Attempt 1:** reached acquisition; not characterized before the runner defect.
- **Attempt 2:** universe 3, all IMMATURE (origin ages 118-121s; block_times
  ~2026-07-23T17:12Z). Channels LATEST_PUMPFUN 8, GECKO_TRENDING 2, DEXSCREENER 1,
  STAGED_DUE 0. mature=0.
- **Attempt 3:** persistent pool populated with 8 `PUMP_CREATE_V2` origins
  (block_times ~17:26Z), matured to 8 DUE over ~15 min outside FULL_PILOT; the
  fresh attempt was seeded with the bounded 8-origin DUE export (copied 8) and
  admitted mature candidates past the 900s gate. Exact final two selected
  candidates: not reached — activation failed before selection (BL-40-03).

## Source and Scheduler accounting

All acquisition and secondary enrichment ran through the Source Governor and
Central Scheduler owners under unchanged per-cycle ceilings (operation ceiling
45, candidate cap 3). No retry, endpoint rotation, source substitution, budget
increase, or paid source. Pool population used bounded governed acquisition
cycles; maturity waiting occurred outside FULL_PILOT through real wall clock and
Scheduler-owned categorical states.

## Lifecycle and memory results

Zero across all three attempts: no lifecycle windows, run steps, memory windows,
episodes, retrieval, decisions, positions, trade events, audits, or PnL. No
attempt started a factory lifecycle run.

## Replay and cleanup results

- Attempt 2: deterministic zero-source replay, one-proof lock released, integrity
  `ok`, foreign-key violations `0`.
- Attempt 3: integrity `ok`, foreign-key violations `0`, all forbidden-capability
  counts `0`; the terminal was not clean at the runner level (BL-40-04, now
  fixed).

## Tests

- New: `tests/test_v2_9_7e_40_full_pilot_admission.py` (admission fail-closed,
  partition, staged reload, maturity-before-cap, pilot-runner pre-lifecycle block,
  activation-failed clean terminate) and
  `tests/test_v2_9_7e_40b_persistent_candidate_pool.py` (stage/mature/export/seed,
  idempotent/categorical, V2 re-record idempotency, immature-seeds-nothing).
- Regressions (all pass): E.11 operational, E.14 pilot runner, E.8 integration,
  E.36-38 maturity, E.33 readiness, E.5/E.6 origin, 7B.4a-4d combined discovery
  (125), combined executor + atomic handoff.

## Forbidden-capability deltas

Zero in every attempt (retrieval queries/matches, paper decisions, positions,
trade events, trade audits, audit reports, episodes, memory windows).

## Permanent locks

Preserved throughout: Solana-only, memecoin-only, paper-only; no wallet/keys/
signing/funds/execution; no paid API; no scores/ranks/confidence/weighted logic;
no embeddings/vectors; no Source Governor/Central Scheduler bypass; 5m
support-only; no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/
trade events/paper audits/PnL; no V2-9.7F / V2-9.8 or later work.

## Final verdict

`V2_9_7E_40_ATTEMPT_CEILING_REACHED`.

## Exact next action

The three-attempt ceiling is exhausted, so no further live attempt is taken under
this prompt. All known blockers are repaired and proved offline at `3ab4bc2`, and
the discovery-only pool mechanism is committed and repeatable. The exact next
action is an operator decision:

1. Authorize a fresh full-pilot attempt from `3ab4bc2` (repopulate the
   discovery-only pool via bounded governed acquisition, wait ~15 min for ≥2 DUE
   outside FULL_PILOT, seed the DUE export, and run `run(mode=FULL_PILOT)`) to
   live-verify BL-40-03/04 and observe whether pool-seeded candidates activate or
   block at the `PUMP_CREATED_UNPAIRED` market-eligibility gate; and/or
2. Open a separate design lane for pre-graduation bonding-curve market identity
   (so unpaired Pump launches can become tracking-eligible), and/or for
   secondary-channel (trending/top/active) candidate discovery with live
   origin verification.

No further live pilot is started, and nothing is tagged, under this prompt.
