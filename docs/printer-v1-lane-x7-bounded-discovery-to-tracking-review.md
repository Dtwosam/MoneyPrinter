# Printer V1 Lane X7 - Bounded Discovery-to-Tracking Review

## 1. Lane Status

**Type:** Documentation/review only.

Lane X7 is not an implementation lane. It produces no code changes, no DB migrations, no test
files, and no runtime modifications. It does not activate automation.

Lane X7 reviews whether `printer-discover-candidates-once` can safely feed a bounded Memory
Factory run later - without enabling automation now - and documents the exact preconditions,
candidate caps, promotion rules, demotion rules, source-budget requirements, stop conditions,
and remaining risks that must be resolved before any automation is permitted.

This document does not unlock:
- discovery automation
- source fetching without explicit operator command
- WATCH_ONLY auto-promotion
- retrieval activation
- paper decisions
- BUY / SELL / HOLD
- paper positions
- PnL
- live trading
- wallet / private keys
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- 1h / 4h / 12h / 24h collection

---

## 2. Anchor Commit and Tag

- **Commit:** `4f99ecf` - Add Lane X6 discovery selection repair
- **Tag:** `printer-v1-lane-x6-discovery-selection-repair`

---

## 3. Source-of-Truth Documents Read

| Document | Role |
|---|---|
| `AGENTS.md` | Build discipline and restriction law |
| `docs/printer-v1-memory-growth-build-order.md` | Active memory-growth lane order |
| `docs/printer-v1-clean-master-spec.md` | Product/system law |
| `docs/printer-v1-memory-factory-guide.md` | Memory Factory policy guide |

---

## 4. Reviewed Commands and Modules

| Module / Command | Status |
|---|---|
| `printer-discover-candidates-once` | Exists - manual, operator-approved, 1-3 candidates max, 4 sources |
| `src/printer_v1/operator_cli/commands.py` (discovery path) | Exists - validates max 1-3, enforces Solana-only |
| `src/printer_v1/discovery/discovery.py` | Exists - `process_discovery_payload`, `route_candidate_to_tracking_queue`, `route_candidate_to_lifecycle` |
| `src/printer_v1/discovery/classifier.py` | Exists - `classify_discovery_candidate`, TRACK_FAST / TRACK_NORMAL / WATCH_ONLY / INSTANT_REJECT |
| `src/printer_v1/discovery/contracts.py` | Exists - `DiscoveryCandidateLabel`, `DiscoveryOutputAction`, `DiscoveryChannelLabel` |
| `src/printer_v1/operator_cli/lane_x6_discovery_selection_repair.py` | Exists - mint/pair dedup, cooldown-aware selection, 9 memory diet labels, auditable reasons |
| `src/printer_v1/operator_cli/lane_x5_five_token_runner.py` | Exists - 5-token TRACK_FAST bounded WINDOW_15M runner, source budget enforcement |
| `src/printer_v1/operator_cli/lane_x3_post_cycle_lifecycle.py` | Exists - enter_cooldown_after_window, reopen_token, check_x3_cooldown_gate, archive_after_memory_window |

---

## 5. Discovery-to-Tracking Safety Checklist

### 5.1 Hard Gates That Are Already In Place

| Gate | Location | Status |
|---|---|---|
| Operator approval required for every discovery run | `_validate_discover_candidates_args` | ENFORCED |
| max_candidates 1-3 (enforced by validator, not a suggestion) | `commands.py:1356` | ENFORCED |
| Solana-only discovery | `_validate_discover_candidates_args` | ENFORCED |
| Timeout max 10 seconds (single source call) | `commands.py:1360` | ENFORCED |
| Source Governor controls all outbound calls | `build_governed_source_request` | ENFORCED |
| WATCH_ONLY explicitly rejected from 15m memory proof cycle | `commands.py:1433-1434` | ENFORCED |
| Duplicate mint/pair rejected before DB write | `_select_discovery_candidates` | ENFORCED |
| Discovery cannot create paper BUY / paper decisions | All hard locks | ENFORCED |
| Discovery is intake, not alpha | All hard locks + X6 `no_discovery_automation` | ENFORCED |
| Backup proof required for X5/X6 | X5 validator, X6 main entry | ENFORCED |
| Source budget gate in X5 (consecutive failure limit) | `lane_x5_five_token_runner.py:1009,1087` | ENFORCED |
| X3 cooldown gate blocks COOLDOWN tokens from re-selection | `check_x3_cooldown_gate` | ENFORCED |
| X6 cooldown-aware filter excludes COOLDOWN/ARCHIVED | `filter_cooldown_blocked` | ENFORCED |

