# Printer V1 V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Final Authorization

Date: 2026-07-31

Lane:
`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Final Authorization`

Branch:
`codex/v2-9-8b-post-repair-15m-final-authorization`

Type: final-authorization / go-no-go. This lane completes the final-authorization
checks and creates the post-repair authorization marker. It does **not** execute
a campaign, contact providers/RPC/WebSockets/sources, mutate the authoritative
database, repair July 31, or unlock any capability.

Verdict:
`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_FINAL_AUTHORIZATION_PASS`

## 0. Baseline and Exact Authorized Launch Commit

| Item | Value |
| --- | --- |
| Start point | `master` |
| Exact authorized launch commit | `444ed0191db2d9c50ad097e3f78607f423ef3e68` |
| Launch commit subject | `Repair post-repair 15m campaign design boundaries` |
| Authorization branch | `codex/v2-9-8b-post-repair-15m-final-authorization` |
| HEAD during all gates | `444ed0191db2d9c50ad097e3f78607f423ef3e68` (unchanged) |
| Worktree during all gates | clean (tracked/staged/unstaged/untracked all empty) |

All preflight and marker gates were performed while HEAD equalled
`444ed0191db2d9c50ad097e3f78607f423ef3e68` and the worktree was clean.

### 0.1 The documentation commit is NOT the launch commit

This final-authorization document and its commit are **evidence-only**. The
documentation commit:

- is not the authorized launch commit;
- is not the authorized launch;
- must not be merged into `master` before campaign execution;
- must not replace the marker's `authorized_git_commit`
  (`444ed0191db2d9c50ad097e3f78607f423ef3e68`).

A later authorized campaign, if this lane's PASS is exercised, must execute from
clean `master` at exactly `444ed0191db2d9c50ad097e3f78607f423ef3e68` — never from
this documentation commit or branch.

## 1. Critical Commit Sequencing (Honored)

- exact HEAD `444ed0191db2d9c50ad097e3f78607f423ef3e68` and clean state confirmed
  before preflight and before marker creation;
- the PASS marker was created **before** this documentation was written or
  committed;
- the documentation commit is separated from, and subordinate to, the marker's
  pinned launch commit.

## 2. Final Gate Results

### 2.1 State confirmation (before preflight)

| Gate | Result |
| --- | --- |
| Exact HEAD `444ed0191db2d9c50ad097e3f78607f423ef3e68` | PASS |
| Clean tracked/staged/unstaged/untracked state | PASS (`git status --porcelain` empty) |
| Authoritative DB is exactly `data/printer_v1.sqlite3` | PASS |
| Secrets file exists at `$HOME/.config/printer-v1/secrets.env` | PASS |
| No active Printer campaign process | PASS |
| No SQLite WAL / SHM / journal sidecars | PASS (only `printer_v1.sqlite3` under `data/`) |
| Post-repair authorization marker does not already exist | PASS (absent before creation) |

### 2.2 Authoritative DB SHA-256 recorded before preflight

```text
DB path:        data/printer_v1.sqlite3
DB SHA-256:     f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
```

This equals the readiness-audit expected hash
`f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511`. No
difference; not BLOCKED. The DB was not mutated at any point.

### 2.3 July 31 permanent marker verification

```text
path:    $HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json
SHA-256: dd079f82a361aa2364b4142384a0b472698759a861a507539939aab839011564  (required — matches)
```

Selected required fields (confirmed):

```text
attempt_number:        1
attempt_scope:         FIRST_AUTHORITATIVE_WINDOW_15M_CAMPAIGN
rerun_authorized:      false
authorized_git_commit: b5761b6501ad757eecdfc8cfabce6828d5a899bd
```

This marker was not edited or recreated. Its SHA-256 was re-verified after
post-repair marker creation and remained
`dd079f82a361aa2364b4142384a0b472698759a861a507539939aab839011564`.

### 2.4 Environment values loaded without printing

The operator loaded the environment immediately before the single preflight:

```bash
set -a
source "$HOME/.config/printer-v1/secrets.env"
set +a
```

