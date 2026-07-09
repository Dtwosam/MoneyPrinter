# Printer V1 V2-2W Discovery Persistence Gate Reform Bounded Proof

Status: `BOUNDED DETERMINISTIC FIXTURE PROOF`

Proof verdict:

`V2-2W Discovery Persistence Gate Reform Bounded Proof: PROOF_PASS_WITH_BLOCKERS`

V2-2J, V2-3, token-age evidence work, source expansion, and live runtime remain
paused. This proof did not run live discovery, fetch sources, run scheduler or
runtime jobs, generate memory, activate retrieval, create paper decisions,
authorize BUY/SELL/HOLD, open positions, create trades, create paper trade
audits, or create PnL.

No scoring, ranking, confidence percentage, weighted logic, embeddings, vectors,
wallet, private-key, real-fund, or live-execution behavior was introduced.

## 1. Source Stack and Anchors

The proof used these documents together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2u-discovery-persistence-gate-reform-design.md`
- `docs/printer-v1-v2-2v-discovery-persistence-gate-reform-implementation.md`
- `docs/printer-v1-v2-2v-1-discovery-persistence-gate-reform-verification.md`

Anchors:

- V2-2U design: `fe60ba6`
- V2-2V implementation: `147d4b7`
- V2-2V.1 verification: `0d3e6c2`

## 2. Proof Setup

| Item | Result |
|---|---|
| Proof mode | Deterministic fixture proof |
| Live source fetching | Not run |
| Persistent DB | `data/printer_v1.sqlite3`, hash checked only |
| Proof DB | `data/printer_v1_v2_2w_discovery_persistence_gate_reform_proof.sqlite3` |
| DB mode | Isolated proof DB |
| Migrations | Existing migration state on proof DB |
| Selection helper exercised | `_select_discovery_candidates()` |
| Supporting helpers exercised | `_fingerprint_change_type()`, `fingerprint_change_is_meaningful()`, `classify_same_token_new_pair()`, cooldown helpers |
| Operator/live evidence distinction | Fixture proof only; no live results claimed |

The proof added deterministic fixture rows to the isolated proof DB only. The
persistent DB SHA-256 remained unchanged before and after the compact proof run.

## 3. Fixture / Live Distinction

This was not a live discovery capacity proof.

The proof used deterministic candidate fixtures to validate the V2-2V Tier 2
gate mechanics:

- MIGRATION resurfacing;
- REVIVAL resurfacing;
- DISTINCT_NEW_EVIDENCE resurfacing;
- Tier 1 hard blocks;
- reporting fields;
- selection-cooldown separation;
- downstream lock preservation.

The fixture rows are proof evidence only. They are not real source responses,
not memory evidence, not retrieval inputs, and not paper-trading inputs.

## 4. Migrations Applied to Proof DB

No new migration was added by this lane.

The proof DB already existed at:

`data/printer_v1_v2_2w_discovery_persistence_gate_reform_proof.sqlite3`

The proof used the existing schema and fixture helpers from the V2-2V test path.
The lane did not mutate the persistent database.

## 5. MIGRATION Proof Result

Result: `PASS`

### Allowed case

Fixture:

- existing mint: `MINT_V2W_R3_MIG`
- existing pair: `PAIR_V2W_R3_MIG_OLD`
- new pair: `PAIR_V2W_R3_MIG_NEW`
- source channel: `PUMPFUN_MIGRATION`

Observed:

- accepted: `1`
- rejected: `0`
- `resurfacing_category`: `MIGRATION`
- `tier2_gate_outcome`: `ALLOWED`
- required reporting fields present: `true`

### Blocked cases

Existing pair on migration channel:

- accepted: `0`
- rejected: `1`
- reject reason: `duplicate_existing_token_or_pair`

Same mint plus new pair on non-migration channel:

- accepted: `0`
- rejected: `1`
- reject reason: `duplicate_existing_token_mint`

Conclusion:

MIGRATION allows only the intended same-token/new-pair migration evidence shape.
It does not recycle an existing pair and does not allow non-migration STNP.

## 6. REVIVAL Proof Result

Result: `PASS`

### Allowed case

Fixture:

- mint: `MINT_V2W_R3_REV`
- pair: `PAIR_V2W_R3_REV`
- prior lifecycle: `ARCHIVED`
- current activity: reviving fixture

Observed:

- accepted: `1`
- rejected: `0`
- `resurfacing_category`: `REVIVAL`
- `prior_lifecycle_state`: `ARCHIVED`
- `tier2_gate_outcome`: `ALLOWED`

### Blocked cases

Queued lifecycle with reviving activity:

- accepted: `0`
- rejected: `1`
- reject reason: `duplicate_existing_token_or_pair`

Archived lifecycle with dead activity:

- accepted: `0`
- rejected: `1`
- reject reason: `duplicate_existing_token_or_pair`

Conclusion:

REVIVAL requires both an eligible prior lifecycle state and reviving activity.
Old or archived tokens do not re-enter merely because they are old.

## 7. DISTINCT_NEW_EVIDENCE Proof Result

Result: `PASS_WITH_REPORTING_NUANCE`

### Allowed case

Fixture:

- mint: `MINT_V2W_R3_DNE`
- pair: `PAIR_V2W_R3_DNE`
- historical payload: dead/low-activity fixture
- current payload: track-fast activity fixture

Observed:

- accepted: `1`
- rejected: `0`
- `resurfacing_category`: `DISTINCT_NEW_EVIDENCE`
- `tier2_gate_outcome`: `ALLOWED`
- `fingerprint_change_type`: `activity_bucket|primary_bucket_group_crossing`

### Blocked cases

No historical discovery payload:

- accepted: `0`
- rejected: `1`
- reject reason: `duplicate_existing_token_or_pair`

Pair-age-only change:

- accepted: `0`
- rejected: `1`
- reject reason: `duplicate_existing_token_or_pair`

Same-group primary bucket helper check:

- `fingerprint_change_is_meaningful(...)`: `false`
- `_fingerprint_change_type(...)`: `primary_bucket_group_crossing`

Conclusion:

DISTINCT_NEW_EVIDENCE allows a returning token/pair only when the evidence
fingerprint changes meaningfully. No-history and pair-age-only cases remain
blocked.

The known V2-2V.1 reporting nuance remains: `_fingerprint_change_type()` can
report `primary_bucket_group_crossing` when primary buckets differ within the
same broad group. The safety gate still uses
`fingerprint_change_is_meaningful()` first, so the same-group primary-bucket
case remains blocked. This is a reporting precision issue, not an allowance
or safety failure.

## 8. Tier 1 Hard-Block Proof Result

Result: `PASS`

Non-Solana candidate:

- accepted: `0`
- rejected: `1`
- reject reason: `non_solana_candidate`

Missing pair address:

- accepted: `0`
- rejected: `1`
- reject reason: `classified_instant_reject_memory_only`

STNP pair drift helper:

- result: `(false, "PAIR_DRIFT_UNRESOLVED")`

Conclusion:

Tier 1 hard blocks still run before Tier 2 resurfacing allowances. The Tier 2
gate did not weaken Solana-only, usable-pair, or unresolved STNP safety.

## 9. Reporting-Field Proof Result

Result: `PASS_WITH_NON_BLOCKING_NUANCE`

Accepted MIGRATION fixture carried:

- `resurfacing_category`
- `resurfacing_reason`
- `tier2_gate_outcome`
- `prior_lifecycle_state`
- `fingerprint_change_type`

Accepted REVIVAL fixture carried:

- `resurfacing_category = REVIVAL`
- `prior_lifecycle_state = ARCHIVED`
- `tier2_gate_outcome = ALLOWED`

Accepted DISTINCT_NEW_EVIDENCE fixture carried:

- `resurfacing_category = DISTINCT_NEW_EVIDENCE`
- `tier2_gate_outcome = ALLOWED`
- `fingerprint_change_type = activity_bucket|primary_bucket_group_crossing`

These are categorical audit labels only. They are not scores, rankings,
confidence values, weighted decisions, trade signals, memory-cleanliness
signals, retrieval signals, or paper-decision signals.

## 10. Selection-Cooldown Separation Proof Result

Result: `PASS`

Fixture:

- existing rotation-state row for mint `MINT_V2W_R3_MIG`
- old pair: `PAIR_V2W_R3_MIG_OLD`
- new migration pair: `PAIR_V2W_R3_MIG_NEW`
- last selected batch sequence: `1`
- checked current batch sequence: `2`

Observed:

- token cooldown check at sequence 2: `(false, "TOKEN_SELECTION_COOLDOWN")`
- new pair cooldown check at sequence 2: `(true, "")`

Conclusion:

Discovery persistence resurfacing and selection cooldown remain separate gates.
The Tier 2 discovery gate can admit a candidate for candidate-universe review,
but selection cooldown can still block repeated active selection later.

## 11. Row-Delta Lock Proof

Result: `PASS`

Forbidden proof DB table deltas:

| Table | Delta |
|---|---:|
| `printer_memory_windows` | 0 |
| `printer_episodes` | 0 |
| `printer_episode_snapshots` | 0 |
| `printer_memory_retrieval_queries` | 0 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 0 |
| `printer_source_requests` | 0 |
| `printer_source_responses` | 0 |
| `printer_source_failures` | 0 |
| `printer_scheduler_jobs` | 0 |
| `printer_paper_pl_calculations` | table absent |

Allowed fixture tables after compact proof:

| Table | Count |
|---|---:|
| `printer_tokens` | 16 |
| `printer_pairs` | 16 |
| `printer_tracking_queue` | 7 |
| `printer_discovery_candidates` | 6 |
| `printer_selection_rotation_state` | 2 |

Persistent DB hash check:

- persistent DB hash unchanged: `true`

Conclusion:

The proof mutated only the isolated proof DB with deterministic fixture rows.
It created no source rows, scheduler jobs, memory rows, retrieval rows, paper
decision rows, paper position rows, trade rows, audit rows, or PnL rows.

## 12. Tests and Checks Run

Required tests:

```text
python -m pytest tests/test_v2_2v_discovery_persistence_gate_reform.py -q
45 passed, 42 subtests passed, 1 pytest cache warning

