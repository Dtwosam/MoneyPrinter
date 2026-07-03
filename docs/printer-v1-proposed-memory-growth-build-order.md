# Printer V1 Proposed Memory Growth Build Order

## Status

**PROPOSED ONLY.**

This document is not active source of truth yet.

It does not update `AGENTS.md`.

It does not supersede:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`

It does not unlock:

- runtime expansion by itself
- source fetching by itself
- retrieval activation
- paper decisions
- BUY / SELL / HOLD
- paper positions
- PnL
- live trading
- wallet/private-key behavior
- paid APIs
- scoring/ranking/confidence/weighted decision systems

All future runtime lanes must remain:

- bounded
- operator-approved
- Source-Governor-controlled
- Central-Scheduler-led
- audit-first
- clean-memory-only for retrieval
- dirty-memory-preserving for audit
- unable to unlock BUY by themselves
- unable to open paper positions by themselves
- unable to create PnL by themselves

---

## Why this proposed build order exists

Lane U/U2 proved the first real clean-memory path:

```text
real WINDOW_15M collection
→ coverage/gap persistence
→ coverage-blocked downgrade
→ E2Y same-pair group selection
→ E2Z clean memory episode creation
→ idempotent replay
→ no retrieval/paper/BUY/position/PnL unlock
````

Lane V proved clean-only audit reporting:

```text
CLEAN_MEMORY only
CLEAN_DATA only
do_not_train = 0 only
WINDOW_5M_MICRO_EVENT excluded as main retrieval memory
retrieval_activation = false
no DB writes
no paper decisions
no BUY/SELL/HOLD
no positions
no PnL
```

Lane W audited memory-growth automation readiness and found:

* 15m single-token memory is fully implemented and proven.
* Discovery framework is solid but manual-only.
* Token selection is memory-value based and auditable.
* Token/pair dedup exists.
* Post-cycle cooldown/archive/rotation are defined but not wired.
* Multi-token tracking is **NOT READY** because E2J/E2I still enforce exactly one TRACK_FAST token.
* Scheduler job kinds and priority exist, but multi-token tracking is not exercised.
* Source Governor exists and limits are defined, but there is no runner-level source-budget/backoff gate.
* One-command automation is **NOT_READY**.
* 5m support is partially implemented but not wired into the bounded loop.
* 1h/4h/12h/24h are documentation-only/blocked until 15m multi-token is proven.

Therefore, the next path should focus on memory growth first, but in controlled steps.

---

# Proposed Build Order

## Lane X1 — Multi-Token 15m Readiness Review

**Type:** documentation/review only.

### Goal

Design the safest way to move from one active TRACK_FAST token to two or three active tokens.

### Allowed

* inspect `_load_and_validate_token_list`
* inspect Lane U runner assumptions
* design a multi-token token-list shape
* design 2-token and 3-token snapshot rotation
* define accepted TRACK_FAST/TRACK_NORMAL combinations
* define source-budget expectations
* define stop conditions
* define test/proof requirements for Lane X2

### Not allowed

* code changes
* runtime behavior changes
* source fetching
* memory mutation
* retrieval activation
* paper decisions
* BUY / SELL / HOLD
* positions
* PnL

### Exit gate

A written readiness design exists for exactly 2-token `WINDOW_15M` tracking, with clear limits and no ambiguity.

---

## Lane X2 — 2-Token Controlled 15m Proof

**Type:** implementation + proof.

### Goal

Allow exactly two operator-approved TRACK_FAST tokens in a bounded 15m Memory Factory run.

### Required behavior

* token list validator accepts exactly two approved TRACK_FAST tokens
* runner rotates snapshots between the two tokens
* each token gets its own valid 15m evidence windows
* Lane U2 audits coverage/gaps per token/pair
* E2Y groups candidates per token/pair
* E2Z creates clean episodes only for qualifying same-token/same-pair groups
* no token/pair mixing
* replay remains idempotent

### Limits

* `max_active_tokens = 2`
* `WINDOW_15M` main only
* `WINDOW_5M_MICRO_EVENT` remains support-only and not required for this lane
* no discovery automation
* no paper decisions
* no BUY / SELL / HOLD
* no positions
* no PnL

### Exit gate

A real isolated proof DB shows two-token tracking works or fails honestly, with all locks preserved.

---

