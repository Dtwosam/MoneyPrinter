# Printer V1 Memory Growth Build Order

## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**ACTIVE SOURCE OF TRUTH.**

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
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
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
# Printer V1 Memory Growth Build Order

## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** documentation/review only.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Design the safest way to move from one active TRACK_FAST token to two or three active tokens.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* inspect `_load_and_validate_token_list`
* inspect Lane U runner assumptions
* design a multi-token token-list shape
* design 2-token and 3-token snapshot rotation
* define accepted TRACK_FAST/TRACK_NORMAL combinations
* define source-budget expectations
* define stop conditions
* define test/proof requirements for Lane X2
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* code changes
* runtime behavior changes
* source fetching
* memory mutation
* retrieval activation
* paper decisions
* BUY / SELL / HOLD
* positions
* PnL
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
A written readiness design exists for exactly 2-token `WINDOW_15M` tracking, with clear limits and no ambiguity.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** implementation + proof.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Allow exactly two operator-approved TRACK_FAST tokens in a bounded 15m Memory Factory run.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* token list validator accepts exactly two approved TRACK_FAST tokens
* runner rotates snapshots between the two tokens
* each token gets its own valid 15m evidence windows
* Lane U2 audits coverage/gaps per token/pair
* E2Y groups candidates per token/pair
* E2Z creates clean episodes only for qualifying same-token/same-pair groups
* no token/pair mixing
* replay remains idempotent
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* `max_active_tokens = 2`
* `WINDOW_15M` main only
* `WINDOW_5M_MICRO_EVENT` remains support-only and not required for this lane
* no discovery automation
* no paper decisions
* no BUY / SELL / HOLD
* no positions
* no PnL
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
A real isolated proof DB shows two-token tracking works or fails honestly, with all locks preserved.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** implementation + tests.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Prevent Printer from tracking the same stale token/pair forever after it already produced enough memory.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* wire `ENTER_COOLDOWN` after completed window/memory criteria
* wire `ARCHIVE_AFTER_MEMORY_WINDOW` where appropriate
* avoid re-selecting the same stale token/pair immediately
* allow intentional revival/reopen later
* record lifecycle events for cooldown/archive/reopen
* preserve old dirty/audit-only memory without blocking new evidence
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* discovery as alpha
* BUY / SELL / HOLD
* paper decisions
* positions
* PnL
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
A token/pair that completes a memory cycle can be cooled down or archived intentionally, and tracking can rotate to a fresh candidate.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** implementation + proof.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Expand from two active tokens to three active tokens.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* three active tokens can be tracked in one bounded run
* scheduler rotation does not starve any token
* each token receives enough snapshots for coverage
* coverage/gap audit remains per token/pair
* E2Y/E2Z do not mix tokens or pairs
* source failures remain acceptable
* dirty windows stay blocked
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Three-token `WINDOW_15M` tracking is proven in an isolated DB with locks preserved.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** implementation + proof.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Expand to five active tokens only after two-token and three-token proofs pass.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* source budget monitoring exists or is proven sufficient
* runner stops safely on rate-limit/source-failure risk
* snapshot gaps are measured per token
* clean/dirty yield is reported
* no dirty memory becomes retrievable
* no paper/retrieval/BUY/position/PnL unlock
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Five-token bounded 15m run completes or stops safely, with clear source budget reporting.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** implementation + tests.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Make discovery and selection reliable enough for memory growth without repeatedly selecting the same stale set.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
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
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* direct paper BUY
* scoring/ranking/confidence
* discovery acting as a trade signal
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Discovery/selection can produce a fresh, useful, non-duplicate Solana memecoin tracking set for bounded memory growth.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** documentation/review only.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Decide whether `printer-discover-candidates-once` can safely feed a bounded Memory Factory run.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* Can discovery run inside a bounded operator command?
* How many new candidates are safe per run?
* What remains manual/operator-approved?
* How do WATCH_ONLY candidates promote?
* How do stale tokens demote or archive?
* What source budget is needed?
* What stop conditions apply?
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
A safe design exists for discovery-to-tracking automation, but automation is not yet enabled.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** implementation + proof.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Wire `WINDOW_5M_MICRO_EVENT` as support-only evidence inside bounded 15m runs.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* 5m support can be captured
* 5m support can link to 15m windows
* 5m never becomes main clean memory
* 5m never unlocks retrieval by itself
* 5m never unlocks paper decisions
* 5m never unlocks BUY/SELL/HOLD
* 5m never opens positions
* 5m never creates PnL
* Lane V continues excluding 5m support-only from main retrieval
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
5m support evidence enriches 15m memory without replacing it.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** bounded operator proof.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Run the first serious memory-growth cycle after multi-token, cooldown, discovery/selection, source budget, and 5m support readiness are proven.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
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
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
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
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
A 6h bounded run grows clean memory without memory pollution or financial/retrieval unlock.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** reporting only.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Give the operator a clear view of memory growth quality.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
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
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* scoring
* ranking
* confidence
* BUY/SELL/HOLD
* paper decision creation
* retrieval activation

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** documentation/review only.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Prepare real 1h memory only after 15m multi-token stability.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* 1h snapshot cadence
* 1h coverage/gap thresholds
* source budget
* stop conditions
* dirty-memory gates
* memory-window identity
* replay/idempotency rules
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* fake 1h from 15m
* real 1h runtime before approval
* BUY/SELL/HOLD
* paper decisions
* positions
* PnL
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
A safe 1h proof plan exists.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
**Type:** implementation + proof.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Collect real `WINDOW_1H` memory from a bounded run.
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
* start with one token
* 15m remains active/stable
* 4h/12h/24h remain disabled
* no fake long-window data
* all locks preserved
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
At least one real 1h memory proof exists or fails honestly, with dirty data blocked.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Documentation/review only.

No real 4h run until 1h is proven.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Real 4h proof only after X13 approval.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Documentation/review only.

No real 12h run until 4h is proven.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Real 12h proof only after X15 approval.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Documentation/review only.

No real 24h run until 12h is proven.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
Real 24h proof only after X17 approval.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
These lanes must remain later and separate:

* clean-memory retrieval reporting revisit
* conservative paper decision review
* WAIT / AVOID / NO_ACTION only
* BUY unlock preconditions review
* paper BUY unlock only by explicit future approval
* paper position reactivation review only after valid clean-memory-backed BUY exists

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
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
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
If this proposed build order is adopted, the immediate next active lane should be:

```text
Lane X1 — Multi-Token 15m Readiness Review
```

Reason:

The Lane W audit found that single-token 15m memory is proven, but multi-token tracking is not ready because the runner still enforces exactly one TRACK_FAST token at the E2J/E2I level.

---
# Printer V1 Memory Growth Build Order


## Adoption Status

ACTIVE SOURCE OF TRUTH after this document and AGENTS.md are committed and tagged.

Created from historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Required supporting audit/readiness source:

- docs/printer-v1-memory-growth-automation-audit.md

Current active memory-growth lane after adoption:

- Lane X1 — Multi-Token 15m Readiness Review

The Memory Growth Automation Audit is a required supporting audit/readiness source. It is not the active lane-order document.

This adoption does not unlock retrieval, paper decisions, BUY, SELL, HOLD, paper positions, PnL, live execution, wallet logic, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, vectors, or dirty-memory decision support.

WINDOW_5M_MICRO_EVENT remains support-only and must never become a main outcome memory window or unlock retrieval, paper decisions, BUY, positions, or PnL by itself.
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

