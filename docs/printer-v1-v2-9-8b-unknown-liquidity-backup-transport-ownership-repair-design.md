# Printer V1 V2-9.8B Unknown-Liquidity Backup Transport Ownership Repair Design

Verdict: `V2_9_8B_UNKNOWN_LIQUIDITY_BACKUP_TRANSPORT_OWNERSHIP_REPAIR_DESIGN_PASS`

## Baseline

- Audit closeout: `78c4d8cc44e5fea6095f362c77827642d244eb68`.
- Confirmed defect: unknown-liquidity backup transports are represented in the source-request manifest M but are absent from action-local A and campaign-owner C.
- Controlling evidence: A=5, C=5, M=9; `M_minus_A=4`; `M_minus_C=4`; requests 1982–1985; logical owners `UNKNOWN_LIQUIDITY_BACKUP|1..4`.

This design remains inside the active Printer V1 source stack and preserves Solana-only, memecoin-only, paper-only V1 restrictions.

## Design decision

Repair ownership plumbing only. Do not change the canonical transport identity and do not weaken pre-holder reconciliation.

### 1. Extend the backup function owner hooks

In `src/printer_v1/discovery/permanent_discovery_availability.py`, extend `run_bounded_unknown_liquidity_backup()` with optional:

- `stage_evidence_sink`
- `transport_identity_observer`

These are the same existing owner hooks already carried through `run_persistent_eligible_token_supply()` for other permanent-discovery stages.

### 2. Feed action-local accounting at measurement time

Construct each backup attempt `MeasuredTransportLedger` with:

`on_transport_recorded=transport_identity_observer`

The observer fires only after `MeasuredTransportLedger.record_transport()` accepts the real transport identity. No identity is fabricated or reconstructed from request counts.

### 3. Seal campaign-owner stage evidence

For each backup attempt that has at least one successfully measured transport identity, seal one stage through `seal_campaign_stage_evidence()` with:

- stage kind `UNKNOWN_LIQUIDITY_BACKUP`;
- stage sequence equal to the existing deterministic attempt ordinal;
- campaign/run/cycle identities from the caller;
- the same attempt `MeasuredTransportLedger`;
- terminal status `COMPLETED` for a complete source result, or `BLOCKED` when a real measured transport ended in a source failure;
- truthful first terminal cause when blocked.

Attach the attempt's source-request coverage and request/response/failure IDs to the sealed evidence before calling `stage_evidence_sink`.

The transport identity inside the sealed ledger remains the provider-produced canonical identity. In particular, a GeckoTerminal backup may retain transport stage `MINT_MARKET_BATCH` while the accounting stage owner is `UNKNOWN_LIQUIDITY_BACKUP|N`. Do not rename or rewrite the transport key.

### 4. Preserve zero/failure semantics

If a request has no accepted measured transport identity:

- do not invent one;
- do not seal an empty successful stage merely to make counts equal;
- retain zero transport count in request coverage;
- preserve existing accounting-blocker behavior on measurement failure;
- let source-request/pre-holder reconciliation fail closed if evidence is incomplete.

### 5. Wire the existing hooks from eligible-token supply

In `run_persistent_eligible_token_supply()`, pass its existing:

- `stage_evidence_sink=stage_evidence_sink`
- `transport_identity_observer=transport_identity_observer`

into `run_bounded_unknown_liquidity_backup()`.

No new owner, global ledger, or parallel accounting path is introduced.

## Explicit non-changes

Do not change:

- `build_pre_holder_budget_snapshot()` equality requirements;
- canonical transport-key construction;
- Source Governor ownership;
- Central Scheduler ownership;
- stage budgets or ceilings;
- one bounded opposite-source backup rule;
- provider ordering/selection logic;
- discovery eligibility rules;
- registry semantics;
- lifecycle, memory, retrieval, decision, or paper-trading behavior.

## Minimum implementation proof

Focused zero-runtime tests only:

1. one successful backup: the same canonical transport identity reaches manifest, action-local observer, and campaign owner;
2. four successful backups: unique `UNKNOWN_LIQUIDITY_BACKUP|1..4` stage evidence and M=A=C identity sets;
3. source failure with a measured transport: real identity is preserved and stage seals `BLOCKED` without inventing success;
4. zero-transport/measurement-failure path: no fabricated identity or empty successful stage;
5. existing pre-holder equality still rejects any deliberately omitted identity;
6. existing eligible-token-supply caller passes both hooks into the backup stage.

No broad regression suite unless focused implementation reveals wider architectural impact.

## Money-usefulness contribution

The repair prevents a lawful market-evidence fallback from consuming a one-use operational attempt solely because its real network call was visible to only one accounting surface. It improves the chance that a future authorized `WINDOW_15M` attempt reaches genuine eligibility/lifecycle work without sacrificing accounting truth.

## What this improves

- Makes unknown-liquidity backup transport ownership complete across M, A, and C.
- Preserves independent three-way accounting rather than self-comparison.
- Keeps the existing fail-closed gate meaningful.

## What this still does not unlock

This design does not authorize implementation, source fetching, runtime, a replacement authorization, `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Completion proof

Implementation is complete only after focused zero-runtime tests prove the owner hooks and stage sealing above, followed by a bounded proof/closeout. A future real operational attempt requires a new explicit operator authorization after that closeout passes.

## Functionality Risks / Setbacks / Efficiency Blockers

- Wiring only the observer repairs A but leaves C incomplete.
- Wiring only stage sealing repairs C but leaves A incomplete.
- Sealing empty success evidence would fabricate accounting truth.
- Rewriting transport-stage identity would expand scope and risk cross-stage regressions.
- Relaxing pre-holder equality would hide defects rather than fix them.
- The consumed DTW-78 authorization cannot be reused under any outcome.
