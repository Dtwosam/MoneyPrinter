# Printer V1 V2-9.8B Post-Repair Four-Token Authoritative Readiness

Date: 2026-08-19

## Verdict

`V2_9_8B_POST_REPAIR_FOUR_TOKEN_AUTHORITATIVE_READINESS_PASS`

This readiness PASS applies only to the exact adopted executable merge commit:

`ffd0ceec0492dc27c0ae703c5dbcbd1b191eca06`

It means the adopted V2-9.8B 4/2/2 code, control, evidence, identity, scheduling, safety, continuation, and one-shot boundaries are ready to advance to a fresh authorization-preparation lane. It is not runtime success proof, does not create an authorization, and does not run Printer.

## Authority

Reviewed against the active source stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

Current-lane control was taken from `CURRENT_HANDOFF.md`; the source stack wins any conflict.

## Adopted target and inherited proof

PR #191 was lawfully adopted into the approved V2-9.8B product branch. Its exact executable merge commit is `ffd0ceec0492dc27c0ae703c5dbcbd1b191eca06`.

The PR #191 production/test blobs reviewed during adoption are the blobs carried by the adopted merge. The bounded pre-adoption proof remains valid by exact blob identity:

- Cycle-2 historical-carrier + diagnostic-durability corrective suites: `8 passed`;
- existing Scheduler compatibility suite: `25 passed`;
- production-module compile: PASS;
- `git diff --check`: clean.

The merge commit itself currently has no separate combined-status entries. That is recorded honestly and is not treated as new runtime proof.

## Readiness contract

The exact adopted path preserves the V2-9.8B contract:

- 4 total tokens;
- 2 cycles;
- 2 tokens per cycle;
- maximum 2 simultaneously active;
- Cycle 2 fresh/disjoint from Cycle 1;
- freeze minimum depth 4 before two-slot selection;
- exact-pool liquidity floor `$3,000`;
- minimum inter-cycle spacing `300s`;
- `WINDOW_15M` root;
- lawful token-local `WINDOW_15M -> WINDOW_1H -> WINDOW_4H` continuation;
- `WINDOW_5M_MICRO_EVENT` support-only;
- retries `0`;
- endpoint rotation `false`;
- one-shot only;
- no rerun, resume, restart, or successor under a consumed authorization.

## A-to-Z readiness findings

### Fresh later-cycle supply

Cycle-2 supply is bound to the exact campaign/run/proposed-cycle/execution identity and uses governed source-request roots. The permanent availability/front-door path retains the `$3,000` exact-pool liquidity admission rule and distinguishes source shortage, eligibility block, and internal failure. PR #191 preserves/rejoins immutable direct-Pump/PumpSwap proof for genuine historical `PUMPSWAP_GRADUATED_CONFIRMED` candidates without requiring same-cycle direct rediscovery. Fresh `MARKET_PRESENT_POOL` remains a separate non-Pump admission path.

Holder context is gathered only for the already-frozen selected pair. Missing descriptive holder coverage is not promoted into a hard selection rule; genuine identity, provenance, or tracking conflicts still fail closed.

### Freeze and neutral selection

The existing V2-9.8B supply contract requires the eligible reserve/freeze depth before the two-slot selection boundary. Neutral selection is deterministic over candidate identity and seed; it introduces no score, rank, confidence percentage, weighted preference, volume threshold, token-age threshold, or provenance quota. It returns exactly two distinct mint+pair candidates or none.

### Cycle-2 disjointness and canonical identity

Pre-admission persistence requires exactly two pair items and mutual distinctness for token identity, token row, mint, pair identity, pair row, canonical market identity, and canonical pool identity.

The multi-cycle coordinator validates the proposed Cycle-2 slots atomically against all prior campaign slot identities and forbids reuse of token-slot, token, token-row, mint, pair, and pair-row identities.

No canonical-market bypass was found. In the adopted later-cycle carrier, `pair_identity` is the exact pool, `canonical_pool_identity` is that exact pool, and `canonical_market_identity` must bind to the exact pair/pool. Therefore cross-cycle canonical pool/market reuse necessarily collides with the already-forbidden prior `pair_identity`.

### Scheduler ownership and atomic admission

The pre-admission attempt owns an exact Central Scheduler job. A transition to RUNNING requires the expected Scheduler lock owner. Pair persistence is two-or-none and terminalization is explicit.

`admit_two_token_cycle_from_attempt` performs the Cycle-2 admission under one immediate transaction: it requires a `PAIR_READY` attempt, exact campaign/run/factory/cycle ownership, reloads the exact frozen pair, reruns persisted campaign admission constraints, atomically inserts the two-slot cycle, and marks the attempt CONSUMED only in the same successful transaction. Failure rolls back.

