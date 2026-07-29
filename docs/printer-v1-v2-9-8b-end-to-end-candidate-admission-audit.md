# Printer V1 V2-9.8B End-to-End Candidate Admission Audit

Date: 2026-07-29

Lane: `V2-9.8B End-to-End Candidate Admission Audit, Repair, and Final Live N2 Proof`

Audit verdict: `COMMITTED_CODE_DEFECT`

This is the mandatory source-grounded blocker classification required by
`docs/printer-v1-python-builder-guide.md`. The post-cursor-repair live N2
failure was not classified from the terminal label alone. The complete
admission path, persisted evidence, pinned provider contracts, prior audit and
repair records, and live-shaped fixture behavior were traced before repair.

## Authority and baseline

The audit used the active source stack in `AGENTS.md`, including the Clean
Master Spec, Post-RC Build Order, Memory Factory Guide, post-Lane-10 architecture
and build order, V2 memory-growth build order, active assistant anchor, and
Python Builder Guide. It also read the current records for the candidate-
acquisition foundation, post-foundation integration, comprehensive pipeline
repair, mint-identity admission repair, durable cursor continuity repair, and
the post-cursor-repair blocked live N2 proof.

The audited repository baseline was clean at
`599179f84e210c050884ebd88398c361a945b9e6`. The authoritative database started
at SHA-256
`898d9b0fa9e99417a3429c21f5dd02817d80d3b78402c4e35d2c261e9e62f1c9`.

Pinned contracts inspected were the repository-owned DexScreener,
GeckoTerminal, Pump creation and bonding-curve, Pump migration, PumpSwap Pool,
Solana RPC account/transaction, SPL Token, Token-2022, holder evidence, and
Source Governor contracts. No unpinned or paid contract was substituted.

## Terminal evidence reconstructed

The prior live N2 correctly bootstrapped both cursor namespaces in `FORWARD`
mode and preserved historical `BACKWARD` heads. Four candidates reached the
foundation. All four then failed with `IDENTITY_MERGE_FAILURE` /
`IDENTITY_NOT_MERGED`; their pool-account responses had Pump program owners and
no exact quote identity.

That result was reproducible from committed control flow:

1. aggregator normalizers and integration observations lost quote or venue
   identity;
2. the pool batch targeted every aggregator `pairAddress` as though it were a
   PumpSwap Pool;
3. Pump bonding curves and generic pools were fed to the PumpSwap decoder;
4. failed decodes still left partial pool/base identity, while the earliest
   pool-role or quote cause was collapsed into identity failure; and
5. the canonical offline transport represented every pool as a synthetic
   PumpSwap account, so this live-shaped path was absent from the proof suite.

The live blocker therefore had a committed deterministic code path. It was not
an honest four-candidate market coincidence and was not eligible to be closed as
`EXPECTED_NEGATIVE_CONDITION`.

## Gate-by-gate audit

| Gate | Honest outcome | Missing/source loss | Target/decoder/role defect | Taxonomy result before repair |
|---|---|---|---|---|
| nomination | provider may nominate no usable Solana candidate | provider outage or incomplete page remains categorical | Dex requested-token correlation was lost when the requested mint appeared on the quote side | quote-side reversal could disappear or nominate the infrastructure base |
| exact mint/pair | pair may be unrelated or incomplete | exact pair, base, or quote may be absent | Dex and Gecko quote/dex facts were discarded downstream | partial identity was reported generically |
| pool role/program | account may be missing or unsupported | RPC account/owner evidence may be unavailable | all pair addresses were decoded as PumpSwap; target/slot association was not retained | owner/layout causes collapsed |
| base/quote identity | unsupported quote is a valid rejection | quote may be absent | integration synthesized `base_mint=mint`; exact orientation was not retained | missing/reversed quote often became identity failure |
| mint/program | unsupported owner/layout is a valid rejection | missing account remains fail-closed | the mint repair correctly binds exact targets and supports SPL plus Token-2022 | precise mint taxonomy already worked |
| holder | genuine concentration is a valid rejection | largest-account or supply evidence may be missing | no holder normalization/merge defect was confirmed | honest `holder_status=FAIL` remains valid |
| safety | provider may return unsafe or no usable safety fact | optional GoPlus evidence may be absent | no new systemic safety defect was confirmed | existing categorical behavior retained |
| market freshness/age | stale or ageless market is a valid rejection | timestamp or current market may be absent | no extraction defect was confirmed beyond pair-identity loss | existing stale/age families retained |
| liquidity | low liquidity is a valid rejection | liquidity may be absent | extraction and floor application were correct | `LIQUIDITY_STATUS_FAILED` retained |
| route/tradeability | zero activity/no route is a valid rejection | route/activity may be absent | extraction and categorical application were correct | `TRADEABILITY_STATUS_FAILED` retained |
| lineage | unsupported Pump claim is a valid rejection | exact origin/migration proof may be absent | valid non-complete Pump bonding curves had no admissible branch; generic pools had no exact-present-pool branch | Pump origin was always forced to graduation failure |
| tracking/cooldown | active tracking or cooldown is a valid rejection | authoritative state remains required | atomic recheck itself was correct | earliest state conflict retained |
| certificate/manifest | fewer than N eligible candidates is honest | any mandatory evidence gap blocks a certificate | incomplete identity was evaluated before precise pool evidence | failure family could mask the first cause |
| sequential execution | no market issue applies | no provider issue applies | observation IDs omitted execution identity and collided on a later established-cursor run | execution failed on a global primary-key collision |

