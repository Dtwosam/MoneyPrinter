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
V2-2A - Audit current discovery/selection pipeline
```

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
- treats V2-2A as implementation instead of audit-only

Assistants must keep `V2-2A` audit-only until it is completed.

Assistants must not move early into:

- `V2-2B`
- `V2-2C`
- implementation
- proof
- automation
- memory generation
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

## 6. V2-2A Boundary

`V2-2A` is audit-only.

Allowed in `V2-2A`:

- static inspection
- read-only DB inspection
- existing artifact review
- audit documentation

Not allowed in `V2-2A`:

- discovery runs
- source fetching
- DB mutation
- memory generation
- runtime
- retrieval
- paper decisions
- BUY/SELL/HOLD
- positions
- trades
- audits
- PnL

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
build order and keep V2-2A as the next audit-only lane unless the operator
explicitly adopts a later source-of-truth update.
