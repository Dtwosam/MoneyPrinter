# Printer V1 Lane E2C-D -- Operator-Approved Token List and First-Cycle Runbook

## 1. Purpose

Lane E2C-D prepares the operator-readiness package needed before a first bounded E2C
source-governed 15m Memory Factory cycle can be considered.

Lane E2C-D does NOT execute the first bounded cycle.

Lane E2C-D provides:

- the operator-approved token list format and rules
- the DB backup procedure
- the E2C-C preflight command usage
- the first-cycle checklist
- the stop conditions
- the rollback notes
- the explicit boundary to the next lane

This document is static planning only. It does not authorize source fetching, scheduler
runtime, snapshot collection, memory creation, retrieval activation, paper decisions,
BUY, SELL, HOLD, paper positions, trade events, paper audits, PnL, wallet logic,
private keys, signing, live trading, real funds, paid APIs, scoring, ranking,
confidence percentages, weighted logic, embeddings, or vectors.

---

## 2. Current Anchor

- Lane E2C-C commit: `da74137`
- Lane E2C-C tag: `printer-v1-post-lane10-lane-e2c-c-active-cycle-readiness`
- Lane E2C-C delivered: `printer-plan-bounded-15m-memory-factory-cycle` dry-run command,
  token list validation, DB preflight, source budget planning, cycle plan output,
  and all 11 hard-lock flags set to False.

Lane E2C-D is anchored to the E2C-C tag above.

---

## 3. Operator-Approved Token List Rules

The first bounded E2C cycle allows only 1-2 operator-approved tokens.

### 3.1 Token count

- Minimum: 1 token.
- Maximum: 2 tokens.
- Exceeding 2 tokens blocks the readiness check.

### 3.2 Token mint format

- Every token_mint must be a valid Solana base58 address.
- Length must be exactly 43 or 44 characters.
- Allowed characters: `123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz`
- Excluded characters: `0` (zero), `O` (capital O), `I` (capital I), `l` (lowercase L).
- The validator (`is_valid_solana_mint`) in `e2c_readiness.py` enforces this.

### 3.3 lifecycle_lane

- Each token must declare exactly one lifecycle lane.
- Allowed values: `TRACK_FAST` or `TRACK_NORMAL`.
- No other values are accepted.
- `TRACK_FAST` tokens are planned as `TRACK_FAST_FIRST_15M` jobs.
- `TRACK_NORMAL` tokens are planned as `TRACK_NORMAL_FIRST_15M` jobs.

### 3.4 Duplicate mints

- Duplicate `token_mint` values within one token list are rejected.
- Each mint must appear at most once.

### 3.5 No invented token addresses

- The operator must supply real Solana token mint addresses that they have independently
  identified and approved.
- Printer does not generate, suggest, rank, or recommend token addresses.
- Printer does not use scoring, ranking, confidence percentages, or weighted logic
  to select tokens.
- This runbook does not contain real token recommendations.

### 3.6 Token list is a tracking input only

- The token list is an operator-approved tracking input for the Memory Factory.
- It is not a buy signal, investment recommendation, or financial advice.
- Printer V1 is paper-trading only. No real funds are involved.

### 3.7 Additional operator metadata fields (required in file)

- `operator_note`: free-text operator annotation for audit visibility.
- `approved_by_operator`: must be `true` before use. A token list with `false` must be
  rejected by the operator before passing to the preflight command.

---

## 4. Example Token List Format

See: `docs/templates/printer-v1-e2c-approved-token-list.example.json`

That file contains a JSON template with placeholder mint addresses clearly marked for
replacement. Do not pass the placeholder file directly to the preflight command.
Replace all placeholder mints with real operator-approved Solana token mint addresses
before use.

Required JSON fields per token entry:

| Field                | Type    | Rules                                                    |
|----------------------|---------|----------------------------------------------------------|
| `token_mint`         | string  | Solana base58, 43-44 chars, no 0/O/I/l chars            |
| `lifecycle_lane`     | string  | `TRACK_FAST` or `TRACK_NORMAL`                           |
| `operator_note`      | string  | Free-text operator annotation (may be empty string)      |
| `approved_by_operator` | bool  | Must be `true` before passing list to preflight command  |

---

## 5. DB Backup Procedure

A DB backup must be created and confirmed before running the E2C-C preflight command
with `--backup-confirmed`.

### 5.1 Check that the DB file exists

Before backing up, confirm the database file is present:

```powershell
Test-Path "data\printer_v1.sqlite3"
```

Expected output: `True`. Stop if output is `False` or the file does not exist.

### 5.2 Create a timestamped backup