## Lane X3 — Post-Cycle Cooldown / Archive / Rotation Wiring

**Type:** implementation + tests.

### Goal

Prevent Printer from tracking the same stale token/pair forever after it already produced enough memory.

### Required behavior

* wire `ENTER_COOLDOWN` after completed window/memory criteria
* wire `ARCHIVE_AFTER_MEMORY_WINDOW` where appropriate
* avoid re-selecting the same stale token/pair immediately
* allow intentional revival/reopen later
* record lifecycle events for cooldown/archive/reopen
* preserve old dirty/audit-only memory without blocking new evidence

### Not allowed

* discovery as alpha
* BUY / SELL / HOLD
* paper decisions
* positions
* PnL

### Exit gate

A token/pair that completes a memory cycle can be cooled down or archived intentionally, and tracking can rotate to a fresh candidate.

---

## Lane X4 — 3-Token Controlled 15m Proof

**Type:** implementation + proof.

### Goal

Expand from two active tokens to three active tokens.

### Required behavior

* three active tokens can be tracked in one bounded run
* scheduler rotation does not starve any token
* each token receives enough snapshots for coverage
* coverage/gap audit remains per token/pair
* E2Y/E2Z do not mix tokens or pairs
* source failures remain acceptable
* dirty windows stay blocked

### Exit gate

Three-token `WINDOW_15M` tracking is proven in an isolated DB with locks preserved.

---

## Lane X5 — 5-Token Controlled 15m Proof + Source Budget Gate

**Type:** implementation + proof.

### Goal

Expand to five active tokens only after two-token and three-token proofs pass.

### Required behavior

* source budget monitoring exists or is proven sufficient
* runner stops safely on rate-limit/source-failure risk
* snapshot gaps are measured per token
* clean/dirty yield is reported
* no dirty memory becomes retrievable
* no paper/retrieval/BUY/position/PnL unlock

### Exit gate

Five-token bounded 15m run completes or stops safely, with clear source budget reporting.

---

## Lane X6 — Discovery / Selection / Dedup Repair

**Type:** implementation + tests.

### Goal

Make discovery and selection reliable enough for memory growth without repeatedly selecting the same stale set.

### Required behavior

* discovery remains intake, not alpha
* selection remains memory-value based, not BUY-probability based
* mint-level dedup works
* pair-level dedup works
* same token/new pair is handled explicitly
* cooldown-aware selection prevents stale recycling
* rotation includes a useful memory diet:

  * pumps
  * dumps
  * fake pumps
  * wick-only moves
  * late-buy traps
  * liquidity decay
  * dead tokens
  * revivals
  * ambiguous cases
* selection reasons remain auditable

### Not allowed

* direct paper BUY
* scoring/ranking/confidence
* discovery acting as a trade signal

### Exit gate

Discovery/selection can produce a fresh, useful, non-duplicate Solana memecoin tracking set for bounded memory growth.

---

## Lane X7 — Bounded Discovery-to-Tracking Review

**Type:** documentation/review only.

### Goal

Decide whether `printer-discover-candidates-once` can safely feed a bounded Memory Factory run.

### Questions

* Can discovery run inside a bounded operator command?
* How many new candidates are safe per run?
* What remains manual/operator-approved?
* How do WATCH_ONLY candidates promote?
* How do stale tokens demote or archive?
* What source budget is needed?
* What stop conditions apply?

### Exit gate

A safe design exists for discovery-to-tracking automation, but automation is not yet enabled.

---

## Lane X8 — 5m Support Evidence Integration

**Type:** implementation + proof.

### Goal

Wire `WINDOW_5M_MICRO_EVENT` as support-only evidence inside bounded 15m runs.

### Required behavior

* 5m support can be captured
* 5m support can link to 15m windows
* 5m never becomes main clean memory
* 5m never unlocks retrieval by itself
* 5m never unlocks paper decisions
* 5m never unlocks BUY/SELL/HOLD
* 5m never opens positions
* 5m never creates PnL
* Lane V continues excluding 5m support-only from main retrieval

### Exit gate

5m support evidence enriches 15m memory without replacing it.

---

## Lane X9 — 6h Conservative 15m Memory Growth Run

**Type:** bounded operator proof.

### Goal

Run the first serious memory-growth cycle after multi-token, cooldown, discovery/selection, source budget, and 5m support readiness are proven.

