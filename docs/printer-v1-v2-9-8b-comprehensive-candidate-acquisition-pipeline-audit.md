# Printer V1 V2-9.8B Comprehensive Live Candidate-Acquisition Pipeline Audit

Date: 2026-07-29
Starting HEAD: `4c113473239cb22bbd40e94aa1ee13d90abe0c50`
Lane: `V2-9.8B Comprehensive Live Candidate-Acquisition Pipeline Audit and Repair`
Gate: 1 of 3 — independent audit

This audit was performed by reading the actual current owners at the required
HEAD before any code change. It confirms, refines, or rejects each preliminary
finding with exact code/test evidence, then states the complete root cause. No
live provider, RPC, N2, N7, campaign, tracking, lifecycle, snapshot, window, or
memory work was run. The authoritative database was not opened for write.

## Owners inspected

| Contract | Owner (at HEAD) |
| --- | --- |
| public N2/N7 dispatch | `operational_memory_factory_command.main` → `run_candidate_acquisition_only` |
| finite integration | `candidate_acquisition_integration.run_candidate_acquisition_integration` |
| live transport plan | `live_candidate_acquisition_transport.LiveCandidateAcquisitionTransportOwner.operations` |
| foundation | `discovery/candidate_acquisition.run_candidate_acquisition` |
| operation planning/execution | integration owner loop; transport `operations()` |
| nomination normalization | foundation `_normalize_observations`; integration `_provider_observations` |
| Pump create/migration decode | transport `indexed_transaction` + `decode_supported_pump_*` |
| candidate-limit enforcement | integration owner (unique-mint check) |
| candidate-specific enrichment | transport `holder_reference`, `goplus_reference`, `mint_batch`, `pool_batch` |
| foundation invocation | integration owner → `run_candidate_acquisition` |
| cursor persistence | foundation `_advance_current_cursor_heads`, `printer_candidate_acquisition_cursors` |
| reports/replay | integration `_persist_integration_report`; foundation report |
| focused tests | `test_v2_9_8b_candidate_acquisition_post_foundation_integration.py`, `..._foundation.py` |

Contracts consulted: DexScreener (`token_mint`/`pair_address` normalization),
GeckoTerminal (`baseToken.address`/`pairAddress` normalization), Pump/PumpSwap
IDL decoders, Solana RPC one-shot transport, and the Source Governor registry
(`solana_rpc` = 30 governed requests/minute).

## Finding dispositions

### 1. `candidate_limit` applied to the raw observation set — CONFIRMED (dominant)

`run_candidate_acquisition_integration` (pre-repair) computed
`unique_mints = {row.mint for row in observations}` over the **entire combined
raw observation set** and raised the terminal `CANDIDATE_LIMIT` when
`len(unique_mints) > policy["candidate_limit"]`. This is a fail-closed stop on
raw source density, not a bound on a normalized candidate-evaluation cohort. It
is the exact mechanism that blocked the prior live N2 proof
(`...proof-post-owner-repair-closeout.md`: 6 raw unique mints > M=4 →
`CANDIDATE_LIMIT`, foundation never entered). The required policy is that raw
density above M is thinned to an M-bounded cohort, never a terminal failure.

### 2. Aggregator nominations bounded before Pump nominations — CONFIRMED

Two independent pre-truncations froze a partial cohort before the full
nomination universe existed:

* `LiveCandidateAcquisitionTransportOwner.dex` truncated the DexScreener
  profiles to the first `cap` (= M) mints (`if len(mints) >= cap: break`)
  **in profile order** before the market batch, so which aggregator mints
  entered was provider-order-dependent.
* `refresh_selected_pairs` selected `sorted(candidates)[:cap]` across DexScreener
  and GeckoTerminal during the market-batch operations, which execute **before**
  the direct Pump create/migration transactions run. The aggregator cohort was
  therefore frozen while `state["origins"]`/`state["migrations"]` were still
  empty. There was no single all-source nomination gather.

### 3. Implemented operation order differs from the approved order — CONFIRMED