### 5.2 Manual Steps That Remain Required (No Automation Exists)

The following steps currently have no wired automation. Each requires an explicit operator
command or manual JSON file construction:

1. **Operator runs** `printer-discover-candidates-once` †' discovery writes to
   `printer_discovery_candidates`.
2. **Operator reviews** discovery output - no automatic selection of candidates for tracking.
3. **Operator runs** `printer-run-lane-x6-discovery-selection-repair` †' X6 reads from the
   discovery candidates table, deduplicates, applies cooldown filter, and returns an auditable
   candidate list.
4. **Operator inspects** X6 output (`selected_candidates`, `memory_diet_summary`,
   `dedup_report`, `cooldown_blocked`) and decides which tokens to track.
5. **Operator constructs** the Lane X5 token list JSON (exactly 5 TRACK_FAST tokens with
   `operator_approved: true`). This is a manual file the operator writes.
6. **Operator runs** `printer-run-lane-x5-five-token-cycle --token-list-path ...
   --backup-proof-path ... --operator-approved`.
7. **Operator runs** X3 cooldown/archive after a cycle completes (`printer-run-lane-x3-post-cycle-lifecycle`).

None of these steps are wired together. Each is an independent operator command.

---

## 6. Proposed Bounded Design

The following design is safe for review. It does NOT enable automation. It describes the
minimum safe operator workflow if a future lane (X8+) were to implement a bounded
discovery-to-tracking pipeline.

### 6.1 Step Sequence (Bounded, Operator-Gated)

```
Step 1 - Discover (one manual run):
  printer-discover-candidates-once
    --operator-approved
    --source-name dexscreener|geckoterminal|pumpportal|pumpswap
    --max-candidates 1|2|3
    --chain solana
    --timeout-seconds [1..10]

Step 2 - Select / Dedup (one manual run):
  printer-run-lane-x6-discovery-selection-repair
    --operator-approved
    --backup-proof-path <path>
    --max-candidates [1..20]
    --db-path <path>

Step 3 - Operator review gate:
  Operator reads X6 output:
    selected_candidates †' inspect each token_mint, pair_address, memory_diet_label,
      selection_reason, lifecycle_status, is_revival, same_token_new_pair
    dedup_report †' confirm no unexpected collapses
    cooldown_blocked †' note blocked tokens (do not recycle immediately)
    memory_diet_summary †' confirm useful variety

Step 4 - Token list construction (manual):
  Operator writes the Lane X5 token list JSON:
    {
      "tokens": [
        { "token_mint": "...", "pair_address": "...", "tracking_lane": "TRACK_FAST",
          "operator_approved": true, "chain": "solana" },
        ... (exactly 5 entries)
      ]
    }

Step 5 - Bounded tracking run:
  printer-run-lane-x5-five-token-cycle
    --operator-approved
    --token-list-path <path>
    --backup-proof-path <path>
    --duration [15m|1h|2h|6h|12h|24h]
    --source-budget-max-failures [default 5]

Step 6 - Post-cycle lifecycle:
  printer-run-lane-x3-post-cycle-lifecycle
    Operator decides: enter_cooldown_after_window or archive_after_memory_window
    per token. Operator runs revival (reopen_token) when appropriate.
```

### 6.2 What This Design Guarantees

- No step executes without explicit operator approval on that step's command.
- Discovery does not automatically feed tracking.
- The X6 selection output is a read-only report; the operator is the link between X6 and X5.
- WATCH_ONLY candidates do not advance unless the operator re-runs discovery on them
  and they reclassify as TRACK_FAST or TRACK_NORMAL.
- COOLDOWN and ARCHIVED tokens cannot re-enter the active set without the operator
  running `reopen_token` in X3 first.
