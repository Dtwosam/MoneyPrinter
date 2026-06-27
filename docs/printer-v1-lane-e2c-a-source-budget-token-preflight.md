# Printer V1 Lane E2C-A Source Budget and Approved Token List Preflight

## 1. Status

This is Post-Lane 10 Lane E2C-A — Source Budget and Approved Token List Preflight.

Lane E2C-A is static inspection and documentation only.

Lane E2C-A does not run a Memory Factory cycle.

Lane E2C-A does not perform source fetching, scheduler execution, snapshot collection, memory creation, retrieval activation, paper decisions, BUY, SELL, HOLD, paper positions, trade events, paper audits, or PnL.

Lane E2C-A does not mutate the persistent database.

Lane E2C-A does not authorize wallet logic, private keys, signing, live trading, real funds, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

## 2. E2B Anchor

Lane E2C-A is anchored to the Lane E2B commit and tag:

- Commit: `f9c7ba8`
- Tag: `printer-v1-post-lane10-lane-e2b-scheduler-bounded-cycle`
- What E2B proved: 74 fixture-based scheduler integration tests (9 classes) covering bounded job enqueue, claim, completion, MEMORY_WINDOW_CLOSE path, clean exit, zero running jobs and zero active locks after exit, max_active_tokens cap enforcement, PAPER_MONITORING exclusion from the E2B bounded cycle, and absence of paper decision job kinds, snapshots, paper decisions, positions, and HTTP libraries.

E2B did not run real source fetching. E2B confirmed the scheduler machinery is ready for a bounded cycle. E2B is a required precondition for E2C.

## 3. Exact Purpose of Lane E2C-A

Lane E2C-A answers one question:

**Can we safely attempt Lane E2C — the first real bounded source-governed 15m Memory Factory cycle — with only 1-2 operator-approved tokens, Source Governor enforced, no scheduler runtime outside an approved command, no memory forcing, and all paper-trading locks still active?**

Lane E2C-A does this by:

- listing all required operator inputs that do not yet exist
- identifying source budget headroom for a minimal 1-2 token cycle
- confirming Source Governor enforcement path
- confirming Central Scheduler requirements
- documenting DB backup and preflight requirements
- documenting all stop conditions
- stating what E2C may and must not do
- issuing a GO / LIMITED GO / BLOCKED recommendation

## 4. Source-of-Truth Documents Checked