The approved integration order (post-foundation design, "Frozen policy and
source plan") is: DexScreener nomination → GeckoTerminal nomination → Pump
create range → Pump migration range → mint/pool batches → present-market
confirmation → holder → GoPlus. The implemented `operations()` placed the two
`candidate_market_batch` operations at positions 3–4, **before** the Pump
create/migration ranges (positions 5–8). Because market materialization also
ran `refresh_selected_pairs`, the misordering is the concrete mechanism of
finding 2: aggregator cohort selection executed ahead of Pump nomination.

### 4. Candidate-specific work bounded to N, not M — CONFIRMED

`holder_reference` and `goplus_reference` operations were generated
`for candidate_index in range(int(policy["selection_capacity"]))` — i.e. **N**
(2 or 7) — even though the policy `source_budgets` size holder/safety at **M**
(4 or 14). Cohort candidates beyond the first N therefore received no holder
observation, so `HOLDER_ACCEPTABLE` failed (`HOLDER_STATUS_MISSING`) for them
and the admissible/reserve pool could never exceed N, defeating
`candidate_reserve_target = n + ((n+1)//2) > n`.

Refinement: the naive fix "holder for all M" is itself infeasible for N7 under
the Source Governor. `solana_rpc` is limited to 30 governed requests/minute
(`SOURCE_REGISTRY["solana_rpc"].default_rate_limit_per_minute`). The fixed N7
Solana cost is create-pages(2) + create-tx(7) + migration-pages(2) +
migration-tx(7) + mint(1) + pool(1) = 20, leaving only 10 holder slots. So the
correct bound is `min(M, 30 − fixed_solana_requests)`: full M for N2 (4), and a
governed-headroom-bounded 10 for N7 — still strictly greater than N=7.

### 5. Candidate-bound work planned before the nomination universe is known — CONFIRMED

The count of candidate-specific operations was fixed at plan-construction time
(holder/GoPlus = N; mint/pool cohort caps applied per aggregate group), before
the complete cross-source nomination universe (aggregator + Pump) was resolved.
The cohort was never selected as one deterministic step over the full universe;
enrichment adapters resolved a per-adapter view of `state` that could disagree
with the eventual foundation cohort.

### 6. `cursor_advanced=true` without committed advancement — CONFIRMED

`signature_page` mutates the shared `create_cursor`/`migration_cursor` dicts,
setting `cursor_advanced = (continuity == "CONTIGUOUS")`, and the integration
persisted that proposed value into work evidence. A durable cursor head only
advances inside the foundation transaction (`_advance_current_cursor_heads`).
When a run stops before the foundation (e.g. the old `CANDIDATE_LIMIT` stop, or
a required-source failure), operation evidence could carry
`cursor_advanced=true` while zero durable heads committed. Proposed movement and
committed movement were not represented as distinct facts in the report.

### 7. Pre-foundation reporting lacks funnel/overlap/cohort/exclusion facts — CONFIRMED

The integration report (`report` dict) carried scheduler/governed/transport/
byte/row totals and, when reached, the nested foundation report — but **no**
pre-foundation nomination count, cross-source overlap, normalization/cohort
size, thinning, or exclusion diagnostics. On any pre-foundation stop the report
was silent about the funnel that produced the stop.

### 8. Offline fixtures never exercised raw density above M — CONFIRMED

`_candidate_rows(count)` and `_CanonicalMockNetworkTransport(count)` were always
invoked with `count == candidate_limit` (4 for N2, 14 for N7), and the mock's
`getSignaturesForAddress` returned `[]` (no Pump identities). Raw unique density
was therefore always exactly M and never above it — precisely the interaction
the live proof surfaced and the offline suite did not.

### 9. Static `operations()` interface incompatible with the phased flow — CONFIRMED, REFINED

The static flat `operations()` list cannot express "generate exactly the
cohort's candidate-specific operations after the full nomination universe is
known," and the transport worked around it with shared mutable `state` and a
per-adapter N-bound. This is a genuine defect. Refinement: a full two-method
protocol rewrite is **not** the safest roadmap-compliant repair. Making the
integration owner the single authoritative source-neutral cohort boundary (over
the complete observation union), tagging each operation with a `phase`
(`NOMINATION` / `ENRICHMENT`), and requiring enrichment to be a proven subset of
the cohort achieves the phased flow's invariants structurally with far less
blast radius than replacing the interface. See the design doc.

## Rejections

None. All nine preliminary findings are confirmed; findings 4 and 9 are refined
rather than rejected.

## Complete root cause

The pipeline never implemented a **single, source-neutral, provider-order-
independent candidate-cohort boundary**. Instead:

1. the transport pre-truncated each aggregator group to M in provider order and
   fixed candidate-specific enrichment at N, before the full nomination universe
   (aggregators + Pump create + Pump migration) existed (findings 2–5, 9); and
2. the integration owner enforced M as a fail-closed ceiling on the **raw**
   combined observation set rather than as a bound on a normalized cohort
   (finding 1).

Consequently raw density above M was a terminal failure instead of thinning to
an M-bounded cohort (the live blocker); the admissible reserve was capped at N;
provider order could influence which aggregator identities entered; proposed and
committed cursor movement were conflated; pre-foundation diagnostics were
missing; and no fixture exercised the density regime that exposes all of this.

The foundation already thins candidates to `candidate_acquisition_capacity = 2N`
(which equals `candidate_limit = M`) and already emits overlap/exclusion
diagnostics — so the repair is to give the **integration owner** an explicit
cohort-selection step consistent with that bound, restore candidate-specific
enrichment to the M-bounded cohort under the Source Governor, tag operation
phase, and add the missing diagnostics and cursor proposed/committed
distinction. No schema or migration change is required: the additional
diagnostics live in the existing report JSON.

## Verdict

Audit complete. Proceed to design and repair. No authoritative-DB write, no live
provider call, no campaign/tracking/lifecycle/memory activity occurred.