### Conservative starting config

```text
duration: 6h
active tokens: 3–5 first, not 10 immediately
main window: WINDOW_15M
support window: WINDOW_5M_MICRO_EVENT only if X8 passed
1h/4h/12h/24h: disabled
paper decisions: off
BUY/SELL/HOLD: locked
positions: locked
PnL: locked
```

### Required report

* discovered tokens
* selected tokens
* tracked tokens
* windows attempted
* clean memories created
* dirty/audit-only windows
* source failures
* coverage failures
* pair switches
* cooldown/archive events
* clean-memory yield per hour
* all locks

### Exit gate

A 6h bounded run grows clean memory without memory pollution or financial/retrieval unlock.

---

## Lane X10 — Memory Growth Reporting / Yield Dashboard

**Type:** reporting only.

### Goal

Give the operator a clear view of memory growth quality.

### Report fields

* discovered token count
* selected token count
* active tracked token count
* WATCH_ONLY count
* TRACK_FAST count
* TRACK_NORMAL count
* windows attempted
* windows completed
* clean memories created
* dirty/audit-only memory count
* coverage blocked count
* source failure count
* clean yield rate
* dirty ratio
* pair switch count
* cooldown/archive count
* all locked-state fields

### Not allowed

* scoring
* ranking
* confidence
* BUY/SELL/HOLD
* paper decision creation
* retrieval activation

---

## Lane X11 — 1h Activation Readiness

**Type:** documentation/review only.

### Goal

Prepare real 1h memory only after 15m multi-token stability.

### Required review

* 1h snapshot cadence
* 1h coverage/gap thresholds
* source budget
* stop conditions
* dirty-memory gates
* memory-window identity
* replay/idempotency rules

### Not allowed

* fake 1h from 15m
* real 1h runtime before approval
* BUY/SELL/HOLD
* paper decisions
* positions
* PnL

### Exit gate

A safe 1h proof plan exists.

---

## Lane X12 — Bounded 1h Proof

**Type:** implementation + proof.

### Goal

Collect real `WINDOW_1H` memory from a bounded run.

### Limits

* start with one token
* 15m remains active/stable
* 4h/12h/24h remain disabled
* no fake long-window data
* all locks preserved

### Exit gate

At least one real 1h memory proof exists or fails honestly, with dirty data blocked.

---

## Lane X13 — 4h Activation Readiness

Documentation/review only.

No real 4h run until 1h is proven.

---

## Lane X14 — Bounded 4h Proof

Real 4h proof only after X13 approval.

---

## Lane X15 — 12h Activation Readiness

Documentation/review only.

No real 12h run until 4h is proven.

---

## Lane X16 — Bounded 12h Proof

Real 12h proof only after X15 approval.

---

## Lane X17 — 24h Activation Readiness

Documentation/review only.

No real 24h run until 12h is proven.

---

## Lane X18 — Bounded 24h Proof

Real 24h proof only after X17 approval.

---

## Later lanes, not immediate

These lanes must remain later and separate:

* clean-memory retrieval reporting revisit
* conservative paper decision review
* WAIT / AVOID / NO_ACTION only
* BUY unlock preconditions review
* paper BUY unlock only by explicit future approval
* paper position reactivation review only after valid clean-memory-backed BUY exists

---

# Adoption Process

This document remains proposed until the operator explicitly approves it.

Adoption requires:

1. operator review
2. requested edits if needed
3. explicit operator approval
4. optional commit/tag of this proposed doc
5. separate AGENTS.md update only after approval
6. clear active-roadmap anchor

Until that happens, this document is only a proposal.

---

# Recommended Immediate Next Lane If Adopted

If this proposed build order is adopted, the immediate next active lane should be:

```text
Lane X1 — Multi-Token 15m Readiness Review
```

Reason:

The Lane W audit found that single-token 15m memory is proven, but multi-token tracking is not ready because the runner still enforces exactly one TRACK_FAST token at the E2J/E2I level.

---

# Final Reminder

Memory growth is the foundation of Printer.

But memory growth must not become:

* unbounded autonomous operation
* discovery-as-alpha
* BUY logic
* position logic
* PnL logic
* dirty-memory training
* fake long-window memory
* score/ranking/confidence logic

The goal is controlled, repeatable, clean Solana memecoin memory growth.
