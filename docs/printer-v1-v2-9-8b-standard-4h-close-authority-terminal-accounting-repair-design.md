# Printer V1 V2-9.8B Standard-4h Close Authority and Terminal Accounting Repair Design

## Baseline

- Root-cause audit baseline: `300010e2ea6b3edff777c7dfb43c55ef23b4871e`.
- Fifth standard-4h authorization is permanently consumed and is not reusable.
- Audit/readiness for this failure is complete.
- This document closes the design/specification step only; it does not authorize runtime, source fetching, memory generation, a fresh authorization, or another 4h campaign.

## Goal

Repair two distinct committed defects exposed by the fifth standard-4h attempt while preserving the existing fail-closed authority model and truthful terminal accounting.

A. Carry already-approved standard-4h execution authority into final `LONG_CONTINUATION_CLOSE` without weakening successor guards globally.

B. Make standard-4h terminal acceptance/accounting recognize only the exact authorized `WINDOW_15M -> WINDOW_1H -> WINDOW_4H` Scheduler/work lineage, while retaining the existing ordinary `WINDOW_15M` contract and failing closed on unexplained work.

## Defect A — Close-authority propagation

### Canonical owners

- `src/printer_v1/operator_cli/one_token_4h_runtime.py`
- standard-4h call path in `src/printer_v1/operator_cli/one_command_15m_factory.py`

The global successor guard in `src/printer_v1/snapshots/lifecycle_continuity.py` remains unchanged.

### Design

1. Reuse `FourHourExecutionAuthority`; do not introduce a public unrestricted boolean authority.
2. `close_current_run_4h()` receives explicit execution authority and validates it through the existing authority model before allowing an already-enabled `WINDOW_4H` successor to resolve at final close.
3. Only the already-approved standard campaign path carries `STANDARD_CAMPAIGN` into its final 4h close. Proof-only behavior remains separately scoped to `PROOF_ONLY` where already authorized by the existing model.
4. Missing, disabled, mismatched, or invalid authority fails closed.
5. `resolve_predecessor_and_successor_for_subject()` keeps `allow_enabled_successor_planning=False` as its global/default posture.
6. No authority from this repair can enable `WINDOW_12H` or `WINDOW_24H`.
7. Ordinary/non-standard `WINDOW_15M` behavior is unchanged.

### Minimum focused proof

- Authorized standard-4h planning authority survives into final close and permits the already-enabled `WINDOW_4H` successor.
- Missing/disabled or mismatched authority still fails closed.
- Global successor default remains fail-closed.
- 12h/24h remain locked.
- Existing ordinary/non-standard behavior remains unchanged.

## Defect B — Standard-4h terminal acceptance/accounting

### Canonical owner

- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`

### Design

Keep the existing 15m accounting/evidence/sealing set intact. Do not broaden that set merely to make Scheduler correspondence pass.

For `STANDARD_4H_CAMPAIGN` only, derive a separate authorized Scheduler-correspondence set from durable exact campaign lineage:

- the existing eligible 15m lifecycle identities; plus
- eligible persisted long-continuation lifecycle work for `WINDOW_1H` and `WINDOW_4H` belonging to the same execution/campaign/campaign-run/token/pair lineage and canonical Scheduler ownership.

The standard-4h correspondence check must compare exact authorized identities against observed campaign-owned `WINDOW_LIFECYCLE` Scheduler ownership. It must not accept jobs merely because they occurred during the campaign, share a work scope, or have a familiar job kind. Any observed ownership outside the exact authorized lineage remains unexplained extra work and fails closed.

Terminal acceptance must be campaign-family aware:

- Ordinary `WINDOW_15M` campaigns retain their existing terminal predicates and reporting contract.
- A standard-4h campaign must not use the old 15m-only assumptions (`18` accounting rows as the complete Scheduler family, exactly two 15m closures, exactly two 15m final memories) as proof that all authorized long continuation work is accounted for.
- Standard-4h terminal truth must instead require the durable standard campaign lineage and its required close/accounting facts to reconcile exactly. No terminal success may be fabricated from wrapper exit code 0.

### Retry/accounting semantics

Scheduler retry bookkeeping is not the same fact as a campaign-level automatic retry. `scheduler_retry_count` remains visible evidence, but standard-campaign `no_automatic_retries` must not become false solely because a Scheduler job was explicitly retried and later reconciled successfully. Scheduler terminal state, failures, unresolved retry-wait work, exact ownership correspondence, and unexplained work remain independently fail-closed.

### Minimum focused proof

- Legitimate standard `15m -> 1h -> 4h` Scheduler ownership reconciles without false `extra_ownership`.
- One genuinely unexpected Scheduler identity still fails closed.
- Ordinary `WINDOW_15M` terminal accounting remains unchanged.
- Scheduler retry bookkeeping is not misreported as a campaign automatic retry, while unresolved/failed Scheduler work still cannot produce terminal success.
- Wrapper/child exit 0 cannot manufacture campaign/proof success.

## Composition rule

The repairs remain conceptually independent:

- A answers whether final 4h close has explicit scoped authority.
- B answers whether observed Scheduler/work ownership belongs to the authorized standard campaign lineage.

A cannot legitimize unexplained Scheduler work. B cannot grant close authority. A healthy terminal result requires both contracts to pass independently.

## Allowed implementation scope

- Focused tests for A and B.
- Minimal production edits in the canonical owners above, plus only the existing standard-4h call path needed to carry authority.
- Documentation closeout and read-only post-repair rereadiness review.

## Not allowed

No global successor-guard weakening; no 12h/24h unlock; no source-budget, ceiling, cadence, provider, Source Governor, Central Scheduler ownership, discovery, or source-policy changes; no runtime/source fetching/memory generation; no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/trades/audits/PnL; no fresh authorization; no live 4h campaign.

## Acceptance gate

Implementation may close only if focused red-to-green tests prove both defect families independently and together, the standard campaign can account for legitimate long continuation without accepting unexplained work, ordinary 15m behavior remains unchanged, and all V1/V2 locks remain intact.

## Rollback / stop conditions

Stop and do not proceed to rereadiness if any repair:

- requires weakening the global successor guard;
- permits authority without explicit `FourHourExecutionAuthority` validation;
- accepts Scheduler work by broad job type/time-range matching rather than exact authorized lineage;
- changes ordinary 15m terminal truth unexpectedly;
- unlocks 12h/24h or any retrieval/financial capability; or
- requires runtime/source fetching to establish correctness.

## Money-usefulness contribution

Prevents a bounded four-hour campaign from wasting already-collected legitimate long-window evidence at deterministic close or from falsely rejecting that authorized work as unexplained. This improves the reliability of persistent quality-memory growth; it does not predict profit or unlock financial action.

## What this improves

- Explicit authority continuity through the final 4h close.
- Truthful standard-4h Scheduler ownership/accounting.
- Clear separation between command completion, Scheduler bookkeeping, and campaign proof truth.

## What this still does not unlock

12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, PnL, live execution, wallets/private keys/real funds, paid APIs, scoring/ranking/confidence/weighted systems, embeddings/vectors, or any new authorization/run.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Mitigation | Minimum proof |
|---|---|---|
| Authority becomes a loose bypass | Reuse and validate `FourHourExecutionAuthority`; keep global default false | missing/mismatched authority negative tests |
| Long work accepted too broadly | Exact durable campaign/run/token/pair/window/Scheduler identity lineage only | unexpected-job negative test |
| 15m behavior regresses | campaign-family-specific standard handling | existing/focused 15m regression |
| Scheduler retry count is confused with campaign retry | keep separate observability and terminal-state checks | retry-semantics focused test |
| Exit 0 is mistaken for proof success | terminal truth remains evidence-derived | incomplete campaign with command success remains non-success |
| Scope drifts into future windows/capabilities | no 12h/24h or financial/retrieval changes | focused lock/static checks |