No secret value was printed, logged, echoed, or committed. Environment-variable
shape is evidenced indirectly by the preflight source-contract gate, which
returned `status=READY`, `external_requests=0`, and
`secret_material_recorded=false`:

- required: `PRINTER_SOLANA_RPC_URL` — consumed by the read-only source-contract
  preflight; gate `READY`; value never exposed;
- optional free holder backup: `PRINTER_HELIUS_API_KEY` — optional; value never
  exposed.

### 2.5 Fresh preflight (exactly one; `preflight-only`)

Command (run exactly once, no other mode):

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  preflight-only
```

| Preflight requirement | Observed | Result |
| --- | --- | --- |
| exit code `0` | `PREFLIGHT_EXIT_CODE=0` | PASS |
| status `V2_9_8_OPERATIONAL_PREFLIGHT_READY` | `V2_9_8_OPERATIONAL_PREFLIGHT_READY` | PASS |
| Git HEAD matches authorized launch commit | `444ed0191db2d9c50ad097e3f78607f423ef3e68` | PASS |
| Git provenance clean | tracked clean; staged/unstaged/untracked all false | PASS |
| `source_calls=0` | `0` | PASS |
| `source_contract.external_requests=0` | `0` | PASS |
| `scheduler_runtime_calls=0` | `0` | PASS |
| `database_writes=0` | `0` | PASS |
| no secret material recorded | `secret_material_recorded=false` | PASS |
| migration count `49` | `49` | PASS |
| latest migration `049_candidate_acquisition_integration.sql` | matches | PASS |
| integrity `ok` | `ok` | PASS |
| zero foreign-key violations | `0` | PASS |
| every active count zero | all 8 active counts `0` | PASS |
| zero locked Scheduler jobs | `locked_scheduler_jobs=0` | PASS |
| holder budget preflight `READY` | `READY` | PASS |
| source contract `READY` | `READY` | PASS |
| token capacity `2` | `2` | PASS |
| main window `WINDOW_15M` | `WINDOW_15M` | PASS |
| `AUTOMATIC_RETRIES=0` | `automatic_retries=0` | PASS |
| candidate acquisition deferred, not a prerequisite | `DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY`, `operational_prerequisite=false` | PASS |
| `WINDOW_1H`/`WINDOW_4H`/`WINDOW_12H`/`WINDOW_24H` locked | all four in `locked_windows` | PASS |
| retrieval / financial baselines preserved | matches `0`, queries `10`, decisions `2`, audit reports `1`, positions `0`, trade events `0`, trade audits `0` | PASS |

Preflight exit code: `0`.
Preflight output SHA-256 (over the exact captured stdout bytes):
`b98082b7a3da8407cc4db0eb5fe83d7ad10cb4dfa4be13fe2a1e450b1aacbc1f`.

### 2.6 DB SHA-256 after preflight (before/after equality)

```text
DB SHA-256 before: f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
DB SHA-256 after:  f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
equality:          true
```

No WAL/SHM/journal sidecars appeared after preflight; HEAD and clean state were
re-verified unchanged.

## 3. Full Non-Secret Preflight Output

The exact preflight stdout (no secrets present in the output):

```json
{
  "active_counts": {
    "campaign_runs": 0,
    "campaign_supervision": 0,
    "campaigns": 0,
    "discovery_work": 0,
    "factory_run_steps": 0,
    "locked_scheduler_jobs": 0,
    "proof_supervision": 0,
    "scheduler_jobs": 0
  },
  "canonical_migration_count": 49,
  "ceilings": {
    "admission_operations": 45,
    "campaigns": 1,
    "cycles": 1,
    "discovery_requests": 2,
    "duration_seconds": 1200,
    "failures": 20,
    "governed_15m_requests": 65,
    "governed_requests_per_token": 21,
    "scheduler_rows": 51,
    "storage_bytes": 67108864
  },
  "database_path": "/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3",
  "database_sha256": "f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511",
  "database_writes": 0,
  "dependency_preflight": {
    "database_writes": 0,
    "dependencies": [
      {
        "importable": true,
        "module": "websockets",
        "required_minimum": "12.0",
        "satisfied": true,
        "version": "16.1.1"
      }
    ],
    "external_requests": 0,
    "interpreter": "/opt/homebrew/Cellar/python@3.12/3.12.13_4/Frameworks/Python.framework/Versions/3.12/bin/python3.12",
    "issues": [],
    "package_path": "/Users/Dtwo1/Developer/MoneyPrinter/src/printer_v1",
    "status": "READY"
  },
  "foreign_key_violations": 0,
  "git_provenance": {
    "git_head": "444ed0191db2d9c50ad097e3f78607f423ef3e68",
    "git_provenance_captured_at": "2026-07-31T14:33:15.183186+00:00",
    "git_staged_changes_present": false,
    "git_tracked_tree_clean": true,
    "git_unstaged_changes_present": false,
    "git_untracked_present": false
  },
  "historical_paper_audit_rows_preserved": 1,
  "holder_budget_preflight": {
    "expected": {
      "available_for_base_work": 30,
      "fixed_charge_before_base_work": 15,
      "holder_worst_case_transport_operations": 5,
      "operation_ceiling": 45,
      "reserved_snapshot_completion_operations": 4,
      "reserved_snapshot_operations": 2,
      "reserved_total": 6,
      "zero_transport_operations": 9
    },
    "issues": [],
    "source_calls": 0,
    "status": "READY"
  },
  "integrity": "ok",
  "latest_canonical_migration": "049_candidate_acquisition_integration.sql",
  "latest_migration": "049_candidate_acquisition_integration.sql",
  "locked_capability_counts": {
    "printer_memory_retrieval_matches": 0,
    "printer_memory_retrieval_queries": 10,
    "printer_paper_audit_reports": 1,
    "printer_paper_decisions": 2,
    "printer_paper_positions": 0,
    "printer_paper_trade_audits": 0,
    "printer_paper_trade_events": 0
  },
  "migration_count": 49,
  "policy": {
    "active_intake_path": "PROVEN_TWO_TOKEN_OPERATIONAL_DISCOVERY_SELECTION",
    "automatic_retries": 0,
    "candidate_acquisition": {
      "cursor_authority": false,
      "deferred_modes": [
        "acquisition-only-n2",
        "acquisition-only-n7",
        "cursor-recovery-n2"
      ],
      "operational_prerequisite": false,
      "public_operational_modes": false,
      "state": "DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY"
    },
    "locked_windows": [
      "WINDOW_1H",
      "WINDOW_4H",
      "WINDOW_12H",
      "WINDOW_24H"
    ],
    "main_window": "WINDOW_15M",
    "main_window_seconds": 900,
    "restart_created": false,
    "successor_created": false,
    "support_5m_only": true,
    "token_capacity": 2
  },
  "scheduler_runtime_calls": 0,
  "source_calls": 0,
  "source_contract": {
    "external_requests": 0,
    "secret_material_recorded": false,
    "status": "READY"
  },
  "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY"
}
```

## 4. Migration, Integrity, FK and Active-State Results

```text
migration_count:            49
latest_migration:           049_candidate_acquisition_integration.sql
canonical_migration_count:  49
integrity:                  ok
foreign_key_violations:     0
active_counts:              all zero
  campaigns=0 campaign_runs=0 campaign_supervision=0
  discovery_work=0 factory_run_steps=0 proof_supervision=0
  scheduler_jobs=0 locked_scheduler_jobs=0
