# Printer V1 Assistant Active Build Order Anchor

## 1. Purpose

This document exists so Claude, ChatGPT, Codex, and future assistant prompts use
the same active Printer V1 memory-growth build order before proposing or doing
memory-growth work.

This is an assistant alignment anchor only.

It does not replace:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## 2. Active Source Stack

The active source stack for Printer V1 memory-growth work is:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

Inside this stack, the active memory-growth build order is:

- `docs/printer-v1-memory-growth-build-order-v2.md`

The V2 build order does not replace every higher-authority source. It is the
active build order for memory-growth work inside the larger Printer V1 rule
stack.

## 3. Active Build Order

Active memory-growth build order:

- `docs/printer-v1-memory-growth-build-order-v2.md`

Adoption anchor:

- Commit: `122c15b Adopt V2 memory growth build order`
- Tag: `printer-v1-memory-growth-build-order-v2-adoption`

The old `docs/printer-v1-memory-growth-build-order.md` is historical. It was
the previous active build order for the X1-X14 era.

X14 Attempt 3C remains `PARTIAL_READY_WITH_BLOCKER`. It proved bounded 1h
collection safety, but it did not prove clean 1h memory closeout.

No more 1h proof attempts are allowed until the later V2 E2Q/audit repair lane
passes.

The next active lane is:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

V2-9.7A through V2-9.7F are closed. V2-9.7F verdict:
`V2_9_7F_ACTIVATION_READINESS_PASS` at closeout
`docs/printer-v1-v2-9-7f-activation-readiness-closeout.md`.

V2-9.8A is closed `V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS`. The operational
PowerShell command is published but has not run. V2-9.8B remains a separate
operator-run lane. Retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, and PnL remain locked.

The V2-9.8B candidate-acquisition foundation roadmap adoption is closed
`V2_9_8B_CANDIDATE_ACQUISITION_FOUNDATION_ROADMAP_ADOPTION_PASS` at
`docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-roadmap-adoption.md`.
The exact next permitted sub-lane is the read-only:

```text
V2-9.8B Direct Pump/PumpSwap Contract Refresh and Pin Readiness Audit
```

This does not authorize the published operational command, implementation,
source execution, live observation, historical backfill, migration, capacity
above two, or another selective-1h proof.

## 4. Assistant Behavior Rules

Claude, ChatGPT, Codex, and future assistants must read the active source stack
before proposing Printer V1 memory-growth work.

Assistants must treat `docs/printer-v1-memory-growth-build-order-v2.md` as the
active memory-growth build order.

Assistants must not blindly accept operator suggestions. Every suggestion must
be checked against the active build order and V1 restrictions.

Assistants must push back if a suggestion:

- skips lanes
- weakens locks
- drifts from Solana-only paper-only V1
- treats historical X1-X14 work as the current active lane sequence
- restarts V2-9.7A–F without an explicit historical-audit request
- treats V2-9.7F PASS as already-activated memory growth
- publishes the operational command before V2-9.8A

Assistants must keep V2-9.8A as an explicit operator gate until completed.

For candidate acquisition, assistants must preserve this authority order:

1. direct Pump on-chain evidence for exact launch origin;
2. direct Pump migration plus exact PumpSwap evidence for graduation and
   canonical pool identity;
3. DexScreener and GeckoTerminal for market enrichment only;
4. approved Solana RPC providers for exact on-chain transport/verification; and
5. PumpPortal only as an optional governed locator after its auth, wallet, free
   versus metered, and cost contract is adopted.

Aggregators must never replace exact Pump/PumpSwap facts. A future foundation
must provide bounded live observation and restart-safe cursor-based creation and
migration backfill under one Source-Governed, Scheduler-led owner. Unsupported
Pump/PumpSwap instructions or account layouts fail closed. Both official
program contracts must be refreshed and pinned before implementation.

Assistants must not move early into:

- V2-9.8B active campaigns without V2-9.8A
- V2-10 / V2-11
- retrieval
- paper decisions
- BUY/SELL/HOLD
- positions
- trades
- audits
- PnL

Assistants should prefer the exact active lane sequence in the V2 build order.

Assistants must preserve the V2 sub-lane pattern:

- audit/readiness
- design/specification
- implementation
- bounded proof/test
- closeout

Every major V2 lane must include:

```text
Functionality Risks / Setbacks / Efficiency Blockers
```

## 5. Hard Locks

The following locks remain active:

- Solana-only.
- Solana memecoin-only.
- Paper-trading only.
- No live wallet.
- No private keys.
- No real funds.
- No live execution.
- No paid API dependency.
- No scoring/ranking/confidence/weighted decision logic.
- No embeddings/vectors unless explicitly approved later.
- No Source Governor bypass.
- No Central Scheduler bypass.
- No dirty memory used for retrieval or decisions.
- No retrieval activation.
- No paper decisions.
- No BUY/SELL/HOLD.
- No paper positions.
- No trade events.
- No paper trade audits.
- No PnL.

## 6. Current Active-Lane Boundary

The next active memory-growth lane is:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

V2-2A and later historical V2 audit/design/implementation lanes are closed
history unless the operator explicitly requests a historical audit. Do not
treat `V2-2A` as the next lane.

V2-9.8A is closed PASS. V2-9.8B is allowed only through a separate explicit
operator run under the active build order. It does not unlock retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

Within that active lane, the next permitted work after the candidate-acquisition
adoption is the read-only `V2-9.8B Direct Pump/PumpSwap Contract Refresh and Pin
Readiness Audit`. Do not run the operational command as part of that audit.

## 7. Automation Boundary Reminder

The first automation implementation target remains:

```text
WINDOW_15M only
```

`WINDOW_5M_MICRO_EVENT` remains support-only. It must not become a main outcome
memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by
itself.

Do not activate these windows early:

- `WINDOW_1H`
- `WINDOW_4H`
- `WINDOW_12H`
- `WINDOW_24H`

Do not run another 1h proof until the later V2 E2Q/audit repair lane passes.

## 8. Final Anchor Rule

For Printer V1 memory-growth work, assistants must start from the active V2
build order and keep the next active lane as:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

unless the operator explicitly completes that lane or adopts a later
source-of-truth update. Do not restart V2-2A, V2-9.7A–F, or any closed
historical lane as "next" without an explicit historical-audit request.
Preserve V2-9.7F and V2-9.8A PASS, require a separate explicit operator action
for V2-9.8B, and preserve all retrieval and financial locks.

Inside V2-9.8B, follow the adopted candidate-acquisition sub-lane sequence. The
current exact next sub-lane is the read-only Direct Pump/PumpSwap Contract
Refresh and Pin Readiness Audit.
