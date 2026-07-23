# Printer V1 V2-9.7E.33 Canonical Operational Readiness Boundary Closure

## Verdict

`V2_9_7E_33_CANONICAL_READINESS_BOUNDARY_PASS`

E.33 closes **all currently known architectural, contract, budgeting,
orchestration, reporting and reproducibility gaps** in the bounded readiness
path. The single committed operational runner now exposes three canonical modes
— `ACTIVATION_ONLY`, `SNAPSHOT_READINESS` and `FULL_PILOT` — and the new
`SNAPSHOT_READINESS` mode composes the *existing* committed owners into the one
runnable path that was previously missing: preflight → live Pump acquisition →
holder eligibility → exactly two complete snapshot bundles or an honest blocker →
report, replay, cleanup, stop. No required step remains outside the repository.
This lane is offline: no live call was made and the single live authorization was
**not consumed**.

## Baseline and scope

- Exact baseline: `5c875e5` (`Prove readiness with configured Helius source`).
- This lane adds no migration and changes no schema, source contract, budget
  constant, Source Governor rule, or lifecycle/memory/retrieval/financial owner.
- It extends exactly one committed module,
  `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`, and
  adds one offline proof,
  `tests/test_v2_9_7e_33_canonical_readiness_boundary.py`.
- No parallel runner, disposable operator harness, or temporary script was
  created. The E.32 blocker — "no committed single entry point produces two
  snapshot bundles" — is resolved inside the canonical runner.

## What was the gap

Through E.32 the committed code had two readiness paths and neither could satisfy
a snapshot-readiness PASS on its own:

1. `run_readiness_only` (now `ACTIVATION_ONLY`) reaches finalized Pump
   acquisition, deterministic selection and the atomic two-or-none activation,
   then stops. It never collects snapshot bundles.
2. `run_operational` (now `FULL_PILOT`) performs live acquisition **and** holder
   eligibility but then hands off to the full lifecycle driver (15m/1h/4h
   windows) — forbidden for a readiness boundary.

The E.25/E.27/E.29 live cycles that produced holder eligibility *and* the
readiness snapshot bundle stitched the committed pieces together only in
uncommitted operator harnesses under `C:\Users\dtwof\PrinterPilot\E2*`, which no
longer exist. E.33 promotes that orchestration into the committed runner.

## The canonical runner and its three modes

`AuthoritativeLiveOperationalCampaignOwner` is the sole internal composition
owner. A single `run(mode=...)` dispatcher selects one of the three canonical
modes (`CANONICAL_OPERATIONAL_MODES`); an unknown mode fails closed with
`UNKNOWN_OPERATIONAL_MODE`.

| Mode | Method | Reaches |
|---|---|---|
| `ACTIVATION_ONLY` | `run_readiness_only` | origin → atomic activation → stop (no bundles) |
| `SNAPSHOT_READINESS` | `run_snapshot_readiness` | preflight → origin → holder eligibility → 2 bundles or blocker → report/replay/cleanup → stop |
| `FULL_PILOT` | `run_operational` | full operational natural lifecycle |

The pre-activation holder-eligibility funnel is now a single shared method,
`_evaluate_holder_eligibility`, used by **both** `FULL_PILOT` and
`SNAPSHOT_READINESS`. This is a behaviour-preserving extraction: the 40 existing
E.11 tests and the E.14 pilot-runner suite pass unchanged, so the operational and
readiness paths are provably the same funnel rather than a divergent copy.

## SNAPSHOT_READINESS boundary

`run_snapshot_readiness` executes, in order:

1. **Preflight** — the committed `build_readiness_source_contract_preflight`
   (zero transport). A non-`READY` preflight (missing Helius secret or any
   contract/budget/pacing/rotation drift) returns `BLOCKED_PREFLIGHT` **before
   any live call and before the authorization can be consumed**.
2. **Single-use refusal** — a committed operation ledger for this `run_id`/
   `cycle_id` is the authorization marker. A second execution against the same
   identity returns `REFUSED_SECOND_EXECUTION` before any transport (no rerun,
   retry, rotation, reconnect, successor or restart).
3. **Live Pump acquisition + bounded governed secondary enrichment** through the
   shared kernel and the durable external-operation log; a source/transport
   fault fails closed (raises) with no retry.
4. **Operation ledger + bounded holder candidates** (candidate cap derived from
   the ledger; ceiling 45, snapshot reservation 6, worst case 43/45).
5. **Holder eligibility** via the shared `_evaluate_holder_eligibility`
   (GoPlus/`solana_rpc`/authenticated-Helius through the existing owners),
   stopping after two eligible candidates.
6. **Exactly two complete snapshot bundles or an honest blocker** — the existing
   `execute_readiness_snapshot_bundle` (exact-pool GeckoTerminal base + at most
   two 15m completion requests) is run for holder-eligible candidates only and
   stops after two complete bundles.
7. **Deterministic DB-only report + zero-source replay** — the committed
   `build_bounded_readiness_report` is built twice; canonical bytes must be
   identical and the replay must make zero source calls.
8. **Disposable cleanup** — any staged first-15m handoff jobs are terminally
   cancelled (none exist because selection/activation is not run).

It **never** calls the lifecycle driver, so no 15m/1h/4h/5m window, memory
window, run step, retrieval, paper decision, position, trade or PnL is ever
created. `READY` is reached only when every fixed gate holds; otherwise the mode
returns a specific honest blocker:

- `BLOCKED_PREFLIGHT` — preflight not READY (zero transport).
- `REFUSED_SECOND_EXECUTION` — single-use marker present (zero transport).
- `BLOCKED_INSUFFICIENT_ELIGIBLE_POOL` — fewer than two holder-eligible candidates.
- `BLOCKED_SNAPSHOT_READINESS` — fewer than two complete snapshot bundles.
- a raised `LiveTransportError`/`LiveOperationalError` on source or owner faults.