historical_paper_audit_rows_preserved: 1
```

## 5. Environment-Variable Shape Checks (no values)

```text
secrets file:              $HOME/.config/printer-v1/secrets.env  (present)
loaded via:                set -a; source "$HOME/.config/printer-v1/secrets.env"; set +a
required PRINTER_SOLANA_RPC_URL:   consumed by source-contract preflight; gate READY; value not exposed
optional PRINTER_HELIUS_API_KEY:   optional holder backup; value not exposed
secret_material_recorded:  false
external_requests:         0
```

No environment value was printed, logged, or committed anywhere in this lane.

## 6. Marker Facts

### 6.1 July 31 first-authoritative marker (preserved)

```text
path:    $HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json
SHA-256: dd079f82a361aa2364b4142384a0b472698759a861a507539939aab839011564  (unchanged)
selected fields:
  attempt_number=1
  attempt_scope=FIRST_AUTHORITATIVE_WINDOW_15M_CAMPAIGN
  rerun_authorized=false
  authorized_git_commit=b5761b6501ad757eecdfc8cfabce6828d5a899bd
```

Not edited, recreated, moved, or reused. Re-verified unchanged after post-repair
marker creation.

### 6.2 Post-repair authorization marker (created this lane)

```text
path:    $HOME/PrinterOperations/v2-9-8/post-accounting-repair-authoritative-window-15m-attempt.json
created: exclusive create-new (O_CREAT|O_EXCL), mode 0600
SHA-256: 6bb58474511527a7e2076a9e7b8096208b7018f4e4eb66dd219a26ba5cd2677b
size:    461 bytes
mode:    0600
exact selected fields:
  attempt_number=1
  attempt_scope=POST_ACCOUNTING_REPAIR_AUTHORITATIVE_WINDOW_15M_CAMPAIGN
  authorized_git_commit=444ed0191db2d9c50ad097e3f78607f423ef3e68
  authorization_verdict=V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_FINAL_AUTHORIZATION_PASS
  authoritative_database_sha256=f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
  created_at_utc=20260731T143502Z
  rerun_authorized=false
