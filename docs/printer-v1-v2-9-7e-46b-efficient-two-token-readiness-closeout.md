# Printer V1 — V2-9.7E.46B Efficient Two-Token Readiness Closeout

**Verdict: `V2_9_7E_46B_BLOCKED_EXECUTOR_NETWORK`.**

E.46B removes the mandatory `LATEST + PERSISTED` readiness pair quota and replaces
it with efficient partition-flexible two-token sourcing from **one deterministic
combined candidate pool**. Any lawful composition — `LATEST + LATEST`,
`LATEST + PERSISTED`, or `PERSISTED + PERSISTED` — of two distinct fully eligible
tokens now satisfies readiness. Provenance remains truthful per-token metadata; it
is never relabelled and never a compulsory quota. The lane also distinguishes
healthy discovery/selection exhaustion from a holder-source outage, and reconciles
pre-lifecycle campaign/run/cycle metadata to honest terminal states. This closeout
does not authorize an E.46 full pilot and does not unlock V2-9.7F.

- **Starting commit:** `de09db5e8a40e5dcf181cfd0d3fba889039a1570`.
- **Live execution HEAD:** `092a4cbdd05dddf2307f0d23c37e17f2a1647cb9`.
- **Ending commit:** the lane commit containing this document; exact SHA is reported
  by the committing task.
- **Live date:** 2026-07-24.

## Established facts carried in

- E.46A's holder failures were caused by a local Wi-Fi interruption. No provider,
  endpoint, retry policy or holder-evidence rule was changed.
- E.46A found two eligible LATEST candidates but stopped because both PERSISTED
  reserves were below `$3,000` **and** because the old code demanded a mixed pair.
- LATEST/PERSISTED remain truthful provenance metadata, not a pair quota.

## Implementation

Partition-flexible sourcing is composed from the existing E.42/E.43/E.44/E.45
owners; no new source call, provider, endpoint, retry, score, ranking, confidence
or weighting was added.

1. **Combined candidate pool.**
   `graduated_liquidity_front_door.combined_reserve_order()` takes one deterministic
   seeded-uniform order over the *union* of the LATEST and PERSISTED eligible
   partitions (domain `COMBINED_TWO_TOKEN`). This supersedes the round-robin reserve
   order for downstream two-token selection and is what makes any lawful composition
   reachable without a one-per-partition quota. Ordering is seeded-uniform only;
   provenance, liquidity magnitude, recency and provider order never affect it.

2. **Partition-flexible selection.**
   `select_two_eligible_tokens()` walks the combined order and runs the injected
   holder gate in that order within a frozen holder-operation `candidate_cap`. On a
   liquidity/holder/gate failure it continues immediately to the next lawful
   candidate; it stops as soon as two distinct holder-eligible tokens exist — of any
   composition — or the pool is exhausted or the cap is reached. A rejected identity
   gets no second chance.

3. **Truthful provenance.** Each selected token carries its real
   `LATEST_GRADUATED` / `PERSISTED_GRADUATED` provenance into the readiness bundle. A
   LATEST token is never relabelled PERSISTED (or vice versa). The immutable
   `printer_pilot_input_readiness_bundle` records both slots' true provenance.

4. **Combined-pool holder funnel.**
   `authoritative_live_operational_campaign.run_operational` now evaluates holder
   eligibility with partition gating disabled (`partition_by_mint=None`), so the
   funnel no longer skips same-partition candidates and stops after any two eligible.
   Final two-token selection walks the seeded combined reserve order and picks the
   first two holder-eligible distinct tokens.

5. **Supply readiness.** `graduated_supply_front_door.build_graduated_supply`'s
   `ready` gate now means "at least two lawful eligible candidates are available in
   the combined reserve pool" (`GRADUATED_SUPPLY_READY`), not "one LATEST plus one
   PERSISTED selected". Fewer than two eligible `$3K+` candidates remains honest
   market supply (`BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL`).

6. **Candidate-search depth (item 6, exact arithmetic).** The holder operation
   ceiling (`OPERATION_CEILING`) is `45`. Of these, `9` are fixed zero-transport
   validations and `2 + 4 = 6` are reserved snapshot/completion operations, leaving
   `30` usable operations. Fully vetting one candidate costs `1` governed exact-pool
   DexScreener liquidity request plus up to `HOLDER_WORST_CASE_TRANSPORT_OPERATIONS`
   (`5`) holder transport operations = `6`, so the ceiling supports
   `floor(30 / 6) = 5` fully vetted candidates before direct-migration discovery pump
   operations are charged. The live front-door combined pool is therefore sized to
   `6` (one more than the holder-vetting depth) so a candidate that fails liquidity or
   holder evidence can be lawfully replaced inside the same bounded budget, and the
   confirmed-LATEST discovery depth is `5`. A larger pool would raise the charged base
   and drive `candidate_cap` below two. The runner no longer stops after a fixed tiny
   four-candidate set.

