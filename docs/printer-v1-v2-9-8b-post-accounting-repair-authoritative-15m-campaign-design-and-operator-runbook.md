# Printer V1 V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Design and Operator Runbook

Date: 2026-07-31

Lane:
`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Design and Operator Runbook`

Branch:
`codex/v2-9-8b-post-repair-15m-campaign-design`

Baseline HEAD:
`d97a382ca831558173fdfa7c5da570d813e2c954`

Type: design/specification only. This document defines policy. It does not
execute, authorize execution, mutate the authoritative database, contact
providers, or unlock any capability.

Verdict:
`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_DESIGN_PASS`

## 0. Boundary

This lane is documentation/specification only.

Allowed work performed for this document:

- static source and documentation consistency review of the repaired ordinary
  `WINDOW_15M` route and its predecessor readiness audit, repair closeout, and
  first-campaign closeout;
- authorship of this design/runbook;
- documentation-only static checks (`git diff --check`, documentation diff
  inspection, risky-unlock language scan, repository status verification).

Not performed and not authorized by this document:

- preflight (`preflight-only`), campaign `run`, `report-only`, `status`,
  `cooperative-stop`, `recover-orphan`, `discovery-only`, or any other
  operational command mode;
- providers, RPC, WebSockets, or source fetching;
- authoritative database mutation or copy-back;
- recovery, N2, N7, cursor reset/advance, campaign, tracking, lifecycle,
  snapshot, window, or memory generation;
- July 31 execution `20260731T002406Z-7612696c7295` repair, rerun,
  reinterpretation, backfill, or reclassification;
- runtime code, test, migration, build-order anchor, or policy changes;
- `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H`, V2-10, retrieval,
  paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL unlock;
- campaign execution authorization of any kind.

This design document is not a launch authorization. The launch command in
Section 4 is intentionally rendered non-authorized: it must not be treated as
authorized for execution until a separate, later final-authorization lane passes
(Section 15). Reading, preparing, or rehearsing this runbook does not authorize
an attempt.

## 1. Post-Repair Campaign Identity Model

A later authorized post-repair attempt must run under a fresh, self-consistent
identity set that has no relationship to the July 31 attempt. No identity below
may be reused, rerun, repaired, or reinterpreted from execution
`20260731T002406Z-7612696c7295`.

### 1.1 New identity set (minted at authorized launch time)

| Identity | Shape | Rule |
| --- | --- | --- |
| `execution_id` | `<UTC compact timestamp>Z-<fresh random hex suffix>` | Newly minted at the authorized launch instant. Must not equal `20260731T002406Z-7612696c7295` or any historical execution id. |
| `campaign_id` | `<execution_id>-campaign` | Derived from the new execution id only. |
| `run_id` | `<execution_id>-campaign-run` | Derived from the new execution id only. |
| `cycle_id` | `<execution_id>-cycle` | Derived from the new execution id only. |
| `configuration_id` | fresh `_NORMAL_CAMPAIGN_POLICY` configuration identity for this attempt | Two-token / `WINDOW_15M` ordinary policy; not copied from a prior attempt row. |
| `supervision_id` | `<execution_id>-supervision` | Derived from the new execution id only. |
| `report_id` | canonical terminal report identity keyed to the new `campaign_id`/`run_id`/`configuration_id` | Written only when six-unit accounting is complete. |
| external artifact identity | `$HOME/PrinterOperations/v2-9-8/<execution_id>/` | New per-attempt directory; must not be the July 31 directory. |

### 1.2 Non-reuse invariants

- The new attempt must **generate** its identity set at launch; it must never
  read, adopt, edit, or continue July 31 rows, artifacts, cursors, or reports.
- No successor/restart/resume/recovery relationship to July 31 may be created.
- No SQL or tooling may `UPDATE`, re-`INSERT`, or re-key any
  `20260731T002406Z-7612696c7295*` row.
- The historical July 31 campaign remains permanently
  `V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`, with campaign/run/
  cycle `TERMINAL_COMPLETED`, `first_terminal_cause = SOURCE_VISIBILITY_SHORTAGE`,
  zero report rows, and its incomplete terminal-summary identity untouched.

### 1.3 Permanent no-rerun marker preservation