Run the following PowerShell block. It:
- blocks if the DB file does not exist
- creates `data\backups\` if it does not exist
- copies the DB to a timestamped backup file
- copies the backup path to the clipboard

```powershell
$src = "data\printer_v1.sqlite3"
if (-not (Test-Path $src)) {
    Write-Error "DB not found: $src -- backup aborted."
    exit 1
}
$ts = (Get-Date -Format "yyyyMMddTHHmmss")
$dst = "data\backups\printer_v1_backup_$ts.sqlite3"
New-Item -ItemType Directory -Force -Path "data\backups" | Out-Null
Copy-Item -Path $src -Destination $dst
Write-Host "Backup created: $dst"
$dst | Set-Clipboard
Write-Host "Backup path copied to clipboard."
```

### 5.3 Confirm the backup

After running the block above:
- Confirm the backup file exists with `Test-Path $dst`.
- Note the backup path from the clipboard or the console output.
- You will pass `--backup-confirmed` to the preflight command only after this step.

### 5.4 DB backup rules

- The backup procedure does NOT mutate the source DB file.
- The backup is a read-only copy operation.
- Do not delete or overwrite the backup file until the cycle lane is complete and verified.
- If the cycle lane mutates the DB unexpectedly, the backup is the restore source (see
  Section 9 -- Rollback Notes).

---

## 6. E2C-C Preflight Command Usage

The E2C-C preflight command (`printer-plan-bounded-15m-memory-factory-cycle`) produces
a dry-run JSON payload. It does NOT execute the cycle.

### 6.1 Command syntax

```
printer-plan-bounded-15m-memory-factory-cycle \
  --token <MINT>:<LIFECYCLE_LANE> \
  [--token <MINT2>:<LIFECYCLE_LANE2>] \
  --backup-confirmed \
  --db-path data/printer_v1.sqlite3
```

### 6.2 Single TRACK_FAST token example (replace mint with real operator-approved address)

```powershell
printer-plan-bounded-15m-memory-factory-cycle `
  --token "REPLACE_WITH_REAL_MINT:TRACK_FAST" `
  --backup-confirmed `
  --db-path data/printer_v1.sqlite3
```

### 6.3 Two-token mixed example (replace mints with real operator-approved addresses)

```powershell
printer-plan-bounded-15m-memory-factory-cycle `
  --token "REPLACE_WITH_REAL_MINT_1:TRACK_FAST" `
  --token "REPLACE_WITH_REAL_MINT_2:TRACK_NORMAL" `
  --backup-confirmed `
  --db-path data/printer_v1.sqlite3
```

### 6.4 Output: BLOCKED

The command outputs `"recommendation": "BLOCKED"` when any of the following are true:

- Token list is empty or has more than 2 entries.
- Any `token_mint` fails Solana base58 format validation.
- Any `lifecycle_lane` is not `TRACK_FAST` or `TRACK_NORMAL`.
- Duplicate `token_mint` values exist.
- `--backup-confirmed` is not passed.
- `--db-path` is not provided or the path does not exist.
- Any RUNNING jobs are present in `printer_scheduler_jobs`.
- Any active locks (locked_at IS NOT NULL) are present in `printer_scheduler_jobs`.
- Any non-paid source exceeds its Source Governor rate limit.

A BLOCKED result means the first cycle must NOT proceed.

### 6.5 Output: LIMITED_GO_FOR_OPERATOR_REVIEW

The command outputs `"recommendation": "LIMITED_GO_FOR_OPERATOR_REVIEW"` when all of the
following are true:

- Token list is valid (1-2 tokens, valid mints, valid lifecycle lanes, no duplicates).
- DB backup was confirmed (`--backup-confirmed` passed).
- DB path exists.
- Zero RUNNING jobs in `printer_scheduler_jobs`.
- Zero active locks in `printer_scheduler_jobs`.
- All non-paid sources report `"allowed": true` from the Source Governor.

`LIMITED_GO_FOR_OPERATOR_REVIEW` does NOT execute the cycle. It means the dry-run
planning conditions are met. The operator must review the full JSON output before any
real execution lane is considered.

### 6.6 Hard-lock flags in output

The command always reports all 11 hard-lock flags as `false`:

```json
"hard_locks": {
  "source_fetching_enabled": false,
  "scheduler_execution_enabled": false,
  "snapshot_creation_enabled": false,
  "memory_creation_enabled": false,
  "retrieval_activation_enabled": false,
  "paper_decisions_enabled": false,
  "buy_enabled": false,
  "sell_enabled": false,
  "hold_enabled": false,
  "positions_enabled": false,
  "pnl_enabled": false
}
```

