# Printer V1 V2-6 1h Audit Gate Repair Closeout

## Status

Verdict: `V2_6_1H_AUDIT_GATE_REPAIR_PASS`

The E2Q memory-window audit boundary was made window-kind-specific. A genuine
`WINDOW_1H` window can now enter audit while `WINDOW_15M` behavior is unchanged,
`WINDOW_5M_MICRO_EVENT` remains support-only, and `WINDOW_4H/12H/24H` are not
enabled. No live or proof 1h cycle was run. This closeout does not begin V2-7.

## Audit And Design (Gate 1)

### The single WINDOW_15M assumption in E2Q

`e2q_memory_window_audit.audit_15m_memory_window` had exactly one window-kind
assumption: Gate 2 hard-required `window_kind == "WINDOW_15M"` and blocked every
other kind with a fixed "5m is not a valid main outcome window" reason. This
blocked a genuine `WINDOW_1H` window identically to a 5m window, even though the
1h structural infrastructure (`lane_e2o_1h_window_close`, Lane X12/X13) already
writes real `WINDOW_1H` rows with `window_start_at`, `window_end_at`,
`snapshot_start_id`, and `snapshot_end_id`. Every other E2Q gate (closed status,
`supporting_context_json.snapshot_id`, snapshot existence, token/pair match,
dirty/stale/acceptable quality classification, idempotent write-back, hard
locks) was window-kind-agnostic and correct.

### Explicit window-kind criteria

- **Valid `WINDOW_15M`** — unchanged: closed, governed snapshot present via
  `supporting_context_json.snapshot_id`, exact token/pair match, normal
  dirty/stale/acceptable quality gates.
- **Support-only `WINDOW_5M_MICRO_EVENT`** — always blocked
  (`E2Q_AUDIT_BLOCKED`) with a support-only reason; never a main outcome window.
- **Genuine `WINDOW_1H`** — admissible only when it has, in addition to the
  shared structural gates:
  - real 1h identity: `window_kind == "WINDOW_1H"`;
  - real duration: non-null `window_start_at`/`window_end_at` spanning at least
    `E2Q_1H_MIN_ELAPSED_SECONDS = 2700s` — the established 1h continuation
    minimum from `lane_e2o_1h_window_close._MIN_ELAPSED_SECONDS`, also enforced
    by Lane Q; a ~900s window (relabelled 15m) fails this floor;
  - governed snapshot anchors: non-null `snapshot_start_id` and
    `snapshot_end_id` (coverage) with the start anchor present in the DB;
  - exact token/pair targeting on the start anchor (the end anchor is the
    audited snapshot, already token/pair-validated by the shared gates);
  - then the normal dirty/quality gates — a genuine but dirty/stale 1h window
    classifies `E2Q_AUDIT_DIRTY` (`do_not_train`), never clean.
- **Rejected `WINDOW_4H/12H/24H`** — blocked with a "not enabled as a main
  outcome window" reason; not implicitly enabled.

A 1h window is never created by relabelling or combining insufficient 15m
evidence: the duration floor, dual governed anchors, and start-anchor targeting
each reject that case structurally before any quality classification.

## Implementation (Gate 2)

Smallest window-kind-specific change to
`src/printer_v1/operator_cli/e2q_memory_window_audit.py`:

- New constants: `E2Q_1H_WINDOW_KIND`, `E2Q_SUPPORT_ONLY_WINDOW_KIND`,
  `E2Q_VALID_MAIN_WINDOW_KINDS = {WINDOW_15M, WINDOW_1H}`,
  `E2Q_UNSUPPORTED_MAIN_WINDOW_KINDS = {WINDOW_4H, WINDOW_12H, WINDOW_24H}`,
  `E2Q_1H_MIN_ELAPSED_SECONDS = 2700.0`. `E2Q_REQUIRED_WINDOW_KIND` stays
  `"WINDOW_15M"` (the base kind).
- Gate 2 rewritten to admit the valid main kinds and block the rest with
  window-kind-specific reasons (support-only for 5m; not-enabled for 4h/12h/24h).
- New structural Gate 8 (`_validate_genuine_1h_window`) runs only for
  `WINDOW_1H`, after the shared structural gates and before quality
  classification. Fifteen-minute windows skip it entirely.
- All existing 15m gates, dirty-memory protections, `do_not_train` write-back,
  idempotent no-op behavior, hard locks, and "no memory/paper creation" outputs
  are untouched.

## Tests (Gate 3)

Fixtures and temporary DBs only. No source calls, scheduler runtime, persistent
DB mutation, or 1h proof.

- Existing E2Q suite `test_post_rc_lane_e2q_memory_window_audit.py`: **97 pass**
  unchanged — including the tests that require a bare `WINDOW_1H` (no anchors) to
  stay blocked, which the repair preserves.
- New `test_v2_6_1h_audit_gate.py` (**19 tests**): valid 15m clean/acceptable
  unchanged; 5m blocked support-only; genuine 1h clean candidate (including at
  the exact 2700s minimum) with `do_not_train=0`; short (<2700s), relabelled
  (missing timestamps), ungoverned (missing anchors), mismatched start-anchor
  token, and open 1h all blocked; dirty/stale genuine 1h classify DIRTY with
  `do_not_train=1` (never clean); 4h/12h/24h not enabled; retrieval, paper, and
  memory/episode tables zero-delta; no extra windows created.

Regression: e2z pipeline wiring, Lane Q 15m integrity guard, Lane H 1h bounded
factory, and Lane X12 1h runner suites remained green.

## Money Usefulness

The factory can now build genuine 1h continuation memories once a real 1h window
is closed with governed evidence, without weakening any 15m dirty-memory
protection. The duration floor and dual-anchor coverage requirement prevent a
short or relabelled window from being promoted as a 1h outcome, so 1h evidence
that reaches clean review is real continuation evidence — the input a future
sustained-vs-fake-pump lane needs, kept honest at the audit boundary.

## Remaining Blockers

- No live or proof 1h cycle was run in this lane (out of scope). A bounded 1h
  proof remains a separate operator-approved step.
- The 1h continuation minimum is `2700s` (45-minute continuation), inherited
  from the established `WINDOW_1H` contract; if a stricter full-3600s definition
  is ever desired it is a separate contract change across e2o_1h/Lane Q/E2Q.
- Coverage beyond dual anchors (per-snapshot completeness counts) is not
  populated by the 1h close writer; E2Q enforces the anchor/duration coverage it
  can observe. Richer 1h coverage accounting is `UNKNOWN_REQUIRES_RESEARCH`.

## Preserved Locks

Solana-only, memecoin-only, paper-only. No retrieval activation, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, funds,
paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors, memory
or episode creation, Source Governor or Central Scheduler bypass, or persistent
DB mutation. `WINDOW_5M_MICRO_EVENT` stays support-only; `WINDOW_4H/12H/24H`
stay disabled.

## V2-7 Readiness Decision

The 1h audit gate is repaired and verified at the unit level. V2-7 (a bounded,
isolated 1h proof) is **permissible next** under the same proof discipline used
for V2-5: fresh isolated DB plus verified backup, persistent-path rejection,
governed sources, `WINDOW_1H` only, bounded budgets, zero retries, persistent DB
hash/counts unchanged, and honest dirty/blocked outcomes. V2-7 is not started
and is not auto-approved by this closeout.