The external permanent marker

```text
$HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json
```

with

```text
attempt_number: 1
attempt_scope: FIRST_AUTHORITATIVE_WINDOW_15M_CAMPAIGN
authorized_git_commit: b5761b6501ad757eecdfc8cfabce6828d5a899bd
rerun_authorized: false
```

must remain byte-identical (SHA-256
`dd079f82a361aa2364b4142384a0b472698759a861a507539939aab839011564`). It must not
be deleted, edited, moved, or reused as a shortcut for a second attempt. Its
`rerun_authorized=false` marker is a permanent boundary on the July 31 execution
identity, not a gate the post-repair attempt may satisfy or bypass.

A post-repair attempt, if ever authorized, must create its **own** attempt
marker under its **own** `execution_id` scope (for example
`post-repair-authoritative-window-15m-attempt.json` with `attempt_number` scoped
to the post-repair series), and must never increment or overwrite the
first-authoritative marker.

## 2. Exact One-Campaign Boundary

- Exactly one authorized post-repair attempt is permitted once (and only once) a
  later final-authorization lane passes.
- No retry, restart, resume, recovery, successor, replacement, discovery-only
  supplement, or automatic second attempt is permitted before, during, or after
  that attempt.
- `AUTOMATIC_RETRIES = 0` (ordinary-path constant; must remain 0).
- Capacity is exactly two (`TOKEN_CAPACITY = 2`).
- Ordinary `WINDOW_15M` only (`MAIN_WINDOW = "WINDOW_15M"`,
  `fifteen_minute_only = True`; `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` /
  `WINDOW_24H` remain in `LOCKED_WINDOWS`).
- `TOTAL_DURATION_SECONDS = 1200` (single 15m-scale bounded attempt).
- Terminalization is final. If the attempt terminalizes for any reason
  (including honest shortage), the one-campaign boundary is consumed. Any further
  attempt requires a brand-new readiness -> design -> final-authorization
  sequence and a brand-new execution identity.

## 3. Fresh Preflight Packet

Preflight is read-only readiness verification. It must be run immediately before
any authorized attempt and must not be treated as authorization to launch. This
document does **not** run preflight.

### 3.1 Exact committed command and authoritative DB target

Preflight command shape (to be run only under the later authorized lane):

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  preflight-only
```

Equivalent published entrypoint: `printer-run-v2-9-8-memory-factory`
(module `printer_v1.operator_cli.operational_memory_factory_command:main`).

Authoritative DB target (single canonical DB):

```text
data/printer_v1.sqlite3
```

resolved via `AUTHORITATIVE_DB = Path(CANONICAL_PERSISTENT_DB).resolve()`.

### 3.2 Required environment-variable names (values never printed)

- required: `PRINTER_SOLANA_RPC_URL`
- optional free holder backup: `PRINTER_HELIUS_API_KEY`

Preflight must confirm that required names are **present and non-empty** without
exposing, logging, or committing their values. A missing or placeholder
(empty/whitespace/template) required variable is a stop condition (Section 8).

### 3.3 Clean Git and exact-HEAD checks

- working tree clean (`git status --porcelain` empty);
- HEAD equals the exact commit that the later final-authorization lane pins for
  this attempt;
- no uncommitted runtime/policy edits;
- branch is the operator-approved launch branch for the attempt.

### 3.4 Database identity and safety checks (read-only)

- DB SHA-256 recorded **before** the attempt (baseline expectation from the
  readiness audit:
  `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511`; the
  authorization lane must re-measure and pin the then-current value);
- migration head = `049_candidate_acquisition_integration.sql` (49 migration
  rows);
- `PRAGMA integrity_check = ok`;
- `PRAGMA foreign_key_check` returns zero rows;
- no WAL / SHM / journal sidecars under `data/` (only `printer_v1.sqlite3`);
- residual-state check: campaigns/runs/cycles/supervision all terminal; zero
  active/runnable rows.

### 3.5 Permanent-marker validation

- first-authoritative marker present, unmodified, `rerun_authorized=false`,
  SHA-256 unchanged;
- July 31 campaign/run/cycle terminal; July 31 report rows = 0; July 31
  terminal-summary artifact present and untouched.

### 3.6 Zero-active-state checks

- zero active supervision (`supervision_state != 'TERMINAL'` count = 0);
- zero active/locked Scheduler jobs (`status NOT IN
  ('SUCCEEDED','FAILED','CANCELLED')` = 0; `locked_at`/`lock_owner` all null/empty);
- zero non-terminal discovery work and factory steps;
- zero active/held candidate-acquisition leases;
- zero owned work after any prior terminalization;
- zero proof-run supervision rows.

### 3.7 Backup and disposable restore-rehearsal requirements

- take a verified byte-exact backup of `data/printer_v1.sqlite3` (record backup
  SHA-256 == pre-attempt DB SHA-256);
- perform a **disposable** restore rehearsal into a scratch/temporary path (never
  overwriting the authoritative DB) to confirm the backup restores and opens with
  matching migration head, integrity `ok`, and zero FK violations;
- the rehearsal DB must be discarded; it must never become the authoritative DB
  and must never be written back.

### 3.8 Explicit operator go/no-go checkpoint

After all of Section 3 passes, an explicit operator **go/no-go** checkpoint is
required. A NO-GO, or any failed/ambiguous preflight item, blocks the attempt and
routes to Section 8. Preflight PASS alone is **not** launch authorization; launch
still requires the Section 15 final-authorization lane.

## 4. Exact Launch Packet (Non-Authorized)

This section defines the exact launch shape. It is intentionally **not** an
authorization. The command below must not be treated as authorized for execution
until the Section 15 final-authorization lane passes.

### 4.1 Ordinary non-placeholder command

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  run --operator-approved
```

