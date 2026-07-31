# Printer V1 V2-9.8B First Authoritative WINDOW_15M Campaign Readiness Audit

Date: 2026-07-30

Reviewed baseline:
`1499eba543967488eef2ddf561764acdb316e501`

Verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_READINESS_PASS`

## Boundary

This was an audit/readiness lane only. It used static inspection of the committed
operational command plus operator-supplied output from the zero-source,
read-only `preflight-only` mode.

It did not run providers, RPC, WebSockets, a live probe, a Memory Factory
campaign, lifecycle collection, snapshots, windows, memory generation, N2, N7,
recovery, cursor reset, another 1h proof, longer-window work, retrieval, paper
decisions, positions, trades, audits, PnL, or any financial capability.

## Evidence Reviewed

- committed HEAD: `1499eba543967488eef2ddf561764acdb316e501`;
- clean and synchronized `master` worktree;
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- `src/printer_v1/operator_cli/readiness_source_contract_preflight.py`;
- `src/printer_v1/sources/operational_source_contracts.py`;
- `src/printer_v1/operator_cli/proof_db_schema_readiness.py`;
- `tests/test_v2_9_8b_operational_factory_active_path_restoration.py`;
- operator-supplied `preflight-only` output from the authoritative Mac checkout.

## Readiness Findings

1. The public operational command is
   `printer-run-v2-9-8-memory-factory` with `preflight-only`, `run`, `status`,
   `cooperative-stop`, `report-only`, and explicitly separate restricted modes.
2. Ordinary `run` fixes active capacity at exactly two tokens and the main window
   at `WINDOW_15M`.
3. `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` remain locked for the
   ordinary campaign.
4. `WINDOW_5M_MICRO_EVENT` remains support-only.
5. Automatic retries are zero; no restart or successor is created by preflight.
6. Candidate-acquisition N2/N7, global cursor, and recovery modes remain deferred
   and are not operational prerequisites or authorities.
7. The authoritative database target is fixed to
   `data/printer_v1.sqlite3`.
8. The preflight opened the database read-only, reported zero database writes,
   and preserved the exact SHA-256 before and after:
   `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`.
9. No SQLite WAL, SHM, or journal sidecar existed before preflight.
10. The canonical migration ledger matched all 49 migrations with head
    `049_candidate_acquisition_integration.sql`.
11. `PRAGMA integrity_check` returned `ok`; foreign-key violations were zero.
12. Active campaign, run, supervision, discovery-work, factory-step, Scheduler,
    Scheduler-lock, and proof-supervision counts were all zero.
13. Locked capability baselines remained exact:
    - retrieval matches: 0;
    - historical retrieval queries: 10;
    - historical paper decisions: 2;
    - historical paper audit reports: 1;
    - paper positions, trade events, and paper trade audits: 0.
14. Source-contract preflight returned `READY`, made zero external requests, and
    recorded no secret material.
15. The runtime dependency preflight passed with Python 3.12 and
    `websockets 16.1.1`, satisfying the required minimum.
16. The holder/source budget preflight returned `READY` with no issues and zero
    source calls.
17. Git provenance showed the tracked tree clean with no staged, unstaged, or
    untracked files.
18. The preflight exit code was 0 and the final Git state remained clean.

## Exact Command Shape Confirmed

Readiness command:

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  preflight-only
```

The future campaign command remains structurally:

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  run --operator-approved
```

This audit does not authorize running that campaign command.

## Money-Usefulness Contribution

The readiness gate reduces the chance that the first authoritative memory-growth
campaign starts with a dirty Git tree, wrong database, schema drift, active
Scheduler residue, broken dependencies, stale locks, source-owner bypass,
insufficient bounded budget, or pre-existing financial-state drift. This
protects the quality and auditability of future paper-only memory.

## What This Audit Improves

- confirms the authoritative campaign has one exact command and DB target;
- confirms two-token, 15m-only ordinary policy;
- confirms Source Governor and Central Scheduler ownership contracts;
- confirms zero-source and zero-write preflight behavior;
- confirms clean terminal starting state and preserved financial locks;
- establishes the evidence needed for campaign design/specification.

## What This Audit Still Does Not Unlock

It does not unlock campaign execution, provider/RPC calls, source fetching,
memory generation, 1h or longer windows, V2-10, retrieval, paper decisions,
BUY/SELL/HOLD, paper positions, trade events, paper-trade audits, PnL, wallets,
private keys, signing, real funds, paid APIs, scoring, ranking, confidence,
weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Runtime evidence was supplied from the operator's local Mac and is not attached
  to GitHub CI.
- A future design must define the exact one-campaign stop boundary, operator
  observation points, terminal evidence bundle, and no-rerun rule before launch.
- Environment values may change between readiness and execution; the final
  preflight must be rerun immediately before any approved campaign.
- A valid preflight does not prove providers will be available or that two
  eligible tokens will be found.
- Honest insufficient supply, provider failure, budget exhaustion, or terminal
  accounting failure must remain valid blocked outcomes rather than trigger an
  automatic retry.

## Acceptance Gate

The readiness audit passes because the exact committed, zero-source preflight
reported:

- status `V2_9_8_OPERATIONAL_PREFLIGHT_READY`;
- exit code 0;
- zero source calls;
- zero Scheduler runtime calls;
- zero database writes;
- unchanged authoritative DB hash;
- clean Git provenance;
- complete migration and integrity checks;
- zero active operational residue;
- preserved retrieval and financial locks.

## Exact Next Permitted Task

```text
V2-9.8B First Authoritative WINDOW_15M Campaign Design and Operator Runbook
```

That next task is design/specification only. It must define the exact launch
command, one-campaign boundary, preflight repetition, operator checkpoints,
terminal evidence, stop conditions, no-rerun policy, and closeout requirements.
It must not execute the campaign or contact sources.