## Comparison against the historical E.25/E.27/E.29 harness behaviour

Each step that the uncommitted E.25/E.27/E.29 operator harnesses performed now
maps to a committed owner invoked by `run_snapshot_readiness`:

| Historical harness step | Committed owner (in-repo) |
|---|---|
| source-contract / secret / budget preflight | `build_readiness_source_contract_preflight` |
| finalized Pump-create acquisition | `LivePumpOriginAdapter` + shared acquisition kernel |
| GoPlus / `solana_rpc` / authenticated Helius holder eligibility | `_evaluate_holder_eligibility` → `_collect_preclose_context`, `resolve_holder_concentration_facts`, `holder_reliability_budget_control` |
| exact-pool GeckoTerminal base + OHLCV + trades bundle | `execute_readiness_snapshot_bundle` → `enrich_eligible_geckoterminal_candidate_15m`, `persist_snapshot_from_source_response` |
| operation accounting / candidate cap / snapshot reservation | `holder_reliability_budget_control` ledger (45 / cap 3 / reservation 6 / worst case 43) |
| Source Governor admission + Central Scheduler ownership | `_admit_source_request` / `_require_owners` |
| redacted DB-only report + zero-source replay | `build_bounded_readiness_report` + `canonical_report_bytes` |
| terminal cleanup | `cancel_job` + forbidden-capability / integrity / FK checks |

No required step remains outside the repository. The only element the harnesses
supplied that is *not* re-implemented is a live wall-clock provider connection;
that is exactly what the separately authorized E.34 live proof provides, through
this committed entry point.

## Preserved invariants

Unchanged and re-verified by the preflight and the offline proof:

- operation ceiling `45`; candidate cap `3` (derived); snapshot reservation `6`
  (2 base + 4 completion); worst case `43/45`
  (Pump 13 + zero-transport 9 + 3×5 holder 15 + snapshot 6);
- fixed sources and deterministic pacing; zero retry / rotation / reconnect;
- secret redaction (`secret_material_recorded = false`; the Helius key is checked
  for presence only and never printed or persisted);
- single-use authorization (one committed entry point; second execution refused).

## Offline fixture proofs

`tests/test_v2_9_7e_33_canonical_readiness_boundary.py` (16 tests, all passing;
transport-shaped fakes only, no live call) proves:

- **complete two-bundle success** → `READY`, two persisted
  `SNAPSHOT_READINESS_COMPLETE` snapshots, all gates true, lifecycle never
  started;
- **missing secret** and **contract drift** each `BLOCKED_PREFLIGHT` before any
  transport (a raising Pump transport is not reached);
- **insufficient holder pool** → `BLOCKED_INSUFFICIENT_ELIGIBLE_POOL`;
- **source failure** (`TIMEOUT`/`HTTP_429`/`UNAVAILABLE`) fails closed with no
  retry; unavailable Governor fails closed;
- **DexScreener nullable liquidity with exact-pool GeckoTerminal fallback** — the
  persisted readiness liquidity is served by the GeckoTerminal exact-pool
  `reserve_in_usd` (`source_name = geckoterminal`), independent of DexScreener;
- **liquidity** and **OHLCV/trade-coverage** blockers →
  `BLOCKED_SNAPSHOT_READINESS`;
- **correct accounting and reservation** (ceiling 45, snapshot reservation 2+4=6);
- **second-execution refusal** without transport;
- **deterministic DB-only replay** (byte-identical report, zero replay source
  calls);
- **cleanup, integrity, foreign keys and zero forbidden-capability deltas**;
- **readiness mode cannot invoke lifecycle or memory owners** — with the
  lifecycle driver mocked, `run` reaches `READY` and the driver's `run` is never
  called; memory windows, run steps and paper decisions are all zero.

Full regression: E.11 authoritative campaign (40), E.14 pilot runner, E.24
reporting, E.26 snapshot contract, E.28 preflight — all pass unchanged, so the
shared-funnel extraction is behaviour-preserving.

## Hard closure rule

E.33 closes all currently known architectural, contract, budgeting,
orchestration, reporting and reproducibility gaps for the bounded readiness path.
After the later, separately authorized E.34 live proof, the following are
**operational blockers** and must **not** automatically create another repair
lane:

- provider unavailability;
- temporary rate limits;
- missing fresh-pair liquidity;
- incomplete indexing;
- insufficient eligible candidates;
- valid fail-closed evidence outcomes.

A later repair lane is permitted **only** if E.34 proves a concrete
committed-code or contract defect.

## Money-usefulness contribution

The readiness boundary is now a single committed, reproducible, fail-closed path
that produces exactly two complete exact-pair snapshot bundles or an honest
blocker, with deterministic accounting, redacted evidence and zero-source replay.
It reduces the remaining work to one separately authorized bounded live proof
(E.34) through this exact entry point, rather than reconstructing an uncommitted
harness whose correctness was never established.

## What remains locked

All Printer V1 Solana-memecoin-only, paper-only, free/public-source, governance,
two-or-none, clean-memory, support-only-5m, retrieval and financial locks remain
unchanged. No lifecycle, memory, corpus, retrieval, decision, position, trade,
PnL, wallet or paid-source capability was touched. V2-9.7F, V2-9.8 and the
operational memory-growth command remain locked and were not started.

## Readiness

**READY** for exactly **one** separately authorized E.34 bounded live proof
through the committed `run(mode=SNAPSHOT_READINESS)` entry point. No tag is
applied in this lane.