- ordinary `run` mode -> `run_operational_campaign` / `_run_operational_campaign`
  -> `AuthoritativeLiveOperationalCampaignOwner.run_operational(
  fifteen_minute_only=True, ...)`;
- `--operator-approved` flag required;
- capacity exactly two; `WINDOW_15M` only; `AUTOMATIC_RETRIES=0`.

### 4.2 Shell / environment loading sequence

1. open a clean shell in the repository root;
2. load the required environment contract (`PRINTER_SOLANA_RPC_URL`, optional
   `PRINTER_HELIUS_API_KEY`) from the operator's secret store, never from a
   committed file and never echoed;
3. confirm `.venv` is the intended interpreter;
4. set `PYTHONPATH=src`;
5. run the exact command in 4.1.

### 4.3 Expected working directory

```text
<repo root>/  (the MoneyPrinter worktree containing data/printer_v1.sqlite3)
```

### 4.4 Proof that no proof/recovery path is used

The ordinary `run` path must be proven, before launch, to:

- use `_NORMAL_CAMPAIGN_POLICY` and the authoritative operational owner (no proof
  DB launcher, no disposable-coordinator entrypoint);
- not invoke N2, N7, candidate-acquisition, cursor, cursor-recovery,
  `recover-orphan`, `selective-1h-*`, or `discovery-only` modes;
- keep candidate-acquisition state
  `DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY` and never read/reset/advance
  any candidate cursor or recovery row;
- target the authoritative `data/printer_v1.sqlite3` (not a proof DB).

### 4.5 Operator-approved flag and non-authorization

- the `--operator-approved` flag is a runtime precondition of the ordinary
  command, **not** the lane authorization;
- the launch command does not become authorized for execution merely because this
  runbook exists, because preflight passed, or because the flag is present;
- authorization exists only after the Section 15 final-authorization lane passes
  and pins the exact commit, DB SHA-256, environment contract, and one-attempt
  marker plan.

## 5. Runtime Observation Contract (For the Later Authorized Attempt)

If a later attempt is authorized and launched, the following observation contract
governs it. This document does not activate it.

- **Source Governor and Central Scheduler ownership:** all source access and all
  lifecycle scheduling flow through the Source Governor and Central Scheduler.
  No engine may open an independent API loop, scheduler, or DB authority.
- **Independent pre-seal transport observer:** the public coordinator installs
  exactly one verification-only `transport_identity_observer`. Each accepted
  transport fires `MeasuredTransportLedger.on_transport_recorded` **before** stage
  sealing, appending exact action-local transport identities. The observer is not
  a second accounting authority and never reconstructs missing stage evidence from
  SQLite rows.
