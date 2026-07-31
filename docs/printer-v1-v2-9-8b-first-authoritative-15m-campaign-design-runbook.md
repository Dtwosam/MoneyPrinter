# Printer V1 V2-9.8B First Authoritative WINDOW_15M Campaign Design and Operator Runbook

Date: 2026-07-30

Design baseline:
`8be6c458859d0a16d75e714b36191bc4a9d31257`

Design verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_DESIGN_PASS`

Implementation decision:
`NO_IMPLEMENTATION_CHANGE_REQUIRED`

## 1. Boundary

This lane is design/specification only. It does not authorize or execute a
campaign, provider/RPC request, source fetch, database mutation, snapshot,
window, memory, retrieval, paper decision, position, trade, audit, PnL, N2, N7,
recovery, cursor reset, another 1h proof, or longer-window work.

The existing committed public command remains the implementation owner:

```text
printer-run-v2-9-8-memory-factory
```

No wrapper, alternative scheduler, source loop, database authority, retry loop,
or campaign runner is introduced.

## 2. Campaign Purpose

The first authoritative campaign exists to grow the persistent paper-only corpus
through exactly one bounded ordinary `WINDOW_15M` campaign while preserving
source ownership, Scheduler ownership, evidence quality, terminal accounting,
and all retrieval and financial locks.

It is not intended to prove profitability, activate retrieval, produce a paper
decision, or unlock BUY/SELL/HOLD.

## 3. Fixed Operational Envelope

The first campaign is fixed to:

- one operator-approved campaign;
- one cycle;
- exactly two active token slots;
- ordinary `run` mode only;
- `WINDOW_15M` as the only main outcome window;
- `WINDOW_5M_MICRO_EVENT` as support-only;
- 1,200 seconds maximum campaign duration;
- two discovery requests maximum;
- 65 governed 15m requests maximum;
- 21 governed requests per token maximum;
- 51 Scheduler rows maximum;
- 45 admission operations maximum;
- 64 MiB storage ceiling;
- 20 source-failure ceiling;
- zero automatic retries;
- zero automatic restart;
- zero successor campaign.

`WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` remain locked.
Candidate-acquisition N2/N7, global cursors, recovery, and backfill remain
deferred and are not operational prerequisites.

## 4. Authority and Ownership

The campaign must use:

```text
public operational command
-> fresh activation preflight
-> canonical pre-campaign backup and restore rehearsal
-> proven two-token operational discovery/selection
-> exact tracking handoff
-> Source Governor
-> Central Scheduler
-> two isolated WINDOW_15M lifecycles
-> clean/dirty/blocked audit
-> terminal accounting and report
-> deterministic report-only replay
-> safe stop with no successor
```

No engine may call a source outside Source Governor. No runtime owner may bypass
Central Scheduler. Aggregator evidence must not replace exact token/pair,
liquidity, freshness, holder, safety, or tradeability requirements.

## 5. Environment Contract

The operator may load:

```text
$HOME/.config/printer-v1/secrets.env
```

Only environment-variable names may appear in logs or closeout documentation.
Secret values must never be printed, copied into the repository, included in a
report, or pasted into chat.

Relevant variables are:

- `PRINTER_SOLANA_RPC_URL` — optional approved HTTPS RPC endpoint; the command may
  use the bounded official public fallback when absent;
- `PRINTER_HELIUS_API_KEY` — optional free-tier holder backup only.

A placeholder, malformed, non-HTTPS, wallet, private-key, signing, funding,
metered trade stream, paid dependency, or execution endpoint is a stop condition.

## 6. Required Final Preflight

A fresh `preflight-only` invocation must run immediately before the one campaign
attempt from the exact commit later pinned by the final authorization review.

Canonical command shape:

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  preflight-only
```

Required result:

```text
status: V2_9_8_OPERATIONAL_PREFLIGHT_READY
exit code: 0
source_calls: 0
scheduler_runtime_calls: 0
database_writes: 0
```

The preflight must also confirm:

- clean synchronized Git state;
- exact authoritative DB target `data/printer_v1.sqlite3`;
- no WAL, SHM, or journal sidecar;
- canonical migration ledger and head;
- database integrity `ok` and zero foreign-key violations;
- zero active campaigns, runs, supervision, Scheduler jobs/locks, discovery work,
  factory steps, and proof supervision;
