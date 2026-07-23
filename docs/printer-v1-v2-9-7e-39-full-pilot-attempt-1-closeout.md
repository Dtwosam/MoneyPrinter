# Printer V1 V2-9.7E.39 Bounded Two-Token Full Pilot Attempt 1 Closeout

## Verdict

`V2_9_7E_39_BLOCKED_PREFLIGHT`

## Restart status

`BLOCKED_PENDING_DESIGN`

This attempt made **zero** live provider calls, created **zero** durable
`FULL_PILOT` authorizations, and created **no** campaign/run/cycle identity. The
single authorized live execution was **not** consumed. It remains available for a
future attempt after the design gap below is closed.

## Summary

The mandatory Phase 1 preflight failed on a required precondition:

> "`FULL_PILOT` uses the committed Pump acquisition, 900-second maturity
> boundary, holder funnel and strict snapshot-readiness gate before lifecycle or
> memory work; fewer than two mature candidates cannot reach holder or snapshot
> work; fewer than two complete readiness bundles cannot reach lifecycle or
> memory."

The committed canonical `run(mode=FULL_PILOT)` path does **not** satisfy this. The
E.36-38 frozen 900-second categorical maturity boundary and the E.26-E.33 strict
two-complete-bundle snapshot-readiness gate were implemented and proved only in
the sibling `SNAPSHOT_READINESS` mode (`run_snapshot_readiness`). The
`FULL_PILOT` mode (`run_operational`) composes bounded newest-create origin
activation **directly** into the 15m→1h→4h lifecycle with no maturity admission
and no readiness-bundle gate.

Per the task rule — "If any preflight requirement fails, make no provider call" —
no live pilot was run. A same-sprint repair is **not** justified because the
correct fix requires a design decision that has not been made (see Phase 4
determination). This attempt therefore stops at a preflight block.

## Baseline and identity

- Exact starting commit: `f7f5d73f260cba58b2953fdf0efbc1b3b4d062d5`
  (`Add snapshot maturity readiness boundary`).