- **Exact owner / action-local reconciliation:** pre-lifecycle completion requires
  exact identity-set equality (both directions) between the single
  `CampaignSixUnitOwner` and the independently observed action-local identities.
  Count-only surfaces stay blocked with
  `ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED`; any mismatch fails closed with
  accounting blocked and no synthetic evidence.
- **Stage sealing and first-cause preservation:** locator, direct-migration, and
  each exact-liquidity round seal/ingest exactly once on a `try/except/finally`
  path before any bounded or unexpected exception escapes. First terminal cause is
  preserved even if a later sink ingestion fails.
- **Exactly two-token selection/tracking boundary:** capacity is exactly two.
  Selection and atomic two-token tracking handoff persist auditable
  selection/rejection reasons and keep token/pair identities isolated.
- **Honest shortage as a terminal outcome:** an honest
  `SOURCE_VISIBILITY_SHORTAGE` (or equivalent honest insufficient-eligible-supply
  terminal) with complete, independently reconcilable stage evidence and a written
  terminal report is an **allowed** terminal outcome. Honest negative learning is
  a valid result, not a failure to be worked around.
- **No manual intervention during execution:** no DB edits, no source pokes, no
  scheduler nudging, no cursor operations. The only permitted operator action
  during execution is an approved **cooperative stop**.

## 6. Operator Checkpoints

Mandatory operator checkpoints for a later authorized attempt:

1. **Before launch** - after Section 3 preflight PASS and the Section 15
   authorization, confirm go/no-go one final time.
2. **After process start** - confirm exactly one process, correct DB target,
   supervision acquired, heartbeat/lease healthy, no proof/recovery mode.
3. **After discovery/selection terminalizes** - confirm exactly two selected (or
   an honest shortage) with persisted selection/rejection reasons and isolated
   identities.
4. **Before accepting any lifecycle result** - confirm stage evidence is complete
   and independently reconciled before trusting any window/memory outcome.
5. **At final terminalization** - confirm terminal cause, supervision terminal,
   lease released, zero active residue, `AUTOMATIC_RETRIES=0`, no
   restart/successor/resume.
6. **Before any report-only replay** - confirm exact `campaign_id`/`run_id`
   identity so replay cannot select a stale historical report.

Any checkpoint failure routes to Section 8 and, if terminal, to Section 9.

## 7. Terminal Evidence Bundle

A later authorized attempt is not accepted until the operator packet contains all
of the following:

1. exact launch command and exact HEAD commit;
2. execution identities (`execution_id`, `campaign_id`, `run_id`, `cycle_id`,
   `configuration_id`, `supervision_id`, `report_id`);
3. authoritative DB SHA-256 **before** and **after**;
4. source-operation accounting and Central Scheduler accounting (calls, budgets,
   remaining);
5. stage identity reconciliation and action-local identity reconciliation
   (owner/action-local equality result);
6. selected and rejected candidates with exact reasons;
7. lifecycle / window / memory outcomes (clean / dirty / blocked /
   `DO_NOT_TRAIN`), with `WINDOW_15M`-only scope;
8. terminal summary and the exact terminal report identity (or a deterministic
   blocked-replay result if no report was written);
9. supervision state, cleanup completion, lease state, lock state, and owned-work
   count after terminalization (all must be terminal/released/zero);
10. report-only exact-identity replay result (zero-source, zero-Scheduler,
    zero-write);
11. retrieval and financial row deltas (must be zero: retrieval matches,
    retrieval queries, paper decisions, paper audit reports, positions, trade
    events, trade audits);
12. external artifact hashes (per-attempt terminal-summary, exhaustion certificate
    if any, and the new attempt marker), plus confirmation the first-authoritative
    marker SHA-256 is unchanged.

An attempt whose bundle is incomplete cannot be accepted as PASS; it is BLOCKED or
BLOCKED_UNSAFE per Section 9.

## 8. Stop Conditions

Stop (do not launch) or terminalize-and-block if any of the following occur:

- failed or ambiguous preflight;
- wrong DB target or wrong/placeholder command;
- missing or placeholder environment contract (required variable absent/empty);
- active residue (non-terminal campaign/run/supervision, active/locked Scheduler
  jobs, active leases, owned work, proof supervision, or sidecar files);