These flags are enforced by `HARD_LOCKS` in `src/printer_v1/operator_cli/e2c_readiness.py`.
Any future lane that allows real execution must explicitly unlock the relevant flags
under a separate operator-approved lane.

### 6.7 Source budget section in output

The command reports `source_budget.planned_sources` for each non-paid source:

- `recent_request_count` -- consumed attempts within the last 60 seconds from DB.
- `rate_limit_per_minute` -- governor rate limit for this source.
- `governor_decision` -- `"allowed"` or `"rate_limit_exceeded"`.
- `allowed` -- `true` or `false`.

If any source reports `"allowed": false`, the recommendation is BLOCKED.

---

## 7. First-Cycle Checklist

Before operator considers moving to a future real-execution lane, all items below
must be confirmed for the specific DB and token list being used.

```
[ ] 1. Working tree is clean (git status --short shows no output).
[ ] 2. Correct E2C-C tag is present:
        git tag | findstr "e2c-c"
        Expected: printer-v1-post-lane10-lane-e2c-c-active-cycle-readiness
[ ] 3. DB backup created and confirmed (see Section 5).
        Backup file path noted and saved.
[ ] 4. Token list is operator-approved.
        approved_by_operator is true for all entries.
        No placeholder addresses remain.
[ ] 5. Token count is 1 or 2.
        Not 0. Not 3 or more.
[ ] 6. Every token_mint is a valid Solana base58 address (43-44 chars, base58 alphabet).
        Validated by preflight command output.
[ ] 7. Every lifecycle_lane is TRACK_FAST or TRACK_NORMAL.
        Validated by preflight command output.
[ ] 8. Source budget is allowed for all non-paid sources.
        preflight output: source_budget.all_sources_allowed == true
[ ] 9. Zero RUNNING jobs in printer_scheduler_jobs.
        preflight output: db_preflight.running_jobs == 0
[ ] 10. Zero active locks in printer_scheduler_jobs.
         db_preflight.active_locks == 0
         No rows with locked_at IS NOT NULL.
         No rows with lock_owner set.
[ ] 11. All 11 hard-lock flags are false in preflight output.
         hard_locks section: every value is false.
[ ] 12. Preflight recommendation is LIMITED_GO_FOR_OPERATOR_REVIEW.
         Not BLOCKED.
[ ] 13. Operator has reviewed the full JSON preflight output.
         All sections read: token_list_validation, db_preflight, source_budget,
         cycle_plan, hard_locks, recommendation_reasons.
[ ] 14. Operator confirms no unexpected state in any section.
```

All 14 items must be checked before a future real-execution lane is proposed.
Any unchecked item means the lane remains BLOCKED.

---

## 8. Stop Conditions

If any of the following occur at any point during preflight or a future execution lane,
the operator must stop immediately and not proceed.

### 8.1 DB and backup stops

- DB backup command fails or produces an error.
- Backup file does not exist after the backup command.
- DB file does not exist at the expected path.
- DB file size is 0 bytes or inconsistent with expected state.

### 8.2 Token list stops

- Token list validation reports `"valid": false`.
- Any `token_mint` fails base58 format check.
- `lifecycle_lane` is not `TRACK_FAST` or `TRACK_NORMAL`.
- Duplicate mints in the list.
- Token count is 0 or more than 2.
- `approved_by_operator` is `false` or missing.
- Placeholder mints remain in the list.

### 8.3 Source budget stops

- Any source reports `"allowed": false` in preflight output.
- Any `"governor_decision": "rate_limit_exceeded"` in planned_sources.
- Source budget read fails or raises an exception.
- Any `"governor_decision": "budget_accounting_error"` appears in planned_sources.
- `all_sources_allowed` is `false` for any reason.

### 8.4 Scheduler and lock stops

- Any row with `status = 'RUNNING'` in `printer_scheduler_jobs`.
- Any row with `locked_at IS NOT NULL` in `printer_scheduler_jobs`.
- Any row with `lock_owner` set in `printer_scheduler_jobs`.
- Preflight DB query fails.

### 8.5 Unexpected activity stops (future execution lane only)

- Any source fetching detected outside an approved bounded command.
- Any snapshot row created outside the bounded cycle.
- Any memory row created in `printer_memories` unexpectedly.
- Any paper decision row created in `printer_paper_decisions`.
- Any BUY, SELL, or HOLD decision row created.
- Any paper position row created in `printer_paper_positions`.
- Any trade event, paper trade audit, or PnL row created.
- Any wallet connection, private key reference, signing, or live execution detected.
- Any paid API dependency activated.
- Any embedding, vector, scoring, ranking, or confidence-weighted path triggered.

### 8.6 Hard-lock stops