This preflight is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`
- `docs/printer-v1-lane-c-source-budget-governor-verification.md`
- `docs/printer-v1-lane-d-scheduler-tracking-window-close-readiness.md`
- `docs/printer-v1-lane-e2a-active-lane-preconditions.md`
- `docs/printer-v1-memory-factory-guide.md`
- `tests/test_post_rc_lane_e2b_scheduler_bounded_cycle.py`
- `src/printer_v1/sources/governor.py`
- `src/printer_v1/sources/contracts.py`
- `src/printer_v1/sources/recording.py`
- `src/printer_v1/sources/governed_execution.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/scheduler/contracts.py`
- `src/printer_v1/scheduler/scheduler.py`
- `src/printer_v1/scheduler/resource_governor.py`
- `src/printer_v1/operator_cli/commands.py`

The current active roadmap extension is:

- `docs/printer-v1-post-lane10-proposed-next-build-order.md`

## 5. Current Locked Capabilities

The following remain locked throughout E2C-A and must remain locked in Lane E2C:

- BUY
- SELL
- HOLD
- paper positions
- trade events
- paper audits
- PnL
- memory creation (for E2C-A; E2C may attempt only if operator approves and evidence passes)
- retrieval activation
- paper decision creation
- wallet logic
- private keys
- signing
- live trading
- real funds
- paid API dependencies
- scoring systems
- ranking systems
- confidence percentage systems
- weighted decision logic
- embeddings
- vectors
- 5m as main outcome memory
- 5m unlocking retrieval or decisions

## 6. Required E2C Operator Inputs

Before Lane E2C may begin, the operator must supply all of the following. None currently exist.

### 6.1 Approved Token List

**STATUS: NOT PROVIDED — E2C IS BLOCKED.**

The operator must explicitly approve 1-2 Solana memecoin token mint addresses.

No approved token list file exists in the repository. Static inspection found no `approved_token_list`, `token_list`, or equivalent configuration file.

This is the primary blocker for E2C. E2C must not begin without at least one operator-approved token mint.

### 6.2 Explicit E2C Scope Approval

The operator must explicitly approve the E2C lane scope before any implementation begins. Approving E2C-A (this document) is not approval for E2C implementation.

### 6.3 Confirmation That E2B Is Committed and Tagged

**STATUS: SATISFIED.**

Lane E2B commit `f9c7ba8` is confirmed committed and tagged as `printer-v1-post-lane10-lane-e2b-scheduler-bounded-cycle`.

### 6.4 DB Backup Confirmation

The operator must confirm whether a DB backup exists before E2C runs. If the persistent DB contains pre-existing data (tokens, pairs, memories, paper decisions), a backup must be made before any E2C cycle attempt mutates it.

**STATUS: NOT CONFIRMED.**

### 6.5 Explicit Paper-Decisions-Off Confirmation

The operator must re-confirm that paper decisions remain off for the first E2C cycle. From AGENTS.md and the memory factory guide: "The first Memory Factory implementation must keep paper decisions off."

**STATUS: Policy confirmed. Explicit E2C re-confirmation required before implementation.**

## 7. Approved Token List Format

When the operator provides the approved token list, it must include:

| Field | Requirement |
|---|---|
| `token_mint` | Exact Solana base58 token mint address (43-44 chars, no spaces, no invented addresses) |
| `label` | Short human-readable label for operator tracking |
| `approved_by` | Operator identity or session marker |
| `approved_at` | ISO 8601 timestamp of approval |
| `lifecycle_lane` | `TRACK_FAST` or `TRACK_NORMAL` (determines job kind and snapshot cadence) |
| `notes` | Optional rationale or risk note |

Example format (operator must fill in real mints — do not invent addresses):

```
token_mint:  <operator-supplied Solana base58 address>
label:       <short label>
approved_by: operator
approved_at: <ISO 8601>
lifecycle_lane: TRACK_FAST | TRACK_NORMAL
notes:       <optional>
```

**Important: no token mint addresses are invented or pre-populated in this document.**

## 8. Recommended 1-2 Token Cap for First E2C Cycle

The first E2C cycle must use at most 2 tokens:

- at most 1 TRACK_FAST token (TRACK_FAST_FIRST_15M job, check interval 120 seconds)
- at most 1 TRACK_NORMAL token (TRACK_NORMAL_FIRST_15M job, check interval 300 seconds)

This keeps the cycle:

- well within max_active_tokens=10, max_track_fast=3, max_track_normal=7 (proven in E2B)
- within conservative source budget headroom for all relevant sources
- observable by the operator in a single cycle report
- safe to stop, cancel, or fail cleanly without corrupting other data

The E1 dry-run default of max_active_tokens=10 remains valid but must not be filled in a first real E2C cycle. The operator must start with 1-2 tokens only.

## 9. Source Budget Checks Required Before E2C

### 9.1 Per-Source Rate Limits (from `src/printer_v1/sources/registry.py`)

| Source | Rate Limit | Stale After | Retry After | Max Retries | Priority Class |
|---|---|---|---|---|---|
| dexscreener | 60/min | 90s | 30s | 3 | token_level |
| geckoterminal | 30/min | 180s | 60s | 2 | discovery |
| pumpportal | 30/min | 60s | 30s | 3 | discovery |
| alternative_me | 10/min | 86400s | 300s | 2 | broad_context |
| coingecko | 20/min | 300s | 120s | 2 | broad_context |
| defillama | 20/min | 900s | 120s | 2 | broad_context |
| goplus | 20/min | 300s | 120s | 2 | protection |
| solana_rpc | 30/min | 120s | 60s | 2 | token_level |
| helius_free | 30/min | 120s | 60s | 2 | token_level |
| pumpswap | 20/min | 120s | 60s | 2 | discovery |
| jupiter_quote | 30/min | 30s | 30s | 2 | paper_realism |

### 9.2 Estimated Per-Cycle Request Count for 1-2 Token First Cycle

For a 15-minute bounded cycle with 1 TRACK_FAST token and 1 TRACK_NORMAL token:

**TRACK_FAST token (check interval: 120 seconds):**
- Approximately 7-8 snapshot requests per source per token over 15m
- Primary sources: dexscreener (pair_market_snapshot), solana_rpc (onchain_reference), goplus (safety_reference)
- Estimated: 7-8 dexscreener + 7-8 solana_rpc + 7-8 goplus = ~21-24 token-level requests

**TRACK_NORMAL token (check interval: 300 seconds):**
- Approximately 3 snapshot requests per source per token over 15m
- Same primary sources
- Estimated: 3 dexscreener + 3 solana_rpc + 3 goplus = ~9 token-level requests

**Broad context (once per cycle, optional):**
- alternative_me: 1 request (stale_after=86400s, one per day is sufficient)
- coingecko: 1 request (stale_after=300s)
- defillama: 1 request (stale_after=900s)
- Total broad context: ~3 requests

**Total estimated cycle requests: ~33-36 for 1 fast + 1 normal token.**

### 9.3 Rate Limit Headroom Assessment

At 33-36 requests over 15 minutes (900 seconds), the average request rate is approximately 2.2-2.4 per minute total across all sources. All per-source rates are well below limits:

- dexscreener: ~7-8 calls in 15m vs. 60/min limit — headroom: very large
- solana_rpc: ~7-8 calls in 15m vs. 30/min limit — headroom: very large
- goplus: ~7-8 calls in 15m vs. 20/min limit — headroom: large
- broad context sources: 1 call each vs. 10-20/min limit — headroom: very large

**Conclusion: rate limit headroom is adequate for a 1-2 token first E2C cycle.**

### 9.4 Unresolved Source Budget Gaps

The following are NOT yet resolved and must be addressed before E2C implementation:

1. **`recent_request_count` must be accurately tracked by the implementation.** The Source Governor's `can_request_source` function receives `recent_request_count` as a caller-supplied argument. The E2C implementation must count recent per-source requests correctly and pass the count — it is not automatically tracked by the governor itself.

2. **No per-cycle aggregate budget report field exists yet.** The E1 dry-run payload has `source_fetching_enabled: False`. A real E2C cycle report must add a budget summary: source name, requests attempted, requests succeeded, requests failed/stale, budget remaining.

3. **Stale and partial response handling under live network conditions has not been tested.** Lane C confirmed this gap. E2C must treat stale/partial as honest failure and not force clean memory from degraded evidence.

4. **`printer_source_rate_limits` table behavior under a multi-request per-source bounded cycle has not been tested end-to-end.** E2C implementation must verify this table is read/written correctly.

## 10. Source Governor Enforcement Requirements

The Source Governor at `src/printer_v1/sources/governor.py` must be enforced as follows in E2C:

### 10.1 What the Source Governor Already Enforces

Confirmed by static inspection of `governor.py` and `contracts.py`:

- Unknown sources are rejected (`unknown_source` decision)
- Paid plan dependencies are rejected (`paid_dependency_rejected`)
- Disallowed request kinds are rejected (`request_kind_not_allowed`)
- Non-Solana-specific sources are rejected for token-level request kinds (`not_solana_token_level_source`)
- Jupiter quote is restricted to `paper_quote_realism` only (`jupiter_quote_paper_only`)
- Rate limit exceeded rejects with `rate_limit_exceeded` and returns retry_after_seconds
- `SourceAdapterContext.governor_approved` must be `True` for adapter execution
- `execution_path` must equal `GOVERNOR_ONLY_EXECUTION_PATH` for adapter execution

### 10.2 What E2C Must Not Bypass

- No engine may call adapter transport functions (`urllib.request.urlopen` or similar) directly without a Source Governor decision first
- Every source request must be recorded in `printer_source_requests` before the adapter executes
- Every response must be recorded in `printer_source_responses`
- Every failure (governor rejection, network error, stale result, malformed data) must be recorded in `printer_source_failures`
- Rate limit failures must be recorded honestly — they must not trigger silent retries or provider rotation

### 10.3 Current Gap: Real Network Adapter Path Not Yet Proven via Source Governor

The current governed execution path (`execute_source_request_with_governor` in `governed_execution.py`) uses `FixtureSourceAdapter` only:

- `SourceAdapterContract.fixture_only` is `True`
- `SourceAdapterContract.supports_network_execution` is `False`
- `FixtureSourceAdapter.execute()` returns synthetic fixture data — no network call is made

For a real E2C cycle that fetches live source data, the E2C implementation must either:

1. Build real network-capable adapter variants that preserve `governor_approved=True` and `GOVERNOR_ONLY_EXECUTION_PATH`, OR
2. Use the existing fixture adapter path but with operator-acknowledged fixture data (not a "real" cycle)

**If option 2 is chosen, E2C is not a real source-governed cycle — it remains a fixture-based cycle. This must be explicitly stated in the E2C scope.**

**If option 1 is chosen, real network adapters must be built and tested before E2C runs.**

This gap must be resolved in the E2C implementation scope definition before work begins.

## 11. Central Scheduler Requirements

The Central Scheduler has been proven sufficient for a bounded cycle by Lane E2B (74/74 tests pass). The following requirements apply to E2C:

### 11.1 Confirmed Scheduler Capabilities (from E2B and static inspection)

- `enqueue_job` inserts PENDING job; blocks DUPLICATE_ACTIVE_JOB by (job_name, job_kind, target_table, target_id)
- `claim_due_job` returns ACQUIRED when job is PENDING and scheduled_for <= now; sets RUNNING + locked_at + lock_owner
- `complete_job` sets SUCCEEDED, clears locked_at/lock_owner, sets finished_at
- `fail_job` sets COOLDOWN (retry) or FAILED, clears locks, increments retry_count, records last_error
- `cancel_job` sets CANCELLED, clears locks
- `release_stale_locks` resets RUNNING jobs with locked_at older than `lock_timeout_seconds` (default 300s) back to PENDING
- Priority order: OPEN_PAPER_TRADE_MONITOR (1) > ACTIVE_EXIT_RISK_TOKEN (2) > TRACK_FAST_MICRO_EVENT (3) > TRACK_FAST_FIRST_15M (4) > TRACK_NORMAL_FIRST_15M (5) > MEMORY_WINDOW_CLOSE (6) > ...
- Token-level job kinds are higher priority than broad-context job kinds by `resource_governor.py`

### 11.2 Job Kind Check Intervals (from `resource_governor.py`)

| Job Kind | Check Interval |
|---|---|
| TRACK_FAST_FIRST_15M | 120 seconds |
| TRACK_NORMAL_FIRST_15M | 300 seconds |
| MEMORY_WINDOW_CLOSE | 60 seconds |
| DISCOVERY_REFRESH | 600 seconds |
| MARKET_REGIME_CONTEXT | 900 seconds |

### 11.3 Scheduler Requirements for E2C

- E2C must use a single bounded operator-approved command — no background worker, no unbounded runtime loop
- E2C must enqueue exactly the jobs required for 1-2 tokens and one MEMORY_WINDOW_CLOSE
- E2C must respect max_active_tokens=10, max_track_fast=3, max_track_normal=7 (enforced by E1 constants)
- E2C must prove zero running jobs and zero active locks after bounded cycle exits (required by E2B gate)
- E2C must not enqueue OPEN_PAPER_TRADE_MONITOR jobs (PAPER_MONITORING remains excluded from E2C scope)
- All job failures must be recorded via `fail_job`; no silent swallowing of scheduler errors

## 12. DB Backup and Preflight Requirements

Before E2C runs against any persistent database:

### 12.1 DB File Location

The operator must confirm the path to the production DB file. The E1 dry-run command uses `--db` flag to pass the DB path. E2C must use the same pattern.

### 12.2 Backup Requirement

**Before any E2C cycle attempt, the operator must:**

1. Identify the current DB file path
2. Create a timestamped backup copy (e.g., `printer_v1_backup_YYYYMMDD_HHMMSS.sqlite3`)
3. Confirm the backup is readable before starting

If no backup exists and E2C writes unexpected data, recovery is not guaranteed.

### 12.3 Migration Check

E2C must confirm that all migrations have been applied to the target DB before running. If the DB is behind the current migration state, the cycle must not begin.

Use: `apply_migrations(db_path)` — the migration system is idempotent (confirmed by E2B tests).

### 12.4 Pre-Cycle DB State Check

Before E2C starts, the operator command should report:

- current count of rows in `printer_scheduler_jobs` (expected: 0 or pre-existing completed jobs)
- current count of rows in `printer_tokens` (expected: 0 before first cycle or pre-existing tokens)
- current count of RUNNING jobs (expected: 0)
- current count of active locks (expected: 0)

If any RUNNING jobs or active locks exist before E2C starts, stop and investigate before proceeding.

## 13. Stop Conditions for E2C

E2C must stop immediately if any of the following occur:

1. **No operator-approved token mint is provided** — do not invent token addresses
2. **Source request bypasses Source Governor** — any direct transport call without governor decision is a hard stop
3. **Source request or failure is not recorded** — every request/response/failure must appear in DB tables
4. **A paid API dependency is required** — reject and stop
5. **Source rate limit is exceeded without honest failure recording** — no silent overflow
6. **Source failures are hidden or silently retried beyond max_retries** — stop and record
7. **max_active_tokens, max_track_fast, or max_track_normal is violated** — hard cap enforcement required
8. **A job remains RUNNING after the bounded cycle exits** — stale lock is a hard stop trigger
9. **An active lock remains after the bounded cycle exits** — hard stop
10. **Central Scheduler is bypassed** — no direct DB writes that skip enqueue/claim/complete path
11. **A stale or partial snapshot satisfies a window-close requirement** — stop and record as dirty/partial
12. **Clean memory would be forced when evidence does not pass** — zero clean memories is valid
13. **A paper decision is created** — hard stop; paper decisions remain off for first E2C
14. **BUY, SELL, or HOLD is created** — hard stop
15. **A paper position is created** — hard stop
16. **A trade event, paper audit, or PnL entry is created** — hard stop
17. **OPEN_PAPER_TRADE_MONITOR job is enqueued** - PAPER_MONITORING remains excluded from E2C scope; hard stop
18. **Wallet, private-key, signing, live-trading, paid API, scoring, ranking, confidence, weighted, embedding, or vector logic appears** — hard stop
19. **Unbounded execution appears** — the cycle must have a max_seconds or max_jobs cap
20. **The operator has not confirmed DB backup** — do not start without backup confirmation

## 14. What E2C May Do Later (When Approved)

When the operator provides the required inputs and the BLOCKED status is resolved, E2C may:

- accept 1-2 operator-approved Solana memecoin token mints as the tracking set
- enqueue TRACK_FAST_FIRST_15M and/or TRACK_NORMAL_FIRST_15M jobs for approved tokens
- enqueue MEMORY_WINDOW_CLOSE job to close the 15m window
- claim and complete scheduler jobs in a bounded sequence
- attempt source requests for approved tokens via Source Governor
- record every source request, response, and failure to DB tables
- record token snapshots for approved tokens
- attempt a 15m memory window build for tokens that pass evidence quality checks
- classify each window as CLEAN_MEMORY, PARTIAL_MEMORY, DIRTY_MEMORY, or DO_NOT_TRAIN
- report zero clean memories if evidence does not pass (this is a valid expected outcome)
- produce a cycle report for operator review before any subsequent cycle

## 15. What E2C Must Still Not Do

Even when approved and running:

- must not fetch sources without Source Governor approval for each request
- must not run an unbounded scheduler loop (bounded cycle only)
- must not create more than 1-2 tokens worth of jobs per cycle
- must not force clean memory when evidence fails quality checks
- must not create paper decisions (including WAIT, AVOID, or NO_ACTION) in first E2C
- must not create BUY, SELL, or HOLD decisions
- must not create paper positions
- must not create trade events, paper audits, or PnL
- must not move any token to PAPER_MONITORING state
- must not enqueue OPEN_PAPER_TRADE_MONITOR jobs
- must not use paid APIs or require paid plan sources
- must not use wallet logic, private keys, signing, or live execution
- must not use scoring, ranking, confidence percentages, or weighted logic
- must not use embeddings or vectors
- must not treat 5m evidence as a main outcome window
- must not unlock retrieval until clean memories exist and a later operator-approved lane authorizes it
- must not begin a second cycle before the operator reviews the first cycle report

## 16. GO / LIMITED GO / BLOCKED Recommendation

**BLOCKED.**

E2C may not begin.

### Reason 1: No Operator-Approved Token List (Primary Blocker)

No approved token list exists in the repository. No token mint addresses have been provided by the operator. E2C requires at least 1 operator-approved Solana memecoin token mint before any cycle can be planned or attempted.

Do not invent token addresses. Do not use placeholder addresses. The operator must explicitly supply real Solana memecoin token mints.

### Reason 2: Real Network Adapter Path Not Yet Proven via Source Governor (Secondary Blocker)

The current governed execution path (`governed_execution.py`) uses `FixtureSourceAdapter` only, with `fixture_only=True` and `supports_network_execution=False`. A real E2C cycle requires either:

- real network-capable adapter variants built and gated by Source Governor (requires implementation lane), OR
- explicit operator acknowledgment that the first E2C cycle uses fixture adapters only (not real source data)

If the operator chooses fixture-only adapters for E2C, the lane must be clearly labeled as a fixture-governed cycle and must not be confused with real source-fetching.

### Reason 3: `recent_request_count` Tracking Not Yet Implemented (Secondary Gap)

The Source Governor's rate limit check (`can_request_source`) receives `recent_request_count` as a caller-supplied argument. No mechanism yet exists to track per-source request counts per cycle and pass them correctly. This must be implemented in the E2C command or a helper before E2C runs.

### What Must Happen Before GO or LIMITED GO

The E2C BLOCKED status upgrades to LIMITED GO when ALL of the following are confirmed:

1. Operator provides 1-2 Solana memecoin token mints with lifecycle lane (TRACK_FAST or TRACK_NORMAL)
2. Operator explicitly approves E2C lane scope (fixture-only or real network, clearly labeled)
3. If real network: real network adapter path is built and proven via Source Governor in a new test
4. If fixture-only: operator acknowledges cycle will use synthetic data, not live source data
5. `recent_request_count` tracking is implemented correctly in the E2C command
6. DB backup exists and is confirmed readable
7. Pre-cycle DB state check passes (zero RUNNING jobs, zero active locks)
8. Operator explicitly re-confirms paper decisions remain off for first E2C
9. E2C-A (this document) is committed and tagged before E2C begins

LIMITED GO means: E2C may begin with the confirmed 1-2 token scope, fixture-only or real-network (clearly labeled), bounded cycle, all paper-trading locks active, paper decisions off, and operator review of cycle report required before any second cycle.

## 17. Lane E2C-A Acceptance Checklist

Lane E2C-A is accepted when:

- E2B anchor commit and tag are confirmed
- exact E2C-A purpose is stated
- source-of-truth documents checked are listed
- required E2C operator inputs are enumerated and status-checked
- approved token list format is defined (with explicit no-invented-addresses note)
- 1-2 token cap recommendation is justified
- per-source rate limit table is present
- per-cycle budget estimate for 1-2 tokens is calculated
- rate limit headroom is assessed
- unresolved source budget gaps are documented
- Source Governor enforcement requirements are explicit
- real network adapter gap is identified
- Central Scheduler requirements are explicit
- DB backup and preflight requirements are documented
- all stop conditions are listed
- what E2C may do is listed
- what E2C must not do is listed
- GO / LIMITED GO / BLOCKED decision is stated with reasons
- BUY, SELL, HOLD, positions, trade events, paper audits, and PnL remain locked
- no code was changed
- no DB mutation occurred
- no source fetching occurred
- no scheduler execution occurred

## 18. Next Recommended Lane

**Lane E2C-A must be committed and tagged before E2C begins.**

Recommended tag: `printer-v1-post-lane10-lane-e2c-a-source-budget-token-preflight`

**The next recommended action before any E2C implementation:**

The operator must supply 1-2 Solana memecoin token mints with explicit lifecycle lane assignment (TRACK_FAST or TRACK_NORMAL) and explicit scope approval (fixture-only cycle or real-network cycle, clearly labeled).

Once that input is provided, the next recommended lane is:

**Lane E2C — First Bounded Source-Governed 15m Memory Factory Cycle**

Lane E2C scope (when authorized):

- accept operator-approved token list (1-2 tokens)
- enqueue TRACK_FAST_FIRST_15M and/or TRACK_NORMAL_FIRST_15M jobs for approved tokens
- run bounded scheduler cycle with Source Governor enforced on every request
- record all source requests, responses, and failures
- attempt 15m memory window build for tokens that pass evidence quality checks
- produce cycle report for operator review
- prove zero running jobs and zero active locks after cycle exits
- accept zero clean memories as valid outcome
- keep paper decisions off
- keep BUY, SELL, HOLD, positions, and PnL locked

Lane E2C does not begin until the operator provides the token list and explicitly approves scope.

5m remains support-only. 15m remains the first main Memory Factory target. Clean memory must never be forced.