- All financial locks remain in effect at every step.

---

## 7. Manual and Operator-Approval Boundaries

| Action | Operator Required | Cannot Bypass |
|---|---|---|
| Running discovery | Yes (`--operator-approved`) | Yes - validator enforces |
| Running X6 selection | Yes (`--operator-approved`) | Yes - blocked without approval |
| Building the token list JSON | Yes (manual file construction) | Yes - no auto-generation |
| Running X5 tracking | Yes (`--operator-approved`) | Yes - validator enforces |
| Running X3 cooldown | Yes (explicit operator command) | Yes - no auto-trigger |
| Running X3 reopen | Yes (explicit operator command) | Yes - no auto-reopen |
| Running X3 archive | Yes (explicit operator command) | Yes - no auto-archive |

---

## 8. Candidate Caps

| Layer | Cap | Enforced By |
|---|---|---|
| Discovery candidates per run | 1-3 | `_validate_discover_candidates_args` (hard validator) |
| X6 selection pool | Up to 20 (default) | `_DEFAULT_MAX_CANDIDATES`, operator-settable |
| Tokens fed to X5 | Exactly 5 TRACK_FAST | `_load_and_validate_five_token_list` (hard validator) |
| Active TRACK_FAST concurrent tokens | 5 | X5 exact token count lock |
| TRACK_NORMAL concurrent tokens | 0 (no X5 path for TRACK_NORMAL) | X5 validator rejects non-TRACK_FAST |
| WATCH_ONLY candidates in tracking | 0 (explicitly rejected) | `commands.py:1433-1434` |

The operator must run enough sequential discovery runs over time to accumulate 5 TRACK_FAST
candidates in the DB. Assuming 1-3 per run, the minimum number of discovery runs to fill a
5-token X5 list is 2 runs (3 + 2 = 5) or up to 5 runs (1 per run).

---

## 9. WATCH_ONLY Promotion Rules

**Current state:** WATCH_ONLY candidates have no automatic promotion path.

When a candidate is classified as WATCH_ONLY by the classifier:
- It is stored in `printer_discovery_candidates` with `discovery_action = 'WATCH_ONLY'`.
- It receives a `WATCH_ONLY_REFRESH` lifecycle event.
- It is explicitly rejected from the 15m proof cycle selection (code: `watch_only_not_eligible_for_15m_memory_proof_cycle`).
- It does NOT appear in X6 `selected_candidates` unless `discovery_action` is `TRACK_FAST` or
  `TRACK_NORMAL` (X6 DB load filters on those actions).

**Proposed promotion path (not yet implemented, future lane):**

A WATCH_ONLY token can only advance to tracking after:
1. The operator re-runs `printer-discover-candidates-once` or `printer-run-manual-intake` on
   the same mint/pair.
2. The classifier re-evaluates and returns `TRACK_FAST` or `TRACK_NORMAL` (meaning the token's
   on-chain metrics improved: liquidity rose above `MIN_TRACK_FAST_LIQUIDITY_USD = 5,000`,
   volume rose above `MIN_TRACK_FAST_VOLUME_5M_USD = 1,000`, and txns rose above
   `MIN_TRACK_FAST_TXNS_5M = 10`).
3. The new TRACK_FAST/TRACK_NORMAL record appears in X6 selection output.
4. The operator includes it in the Lane X5 token list.

No code changes in this lane. The above is the proposed future design.

---

## 10. Stale Token Demotion and Archive Rules

The following rules exist in X3 and X6. They are not automated.

### 10.1 Cooldown (TRACK_FAST †' COOLDOWN)

- Trigger: Operator runs `enter_cooldown_after_window` after a tracked token completes a
  sufficient memory window or the operator decides the token has yielded enough evidence.
- Effect: `printer_tracking_queue.queue_status = 'COOLDOWN'`.
- X3 gate: `check_x3_cooldown_gate` blocks COOLDOWN tokens from re-selection.
- X6 filter: `filter_cooldown_blocked` excludes COOLDOWN tokens from X6 output unless
  `cooldown_aware=False`.
- Duration: no automatic expiry - operator decides when to reopen.

### 10.2 Archive (COOLDOWN †' ARCHIVED)

