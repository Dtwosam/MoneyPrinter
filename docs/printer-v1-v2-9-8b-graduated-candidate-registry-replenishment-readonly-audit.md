# Printer V1 V2-9.8B Graduated-Candidate Registry Replenishment Read-Only Audit

Date: 2026-08-16

Lane: `V2-9.8B Graduated-Candidate Registry Replenishment Read-Only Audit`

Type: audit/readiness only. No source fetching, RPC, Scheduler runtime, authoritative DB mutation, authorization, memory generation, retrieval, paper decision, position, trade, audit, PnL, wallet, signing, or real funds.

## 1. Verdict

`V2_9_8B_GRADUATED_CANDIDATE_REGISTRY_REPLENISHMENT_READONLY_AUDIT_PASS_REPLENISHMENT_REACHABLE_BUT_STRUCTURALLY_INSUFFICIENT_FOR_PERSISTENT_PER_CYCLE_SUPPLY`

The current production code can add new `PUMPSWAP_GRADUATED_CONFIRMED` rows, but only through the bounded direct Pump migration stage that runs once at campaign start. That stage intentionally owns one cursor-free finalized Pump-program tail page, one collection round, exact Pump/PumpSwap verification, and fail-closed persistence after transport-accounting reconciliation.

The active persistent supply loop then evaluates the exported graduated registry. When capacity remains short and the temporal acquisition owner is used, the later refresh path does not reopen direct Pump migration or the DexScreener fresh-profile locator. Its production refresh composition reopens only one GeckoTerminal fresh-pool nomination plus the existing PumpSwap protocol-confirmation owner.

Therefore the registry is reachable, but it is not a complete or persistent per-cycle replenishment mechanism. A weak initial live-tail page can leave the campaign dependent on an aging registry even while lawful fresh candidate channels still exist.

Primary Python Builder Guide classification:

`MISSING_INTEGRATION`

No evidence justifies weakening exact-pool identity, PumpSwap orientation, protocol confirmation, tracking rules, or the `$3,000` liquidity floor.

## 2. Baseline and authority

Production-code anchor inspected: `35251a7aee54245e3a8e2861ce830910448555bd`.

The immediately preceding exact-pool final reconciliation was supplied separately and records local HEAD `38d119fbbfcb6a31c075cb4861421b233c90eaf8`; that local commit is not available from GitHub. It changed no production code. This audit therefore inspects the exact production-code anchor used by that reconciliation and makes no claim that the local audit-only commit is remotely reachable.

Controlling sources remain the active Printer V1 source stack, including `AGENTS.md`, the Clean Master Spec, Post-RC build order, Memory Factory Guide, current-state audit, active V2 memory-growth build order, the Python Builder Guide, and adopted candidate-acquisition/provider contracts.

The adopted candidate-acquisition clarification remains controlling: discovery is multi-source; DexScreener and GeckoTerminal may nominate directly; Pump/PumpSwap is mandatory for exact Pump-specific claims but is not the exclusive candidate universe; no source quota, score, rank, confidence, or weighting is allowed.

## 3. Static findings

### 3.1 `record_graduated_candidate` is reachable

`run_direct_migration_discovery()` performs:

1. one Source-Governed finalized `getSignaturesForAddress` Pump-program page;
2. bounded finalized transaction inspection;
3. exact pinned Pump migrate verification;
4. exact PumpSwap pool confirmation;
5. transport/accounting reconciliation;
6. `record_graduated_candidate(...)` only after reconciliation passes.

So the registry is not dead code and replenishment is not categorically disabled.

### 3.2 Direct Pump replenishment is deliberately one-shot

The restored direct path rejects any `collection_rounds != 1`, forbids settle sleep and automatic reverify, and owns no cursor/backfill/recovery semantics. In `run_persistent_eligible_token_supply()`, it is invoked once before the persistent evaluation loop.

Result: the Pump-specific registry can gain candidates only from the single campaign-start tail page unless a separate future owner explicitly reopens that stage.

### 3.3 Fresh non-registry candidates already have a lawful path

At campaign start, permanent availability can also:

- record DexScreener fresh-pool/profile nominations;
- run GeckoTerminal fresh-pool nomination;
- run bounded liquidity backup;
- run existing protocol confirmation;
- promote retained-liquidity protocol-confirmed candidates directly into the campaign eligible set.

This proves the architecture already recognizes that `PUMPSWAP_GRADUATED_CONFIRMED` is not the only lawful admission lineage.

### 3.4 Temporal shortage refresh is materially narrower than campaign-start intake

The temporal refresh composition performs only:

1. `run_geckoterminal_fresh_nomination()`;
2. `process_protocol_confirmation_queue()`.

It does not rerun:

- direct Pump finalized live-tail discovery;
- DexScreener fresh-profile discovery/nomination.

The 900-second acquisition horizon and canonical discovery-refresh cadence also admit only one normal delayed refresh under the current design.

### 3.5 The persistent loop can therefore stop before the full fresh universe is exhausted

The supply service correctly continues evaluation while known inventory remains and preserves cumulative source budgets. But once the known graduated inventory is exhausted, its only temporal reopening is the narrower GeckoTerminal/protocol path above.

Consequently, `ALL_REACHABLE_CANDIDATES_EVALUATED` or `NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE` describes the universe reachable through the current composition, not necessarily every still-lawful fresh source channel.

That is an architecture false-shortage risk when capacity is below the permanent required depth of four.

## 4. Cycle-2 implication

The prior Cycle-2 evidence showed that the old graduated cohort yielded too few current eligible tokens, with the dominant loss coming from historical pools absent from current DexScreener responses. Nothing in this audit contradicts those rejections.

The new conclusion is narrower and more useful: after those candidates correctly fail, Printer does not yet have a complete multi-source mechanism to keep replacing them within the same bounded selection cycle.

The correct response is replenishment/continuation repair, not evidence-gate relaxation.

## 5. Money-usefulness contribution

A persistent fresh-acquisition loop improves the chance that Printer learns from currently tradeable Solana memecoins instead of repeatedly spending scarce source budget rechecking a decaying historical cohort.

It preserves realistic failure handling: bad candidates are discarded or retained as negative evidence, while the system keeps searching for distinct candidates under the same evidence standards.

## 6. What the next design must improve

The next design may replace the incomplete continuation boundary with one bounded per-cycle acquisition owner that:

- preserves the current eligible reserve and mandatory revalidation;
- reopens the already-approved fresh sources while eligible depth remains below the required capacity;
- includes direct Pump/PumpSwap, DexScreener fresh nomination, and GeckoTerminal fresh nomination without source scoring/ranking/weighting;
- keeps every provider request Source-Governed and every delayed opportunity Central-Scheduler-owned;
- deduplicates exact mint/pool identities across rounds;
- persists candidate-local rejects and durable nomination/eligibility state rather than rediscovering the same bad identities as if new;
- preserves cumulative source-operation and duration ceilings across the entire cycle;
- stops only on capacity met, hard budget/duration exhaustion, supervision/cancellation failure, attributable provider terminal failure, or a certificate proving no further lawful acquisition opportunity remains.

## 7. What remains locked

This audit does not unlock another four-token proof, source fetching, runtime campaign execution, memory generation, `WINDOW_1H`/`4H`/`12H`/`24H`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, PnL, wallets, signing, live execution, paid APIs, scoring/ranking/confidence/weighted logic, or embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## 8. Minimum proof before completion of the future implementation

Use risk-based verification only:

1. deterministic RED/GREEN tests proving fresh acquisition reopens more than one lawful round while capacity is short;
2. tests proving Pump, DexScreener, and GeckoTerminal source opportunities remain categorical and Source-Governed;
3. tests proving candidate-local failure does not terminate peer acquisition;
4. tests proving cumulative budget and duration never reset between rounds;
5. tests proving exact mint/pool deduplication and persisted rejection suppression;
6. tests proving capacity met stops immediately;
7. tests proving terminal exhaustion requires no lawful fresh opportunity remaining;
8. one bounded disposable proof with fixture transports only before any live authorization review.

No broad regression suite is required until lane closeout unless the change surface grows materially.

## 9. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Required control |
| --- | --- |
| Turning persistence into an unbounded polling loop | Fixed acquisition horizon, cumulative operation budget, Scheduler-owned delayed opportunities |
| Re-running sources without durable dedup | Persist exact candidate identity/disposition and suppress already-terminal candidate work until a lawful freshness/requalification boundary |
| Requiring every candidate to enter the Pump graduated registry | Preserve direct aggregator nomination for non-Pump/unknown-origin candidates |
| Treating a candidate-local Pump verification failure as provider death | Keep candidate-local rejection separate from channel availability |
| Weakening liquidity or exact-pool gates to increase yield | Prohibited; replenish candidates instead |
| Adding source quotas/preferences | Prohibited; categorical deterministic source schedule only |
| Resetting budgets after a wait | Prohibited; one cumulative campaign/cycle ledger |
| Retrying the four-token proof before repair proof | Prohibited |

## 10. Exact next lane

`V2-9.8B Persistent Per-Cycle Multi-Source Fresh Acquisition Continuation Design`

The design may proceed from this audit. Implementation remains gated on an approved design and must be followed by bounded disposable proof and closeout before any new live proof/authorization review.
