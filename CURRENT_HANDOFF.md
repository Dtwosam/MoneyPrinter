# Printer V1 Handoff

## Current implementation

Branch: `assistant/terminal-only-expired-orphan-reconciliation`.

This branch is design-only. It is based on the fully verified four-token
Standard-4H operational anchor
`4403d8e7215a25c055a229497fc05163a9411d98` and currently contains the approved
terminal-only expired-orphan reconciliation design at:

`docs/superpowers/specs/2026-09-10-terminal-only-expired-orphan-reconciliation-design.md`

No production runtime code has been changed in this lane yet.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor
remains the sole governed source-request owner and Central Scheduler remains the
sole Scheduler owner. Retrieval, decisions, positions, PnL, signing, wallets and
live trading remain locked. `WINDOW_5M_MICRO_EVENT` is support-only;
`WINDOW_12H` and `WINDOW_24H` remain locked.

The verified 4/2/2 path still proves exactly two Cycle-1 slots plus a fresh,
disjoint two-slot Cycle 2 can progress through owned
`WINDOW_15M -> WINDOW_1H -> WINDOW_4H` lifecycles and, when governed evidence is
clean, form four exact clean 4h episode/fingerprint pairs. The pre-consumption
four-token composition preflight remains intact.

## Latest meaningful result

A targeted host/process continuity and governed provider-failure audit found no
second deterministic provider/RPC blocker: graceful live transport and lease
failures already flow through the child-owned terminal coordinator and fail
closed.

The audit did prove one architectural operational-resilience gap. If the
one-shot child or host terminates abruptly after authorization consumption,
Python cleanup handlers may never execute. The authoritative database can then
retain nonterminal campaign/run/cycle/supervision/factory/Scheduler ownership.
Lease expiry alone does not terminalize those rows, while the next four-token
zero-state gate correctly refuses any nonzero active ownership.

The existing `recover-orphan` path cannot solve this generically because it is
intentionally hard-bound to one historical execution and exact historical
hashes.

The approved design introduces a separate, explicit terminal-only recovery
authority for the exact operational `four-token-standard-four-hour-run` mode. It
uses read-only exact orphan inspection plus a stable inspection SHA, proves the
original consumed/non-reusable authorization facts, process absence, expired
exact lease ownership, database health, and lawful 4/2/2 admitted shape, creates
a verified pre-recovery backup, then delegates only to the existing terminal
reconciliation and supervision-cleanup owners.

The design explicitly forbids resume, retry, rerun, restart, successor creation,
source/provider/RPC calls, Scheduler execution, new lifecycle work, clean-memory
promotion, retrieval, decisions, financial actions, and 12h/24h unlocks.

No live provider/RPC execution, Scheduler operation, authoritative database
mutation, wallet/signing or trading operation was performed in this lane.

## Proven blocker

A consumed four-token Standard-4H run can become a durable expired orphan after
catastrophic child/host loss. The current code has no generic authorized
terminal-only closeout for that state, so the unchanged zero-state gate can
remain blocked indefinitely by truthful active residue.

This is not permission to resume the interrupted campaign. The consumed
campaign must remain permanently non-reusable and must terminalize as failed.

## Exact next permitted action

User review of
`docs/superpowers/specs/2026-09-10-terminal-only-expired-orphan-reconciliation-design.md`.

After explicit approval of that written spec, create the implementation plan via
the architectural planning workflow. Do not implement production code before
that approval. Do not run Printer operationally or mutate the authoritative
database without a separate explicit authorization for that exact operation.