```

The marker was read back and every field verified exactly. It contains no
`execution_id` (the ordinary `run` command generates that internally at launch).
It was created only after every preflight/state gate passed, using exclusive
file creation; if it had already existed the lane would have failed closed
without creating or overwriting it.

## 7. No Runtime Occurred

Confirmed for this lane:

- no campaign was created or executed;
- no provider, RPC, WebSocket, or source request was made (`source_calls=0`,
  `external_requests=0`);
- no Central Scheduler runtime work occurred (`scheduler_runtime_calls=0`);
- no database write occurred (`database_writes=0`; DB SHA-256 unchanged);
- no `run --operator-approved`, `status`, `report-only`, `discovery-only`,
  recovery, N2, N7, cursor, or `selective-1h-*` mode was run;
- no backup, restore rehearsal, or DB copy was created;
- no campaign/run/cycle/supervision/Scheduler/lifecycle/window/memory row was
  created;
- July 31 was neither repaired nor reclassified;
- no runtime code, tests, migrations, anchors, build order, or policy changed.

The only mutations made anywhere by this lane were: (a) creating the external
post-repair authorization marker file, and (b) authoring/committing this
documentation file.

## 8. Money-Usefulness Contribution

This authorization converts the post-accounting-repair readiness and design
PASSes into a single, safely-bounded, ready-to-launch state for exactly one 15m
learning attempt — without spending any governed source budget, without
mutating the authoritative corpus, and without risking a repeat of the July 31
failure mode (governed budget spent while terminal accounting/reporting is
incomplete). It makes no profit claim and creates no financial capability. It
keeps honest negative learning (an honest pre-lifecycle shortage) a first-class
`HONEST_BLOCKED` outcome rather than pressure toward fake profit or fake memory.

## 9. What This Authorization Improves

- proves, at the exact pinned launch commit and with a clean tree, that the
  repaired ordinary route passes a fresh zero-source `preflight-only` with every
  readiness field green;
- pins the exact authoritative DB SHA-256 into a create-new-only authorization
  marker, establishing the authorization-to-execution anchor before any launch;
- preserves the July 31 permanent no-rerun boundary byte-identically;
- cleanly separates this zero-source authorization from the launch-time internal
  backup/restore gate, which remains inside the ordinary `run` command;
- records a complete, reproducible non-secret evidence bundle for the single
  authorized attempt.

## 10. What Remains Locked

- campaign execution beyond the single authorized attempt this PASS permits;
- providers, RPC, WebSockets, and source fetching (until the authorized attempt);
- July 31 repair, rerun, backfill, or reclassification;
- recovery, N2, N7, cursor reset/advance, candidate-acquisition authority;
- clean-memory creation, retrieval activation;
- `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H`, V2-10;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL;
- live wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

## 11. Proof Required Before Campaign Acceptance

The single authorized attempt (a later, separate operator-execution action) is
not accepted as a campaign PASS unless it produces the full terminal evidence
bundle (design runbook Section 7), including:

- exact launch command and exact HEAD `444ed0191db2d9c50ad097e3f78607f423ef3e68`
  from clean `master`;
- fresh internally generated identity set bound to this marker's SHA-256
  (`6bb58474511527a7e2076a9e7b8096208b7018f4e4eb66dd219a26ba5cd2677b`), with the
  July 31 marker SHA-256 still unchanged;
- internal backup/restore-gate evidence (backup SHA-256 == pre-launch DB
  SHA-256; disposable rehearsal discarded, never written back);
- authoritative DB SHA-256 before and after;
- complete six-unit source/Scheduler accounting with exact owner/action-local
  identity reconciliation;
- exactly two selected token/pair identities and two real terminal `WINDOW_15M`
  lifecycles for a Campaign PASS, or a complete `HONEST_BLOCKED` pre-lifecycle
  shortage record;
- a canonical exact-identity terminal report (or deterministic blocked-replay);
- terminal supervision/lease/lock/owned-work all terminal/released/zero;
- zero retrieval and financial row deltas.

A complete pre-lifecycle shortage is `HONEST_BLOCKED`, never a PASS; incomplete
or untrustworthy accounting is `BLOCKED_UNSAFE`.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

- **Provider availability / eligible supply unproven.** Two-token eligible
  supply cannot be guaranteed until the authorized live attempt; an honest
  pre-lifecycle `HONEST_BLOCKED` shortage remains a likely, allowed outcome —
  never a PASS.
- **One-attempt boundary consumed on invocation.** Once the marker exists and
  `run --operator-approved` is invoked, the single-attempt boundary is consumed
  even if the internal backup/restore gate blocks before any campaign/source
  work. Any further attempt requires a fresh readiness → design →
  final-authorization sequence and a brand-new execution identity.
- **Environment drift.** Environment values may drift before launch; the launch
  sequence re-loads `secrets.env` and the ordinary command re-validates the
  source contract. The `caffeinate` host-awake safeguard must be active for the
  ~20-minute run; host sleep or a second concurrent process is prohibited.
- **Preflight output non-determinism.** The preflight embeds a fresh
  `git_provenance_captured_at` timestamp, so the output SHA-256
  (`b98082b7…`) identifies this exact run; a re-run would differ by timestamp
  only. Exactly one preflight was run.
- **Post-lifecycle identity gate residual.** Holder/scheduler stages after
  lifecycle start are outside the pre-lifecycle action-local identity gate (a
  documented repair residual); full-run transport equality would need an
  explicit sealed-stage design lane first.
- **Marker-shortcut temptation.** The July 31 first-authoritative marker must
  never be deleted/reused; the post-repair marker is create-new-only and must
  never be overwritten, incremented, or given an `execution_id`.
- **Documentation branch must stay unmerged.** This evidence branch must not be
  merged into `master` before the authorized attempt; the launch must run from
  clean `master` at `444ed0191db2d9c50ad097e3f78607f423ef3e68`.

## 13. Verdict

```text
V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_FINAL_AUTHORIZATION_PASS
```

## 14. Exact Next Permitted Action

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Operator Execution
```

That means exactly one execution from clean `master` at the marker-pinned commit
`444ed0191db2d9c50ad097e3f78607f423ef3e68`, under the approved design/operator
runbook
(`docs/printer-v1-v2-9-8b-post-accounting-repair-authoritative-15m-campaign-design-and-operator-runbook.md`).
It does not authorize a retry, successor, or second process.

This final-authorization branch must remain unmerged until the single authorized
attempt is exercised (and, if it terminalizes without a Campaign PASS, until a
fresh readiness → design → final-authorization sequence is run). The launch must
never execute from this documentation commit or branch.