Materialization requires that exact consumed attempt and admitted cycle, revalidates canonical pool/pair identity, and copies the exact frozen pair into the lifecycle selection batch without reselection.

### 15m root and continuation

The origin/lifecycle integration root is `WINDOW_15M`. The standard continuation policy supports exactly the bounded first-four-hour transitions:

- `WINDOW_15M -> WINDOW_1H`;
- `WINDOW_1H -> WINDOW_4H`.

The token-local continuation owner requires exact campaign/configuration/token/pair/lifecycle/window identity, closed clean predecessor memory, eligible evidence, fresh governed provenance, accepted safety context, continuous lifecycle evidence, and token/campaign budget. Once those hard gates pass, outcome or learning-need labels do not stop or promote either standard first-four-hour transition.

The standard 4h owner requires the predecessor to be exactly `WINDOW_1H`, the successor to be exactly `WINDOW_4H`, exactly two owned token slots, and both owned first-hour closes to be terminal before 4h planning. `WINDOW_12H` and `WINDOW_24H` remain locked.

### Safety semantics

The current safety policy preserves the intended optional-evidence rule:

- `LIQUIDITY_LOCK_OR_BURN_UNKNOWN` is source-coverage pending, not a hard blocker;
- `KNOWN_RISK_FLAGS_UNKNOWN` is source-coverage pending, not a hard blocker;
- explicit `LIQUIDITY_UNLOCKED_OR_DANGEROUS` is a hard blocker;
- explicit `KNOWN_RISK_FLAGS_PRESENT` is a hard blocker.

The authoritative safety adapter computes the effective accepted/blocked gate from the persisted composite. The continuation policy consumes that effective gate, so unknown lock/burn or known-risk coverage does not become an accidental mandatory prerequisite for either `15m -> 1h` or `1h -> 4h` when the other hard safety/provenance requirements pass.

This does not label unknown evidence as `SAFETY_CLEAN` and does not convert safety into trading approval.

### 5m support-only and long-window locks

`WINDOW_5M_MICRO_EVENT` remains parented to an exact `WINDOW_15M` row, cannot create `CLEAN_MEMORY`, cannot activate retrieval or paper/financial capability, and rejects cross-token/cross-pair linkage. It does not independently create a main outcome, continuation, position, decision, or PnL.

12h/24h remain locked.

### One-shot / retry boundary

The standard four-token one-shot wrapper remains:

- allowed invocation count `1`;
- automatic retry `False`;
- manual rerun `False`;
- resume `False`;
- restart `False`;
- successor `False`.

Source retries remain `0` and endpoint rotation remains `false` under the 4/2/2 contract.

## Classification

### A — proven code defect

**None found in this readiness audit.**

No new functional defect was proven in fresh Cycle-2 supply, proof rejoin, exact-pool admission, freeze/selection, disjointness, Scheduler ownership, atomic Cycle-2 admission, materialization, 15m root, 1h/4h continuation, safety semantics, support-only 5m, or one-shot controls.

### B — source scarcity

**Not proven by this static readiness audit.**

A future authorized run may truthfully observe insufficient fresh eligible source supply. Such an outcome must remain attributable as source/coverage evidence rather than rewritten as a code defect.

### C — provider limitation

**No new blocking provider limitation is proven.**

Free providers can still return unavailable, stale, partial, malformed, rate-limited, or missing evidence. Those are governed runtime outcomes and must remain distinguishable from internal failures.

### D — honest market block

**Not proven now.**

A future authorized run may honestly fail to obtain the required eligible reserve depth, exact-pool `$3,000` liquidity, or another categorical market/evidence prerequisite. That must not be bypassed.

### E — missing evidence / proof

**Full post-repair 4/2/2 runtime proof remains intentionally missing.**

No campaign was executed during this readiness lane. This is not a readiness code defect. The next fresh authorized one-shot campaign, if separately prepared and approved, is the bounded runtime proof of actual two-cycle completion under current market/provider conditions.

## Locks preserved

Solana-only; Solana memecoin-only; paper-only. No live wallet, private keys, signing, real funds, or live execution. No paid API dependency. No scoring/ranking/confidence/weighted decision logic. No embeddings/vectors. No Source Governor bypass. No Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits, and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

All historical four-token authorizations remain consumed, immutable, and non-reusable.

## Readiness closeout

Verdict:

`V2_9_8B_POST_REPAIR_FOUR_TOKEN_AUTHORITATIVE_READINESS_PASS`

Exact executable target that may advance:

`ffd0ceec0492dc27c0ae703c5dbcbd1b191eca06`

### Next permitted action

A **fresh V2-9.8B 4/2/2 authorization-preparation lane** for this exact adopted executable commit.

That lane must create a genuinely new one-shot authorization only if its own preparation checks pass. It must not reuse, rerun, resume, restart, or create a successor to any consumed authorization.

Do not run Printer merely from this readiness PASS.