## Confirmed systemic defects

1. DexScreener exact quote mint and DEX identity were not preserved by the
   admission normalizer.
2. GeckoTerminal exact quote-token and DEX relationships were not preserved.
3. Integration observations synthesized candidate/base equivalence and omitted
   exact quote identity.
4. Dex requested-token correlation was not retained, so a target returned on
   the quote side could be dropped or treated as the base asset instead of
   receiving a precise orientation rejection.
5. The pool batch sent Pump bonding curves, PumpSwap Pools, and generic pools
   through one PumpSwap-only interpretation.
6. Pool batch evidence did not retain exact target, response slot/address,
   account role, or first decoder failure.
7. A generic non-Pump exact-present-pool branch was absent even when an
   aggregator supplied exact orientation and RPC supplied exact account owner
   and executable program evidence.
8. `PUMP_ORIGIN_CONFIRMED` was categorically rejected even for an exact,
   non-complete, pinned Pump bonding curve.
9. Identity completeness included pool/quote validity and allowed
   non-pool observations to participate in pool base/quote merge, hiding
   missing/reversed pool evidence behind `IDENTITY_*` failures.
10. Failure-family selection replaced precise admission causes with generic
    identity/admission labels.
11. Observation IDs were content-only despite a global primary key, causing
    deterministic collisions across distinct established-cursor executions.
12. Existing canonical offline fixtures synthesized a PumpSwap-shaped account
    for every pair and therefore hid all three real pool-role paths.

All twelve defects are within the requested admission chain and form one
cohesive repair. None requires a schema or migration.

## Rejected findings and honest outcomes

The audit rejected the proposition that every prior candidate needed code
repair. Real candidates must still be rejected for an unsupported mint or pool
program, absent/malformed provider evidence, high holder concentration, stale
market evidence, low liquidity, zero tradeability, unsupported lineage,
tracking/cooldown conflict, or any incomplete mandatory gate.

Holder evidence mapping was specifically rechecked: the RPC owner passes the
exact candidate mint to both `getTokenLargestAccounts` and `getTokenSupply`, and
the adopted normalizer compares raw amounts against exact supply. No evidence-
mapping defect was found. Likewise, liquidity and activity facts were already
extracted categorically and remain honest rejection gates.

`UNKNOWN_ORIGIN` is not itself a rejection under the approved non-Pump branch.
It remains categorical and does not assert Pump lineage. A candidate still
needs an exact current pool, owner/program relationship, orientation, mint,
holder, safety, market, age, liquidity, tradeability, and state evidence.

## Capacity and capability finding

Before repair, current source operations could not reliably produce a complete
certificate for every supported real candidate role because only a synthetic
PumpSwap-shaped pool could satisfy the pool step. The defect was systemic.

The repair must not alter `M=2N`, active runtime capacity two, source budgets,
cursor namespaces/directions, Scheduler ownership, Source Governor ownership,
cohort selection, safety floors, or any financial capability. No campaign,
tracking handoff, lifecycle, snapshot, window, memory, retrieval, decision,
position, trade, audit, or PnL work is authorized.

## Audit conclusion

Classification: `COMMITTED_CODE_DEFECT`.

Repair is justified only for the confirmed systemic defects above. Honest
market and evidence rejections remain fail-closed. A schema or migration is not
required; discovery of one would stop this lane `BLOCKED`.