7. **Terminal classification (item 8).**
   `_classify_pre_lifecycle_terminal` and `select_two_eligible_tokens` distinguish:
   - a holder **source/network outage** (any evaluated candidate's holder reason is a
     transport/auth/rate-limit/stale/collection failure) →
     `PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED`;
   - **approved candidate-search capacity exhausted** (the cap stopped coverage while
     healthy sources answered) →
     `PRE_LIFECYCLE_DISCOVERY_SELECTION_CAPACITY_EXHAUSTED`;
   - **fewer than two eligible after full bounded coverage** by healthy sources →
     `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`.
   Healthy-source exhaustion is never casually attributed to the market.

8. **Pre-lifecycle terminal metadata reconciliation (item 9).** On every
   pre-lifecycle terminal path, `_reconcile_pre_lifecycle_terminal_metadata`
   transitions the launch graph (campaign `RUNNING` / run `RUNNING` / cycle `PLANNED`)
   to honest terminal states: `TERMINAL_STOPPED` for a clean `PILOT_INPUT_READY`
   governed safe stop, `TERMINAL_BLOCKED` for every other pre-lifecycle cause.
   Already-terminal rows are left untouched (immutable). No terminal proof leaves
   `RUNNING/RUNNING/PLANNED` metadata with zero active work. This creates no restart
   or successor.

9. **FULL_PILOT unchanged / no lifecycle.** `FULL_PILOT` retains its call surface;
   this lane starts no lifecycle. The selection improvement applies identically to
   both readiness and full-pilot admission, but no memory, retrieval, decision,
   position, trade, audit or PnL capability is unlocked.

### Preserved invariants

Source Governor and Central Scheduler ownership; deterministic ordering; existing
source order; no retry-until-success, endpoint rotation or provider racing; `$3,000`
fresh exact-pool liquidity; exact pool/mint identity; valid holder evidence;
two-or-none readiness; no scoring/ranking/confidence/weighting.

## Files changed

- `src/printer_v1/discovery/graduated_liquidity_front_door.py` — combined-pool order,
  `select_two_eligible_tokens`, composition label, terminal + source-outage constants.
