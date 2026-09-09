# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.

Latest fully verified code HEAD before this handoff-only update:
`028bac669ca88d900ffc3d8fd54492178c18c505`.

GitHub Actions run `34380325454` is green on that HEAD:

- focused post-holder/reconciliation boundary: **29 passed**;
- shared discovery/admission + Cycle-2 boundary: **375 passed, 2 deselected, 32 subtests passed**;
- affected-module compile: passed;
- diff whitespace check: passed.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor
remains the sole governed source-request owner and Central Scheduler remains the
sole scheduler owner. Retrieval, financial, position, signing, wallet and live
trading capabilities remain locked.

The discovery/admission path now proves all of the following without weakening
liquidity, evidence, freshness, tracking, safety or source-budget contracts:

- exactly two freeze-ready candidates satisfy the operational two-slot cycle;
  surplus depth remains diagnostic only;
- legitimate non-Pump present pools nominated by DexScreener or GeckoTerminal
  can reach the generic Source-Governed protocol verifier without invented
  Pump/PumpSwap lineage;
- generic protocol-confirmed candidates retain exact mint, pool, token program,
  pool program, base mint, quote mint and venue through market revalidation;
- protocol -> market resume works with the canonical governed DexScreener
  transport when no injected factory is supplied;
- resume accounting charges exactly the governed <=30-mint batches actually
  executed and leaves overflow durably pending;
- successful protocol-confirmed market revalidation recreates active
  `MEMORY_OBSERVATION_ELIGIBLE`;
- generic candidates do not write the Pump-registry-bound graduated market-floor
  or legacy eligible-reserve compatibility tables; their durable truth remains
  in generalized exact-market/reserve layers;
- a generic insufficient-pool terminal cannot be emitted while market,
  reconciliation, protocol-confirmation or protocol-resume work is still pending
  with its exact lawful stage capacity, flat source budget and acquisition time;
- Cycle-2 campaign-history disjointness is enforced before seeded
  freeze/selection and rechecked again inside admission;
- holder evaluation only consumes the already-disjoint selected pair and cannot
  reintroduce Cycle-1 identities from the broader reserve;
- pre-admission `PAIR_READY` persistence is exact-two and SAVEPOINT-atomic;
- Cycle-2 admission claims tracking authority, creates both slots and performs
  `PAIR_READY -> CONSUMED` inside one `BEGIN IMMEDIATE` transaction, with
  rollback on second-slot, identity or persistence failure;
- the four-token admission checkpoint still requires exactly two cycles, two
  slots per cycle, four campaign-distinct identities, one consumed Cycle-2
  attempt matching the frozen pair, and no premature Cycle-2 lifecycle work.

## Latest meaningful result

The final failures uncovered in this lane were both software-induced generic
candidate starvation surfaces:

1. generic market revalidation attempted to write
   `printer_graduated_market_floor_state`, whose foreign key intentionally
   requires a PumpSwap-graduated registry parent;
2. after that was separated, generic eligibility attempted to write the legacy
   `printer_eligible_token_reserve`, which has the same Pump-registry parent
   contract.

Both Pump-only projections remain strict. Generic candidates now bypass only
those incompatible compatibility projections while retaining generalized
exact-market, market-ready and MOE evidence.

The expanded shared suite proved Cycle-2 disjointness, atomic consumption,
frozen-pair materialization and the admission checkpoint together with the
generic resume repair.

## Proven blocker

None remains in the scoped discovery/admission + Cycle-2 disjoint/atomic
admission engineering lane.

This is **not** operational authorization and does not establish authoritative
database or live-run readiness. No operational Printer run, provider execution,
Scheduler operation or authoritative database mutation was performed in this
lane.

## Exact next permitted action

Review/integrate the green branch or begin a newly scoped engineering lane from
the repository state. Do not run Printer operationally or mutate the
authoritative database without a new explicit authorization boundary.
