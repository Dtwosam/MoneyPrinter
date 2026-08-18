# Printer V1 V2-9.8B Post-Repair Standard 15m-to-1h-to-4h Bounded Campaign Design

Date: 2026-08-18

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_STANDARD_15M_TO_1H_TO_4H_BOUNDED_CAMPAIGN_DESIGN_PASS`

Implementation disposition:

`IMPLEMENTATION_NOT_REQUIRED`

## Purpose

Define the exact next bounded operational campaign shape after the completed V2-9.8B A0/A/E/F/G/D/B/C/H/I/J repair program and post-repair operational rereadiness PASS.

This is design/specification only. It performs no provider/RPC/WebSocket call, no authoritative database mutation, no authorization preparation or consumption, no Memory Factory execution, no lifecycle/window/memory creation, no retrieval, no paper decision, no paper position, no trade, no audit/PnL action, and no 12h/24h activation.

## Authority

Apply the active Printer V1 source stack in order:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

Current-lane pointer:

- `CURRENT_HANDOFF.md`

Immediate governing closeout:

- `docs/printer-v1-v2-9-8b-post-repair-operational-rereadiness-and-baseline-reconciliation.md`

Historical roadmaps, old authorizations, old runbooks and earlier handoffs are evidence only where they do not conflict with this stack and the current handoff.

## Fixed Product Baseline

Repaired product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

No product-source change is required by this design.

A future authorization-preparation branch may add only the documentation/authorization artifacts required by the existing one-shot protocol. Any product-source, migration or capability delta relative to `df1aced...` is a stop condition and requires a new scoped audit/design before runtime.

## Campaign Objective

Run one fresh, operator-approved, bounded, paper-only standard campaign that:

1. acquires and selects exactly two lawful Solana memecoin token/pair slots through the repaired ordinary operational supply path;
2. observes each activated slot through `WINDOW_15M`;
3. continues through `WINDOW_1H` when the existing hard evidence/identity/provenance/safety/continuity/resource gates permit;
4. waits for both owned first-hour verdicts to become terminal;
5. plans `WINDOW_4H` work only for token slots that satisfy the unchanged token-local standard 1h-to-4h hard gates;
6. writes truthful clean/dirty/blocked memory and terminal evidence to the authoritative persistent corpus; and
7. safe-stops with authoritative accounting/report/replay and no automatic successor.

The campaign exists to grow reliable paper-only learning memory. It is not a trade, alpha, scoring or financial-action campaign.

## Public Execution Boundary

The standard campaign must use the existing public operational path:

- public command owner: `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- standard policy owner: `src/printer_v1/operator_cli/operational_standard_4h.py`;
- standard one-use application owner: `src/printer_v1/operator_cli/standard_four_hour_one_shot_wrapper.py`;
- live internal composition owner: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`.

Authorized child mode:

`standard-four-hour-run`

Direct invocation of the standard campaign without the fresh one-use wrapper/authorization is not authorized by this design.

The legacy proof path is not production authority.

## Authoritative Database Contract

Canonical persistent DB path remains the code-owned target:

`data/printer_v1.sqlite3`

The future authorization-preparation lane must read and bind the actual host DB identity at that time, including the existing wrapper-required fields:

- path;
- SHA-256;
- size;
- inode;
- mtime_ns;
- migration count; and
- migration head.

This GitHub design does not claim the current host SQLite bytes or filesystem identity are ready; that is a host-readiness fact to prove before authorization.

Required migration head:

`058_direct_pump_migration_cursor.sql`

No migration `059_*` is authorized or required. Any ledger mismatch, unknown migration, missing 058, integrity failure, foreign-key failure or DB-identity drift blocks authorization preparation.

## Standard Campaign Policy

The existing standard policy remains authoritative and must not be independently redefined by a wrapper, runbook or operator command.

Required current contract:

- policy version: `V2-9.8-STANDARD-4H-OPERATIONAL-V1`;
- token capacity: exactly `2`;
- root main window: `WINDOW_15M`;
- first-hour predecessor for 4h: exactly `WINDOW_1H`;
- standard successor: `WINDOW_4H`;
- pre-lifecycle acquisition duration: `900` seconds;
- post-supply bounded duration: `14,700` seconds;
- automatic retries: `0`;
- endpoint rotation: `False`;
- locked windows: `WINDOW_12H`, `WINDOW_24H`;
- one-use wrapper required;
- planning barrier: both owned first-hour verdicts terminal.

Capacity remains derived from the canonical lifecycle arithmetic, not hand-maintained numeric authority.

Current repaired/proven values are expected to resolve to:

- lifecycle request outer ceiling: `236`;
- lifecycle requests per token: `117`;
- lifecycle Scheduler outer ceiling: `210`.

The future authorization-preparation lane must derive these values from committed code at the exact launch baseline. If the derived values differ, stop and reconcile the drift; do not hand-edit an authorization to force the old numbers.

## Candidate Acquisition and Selection

### First-cycle supply

Use the repaired ordinary operational supply path. Do not substitute a manual token list or historical selected pair.

Lawful source-specific candidate authority includes:

1. direct Pump migration plus exact PumpSwap confirmation for Pump-graduated candidates; and
2. `MARKET_PRESENT_POOL` admission for eligible DexScreener/GeckoTerminal-nominated Solana market candidates when the exact present pool is confirmed under the repaired source-specific law.

A market-present candidate must not be forced to fabricate Pump origin or Pump migration evidence it does not possess.

A direct-Pump candidate must retain its exact migration/PumpSwap authority and may not be downgraded to aggregator-only lineage.

### Exact liquidity floor

The active market-performance floor remains exactly:

`liquidity_usd >= 3000`

The floor applies to fresh governed evidence for the exact Solana mint and exact confirmed/current pool identity.

Below-floor liquidity and unproven liquidity remain truthful evidence but cannot consume an active token slot.

`$3,000` remains the only numeric market-performance threshold. Liquidity magnitude above the floor must not become a score, rank, weight or preference.

### Selection

Select exactly two active token/pair slots through the repaired deterministic categorical selection law.

Forbidden selection behavior:

- scoring;
- ranking;
- confidence percentages;
- weighted decision logic;
- winner chasing;
- manual pair substitution after selection;
- token-level liquidity substituted for exact-pair liquidity;
- stale historical pair authority substituted for current exact identity.

### Later-cycle fresh supply

If the canonical one-shot runner lawfully reaches a later cycle inside the same authorized invocation, only the repaired later-cycle acquisition path may supply it.

It must preserve:

- cooperative bounded acquisition quanta;
- Source Governor ownership;
- Central Scheduler ownership;
- durable accounting before yielding/resuming;
- the repaired `MARKET_PRESENT_POOL` bridge;
- exact mint+pair identity;
- no manual carry-forward that bypasses current market evidence; and
- no separate successor process.

A later-cycle source shortage or honest market exhaustion is not automatically a code defect.

## Source Governor and Central Scheduler

Every external source transport must remain admitted through Source Governor before transport.

Central Scheduler ownership must be present before source/lifecycle work proceeds.

No module may add its own retry loop, provider rotation, reconnect loop, hidden source session or scheduler bypass.

The internal live composition must continue to fail closed when either owner is unavailable or has the wrong owner identity.

## Holder and Safety Design

### Selected-slot ownership

Holder work remains bounded to selected-slot ownership under the repaired Slice I law. Holder concentration must not become a pre-selection ranking or automatic admission veto.

### Honest UNKNOWN

Unsupported or unavailable holder condition must remain honest UNKNOWN/optional evidence under the current safety policy unless an independent hard provenance/target/source rule is violated.

The design must not convert missing holder evidence into a fabricated safe or unsafe fact.

### Optional safety fields

Current optional source-coverage fields such as liquidity lock/burn and known-risk flags remain UNKNOWN when the evidence cannot prove them. They are not made mandatory by this campaign design.

An exact-pair explicit dangerous/unlocked liquidity state may remain hard evidence under the existing safety law. This design does not weaken existing real hard blockers.

### Hard safety/provenance gates

Do not weaken:

- exact target mint/pair matching;
- mandatory source usability where the existing composite requires it;
- freshness;
- source-request/response/failure provenance;
- mint authority/freeze/token-program and other existing hard safety rules;
- exact memory-window binding; or
- existing safety-composite acceptance logic.

## Window and Continuation Design

### `WINDOW_5M_MICRO_EVENT`

Remains support-only.

It cannot independently create a main outcome, authorize continuation, activate retrieval, create a decision, position, trade, audit or PnL.

### `WINDOW_15M`

First main outcome window for each activated slot.

Continuation must use the existing hard gate law. Price direction, pump outcome, learning-interest label or holder-concentration description must not independently decide continuation.

### `WINDOW_1H`

Standard first-hour continuation/failure window for otherwise-valid slots.

At the Scheduler-owned first-hour close, the repaired path must collect/bind fresh first-hour safety authority against the exact first-hour closing snapshot before the first-hour memory outcome/audit is finalized.

No stale 15m safety composite may be copied forward as 1h authority.

### Exact H predecessor cutoff

The 1h-to-4h decision must use only evidence valid at the exact predecessor close cutoff.

No later snapshot, later safety evidence or hindsight fact may repair or upgrade the predecessor after the decision boundary.

Promotion authority and safety authority remain separate inputs.

### `WINDOW_4H`

The standard 4h barrier must wait until both owned first-hour verdicts are terminal.

For each token slot, the unchanged token-local hard gates decide whether a 4h suffix is lawful.

A token may be blocked while the other proceeds if the existing standard policy permits that mask. No outcome label may be turned into a score or forced-continuation preference.

No 12h/24h work may be planned or scheduled by this campaign.

## Accounting, Terminal Closure, Report and Replay

Campaign accounting must remain evidence-derived from durable request/transport identities and existing non-transport accounting evidence. Bare counters must not become authority.

SOURCE failures and INTERNAL failures must remain truthfully classified; an internal orchestration defect must not be relabeled as provider scarcity, and honest source scarcity must not be "fixed" by fabricated success.

All terminal paths must use the unified terminal closure behavior and preserve the first terminal cause.

At terminal:

- remaining attributable Scheduler work is reconciled/cancelled through the Scheduler owner;
- campaign/run/cycle/window state is terminally reconciled;
- active ownership is removed safely;
- final report is assembled from authoritative evidence;
- promotion reporting remains separate from safety reporting;
- zero-work/read-only replay performs no provider/source call and no database mutation; and
- no retry, rerun, resume, restart or automatic successor is created.

## One-Use Authorization Design

The campaign may run only after a fresh standard-four-hour authorization package is prepared and independently reviewed.

The authorization must be new. Every historical standard-4h or other one-shot authorization remains consumed/non-reusable according to its recorded state.

Required one-shot policy:

- allowed invocation count: `1`;
- automatic retry: `False`;
- manual rerun: `False`;
- resume: `False`;
- restart: `False`;
- successor: `False`.

The preparation/review lane must bind:

- exact launch branch and HEAD;
- exact repaired product-code ancestry/source diff;
- fresh authorization ID;
- temporal validity window;
- authoritative DB identity;
- migration head 058;
- derived standard capacity;
- exact command mode `standard-four-hour-run`;
- operator approval; and
- explicit prior-authorization non-reuse evidence.

No authorization is created or consumed in this design lane.

## Pre-Run Stop Conditions

Authorization preparation/review must stop before runtime if any of these is true:

- product source differs from the approved repaired baseline without a new scoped audit/design;
- authoritative DB identity cannot be read and bound;
- migration head is not 058 or migration 059 exists;
- DB integrity/foreign-key/migration-ledger checks fail;
- required runtime dependency/interpreter/package preflight fails;
- derived standard capacity does not equal the committed standard policy contract;
- Source Governor or Central Scheduler ownership is unavailable;
- a historical authorization would have to be reused;
- the new authorization cannot be made one-use and temporally valid;
- 12h/24h, retrieval or a financial capability appears unlocked; or
- the launch command would require a wallet, private key, signing, real funds, paid API, scoring/ranking/confidence/weighted logic, embeddings or vectors.

## Runtime Classification Rule

Once a future authorized campaign is running, a truthful bounded stop is not automatically a repair defect.

Classify first as one of:

- committed code defect;
- stale fixture/test expectation;
- host/environment/preflight failure;
- provider/source limitation;
- honest market/supply block;
- honest missing/unproven evidence;
- authorization/identity mismatch; or
- bounded budget/duration/cancellation stop.

Reopen only the minimum responsible lane when evidence proves a code defect.

## Implementation Decision

`IMPLEMENTATION_NOT_REQUIRED`

Reason:

The repaired baseline already contains the required operational owners and the immediately preceding integrated proof/independent closeout covered the representative seams needed by this design, including:

- Pump/PumpSwap protocol authority;
- source accounting and SOURCE/INTERNAL failure truth;
- Scheduler/cadence and exact-pair suppression;
- direct Pump migration acquisition;
- later-cycle `MARKET_PRESENT_POOL` bridge;
- exact H predecessor cutoff and standard 15m -> 1h -> 4h continuation;
- selected-slot holder ownership and honest UNKNOWN;
- promotion/safety reporting separation and zero-work replay;
- migration/capability locks; and
- code/diff hygiene.

That proof passed 386 tests plus 32 subtests against the repaired baseline. This design introduces no new behavior that needs implementation.

If a future host-readiness or authorization-preparation check exposes a real product defect, stop and open a new minimum audit/design/implementation chain. Do not patch code inside the authorization lane.

## Verification for This Design Lane

Minimum sufficient verification:

- reread active authority stack and current handoff;
- inspect the exact repaired public command, standard policy, standard one-use wrapper, source-specific graduated supply/front door, safety authority and terminal closure contracts;
- preserve the immediately preceding integrated proof as bounded code evidence;
- verify the design branch contains documentation changes only relative to the rereadiness branch;
- verify master remains untouched.

No broad regression suite or live provider proof is required for a documentation-only design that adds no runtime behavior.

## Money-Usefulness Contribution

This design gets Printer back to useful clean-memory growth without weakening the evidence that makes the memory trustworthy. It preserves diverse lawful candidate intake, exact-pair liquidity realism, full 15m/1h/4h trajectories, truthful blocked outcomes, and clean terminal accounting while preventing stale authorization reuse or premature financial capability.

## What This Still Does Not Unlock

This design does not unlock:

- campaign execution;
- authorization consumption;
- 12h or 24h;
- retrieval;
- paper BUY/SELL/HOLD;
- WAIT/AVOID/NO_ACTION activation;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live trading;
- wallets/private keys/signing/real funds;
- paid APIs;
- scoring/ranking/confidence/weighted logic; or
- embeddings/vectors.

## Exact Next Permitted Task

`V2-9.8B Post-Repair Fresh Standard-4H One-Use Authorization Preparation`

Type: preparation/readiness only.

It may perform host-local read-only preflight, bind the exact DB and repository identity, derive the current standard capacity, construct one fresh authorization package, and stop for independent review.

It must not consume the authorization or start the campaign.

After preparation, the required next gate is:

`V2-9.8B Post-Repair Fresh Standard-4H One-Use Authorization Independent Review`

Only an independent review PASS may authorize at most one bounded campaign invocation while the authorization remains temporally valid.

## Closeout

`V2_9_8B_POST_REPAIR_STANDARD_15M_TO_1H_TO_4H_BOUNDED_CAMPAIGN_DESIGN_PASS`

`IMPLEMENTATION_NOT_REQUIRED`

No provider/source operation was performed.

No authoritative DB mutation was performed.

No authorization was created or consumed.

No product source or migration was changed.

No financial or long-window capability was unlocked.