python -m pytest tests/test_post_rc_controlled_discovery_cycle.py -q
8 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2s_selection_cooldown.py -q
80 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2c_selection_batch.py -q
120 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2p_pair_age_context.py -q
67 passed, 1 pytest cache warning

python -m pytest tests/test_v2_2m_audit_only_handoff.py -q
95 passed, 1 pytest cache warning
```

Total targeted result:

```text
415 passed
42 subtests passed
0 failed
```

The pytest cache warning was non-failing and came from pytest being unable to
create/update one cache path because it already existed. It did not affect proof
logic or test results.

Git checks run after report creation:

```text
git diff --check
git status --short
git diff --stat
git diff --name-only
```

## 13. Safety Confirmations

Confirmed:

- No live discovery run.
- No source fetching run.
- No Source Governor bypass.
- No Central Scheduler bypass.
- No scheduler/runtime job run.
- No memory generation.
- No memory window creation.
- No retrieval activation.
- No paper decision creation.
- No BUY/SELL/HOLD unlock.
- No paper position creation.
- No trade, paper audit, or PnL creation.
- No wallet, private-key, real-fund, signing, or live-execution logic.
- No paid API dependency.
- No scoring, ranking, confidence, or weighted logic.
- No embeddings or vectors.
- No token-age evidence work.
- No source expansion.
- `WINDOW_5M_MICRO_EVENT` remains support-only.

## 14. Remaining Blockers

The V2-2W proof closes the V2-2V persistence-gate proof requirement.

Remaining broader blockers outside this lane:

- token creation age remains unavailable from current live discovery shapes;
- native 15m price/volume fields still require staged governed evidence;
- A3 remains blocked by token age;
- A4 remains helper-only unless later approved work wires it safely;
- source expansion remains paused;
- V2-3 remains paused until V2-2 closeout is accepted;
- the `_fingerprint_change_type()` same-group reporting nuance remains
  non-blocking but should be carried into closeout notes.

## 15. Final Verdict

`V2-2W Discovery Persistence Gate Reform Bounded Proof: PROOF_PASS_WITH_BLOCKERS`

The proof demonstrates:

- MIGRATION admits only same-token/new-pair migration evidence and blocks
  existing-pair or non-migration STNP cases;
- REVIVAL admits only eligible archived/cooldown tokens with reviving activity;
- DISTINCT_NEW_EVIDENCE admits only meaningful evidence changes and blocks
  missing-history or pair-age-only cases;
- Tier 1 hard blocks remain intact;
- required categorical reporting fields are visible;
- discovery persistence resurfacing remains separate from selection cooldown;
- isolated proof DB fixture rows create zero downstream memory, retrieval,
  paper, source, scheduler, trading, audit, or PnL rows;
- persistent DB hash remains unchanged.

## 16. Next Recommended Lane

V2-2J may resume as a documentation closeout lane if the operator accepts this
proof.

V2-2J should consolidate V2-2K through V2-2W findings, preserve the remaining
token-age, native-15m, A3/A4, source-expansion, and reporting-nuance blockers,
and explicitly keep V2-3 paused until the operator accepts the closeout.