- Any hard-lock flag in `hard_locks` is `true` when it should be `false`.
- Any future command output shows `buy_enabled: true`, `sell_enabled: true`,
  `hold_enabled: true`, `positions_enabled: true`, `pnl_enabled: true`,
  `paper_decisions_enabled: true`, `scheduler_execution_enabled: true`,
  `source_fetching_enabled: true`, `snapshot_creation_enabled: true`,
  `memory_creation_enabled: true`, or `retrieval_activation_enabled: true`
  when not explicitly authorized by a separate operator-approved lane.

---

## 9. Rollback Notes

### 9.1 When to roll back

Roll back the DB if a future cycle lane mutates the DB in a way that was not expected
or explicitly authorized. Do not attempt to roll back based on suspicion -- confirm
unexpected mutation by comparing row counts before and after.

### 9.2 How to restore the DB backup

If the persistent DB was mutated unexpectedly and the backup was created per Section 5:

```powershell
# Step 1: Confirm backup file exists.
$backup = "data\backups\printer_v1_backup_YYYYMMDDTHHMMSS.sqlite3"
Test-Path $backup

# Step 2: Rename (do not delete) the current DB to preserve the unexpected state.
$ts = (Get-Date -Format "yyyyMMddTHHmmss")
Rename-Item "data\printer_v1.sqlite3" "data\printer_v1_unexpected_state_$ts.sqlite3"

# Step 3: Copy the backup to the DB path.
Copy-Item -Path $backup -Destination "data\printer_v1.sqlite3"

# Step 4: Confirm restore.
Test-Path "data\printer_v1.sqlite3"
```

Replace `YYYYMMDDTHHMMSS` with the actual timestamp from your backup file.

### 9.3 Confirming DB state after restore

After restore, run the preflight command again to confirm DB state:

```powershell
printer-plan-bounded-15m-memory-factory-cycle `
  --token "REPLACE_WITH_REAL_MINT:TRACK_FAST" `
  --backup-confirmed `
  --db-path data/printer_v1.sqlite3
```

Confirm:
- `db_preflight.running_jobs == 0`
- `db_preflight.active_locks == 0`
- `db_preflight.preflight_passed == true`

### 9.4 Inspecting git state after unexpected behavior

```powershell
# Show working tree status.
git status --short

# Show recent commits.
git log --oneline -10

# Confirm E2C-C tag is still intact.
git tag | findstr "e2c-c"

# Show what changed since E2C-C tag.
git diff printer-v1-post-lane10-lane-e2c-c-active-cycle-readiness --stat
```

### 9.5 Automated rollback not included in this lane

Lane E2C-D does not include or execute any automated rollback logic.
All rollback steps above are manual operator procedures.
No rollback is executed as part of this document.

---

## 10. Explicit Next-Lane Boundary

Lane E2C-D does NOT execute the first bounded cycle.

Real execution remains blocked.

Real execution -- including source fetching, scheduler runtime, snapshot collection,
memory window builds, and memory audit -- remains blocked until a later
operator-approved lane explicitly allows it.

### 10.1 What E2C-D closes

- Token list format and rules are documented.
- DB backup procedure is documented.
- E2C-C preflight command usage is documented.
- First-cycle checklist is documented.
- Stop conditions are documented.
- Rollback notes are documented.

### 10.2 What remains blocked after E2C-D

All of the following remain blocked until separately authorized:

- Source fetching (adapter calls to any source).
- Scheduler runtime execution.
- Snapshot collection (any row in `printer_token_snapshots` or `printer_context_snapshots`).
- Memory window building.
- Memory creation (any row in `printer_memories`).
- Retrieval activation.
- Paper decisions (WAIT, AVOID, NO_ACTION, BUY, SELL, HOLD).
- Paper positions, trade events, paper trade audits.
- PnL calculation or reporting.
- Wallet logic, private keys, signing, live trading, real funds.
- Paid APIs.
- Scoring, ranking, confidence percentages, weighted logic.
- Embeddings or vectors.

### 10.3 Possible next lane

The next lane after E2C-D may be one of the following, depending on operator roadmap
review:

- First-cycle fixture simulation (dry-run or synthetic evidence cycle, no real source
  calls, no persistent DB mutation).
- First bounded real execution lane (requires separate explicit operator approval,
  scoped token list, DB backup confirmed, all preflight checks passing).

No execution lane is activated by this document. The operator must explicitly approve
a named next lane before any real cycle execution begins.

---

*Document status: Lane E2C-D static planning -- docs only, no code, no cycle execution.*
*Anchor: commit da74137 / tag printer-v1-post-lane10-lane-e2c-c-active-cycle-readiness*