- Trigger: Operator runs `archive_after_memory_window` on a token already in COOLDOWN.
- Effect: `printer_tracking_queue.queue_status = 'ARCHIVED'`.
- X6 filter: ARCHIVED tokens are blocked by `filter_cooldown_blocked` (same as COOLDOWN).
- Archive is a stronger demotion - the token is considered fully retired from active rotation.
- Revival is still possible (see §10.3), but requires more deliberate operator action.

### 10.3 Revival / Reopen (COOLDOWN or ARCHIVED †' QUEUED)

- Trigger: Operator runs `reopen_token` on a cooled-down or archived token.
- Effect: Inserts a new `printer_tracking_queue` entry with `queue_status = 'QUEUED'`.
- X6: The QUEUED status is treated as "allowed" by `filter_cooldown_blocked`.
- If `include_revivals=True` (X6 default), the token appears in `selected_candidates` with
  `is_revival=True` and receives the `REVIVAL` memory diet label.
- The operator still must add the revived token to the X5 token list manually.

### 10.4 Stale But Not Cooled

A token that appears repeatedly in discovery results without ever completing a tracked window
will accumulate multiple `printer_discovery_candidates` rows. X6 dedup collapses these to the
freshest record. The operator is responsible for deciding when to cool down or archive tokens
that are not making progress.

---

## 11. Source-Budget Requirements

### 11.1 Discovery Source Budget

Each `printer-discover-candidates-once` invocation makes exactly one outbound source call to
one of the four approved sources (dexscreener, geckoterminal, pumpportal, pumpswap). The call
is governed by the Source Governor. No rate-limit bypass is permitted.

Caps enforced by `_validate_discover_candidates_args`:
- `timeout_seconds`: must be (0, 10].
- `max_candidates`: must be [1, 3].
- One source, one call, one run.

### 11.2 X5 Tracking Source Budget

The X5 runner enforces a consecutive-failure budget across all five tokens:

```
source_budget_max_consecutive_failures = N (default: 5)

If consecutive_source_failures > N:
    STOP immediately with lane_x5_status = LANE_X5_STATUS_STOPPED
    No more source calls made.
    DB writes for completed windows are preserved.
```

This budget is per-cycle, not per-token. Any consecutive failures across the A/B/C/D/E rotation
contribute to the same counter. The budget resets to zero on each successful source call.

### 11.3 Combined Budget Estimate (Discovery + Tracking)

For a minimal combined run:
- Discovery: 1-3 source calls (one per `printer-discover-candidates-once` invocation, repeated
  2-5 times to accumulate 5 candidates).
- Tracking: up to `5 Ã- snapshots_per_token` source calls during a bounded X5 run.
- At 90-second snapshot intervals for a 15m window: ~10 snapshots per token per window.
- Five tokens Ã- 10 snapshots = 50 source calls per 15m window cycle.
- X5 stops immediately on `source_budget_max_consecutive_failures` consecutive failures.

No concurrent outbound calls. Source Governor serializes all calls.

---

## 12. Stop Conditions

### 12.1 Discovery Stop Conditions

| Condition | Behavior |
|---|---|
| Source call fails or times out | No candidates added to DB; error returned in payload; operator can retry |
| Source returns zero matching candidates | Empty result returned; `accepted_candidates = []`; valid outcome |
| `max_candidates` reached | Selection stops accepting; rest are rejected with `max_candidates_reached` |
| Non-Solana response | Candidate rejected with `non_solana_candidate` |
| Duplicate mint/pair in DB | Candidate rejected with `duplicate_existing_token_or_pair` |
| Weak copycat (dead near-zero + same symbol/name) | Candidate rejected with `weak_copycat_candidate` |

### 12.2 X6 Selection Stop Conditions

| Condition | Behavior |
|---|---|
| No candidates in DB | `selected_count = 0`; valid outcome (`zero_candidates_is_valid = True`) |
| All candidates deduplicated away | `selected_count = 0`; dedup_report documents collapses |
| All candidates cooldown-blocked | `selected_count = 0`, `cooldown_blocked_count = N` |
| `max_candidates` pool cap reached | Selection truncated; remaining candidates not included |

