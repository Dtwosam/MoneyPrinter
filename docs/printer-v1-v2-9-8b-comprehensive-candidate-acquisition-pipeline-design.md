# Printer V1 V2-9.8B Comprehensive Candidate-Acquisition Pipeline Repair Design

Date: 2026-07-29
Depends on: `printer-v1-v2-9-8b-comprehensive-candidate-acquisition-pipeline-audit.md`
Gate: 2 of 3 — complete repair design

## Canonical flow (target)

```text
bounded nomination from every approved nomination-bearing source
  (DexScreener, GeckoTerminal, direct Pump create, direct Pump migration)
→ exact normalization and source-preserving deduplication
→ local categorical exclusions
→ deterministic source-neutral candidate cohort bounded by M
→ candidate-specific market/on-chain/holder/safety enrichment (cohort only)
→ foundation admission
→ certificates and reserve
→ exact-N all-or-none manifest
```

`M = candidate_limit = candidate_acquisition_capacity = 2N` (4 for N2, 14 for
N7). `M` is the upper bound on candidates that enter the expensive admission
funnel and receive candidate-specific enrichment. `N` (2 or 7) is the exact
manifest capacity. Active Memory Factory capacity stays exactly two.

## Chosen architecture (safer than a full interface rewrite)

The audit proved a full two-method transport protocol is unnecessarily risky.
The safer roadmap-compliant design makes the **integration owner the single
authoritative, source-neutral, provider-order-independent cohort boundary** and
keeps the transport as a flat, phase-tagged operation plan:

1. **Phase tagging.** `AcquisitionSourceOperation` gains
   `phase ∈ {NOMINATION, ENRICHMENT}` (default `NOMINATION`, preserving every
   existing frozen owner). NOMINATION operations contribute identities to the
   nomination universe; ENRICHMENT operations are candidate-specific and may
   only address cohort identities.

2. **Transport nomination emission is uncapped.** DexScreener/GeckoTerminal
   market materialization now emits **one best pair per mint for every nominated
   identity** (bounded only by the DexScreener 30-address transport limit and
   the owner's row/byte ceilings), never pre-truncated to M. The DexScreener
   profile→batch step is bounded by the real 30-address endpoint limit, not by
   M. Direct Pump create/migration transactions emit their identities as before.
   No aggregator freezes a partial cohort ahead of the Pump nominations.

3. **One unified cohort function in the transport.** `cohort_mints()` returns
   the M lexicographically-smallest identities of the complete nomination union
   `aggregator_pairs ∪ origins ∪ migrations`. It is a pure function of the
   nominated identity set, so provider execution order cannot change membership.
   `mint_batch`, `pool_batch`, holder, and GoPlus all address exactly this
   cohort. This is not a source quota, preference, score, rank, confidence, or
   weighting — it is a deterministic identity bound identical to the foundation's
   existing `mints[:candidate_acquisition_capacity]`.

4. **Candidate-specific enrichment covers the cohort, governed.** Holder and
   GoPlus operations are generated for `enrichment_count = min(M, 30 −
   fixed_solana_requests)` cohort candidates, where the Source Governor caps
   `solana_rpc` at 30 governed requests/minute. For N2 this is the full M=4; for
   N7 it is 10 (> N=7), the exact governed headroom. If the headroom ever fell
   below N the transport fails closed
   (`ACQUISITION_ENRICHMENT_HEADROOM_BELOW_SELECTION`) rather than shipping a
   plan that cannot form a distinct N-item manifest.

5. **Integration-owner cohort authority.** After the operation loop the owner:
   * builds the nomination universe from NOMINATION-phase identities and records
     per-source overlap;
   * selects `cohort = sorted(nomination_universe)[:M]` (thinning, never a
     terminal stop; raw density above M is normal);
   * fails closed on `OUT_OF_COHORT_ENRICHMENT` if any ENRICHMENT-phase identity
     is outside the cohort (candidate-bound work reached beyond the cohort);
   * filters observations to cohort identities and fails closed on
     `CANDIDATE_COHORT_OVERFLOW` if more than M unique identities survive
     (defensive; unreachable under a correct bound);
   * passes only cohort observations to the foundation.

The old fail-closed `CANDIDATE_LIMIT` on raw density is removed.

## Reporting and cursor semantics

The integration report gains, and persists (even on a pre-foundation stop):

* `pre_foundation_funnel`: raw observation rows, raw unique nominations,
  nomination rows by source, per-identity nominating-source counts,
  cross-source overlap count, cohort bound M, cohort size, thinned-beyond-cohort,
  enrichment identities, and out-of-cohort-enrichment count;
* `cursor_advances_proposed` (from operation cursor evidence) and
  `cursor_advances_committed` (durable heads written for this execution, zero
  unless the foundation transaction ran) — making proposed and committed cursor
  movement distinct facts.

Foundation ownership is unchanged: it remains the sole owner of certificates,
reserve, exact-N manifest, durable cursor-head advancement, replay, and the
atomic tracking/cooldown recheck. N2 alone produces the read-only two-item
projection; N7 records projection zero and the legacy adapter rejects it. Runtime
handoff stays zero.

## Invariants preserved

* raw observations bounded by request/operation/row/byte/page/duration ceilings;
* raw source density above M is not terminal;
* M bounds funnel candidates; only cohort candidates get candidate-specific work;
* Pump, DexScreener, and GeckoTerminal nominate under one authority boundary;
* no source quota/preference/score/rank/confidence/weighting;
* provider execution order cannot change cohort membership;
* duplicates and overlap consume one cohort identity;
* proposed vs committed cursor movement distinct;
* reports persist exact pre-foundation funnel and overlap facts;
* foundation remains the sole certificate/reserve/manifest/cursor owner;
* N2-only two-item projection; N7 runtime-neutral; active capacity two;
* Solana-only, paper-only; no wallet/signing/funds/paid dependency; no
  Scheduler/Governor bypass; no scoring/embeddings; no schema or migration.

`M = 2N` is unchanged: the policy itself is sound; only its placement
(integration-owner cohort bound, not raw-observation ceiling) and the
enrichment bound (M under the governor, not N) were defective.

## Test/proof plan

* Existing frozen owners default to NOMINATION and keep passing (cohort == M when
  density == M; no thinning; no out-of-cohort work).
* New high-density N2/N7 proofs through the real public CLI path with frozen
  low-level transports: raw density above M thins to an M cohort, exact-N
  manifest, projection two/zero, replay equality, enrichment only for cohort.
* Cohort-membership provider-order independence via permuted frozen operations.
* Pump/Dex/Gecko overlap participation; out-of-cohort enrichment fail-closed;
  cursor proposed-vs-committed on success and on a pre-foundation stop.
* Existing edge cases (budget, gap, unsupported contract, identity conflict,
  stale, N−1 insufficiency, cancellation, renewal failure, idempotent replay,
  ceilings) remain green.

## Gate result

Gate 2 passes. An implementer has the exact cohort boundary, phase contract,
governed enrichment bound, diagnostics, cursor semantics, and proof cases with no
schema change and no new external contract.
