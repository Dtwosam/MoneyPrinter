# Printer V1 V2-9.8B Comprehensive Candidate-Acquisition Pipeline Repair Closeout

Date: 2026-07-29
Starting HEAD: `4c113473239cb22bbd40e94aa1ee13d90abe0c50`
Lane: `V2-9.8B Comprehensive Live Candidate-Acquisition Pipeline Audit and Repair`

## Verdict

`V2_9_8B_COMPREHENSIVE_CANDIDATE_ACQUISITION_PIPELINE_REPAIR_PASS`

The audit, design, implementation, and high-density N2/N7 offline proofs pass as
one coherent repair. This PASS authorizes only a separately explicit future
N2-first live proof. It does not authorize a retry, N7 live run, campaign,
tracking, lifecycle, memory, retrieval, or any financial capability.

## Confirmed and rejected preliminary findings

All nine were CONFIRMED with exact code/test evidence; findings 4 and 9 were
refined, none rejected (see the audit doc for line-level evidence):

1. CONFIRMED — `candidate_limit` was enforced on the raw combined observation set
   (fail-closed `CANDIDATE_LIMIT`), the exact prior live blocker.
2. CONFIRMED — aggregators pre-truncated to M in provider order and before Pump.
3. CONFIRMED — market confirmation ran at plan positions 3–4, ahead of the Pump
   ranges, contrary to the approved order.
4. CONFIRMED, refined — holder/GoPlus were bound to N; correct bound is
   `min(M, governed Solana headroom)`, since `solana_rpc` is 30 requests/minute.
5. CONFIRMED — candidate-bound operation counts were fixed before the nomination
   universe was known.
6. CONFIRMED — proposed `cursor_advanced` could appear with zero committed heads.
7. CONFIRMED — pre-foundation reporting lacked nomination/overlap/cohort/exclusion
   diagnostics.
8. CONFIRMED — offline fixtures never exercised raw density above M.
9. CONFIRMED, refined — the static interface was incompatible with the phased
   flow; the safer repair adds a `phase` tag and an integration-owner cohort
   authority instead of a full two-method interface rewrite.

## Full root cause

The pipeline never implemented a single source-neutral, provider-order-
independent candidate-cohort boundary. The transport pre-truncated each
aggregator to M in provider order and fixed candidate-specific enrichment at N
before the complete nomination universe existed, and the integration owner
enforced M as a fail-closed ceiling on the raw observation set rather than as a
bound on a normalized cohort. Raw density above M therefore terminated the run
instead of thinning; the reserve was capped at N; provider order could influence
aggregator membership; proposed and committed cursor movement were conflated; and
no fixture exercised the density regime.

## Final architecture

```text
bounded nomination (Dex + Gecko + Pump create + Pump migration, uncapped to M)
→ normalization + source-preserving dedup
→ local categorical exclusions
→ integration-owner deterministic source-neutral cohort bounded by M
→ candidate-specific enrichment for cohort only (M, bounded by the Solana minute)
→ foundation admission → certificates + reserve → exact-N all-or-none manifest
```

* Integration owner is the single cohort authority: it thins the nomination
  universe to `sorted(universe)[:M]`, fails closed on `OUT_OF_COHORT_ENRICHMENT`
  and the defensive `CANDIDATE_COHORT_OVERFLOW`, filters observations to the
  cohort, and persists a `pre_foundation_funnel` plus proposed/committed cursor
  counts even on a pre-foundation stop.
* `AcquisitionSourceOperation.phase` (`NOMINATION`/`ENRICHMENT`, default
  `NOMINATION`) separates the stages; existing frozen owners are unchanged.