### 12.3 X5 Tracking Stop Conditions

| Condition | Behavior |
|---|---|
| `consecutive_source_failures > source_budget_max_consecutive_failures` | STOPPED immediately; partial results preserved |
| `cycle_budget` exhausted (test/proof mode) | COMPLETED; all windows closed |
| Duration profile elapsed | COMPLETED; all windows closed |
| All five tokens error on the same tick | Source budget incremented; may trigger STOP |

---

## 13. Forbidden Behaviors

The following are forbidden at every stage of the discovery-to-tracking pipeline. These locks
exist in X3 (23 locks), X5 (24 locks), and X6 (24 locks) independently.

| Forbidden Behavior | Why |
|---|---|
| Discovery acting as a trade signal | Discovery is intake, not alpha |
| WATCH_ONLY auto-promoting to TRACK_FAST | No promotion logic exists; requires operator re-evaluation |
| Discovery creating paper BUY / paper decisions | All paper decision tables are forbidden write targets |
| Candidate count > 3 per discovery run | Hard validator cap |
| Token count ‰  5 in X5 | Hard exact-count validator |
| TRACK_NORMAL / WATCH_ONLY in X5 token list | X5 validator rejects non-TRACK_FAST lanes |
| Discovery bypassing Source Governor | Source Governor controls all outbound calls |
| Discovery without operator approval | Both discovery and X5/X6 require `--operator-approved` |
| Retrieval activation from discovered candidates | Forbidden by all hard lock sets |
| BUY / SELL / HOLD decisions from discovered candidates | Forbidden by all hard lock sets |
| Paper positions from discovered candidates | Forbidden by all hard lock sets |
| Scoring / ranking / confidence on candidates | Forbidden by all hard lock sets |
| Cooldown tokens recycled without operator reopen | X3 gate + X6 filter both block it |
| Source budget bypass | `no_source_budget_bypass` lock in X5 and X6 |
| 1h / 4h / 12h / 24h collection from discovery | X5 and X6 hard locks |
| Embeddings / vectors from candidates | Forbidden by all hard lock sets |

---

## 14. Evidence Required Before X8 or Later Automation

Before any future lane (X8 or later) can safely automate any part of the
discovery-to-tracking pipeline, all of the following must be true:

### 14.1 Proved in Prior Lanes (Already Done)

- [x] Single-token 15m memory collection proven (Lane U/U2/V)
- [x] Two-token 15m rotation proven (Lane X2)
- [x] Three-token 15m rotation proven (Lane X3/X4)
- [x] Five-token 15m rotation proven with source budget enforcement (Lane X5)
- [x] Discovery/selection dedup proven with auditable reasons and cooldown awareness (Lane X6)
- [x] Post-cycle lifecycle (cooldown/archive/reopen) proven (Lane X3)

### 14.2 Required for X8 Automation (Not Yet Done)

- [ ] **Operator has run the manual flow** (Steps 1-6 from §6.1) at least once on a real DB
  and confirmed that the combined output is correct and useful.
- [ ] **WATCH_ONLY promotion path** is designed, approved by operator, and implemented with
  its own operator gate and test coverage.
- [ ] **TRACK_NORMAL tracking lane** is designed and implemented, or explicitly decided that
  TRACK_NORMAL candidates are permanently ineligible for the 5-token X5 path.
- [ ] **Cooldown trigger is wired** into the post-X5 run flow (currently manual X3 step).
  Until wired, operators must remember to cool down tokens after each cycle manually.
- [ ] **X7 review document** (this document) is committed and tagged before any automation
  lane begins.
- [ ] **Operator approves this document** - no automation lane can start without explicit
  operator approval of the X7 design.
- [ ] **Source budget observed** in at least one real multi-source discovery run to confirm
  the Source Governor prevents rate-limit exhaustion across the combined workflow.

---

## 15. Risks Remaining After X6