- `src/printer_v1/operator_cli/graduated_supply_front_door.py` — combined reserve
  consumption, partition-flexible `ready`, `combined_reserve_count` diagnostic.
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` —
  combined-pool holder funnel, first-two-eligible selection, true-provenance readiness
  bundle, `_classify_pre_lifecycle_terminal`.
- `src/printer_v1/operator_cli/two_token_operational_pilot_runner.py` — deeper safe
  candidate-search depth, pre-lifecycle terminal metadata reconciliation.
- `tests/test_v2_9_7e_46b_efficient_two_token_readiness.py` — new focused proof.

Not touched: holder adapters/endpoints/retry policy, evidence thresholds, source
budgets, migrations, Source Governor, Central Scheduler, memory-quality rules,
lifecycle driver, or any capability lock.

## Offline proof

Focused and directly-affected regressions, stopped on the first relevant failure:

- New focused proof `tests/test_v2_9_7e_46b_efficient_two_token_readiness.py`:
  **15 passed**.
- E.43 front door + E.45 holder-reserve funnel + E.45 pilot-input readiness:
  **39 passed**.
- E.44 FULL_PILOT supply integration: **7 passed** (the partition-flexible `ready`
  and campaign selection remain compatible with the mixed and below-floor cases).
- E.14 two-token operational pilot runner: the deliberate candidate-search depth
  contract was updated (`max_candidates` 4→5, `front_door_max_candidates` asserted 6)
  and the pre-lifecycle reconciliation class passes
  (`test_production_invocation_receives_real_canonical_timing` +
  `PilotInputReadinessModeTests`: **3 passed**; the eight preceding target-preparation
  and holder-readiness-preflight tests passed).
- Changed-file `py_compile`: PASS. Changed-module import smoke: PASS.
  `git diff --check`: PASS.

One **pre-existing, unrelated** baseline failure was confirmed and deferred:
`test_v2_9_7e_33_canonical_readiness_boundary.py::CanonicalModeSurfaceTests::test_activation_only_dispatch_starts_no_lifecycle`
fails identically at the starting commit `de09db5` with this lane's changes stashed
(`readiness.status == 'NOT_READY'` in `ACTIVATION_ONLY` mode). It is a different
canonical mode, does not touch the partition-flexible two-token path, and is not in
this lane's scope. The remaining 15 E.33 tests pass.

The focused proof establishes: all three lawful compositions
(`LATEST+LATEST`, `LATEST+PERSISTED`, `PERSISTED+PERSISTED`) select two tokens;
several early candidate failures continue to later eligible candidates; exhaustion
of one provenance partition does not block selection; the combined pool contains both
partitions (bounded discovery reserve is one pool); the loop is finite with exact
operation accounting (one op per evaluated candidate, each identity once, cap
respected); a source outage and a healthy coverage/capacity exhaustion are classified
separately; one eligible candidate still blocks honestly; readiness writes
`PILOT_INPUT_READY` only for two fully eligible candidates and records true
provenance; and pre-lifecycle campaign/run/cycle metadata reconciles to terminal.
The E.43 front-door, E.44 supply-integration, and E.45 holder-reserve/readiness
regressions continue to pass unchanged.

## One bounded live readiness execution

Exactly one canonical `PILOT_INPUT_READINESS` execution was launched at HEAD
`092a4cb` with `PRINTER_HELIUS_API_KEY` present (by presence only), clean tracked
Git provenance, fresh identity `e46b-readiness-20260724-092a4cb-2`, and isolated
disposable artifacts. There was no retry, restart, rotation, race, or successor.

| Field | Evidence |
|---|---|
| Readiness source-contract preflight | Passed (secret present by presence only; no secret material recorded) |
| Supervision status at termination | `STARTING` (never reached a terminal) |
| DexScreener locator | 1 governed request, 1 response, **0 failures** — provider egress works |
| Source failures recorded | 0 |
| Graduated registry rows confirmed | 0 (direct-migration discovery still in progress) |
| `PILOT_INPUT_READY` bundles | 0 |
| Lifecycle | not started |
| Terminal cause | none — the executor process was terminated externally before a terminal |

**Nature of the block.** The execution genuinely started: it passed the
zero-transport source/secret/budget preflight and completed one governed
DexScreener fresh-profile locator request successfully (so the block is **not** a
network or source-availability failure and **not** a missing secret). It was inside
the bounded direct-migration discovery phase (the PumpPortal migration stream, whose
canonical uncompressed collection window alone is ~120 s) when the fresh-executor
environment terminated the process at approximately two minutes — far below the
~15-minute bounded readiness window an honest run requires (the comparable E.46A
readiness run took 875 s of supervised wall time). No timing may be compressed to fit
a shorter window, and no code was modified after the execution to force a result.

Because the executor could not sustain the required execution window, this is an
executor-environment block (`V2_9_7E_46B_BLOCKED_EXECUTOR_NETWORK`): the fresh
executor did not reach a readiness terminal. **No readiness PASS is claimed.** No
`PILOT_INPUT_READY` bundle, activation, lifecycle, memory, retrieval, decision,
position, trade, audit or PnL was created; the attempt DB independently confirms
zero graduated rows, zero readiness bundles, and zero forbidden rows. The
disposable artifacts (target, backup, lock) live only in an isolated scratch
directory and never entered the repository or any persistent corpus.

The one observed cost of the external termination is that the isolated attempt DB
retained `RUNNING/RUNNING/PLANNED` campaign/run/cycle metadata — the runner's item-9
reconciliation code never executed because the process was killed before finalize.
This is exactly the failure mode item 9 exists to prevent on a *governed* terminal;
it cannot run when the OS terminates the interpreter mid-cycle. The offline proof
confirms the reconciliation itself works on every governed pre-lifecycle terminal.

## Money-usefulness contribution

The lane removes an artificial supply constraint that made honest readiness harder
than the market requires: two liquid, holder-valid graduated tokens now qualify
regardless of whether they are both freshly graduated, both persisted, or mixed.
This raises the probability that a lawful, non-fabricated two-token input set exists
for a later authorized pilot, without weakening the `$3,000` liquidity floor, exact
pool/mint identity, or holder-evidence gate. No memory, paper result, trade or profit
claim is made.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Functionality risk:** the combined-pool selection is exercised offline on
  fixtures; a live end-to-end readiness PASS depends on provider reachability that is
  environment-gated (see live result).
- **Setback:** the holder operation ceiling caps fully vetted candidates at five, so
  a run with many below-floor or holder-failing candidates can still exhaust coverage;
  this is now reported honestly as coverage/capacity insufficient, not market failure.
- **Efficiency blocker:** discovery pump operations reduce the holder `candidate_cap`;
  the front-door pool is sized to the maximum safe depth (6) to leave room for lawful
  replacement without breaching the ceiling. This is not permission to cache stale
  evidence, race providers, or add retries/endpoints.

## Remaining locks and next lane

All permanent Printer V1 locks remain in force: Solana memecoin only, paper only, no
wallets/private keys/funds/live execution, no paid APIs, no scoring/ranking/
confidence/weighted logic, no Source Governor or Central Scheduler bypass, no dirty
memory for decisions, and no BUY/SELL/HOLD, positions, trade, audit, or PnL unlock.

A separate E.46 full-pilot retry is **not ready**. The partition-flexible two-token
implementation is complete and offline-proven, but a live readiness PASS was not
obtained: the fresh-executor environment could not host the ~15-minute bounded
readiness window (the process was terminated at ~2 minutes with providers reachable
and the secret present). A separately authorized E.46 full-pilot retry requires,
first, one clean live `PILOT_INPUT_READINESS` PASS producing a real immutable
`PILOT_INPUT_READY` bundle from two distinct fully eligible tokens of any lawful
provenance composition, run in an executor able to sustain the full bounded window.
A PASS here would only make that retry ready; it does not run the pilot and does not
unlock V2-9.7F. V2-9.7E remains active; V2-9.7F is not ready and was not started.