* The live transport emits uncapped aggregator nominations (bounded by the real
  DexScreener 30-address limit and the owner's ceilings), selects one unified
  `cohort_mints()` over the full union for all candidate-specific work, and
  generates `enrichment_count = min(M, 30 − fixed_solana_requests)` holder/GoPlus
  operations (4 for N2, 10 for N7 — both > N).
* The foundation remains the sole owner of certificates, reserve, exact-N
  manifest, durable cursor advancement, replay, and the tracking/cooldown
  recheck. `M = 2N` and active capacity two are unchanged.

## Files changed

* `src/printer_v1/operator_cli/candidate_acquisition_integration.py` — cohort
  authority, phase field, funnel/overlap/cursor diagnostics, fail-closed guards;
  removed the raw `CANDIDATE_LIMIT` stop.
* `src/printer_v1/operator_cli/live_candidate_acquisition_transport.py` —
  uncapped nomination emission, unified `cohort_mints()`, dual-key aggregator
  identity, governed M-bounded enrichment, phase tags.
* `tests/test_v2_9_8b_candidate_acquisition_post_foundation_integration.py` —
  updated plan/dispatch expectations; added high-density N2/N7, order-
  independence, Pump/Dex/Gecko overlap, out-of-cohort fail-closed, and cursor
  proposed/committed proofs.
* `docs/…-audit.md`, `docs/…-design.md`, this closeout.

No source code outside the two owners, no schema, no migration, and no database
were changed.

## Tests and proof totals

* Candidate-acquisition suites: 60 passed (35 integration + 25 foundation).
* Affected regression set (12 files importing the changed modules): 190 passed.
* Broad affected suite at closeout: the full V2-9.8 generation
  (`test_v2_9_8a_public_operational_command` + all `test_v2_9_8b_*`) — 244 passed,
  24 subtests passed. The changed code lives only in the two acquisition owners,
  which are imported exclusively by this generation's files (verified by grep),
  so this is the complete affected surface.
* Fresh-DB migration compatibility: latest `049_candidate_acquisition_integration.sql`,
  integrity `ok`, zero FK violations.
* Compilation: all changed modules compile.

### N2 offline proof (real public CLI path, frozen low-level transports)

| Property | Baseline (density = M) | High density (raw > M) |
| --- | ---: | ---: |
| raw unique nominations | 4 | 6 (> 4) |
| candidate cohort | 4 (≤ 4) | 4 (≤ 4) |
| thinned beyond cohort | 0 | 2 |
| Dex/Gecko cross-source overlap | ≥ 1 | ≥ 1 |
| enrichment identities | ≤ 4 (cohort only) | ≤ 4 (cohort only) |
| out-of-cohort enrichment | 0 | 0 |
| certificates / manifest | 2 / one two-item | 2 / one two-item |
| projection | 2 | 2 |
| runtime handoff | 0 | 0 |
| status | COMPLETED | COMPLETED |
| scheduler jobs / transport ops | 20 / 19 | 20 / 19 |

Provider-order permutation over six nominations yields the identical four
lexicographically-smallest cohort identities. Zero-source replay equals the
terminal report.

### N7 offline proof

| Property | Baseline (density = M) | High density (raw > M) |
| --- | ---: | ---: |
| raw unique nominations | 14 | 16 (> 14) |
| candidate cohort | 14 (≤ 14) | 14 (≤ 14) |
| certificates selected / manifest | 7 / one runtime-neutral | 7 / one runtime-neutral |
| projection | 0 | 0 |
| legacy adapter on N7 manifest | rejects (`LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO`) | rejects |
| status | COMPLETED | COMPLETED |
| scheduler jobs / transport ops | 44 / 37 | — |
| Solana governed requests | 30 (≤ 30 minute) | 30 |

### Also proven

Pump/Dex/Gecko overlap under one cohort boundary; malformed/infrastructure/
identity-conflicting exclusions; cohort insufficient for exact N
(`INSUFFICIENT_ELIGIBLE_POOL`); out-of-cohort enrichment fails closed
(`OUT_OF_COHORT_ENRICHMENT`); request/operation/row/byte/page/duration limits;
Scheduler/Governor/transport reconciliation (one job + one governed request per
external operation); cursor commit (2 durable heads on success) and rollback
(0 committed with proposed advances on a pre-foundation stop); exact report/
replay equality with zero source calls; lease cleanup with zero Scheduler
residue; and zero tracking/memory/retrieval/financial deltas.

## Database hash

`data/printer_v1.sqlite3` SHA-256 unchanged, byte-identical to the required
authoritative value:

`516e2b000eb8f2bd10341a5464bb2bcfb19ecf7986f7a011864ce7390b124d1a`

## Commit and worktree

Commit: `Repair candidate acquisition pipeline` (single commit, not tagged).
Worktree clean after commit; only the two owners, the focused test file, and the
three lane docs are included. No live provider, RPC, campaign, or authoritative-DB
write occurred in this lane.

## Remaining risks

1. N7 candidate-specific enrichment is bounded to 10 cohort candidates by the
   30-request Solana governed minute (not the full M=14). Exact-N=7 and a reserve
   up to 10 are supported; the full `candidate_reserve_target = 11` is not
   reachable live for N7 under the current Solana rate. This is a governor bound,
   honestly reported, not a defect.
2. Raw nomination density is bounded by the DexScreener 30-address transport
   limit; densities far above that would be transport-truncated (still ≥ M, so
   the cohort is unaffected for M ≤ 14).
3. Pump-lineage overlap was proven with a frozen owner; the live-mock path proved
   Dex/Gecko overlap and full accounting. A live N2 proof remains the only way to
   establish real-market density behaviour.
4. Offline fixtures remain synthetic mechanics only
   (`UNPROVEN_NO_INDEPENDENT_SAMPLE`); no real-market reliability is claimed.

## Exact next permitted task

A separately explicit, operator-authorized **N2-first bounded live acquisition
proof** using the repaired public CLI path. No retry, N7 live run, campaign,
tracking, lifecycle, snapshot, window, memory, selective-1h, retrieval, or
financial activation is authorized by this closeout.