- preserved locked-capability baseline;
- source and dependency contract readiness;
- bounded holder/source budget readiness;
- no secret material recorded.

Any failed gate ends the attempt before runtime. It does not authorize repair or
rerun inside the same lane.

## 7. One-Attempt Guard

Before the campaign command is invoked, the final authorized operator packet
must create one external attempt marker under:

```text
$HOME/PrinterOperations/v2-9-8/
```

The marker must record only:

- authorization verdict;
- exact Git commit;
- UTC timestamp;
- authoritative DB SHA-256 from the final preflight;
- statement that this is the first authoritative `WINDOW_15M` attempt.

If the marker already exists, the campaign command must not run. The marker is
created after final preflight PASS and immediately before command invocation.
It is never removed to permit a retry.

The command itself remains responsible for its unique execution directory,
verified pre-campaign backup, disposable restore rehearsal, reports, and runtime
identities.

## 8. Exact Campaign Command Shape

The only campaign command is:

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  run --operator-approved
```

It must run once, in the foreground, from the repository root. Its combined
stdout/stderr and exit code must be captured outside the repository.

The operator must not invoke:

- `discovery-only`;
- `selective-1h-preflight`;
- `selective-1h-proof`;
- `recover-orphan`;
- any V2-9 proof launcher;
- any legacy or lane-specific runner;
- a second `run` command.

## 9. Operator Checkpoints

### Checkpoint A — Before invocation

Confirm final authorization PASS, exact pinned commit, clean Git state, fresh
preflight PASS, DB hash, absence of attempt marker, and no active runtime.

### Checkpoint B — Immediately after invocation

Create the attempt marker and invoke the command exactly once. Do not edit code,
change branches, pull, commit, source a different environment file, or launch a
second campaign while it is active.

### Checkpoint C — During the bounded campaign

Observe only. Do not manually fetch sources, manipulate Scheduler rows, change
token selection, modify the DB, or restart failed work.

If the foreground command has not terminalized after the 1,200-second campaign
ceiling plus a small closeout allowance, use `status` from a second terminal.
If an operator stop is required while supervision is still active, use exactly
one canonical cooperative stop:

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  cooperative-stop --operator-approved
```

Do not kill the process first. Do not invoke recovery automatically.

### Checkpoint D — After terminal exit

Record the command exit code and preserve all output. Never invoke `run` again,
regardless of PASS, honest shortage, provider failure, budget exhaustion,
accounting block, interruption, or operator mistake.

Run the zero-source auxiliary checks once:

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  status

PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  report-only

PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  preflight-only
```

These checks must be captured with their exit codes. They do not authorize a
successor.

## 10. Required Evidence Package

The campaign closeout must receive:

1. exact Git HEAD and clean/synchronized status before launch;
2. final preflight JSON and exit code;
3. authoritative DB SHA-256 before launch;
4. one-attempt marker;
5. campaign stdout/stderr and exit code;
6. canonical application execution directory identity;
7. pre-campaign backup and restore-rehearsal evidence;
8. terminal campaign report;
9. `status` output;
10. deterministic `report-only` output;
11. post-terminal `preflight-only` output;
12. authoritative DB SHA-256 after terminalization;
13. migration head, integrity, and foreign-key result after terminalization;
14. source-operation and Scheduler totals;
15. candidate-observed, validated, eligible, and selected counts;
16. exact token/pair identities when lifecycle work starts;
17. main-window and evidence-quality outcomes;
18. clean, dirty, blocked, and `DO_NOT_TRAIN` reasons;
19. active/orphan work and lock counts;
20. restart/successor indicators;
21. retrieval and financial table deltas;
22. final Git status.

No secret value may appear in the evidence package.

## 11. Factual Outcome Classification

### Campaign PASS

A PASS requires all of the following:

- one authorized command invocation only;
- exactly two valid token/pair handoffs;
- two isolated completed `WINDOW_15M` lifecycle closeouts;
- trustworthy clean/dirty/blocked classification without forced clean memory;
- complete six-unit campaign accounting;
- terminal campaign/run/cycle/factory state;
- zero active or orphan Scheduler/runtime work;
- zero locked jobs or leases left by the attempt;
- deterministic zero-source report replay;
- valid backup/restore evidence;
- integrity `ok` and zero foreign-key violations;
- zero retrieval and financial deltas;
- no restart or successor.

Verdict:

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_PASS
```

### Honest BLOCKED outcome