| Risk | Severity | Status |
|---|---|---|
| **No WATCH_ONLY promotion path** - tokens that miss the TRACK_FAST threshold sit in DB forever without any advancement | Medium | Open - future design needed |
| **TRACK_NORMAL is an orphan lane** - X5 accepts only TRACK_FAST; TRACK_NORMAL candidates from discovery have no bounded tracking runner | Medium | Open - either implement or deprecate |
| **Manual token list construction** - the gap between X6 output and X5 token list JSON is 100% manual; operator can make errors | High | Open - mitigated only by X6 audit output and X5 validator |
| **No automated cooldown trigger** - operator must remember to run X3 after each cycle; if they forget, old tokens remain QUEUED indefinitely | Medium | Open - future lane to wire post-cycle hook |
| **Stale candidates in DB** - if operator runs discovery many times without X6 review, old TRACK_FAST candidates pile up; X6 dedup collapses them but freshness is based on `captured_at`, which may not reflect market reality | Low | Mitigated by X6 cooldown filter; no automated cleanup |
| **Same-token/new-pair accumulation** - a token with many pair addresses generates multiple discovery rows; X6 detects and documents this, but does not resolve which pair is the canonical one | Low | Open - operator must choose the correct pair for the token list |
| **Source Governor not validated under combined load** - discovery + X5 tracking uses the same Source Governor; combined rate-limit behavior under a real run has not been observed | Medium | Open - first real combined run will validate |
| **Memory diet is deterministic but not validated against real market data** - X6 diet labels (PUMP, DUMP, etc.) are assigned from API field values; accuracy depends on API data quality | Low | Expected - diet is for memory variety, not prediction |
| **No 5m support in current X5 path** - `WINDOW_5M_MICRO_EVENT` remains blocked in X5; discovery may surface tokens where 5m evidence would be useful | Low | By design - X8 addresses 5m integration |

---

## 16. Readiness Verdict

### Summary

The individual components of the discovery-to-tracking pipeline are all implemented and
proven in isolation:

- `printer-discover-candidates-once` †' works, gated, 1-3 candidates per run.
- `lane_x6_discovery_selection_repair` †' works, dedup + cooldown-aware + diet labels.
- `lane_x5_five_token_runner` †' works, source budget enforced, 5-token WINDOW_15M.
- `lane_x3_post_cycle_lifecycle` †' works, cooldown/archive/reopen.

However, the steps are not wired. The operator must manually bridge:
1. Discovery †' X6 selection †' manual token list †' X5 run †' manual X3 cooldown.

Key open blockers before automation:
- No WATCH_ONLY promotion path.
- No TRACK_NORMAL tracking runner.
- No automated post-cycle cooldown hook.
- No manual run evidence in a real combined workflow.

### Verdict

```
PARTIAL_READY_WITH_BLOCKERS
```

Discovery can safely feed a bounded Memory Factory run **with operator review at every step**.
The design for doing this safely is documented above (§6). Automation is not enabled and must
not be enabled without resolving the blockers listed in §14.2.

---

## 17. Exit Gate Result

```
lane: X7
type: documentation/review only
verdict: PARTIAL_READY_WITH_BLOCKERS
automation_enabled: false
code_changes: 0
db_mutations: 0
memory_created: 0
paper_decisions_created: 0
retrieval_activated: false
buy_enabled: false
sell_enabled: false
hold_enabled: false
positions_created: 0
pnl_created: 0
```

---

## 18. Next Recommended Lane

Based on this review, the recommended next lane is:

**Lane X8 - 5m Support Integration**

Compatibility label: Lane X8 - 5m Support Integration

Rationale: The build order defines X8 as wiring `WINDOW_5M_MICRO_EVENT` as support-only
evidence inside bounded 15m runs. The five-token WINDOW_15M path (X5) is proven. The
discovery/selection path (X6) is proven. X8 can now focus on the 5m linkage without
first resolving all of the X7 blockers.

If the operator prefers to resolve the discovery-to-tracking automation blockers before 5m
support, the alternative is to return to X7 blockers as a separate implementation lane
(tentatively X7B) before X8. The operator decides.

---

## 19. Automation Status Declaration

```
discovery_to_tracking_automation_enabled: false
watch_only_promotion_enabled: false
track_normal_runner_enabled: false
post_cycle_cooldown_automated: false
all_financial_locks_enforced: true
all_hard_locks_x3: 23
all_hard_locks_x5: 24
all_hard_locks_x6: 24
```