- accounting mismatch (owner vs action-local identity inequality; count-only
  surfaces; six-unit evidence incomplete);
- incomplete stage evidence (any stage unsealed or unreconciled);
- unexpected retry, restart, resume, successor, or automatic second attempt;
- provider/source ceiling reached in a way that prevents complete, honest,
  reconcilable accounting;
- token/pair identity conflict (duplicate, drift, or cross-contamination);
- unsafe lifecycle state (dirty promoted clean, window not closing, scheduler
  pileup);
- any retrieval or financial row delta;
- any attempt to touch, rerun, repair, reinterpret, or reference-as-authority the
  July 31 execution `20260731T002406Z-7612696c7295` or its permanent marker.

## 9. Closeout Requirements

A later authorized attempt closes with exactly one verdict.

### 9.1 PASS

- exactly one authorized attempt ran;
- complete terminal evidence bundle (Section 7);
- exact owner/action-local reconciliation succeeded;
- a canonical terminal report was written under the new identity, or an honest
  shortage terminalized with complete, reconcilable stage evidence **and** a
  written honest terminal report;
- authoritative DB integrity/migration/FK intact; before/after SHA-256 recorded;
- all retrieval/financial deltas zero;
- supervision terminal, lease released, zero residue, `AUTOMATIC_RETRIES=0`, no
  restart/successor/resume;
- first-authoritative marker unchanged; new per-attempt marker created honestly.

### 9.2 Honest BLOCKED

- the attempt (or preflight) stopped honestly at a defined stop condition without
  producing usable clean memory, but preserved all safety properties, produced no
  false report, made no unauthorized mutation, and left zero active residue;
- honest source shortage/ceiling with complete accounting but no clean memory is a
  legitimate BLOCKED (or, if all stage evidence and report are complete, may be a
  PASS with an honest-shortage terminal report per 9.1);
- closeout records the exact blocker, evidence, and that no rerun is authorized
  without a fresh sequence.

### 9.3 BLOCKED_UNSAFE

- the attempt reached a state where terminal accounting/reporting is incomplete or
  cannot be trusted (as with July 31), or any safety property is uncertain;
- no synthetic report, no DB repair, no report fabrication is permitted;
- a permanent no-rerun marker for the attempt's execution identity is created;
- closeout records the exact defect and routes to a read-only forensic audit lane,
  never to an automatic rerun.

All three outcomes require: money-usefulness contribution, what improved, what
remains locked, `Functionality Risks / Setbacks / Efficiency Blockers`, and the
exact next permitted lane.

## 10. Money-Usefulness Contribution

This design converts the post-accounting-repair readiness PASS into an executable
launch, observation, and closeout policy for a **single** bounded 15m learning
attempt. Its money-usefulness is defensive and preparatory:

- it makes a future bounded 15m attempt safe to attempt exactly once, so Printer
  can grow honest clean `WINDOW_15M` memory (or record honest negative learning)
  without corrupting the authoritative corpus;
- it prevents a repeat of the July 31 failure mode (governed source budget spent
  while terminal accounting/reporting is incomplete and a stale report is
  surfaced) by requiring independent pre-seal observation, exact reconciliation,
  and exact-identity report-only replay before any result is accepted;
- it keeps honest shortage a first-class outcome, so the machine is not pressured
  into fake profit, fake memory, or forced attempts.

It makes no profit claim and creates no financial capability.

## 11. What This Design Improves

- gives an operator an executable identity, preflight, launch, observation,
  checkpoint, evidence, stop, and closeout policy that does not require inventing
  any of those on the spot;
- pins a fresh non-reused identity model and a strict one-campaign boundary;
- makes the July 31 no-rerun boundary and permanent marker explicit and
  inviolable;
- ties acceptance to the repaired accounting/exact-identity contract rather than
  to raw exit codes or row counts;
- defines honest BLOCKED / BLOCKED_UNSAFE closeouts so a bad attempt cannot be
  laundered into a PASS.

## 12. What This Design Still Does Not Unlock

It does not unlock:

- campaign execution or execution authorization;
- providers, RPC, WebSockets, or source fetching;
- July 31 repair, rerun, backfill, or reclassification;
- recovery, N2, N7, cursor reset/advance, or candidate-acquisition authority;
- memory generation or clean-memory promotion (those only occur inside a later
  authorized attempt, not from this document);
- `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H`;
- V2-10;
- retrieval;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

## 13. Proof Required Before Completion

For this design lane (documentation-only):

- source/document consistency review against `AGENTS.md`, the Clean Master Spec,
  the memory-growth build order V2, the memory factory guide, the assistant
  anchor, the readiness audit, the accounting/exact-identity repair closeout, and
  the first-authoritative campaign closeout - **done**;
- risky-unlock language scan - **done** (no unlock/authorize-execution wording);
- `git diff --check` - **done** (no whitespace/conflict errors);
- documentation diff inspection - **done** (single new design file);
- repository status verification - **done** (only the new design file staged).

Proof required later, before any attempt (not part of this lane): fresh Section 3
preflight PASS and a passing Section 15 final-authorization lane.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

- **Provider availability / eligible supply unproven.** Two-token eligible supply
  cannot be guaranteed until an authorized live attempt; honest shortage remains a
  likely and allowed terminal outcome. Mitigation: honest-shortage terminal path
  and complete accounting requirements.
- **Environment drift.** Environment values may drift after this design; a fresh
  zero-source preflight and env-name presence check are mandatory before launch.
- **Post-lifecycle identity gate residual.** Holder/scheduler stages after
  lifecycle start are outside the pre-lifecycle action-local identity gate (repair
  residual). If a future attempt requires full-run transport equality beyond
  pre-lifecycle shortage terminals, an explicit sealed-stage design lane is needed
  first.
- **Historical residue confusion.** The authoritative DB holds terminal history
  (18 terminal campaigns/runs, terminal leases, July 31 rows). Preflight must keep
  distinguishing terminal history from active residue.
- **Marker-shortcut temptation.** The first-authoritative marker must never be
  deleted/reused; a post-repair attempt needs its own marker.
- **Report-surface trust.** If accounting is incomplete, the exact-identity
  report-only path fails closed rather than surfacing a stale report - this is
  correct, but means an incomplete attempt yields BLOCKED/BLOCKED_UNSAFE, not a
  usable report.
- **One-shot cost.** Because capacity is one attempt with `AUTOMATIC_RETRIES=0`, a
  wasted attempt consumes the authorized boundary and forces a fresh
  readiness->design->authorization cycle.

## 15. Exact Next Permitted Lane

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Final Authorization
```

Type: final-authorization / go-no-go only (still not execution by default).

That lane must, before any launch:

- pin the exact launch commit and confirm clean Git and exact HEAD;
- run and record a fresh zero-source `preflight-only` PASS (Section 3);
- re-measure and pin the current authoritative DB SHA-256, migration head,
  integrity, and FK state;
- confirm the first-authoritative permanent marker is unchanged and define the new
  per-attempt marker plan;
- confirm zero active supervision/Scheduler/lease/owned-work residue;
- record an explicit operator go/no-go;
- only then, if PASS, authorize exactly one attempt of the Section 4 command under
  the Section 5 observation contract, the Section 6 checkpoints, and the Section 7
  evidence bundle.

It must not itself repair/rerun July 31, mutate the authoritative database,
contact providers/RPC/WebSockets/sources, run recovery/N2/N7/cursor operations,
change runtime/tests/migrations/policy, or unlock retrieval/financial capabilities.

Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL
remain locked.

## 16. Acceptance Gate

`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_DESIGN_PASS` because the
runbook is executable without inventing identity, preflight, launch, observation,
stop, or closeout policy:

- a fresh non-reused identity model and strict one-campaign boundary are defined;
- fresh preflight, exact non-placeholder command, DB target, and env names are
  defined;
- the launch command is explicitly non-authorized until a later final-authorization
  lane passes;
- the runtime observation contract, operator checkpoints, terminal evidence
  bundle, stop conditions, and PASS / honest BLOCKED / BLOCKED_UNSAFE closeouts are
  all specified;
- the July 31 no-rerun boundary and permanent marker are preserved and inviolable;
- no capability is unlocked and no execution is authorized by this document.