Insufficient eligible supply, attributable provider failure, source-budget
exhaustion, or another bounded market/evidence shortage is BLOCKED rather than a
reason to retry. It is acceptable only when terminal accounting, preservation,
reporting, integrity, no-unlock deltas, and safe stop remain complete.

Verdict:

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED
```

The closeout must preserve the exact first terminal reason.

### Unsafe BLOCKED outcome

Incomplete accounting, missing terminal report, residual active work, database
integrity or foreign-key failure, history loss, unauthorized mutation, source or
Scheduler bypass, financial delta, restart, successor, or inability to determine
factual state is an unsafe BLOCKED result. It does not permit recovery or rerun
without a later dedicated audit and operator approval.

Verdict:

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE
```

## 12. Stop and No-Rerun Rules

Stop before launch on any failed preflight gate, changed Git commit, dirty tree,
wrong DB, sidecar, placeholder environment value, active residue, migration
mismatch, locked-capability drift, or missing final authorization.

After invocation:

- there is no retry;
- there is no replacement campaign;
- there is no discovery-only supplement;
- there is no cursor reset or recovery;
- there is no 1h continuation or proof;
- there is no capacity increase;
- there is no manual source fetch;
- there is no direct DB repair;
- there is no automatic next lane.

Any follow-up requires closeout and a new explicit operator-approved lane.

## 13. Closeout Requirements

The bounded campaign execution and closeout remain separate steps.

The closeout must:

- review the complete evidence package;
- reconcile every claimed count to durable evidence;
- preserve the first terminal reason;
- distinguish market shortage from provider failure;
- distinguish evidence quality from market outcome;
- confirm unrelated same-token and cross-campaign history preservation;
- confirm zero retrieval/decision/position/trade/audit/PnL delta;
- state what the campaign improved and what remains locked;
- document functionality risks, setbacks, and efficiency blockers;
- produce PASS, BLOCKED, or BLOCKED_UNSAFE without rerunning.

## 14. Money-Usefulness Contribution

This design gives Printer one controlled chance to add persistent, diverse,
paper-only 15m evidence without confusing source availability, token outcome, or
row count with useful memory. It protects prior learning evidence and preserves
honest negative outcomes, traps, shortages, and dirty reasons that matter for
future capital-protection decisions.

## 15. What This Design Improves

- fixes one campaign, one cycle, two-token, 15m-only scope;
- requires final preflight immediately before launch;
- prevents accidental rerun through an external attempt marker;
- defines operator checkpoints and cooperative stop behavior;
- defines the exact terminal evidence package;
- defines factual PASS/BLOCKED/BLOCKED_UNSAFE outcomes;
- keeps campaign execution separate from closeout.

## 16. What This Design Still Does Not Unlock

This design does not unlock campaign execution, provider/RPC calls, memory
generation, 1h/4h/12h/24h work, V2-10, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, paper-trade audits, PnL, wallets, private keys,
signing, real funds, paid APIs, scoring, ranking, confidence, weighting,
embeddings, or vectors.

## 17. Functionality Risks / Setbacks / Efficiency Blockers

- Free/public sources may fail or rate-limit, producing an honest BLOCKED result.
- Two eligible tokens may not be available inside the bounded source budget.
- Local environment configuration can drift after readiness and must be rechecked.
- The command and terminal report are large surfaces; closeout must remain
  evidence-driven rather than rely on the process exit code alone.
- An operator may be tempted to rerun after a shortage; the permanent attempt
  marker and explicit no-rerun rule prevent that shortcut.
- A terminal process failure can leave ambiguous state; ambiguity is
  BLOCKED_UNSAFE, not permission for direct repair.
- Runtime evidence is local rather than GitHub CI evidence and must be preserved
  carefully outside the repository.

## 18. Design Acceptance and Next Task

The existing implementation already satisfies the required command boundary and
passed the audit-only readiness gate. No implementation change is approved by
this design.

Design verdict:

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_DESIGN_PASS
```

Exact next permitted task:

```text
V2-9.8B First Authoritative WINDOW_15M Campaign Final Authorization Review
```

That review is read-only and documentation-only. It must pin the exact launch
commit, verify this runbook against the implementation and current operator
environment, confirm the one-attempt marker and evidence paths, and produce the
exact copy-paste command packet. Only an explicit final-authorization PASS may
authorize exactly one campaign attempt. It may not itself execute the campaign.