- Branch: `master`.
- Tracked tree before and after this attempt: clean (only pre-existing untracked
  operator artifacts present; none committed except this lane's two documents).
- Campaign/run/cycle identity created: none.
- Durable `FULL_PILOT` authorization created: none.
- Authorization consumed: none.
- Live provider calls (Solana public RPC, GeckoTerminal, GoPlus, Helius): `0`.
- Isolated pilot DB / artifact paths opened or mutated: none.
- `SNAPSHOT_READINESS` executions: `0`. `FULL_PILOT` executions: `0`.

## Phase 1 preflight results

| Preflight requirement | Result |
|---|---|
| Exact HEAD `f7f5d73` and clean tracked tree | PASS |
| Required configuration/secrets without disclosure | Not reached (blocked earlier) |
| New campaign/run/cycle identity | Not created (fail-closed) |
| Exactly one new durable `FULL_PILOT` authorization | Not created (fail-closed) |
| `FULL_PILOT` uses the 900-second maturity boundary before holder/snapshot work | **FAIL** |
| `FULL_PILOT` uses the strict snapshot-readiness gate before lifecycle/memory | **FAIL** |
| Fewer than two mature candidates cannot reach holder or snapshot work | **FAIL** |
| Fewer than two complete readiness bundles cannot reach lifecycle or memory | **FAIL** |
| Approved source/Scheduler/budget/cleanup/single-use owners active | Present in code, not exercised |
| No hidden retry/rerun/waiting/rotation/successor | PASS (structural; not exercised) |
| Exact isolated pilot DB and artifact paths approved | Not reached (blocked earlier) |

The first failing requirement is sufficient to block per the task. No provider
call was made.

## Evidence — the committed FULL_PILOT path

The dispatch entry point routes `FULL_PILOT` to `run_operational`:

```text
run(mode=FULL_PILOT) -> run_operational   (authoritative_live_operational_campaign.py:1129-1130)
```

`run_operational` (`authoritative_live_operational_campaign.py:1137-1241`) does,
in order:

```text
build fixtures from live Pump origin + secondary transports
-> build_ledger
-> _finalized_holder_candidates(origin_proofs, limit=...)   # structural only
-> _evaluate_holder_eligibility(bounded_candidates)          # holder I/O on ALL bounded candidates
-> fixtures.direct_observations = bounded_candidates
-> self._driver.run(...)                                     # -> lifecycle
```

There is **no** call to `evaluate_snapshot_maturity`, **no** `mature_candidates`
filter, and **no** two-complete-bundle readiness gate on this path.

`OriginToLifecycleCampaignDriver.run`
(`origin_lifecycle_campaign.py:207-313`) then:

```text
executor.execute(...)                        # activate exactly two origin slots
-> materialize_origin_activated_batch(...)   # mirror the two slots into a batch
-> run_one_command_15m_factory(...)          # BEGIN the 15m/1h/4h lifecycle
```

Lifecycle begins as soon as two structurally valid origin slots activate. Origin
proofs are the bounded newest-create Pump set, which the E.35 audit measured at
roughly 170-243 seconds old across six live observations — well under the frozen
900-second maturity boundary.

By contrast, the maturity boundary and readiness gate DO exist on the
`SNAPSHOT_READINESS` path (`run_snapshot_readiness`,
`authoritative_live_operational_campaign.py:1437-1830`):

```text
bounded_candidates
-> evaluate_snapshot_maturity(block_time, evaluated_at)     # 900s boundary   (:1625-1635)
-> mature_candidates = DUE only                             (:1636-1640)
-> _evaluate_holder_eligibility(mature if >=2 else ())      # zero holder I/O when <2 mature (:1682-1695)
-> require exactly two complete exact-15m bundles or block  (:1702-1707)
-> status BLOCKED_INSUFFICIENT_MATURE_POOL when <2 mature   (:1803-1806)
```

The HEAD commit `f7f5d73` (`Add snapshot maturity readiness boundary`, +74 lines
to the runner) added exactly this wiring to `run_snapshot_readiness`. It did not
touch `run_operational`.

## Why launching anyway would be wrong (not merely conservative)

1. It violates the explicit task rule to make no provider call when a preflight
   requirement fails.
2. `run_operational` enables `continuous_first_hour=True` and
   `continuous_four_hour=True`, so a launch would begin a multi-hour real-time
   lifecycle on candidates roughly three to four minutes old — exactly the
   young-candidate diet the E.35 audit flagged and the E.36-38 boundary was
   built to stop before holder/snapshot work.
3. It would spend the single scarce live authorization on a run whose full-pilot
   maturity/readiness sequencing the operator has explicitly deferred designing
   (E.34/E.35/E.36 all state: "a separate operator decision is required before
   the full two-token pilot can be considered").

## Phase 4 repair determination — NOT attempted

A same-sprint narrow repair is **not** justified. Reasons:

- **The fix is not narrow.** Making `FULL_PILOT` gate on maturity and on two
  complete readiness bundles before lifecycle requires restructuring the
  origin→activation→lifecycle composition
  (`run_operational` + `OriginToLifecycleCampaignDriver.run`), which is the
  cross-cutting lifecycle-integration boundary — not a micro-repair.
- **A rule is genuinely missing at the design level.** The E.36 design froze the
  categorical maturity boundary for `SNAPSHOT_READINESS` only. It does not define
  full-pilot semantics: whether a full pilot must require pre-lifecycle completed
  exact-15m bundles at all (the lifecycle itself captures the 15m window), how
  the 900-second admission interacts with the lifecycle's own windows, and how a
  `BLOCKED_INSUFFICIENT_MATURE_POOL` outcome should terminate a full pilot versus
  a dry run. Implementing now would invent policy, ownership, and timing.
- Per Phase 4: "micro-design only if a rule is genuinely missing" and "If repair
  requires another live observation to understand the cause, classify it honestly
  and stop without guessing." The missing element here is a design decision, so
  the honest status is `NOT_FIXED_REQUIRES_DESIGN`.

No code, configuration, test, contract, budget, cap, reservation, threshold, or
database was changed by this attempt.

## What was fixed

Nothing. This attempt is investigation-only.

## What was not fixed

The `FULL_PILOT` path lacks the 900-second maturity boundary and the strict
snapshot-readiness bundle gate before lifecycle/memory. It remains
`NOT_FIXED_REQUIRES_DESIGN`. See the blocker register entry `BL-39-01`.

## Tests / checks run

- Static verification only (documentation/audit work; no code change).
- HEAD and clean-tree verification: PASS.
- Direct reading of the committed dispatch, `run_operational`,
  `run_snapshot_readiness`, and `OriginToLifecycleCampaignDriver.run`: confirms
  the gap above.
- No focused suites were run because no code changed. The referenced E.36-38
  fixtures (`tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py`) prove the
  boundary for the readiness path only and are unaffected.

## Money-usefulness contribution

This preflight block protects the single scarce live authorization and operator
time from a full pilot that would begin a real multi-hour lifecycle on immature
candidates with no maturity or readiness protection, producing lifecycle and
memory work that the recent E.36-38 boundary was specifically designed to
prevent. It keeps the honest completed-candle and maturity discipline intact and
converts a latent architectural gap into an explicit, designed-before-run
requirement.

## What remains locked

Live execution, a second pilot attempt, operational memory growth, lifecycle
creation on immature candidates, clean-memory creation, retrieval, decisions,
BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets, private keys,
signing, real funds, paid APIs, retries, endpoint rotation, scoring, ranking,
confidence percentages, weighted logic, embeddings, vectors, 12h/24h, V2-10, and
later lanes.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Effect | Required handling |
|---|---|---|
| FULL_PILOT lacks maturity + readiness gating | A launched pilot would run a real lifecycle on ~3-4 minute-old candidates | Design full-pilot maturity/readiness sequencing before any launch |
| Two proven gates live only in SNAPSHOT_READINESS | The full pilot cannot inherit them without an integration design | Do not copy readiness-mode wiring blindly; full-pilot semantics differ |
| Young-candidate diet is structurally repeatable | Even a corrected gate may honestly block on supply | Accept honest `BLOCKED_INSUFFICIENT_MATURE_POOL`; do not widen/retry/wait |
| Single-use authorization is scarce | An unguarded launch would waste it | Keep the authorization uncreated until design + offline proof pass |

## Exact next action

Remain inside V2-9.7E. Open a **design-only** checkpoint (proposed
`V2-9.7E.40`) that specifies how `FULL_PILOT` sequences: bounded acquisition →
900-second categorical maturity admission (Scheduler-owned) → holder funnel →
strict snapshot-readiness bundle policy → two-token lifecycle, including the
honest full-pilot terminal semantics for fewer than two mature candidates and
fewer than two complete bundles, and the interaction between pre-lifecycle
readiness and the lifecycle's own 15m window. After that design is frozen and
proved offline with fixtures, a subsequent prompt may authorize one live full
pilot. Do not launch a live pilot before then.

## Stop boundary

E.39 stops after one evidence-backed closeout and blocker-register commit. It
issues no live command, creates no authorization, runs no readiness, runs no full
pilot, tags nothing, and advances to no new roadmap lane.
