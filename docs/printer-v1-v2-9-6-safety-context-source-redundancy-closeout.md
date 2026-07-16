# Printer V1 V2-9.6 Safety Context Source Redundancy Closeout

## Verdict

`V2_9_6_SAFETY_REDUNDANCY_PASS`

Lane: `V2-9.6 - Safety Context Source Redundancy`

V2-9.6 reduces GoPlus and Solana-RPC transport risk for the mandatory safety
context without weakening any safety evidence. GoPlus stays the sole primary
provider-risk contributor and is untouched. The Solana-RPC holder call (which
supplements only the authoritative on-chain holder-concentration field when
GoPlus cannot provide it) gains exactly one governed free/public backup RPC
endpoint, attempted at most once and only after an eligible transient
primary-RPC failure. Missing GoPlus evidence is never relabeled safe, no
unsupported LP-lock claims are added, and incomplete or conflicting safety
stays dirty/blocking. Deterministic proof is green; no live source call,
Attempt 5, or V2-10 work was performed.

## Audit result — existing composite-safety path

- **GoPlus (`safety_reference`)** is the mandatory primary provider-risk
  contributor: mint/freeze authority, metadata mutability, supply sanity,
  known-risk flags, token program, and holder concentration. If GoPlus is not
  usable, the composite blocks with `GOPLUS_MANDATORY_SAFETY_SOURCE_NOT_USABLE`
  (`SAFETY_BLOCKED_FOR_15M_MEMORY`) — it is never relabeled safe.
- **Solana RPC (`holder_concentration_reference`)** independently derives only
  one authoritative on-chain field — holder concentration, via
  `getTokenLargestAccounts` + `getTokenSupply` — and only when GoPlus's holder
  label is `HOLDER_CONCENTRATION_UNKNOWN`.
- The composite (`persist_safety_composite`, `MAX_CONTRIBUTIONS=2`) admits
  GoPlus plus exactly one holder contribution. A GoPlus-vs-RPC holder
  disagreement raises `HOLDER_CONCENTRATION_SOURCE_CONFLICT`, resets the label
  to UNKNOWN, and blocks. LP lock/burn is retained only from an exact-pair
  explicit unlocked/removed state (`_exact_liquidity_danger`) — no unsupported
  lock assumptions. Provenance-incomplete contributions block.
- The RPC holder transport already accepts an `rpc_url`, so a backup endpoint is
  injectable. Its failure taxonomy previously conflated transport with parse and
  4xx with 5xx, so eligibility needed the same precise split V2-9.5 introduced.

Result: the safety path already fails closed correctly; V2-9.6 only adds one
transport-resilience hop to the holder RPC without changing any classification.

## Implementation — narrowest safe contract

- `src/printer_v1/sources/solana_rpc_holder.py`: added the free/public keyless
  backup endpoint constant `SOLANA_PUBLIC_RPC_BACKUP_URL` (operator overridable,
  read-only, no key — consistent with the allowed "Solana public RPC" source),
  and refined the `_rpc_post` failure taxonomy so eligibility is precise:
  TLS/connection/read-timeout -> `solana_rpc_transport_failure` (eligible),
  HTTP 5xx -> `solana_rpc_http_server_error` (eligible), HTTP 429 ->
  `solana_rpc_rate_limited` (eligible), while JSON/decode defects ->
  `solana_rpc_malformed_response` and HTTP 4xx -> `solana_rpc_http_client_error`
  (both NOT eligible). The 429 string existing tests assert is preserved.
- `src/printer_v1/operator_cli/safety_context_source_redundancy.py` (new): the
  eligibility allowlist, `is_eligible_transient_solana_rpc_failure`, the default
  real backup adapter builder (bound to the backup endpoint), and the governed
  backup executor.
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
  (`_collect_preclose_context`): after the primary holder RPC fails with an
  eligible transient type, one governed backup RPC request is made
  (request key `{run}:{step}:context:holder_backup`). The composite receives a
  single holder execution — the backup if it produced a response, otherwise the
  preserved failed primary — so there is exactly one holder contribution. Both
  source attempts are persisted independently. The per-token holder RPC request
  budget was raised from 1 to 2 (primary + one backup:
  `_MAX_HOLDER_RPC_REQUESTS_PER_TOKEN`).
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`: the 4h-phase
  `holder_fallback_max` was raised from 1 to 2 for the same reason.

## Source and budget behavior

- Both attempts pass through the Source Governor and are Central-Scheduler owned
  (the backup runs synchronously inside the already-scheduled window-close
  context step — no new job, no new step, no cadence anchor or deadline
  movement).
- Both attempts are separately persisted: the primary failure row is preserved;
  the backup records its own request/response or failure row.
- Both attempts are separately budgeted: the backup is rate-budgeted against
  Solana RPC's own recent-request window, and the run/phase holder-RPC ceilings
  now allow primary + one backup (2 per token). The phase request ceiling
  already had headroom.
- At most one backup per token; the backup only supplies the on-chain holder
  field and never fabricates GoPlus-only provider-risk fields (mint/freeze
  authority, LP lock/burn, risk flags). No retry loops, recursion, or endpoint
  rotation. Non-eligible primary failures (malformed, parser defect, HTTP 4xx,
  RPC-level data error, governor/budget rejection) never fall back.
- Exactly one holder contribution and one composite row per snapshot; no
  duplicate contributions or evidence rows.

## Proof results

Focused deterministic proof `tests/test_v2_9_6_safety_context_source_redundancy.py`
(fixture-only, no live sources): **7 passed, 7 subtests passed.** It proves:

- primary holder-RPC success makes no backup call (backup adapter raises if built);
- each eligible transient failure (`solana_rpc_transport_failure`,
  `solana_rpc_http_server_error`, `solana_rpc_rate_limited`) plus a valid backup
  yields exactly one holder contribution (from `solana_rpc`), 2 persisted
  solana_rpc requests, 1 preserved primary failure, and no source conflict;
- double failure (primary + backup) leaves holder `UNKNOWN`, keeps the composite
  off `SAFETY_CLEAN`, and persists both attempts;
- non-retryable primary failures (`solana_rpc_malformed_response`,
  `solana_rpc_http_client_error`, `solana_rpc_holder_rpc_error`,
  `solana_rpc_holder_fixture_failure`) do not fall back (1 solana_rpc request);
- GoPlus stays mandatory: an unusable GoPlus blocks the composite
  (`GOPLUS_MANDATORY_SAFETY_SOURCE_NOT_USABLE`) even with a healthy RPC holder —
  missing GoPlus is never relabeled safe;
- a GoPlus-vs-holder disagreement raises `HOLDER_CONCENTRATION_SOURCE_CONFLICT`
  and blocks;
- provenance, replay, supervision, isolation, and locks are exercised via the
  governed source rows and the regression suites below.

Nearby regressions (fixture-only), all green:

- Composite safety contract, shared context evidence, V2-9.5 exact-pair
  redundancy, V2-8.1 4h runtime (with the raised holder budget), V2-9.2/9.3/9.4,
  V2-4/V2-5 full-runner, Source Governor / adapter contract, e2m persistence:
  `189 passed, 21 subtests`.
- Cadence, continuity, continuous lifecycle and runtime integration, long-window
  cadence/continuity, Lane Q, Lane K/E2Z, E2Z clean-memory, E2Q audit,
  financial-action lock, scheduler: green (run in batches; zero failures).

Replay remains source-free and read-only, DB isolation holds, supervision and
cancellation are unchanged (the backup is synchronous inside the scheduled step;
their suites pass unchanged and the backup never fires on the success paths they
exercise).

### Pre-existing, out-of-scope failures (not caused by V2-9.6)

Verified on clean HEAD `634ddd0` before any V2-9.6 change and unchanged after:

- the 12 known discovery acceptance/quota/stage failures
  (`test_v2_2m` / `test_v2_2h1` / `a3` / `a4`) — explicitly kept out of scope;
- 3 pre-existing `test_post_rc_real_evidence_collection.py` operator-output
  failures (`test_clean_safety_gives_clean_eligible_true`,
  `test_holder_rate_limit_reporting_is_clear_and_redacted`,
  `test_partial_safety_gives_nonempty_unresolved_fields`) — a separate
  operator-output drift cluster, untouched here.

Both clusters fail identically before and after this lane and are left for a
separate operator-approved cleanup.

## Money-usefulness contribution and what this improves

V2-9.6 does not itself add clean memory. Its contribution is safety-context
resilience: the transient Solana-RPC transport failures that (alongside the
GoPlus failure) made Attempt 4's 15m window DIRTY can now be survived by one
governed, honest backup endpoint for the authoritative on-chain holder field.
Combined with V2-9.5's price-snapshot redundancy, this materially increases the
chance a future authorized run closes a clean window and reaches the 4h phase —
without ever accepting wrong-pair, stale, or GoPlus-missing safety as clean.

## What remains locked

Unchanged and locked: retrieval activation, paper decisions, BUY/SELL/HOLD,
paper positions, trade events, paper trade audits, PnL, wallet/private-key/live
execution, paid API dependencies, scoring/ranking/confidence/weighted logic,
embeddings/vectors, WINDOW_12H, and WINDOW_24H. WINDOW_5M_MICRO_EVENT stays
support-only. GoPlus, Solana public RPC (primary and backup), and the backup
endpoint are all free/public and read-only; no paid dependency is introduced.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The backup covers only the on-chain holder-concentration field. GoPlus's
   provider-risk fields (authorities, LP lock/burn, risk flags) have no
   equivalent backup — a GoPlus transport failure still makes the window
   safety-incomplete (dirty/blocking), which is the correct fail-closed
   behavior but not a redundancy.
2. If a transient window takes down both the primary and backup RPC endpoints at
   the same close, the holder field stays UNKNOWN and the window stays
   blocking. Redundancy reduces, not eliminates, free-source fragility.
3. The backup endpoint host is a configured default; operators should confirm it
   remains free/keyless before an unattended long run and can override it.
4. The pre-existing discovery (12) and real-evidence-collection (3) test drift
   remain open for a separate cleanup lane.

## Whether Attempt 5 is technically ready but still unauthorized

Technically, yes. The durable launcher/supervision (V2-9.4), exact-pair price
redundancy (V2-9.5), and now safety-context holder redundancy (V2-9.6) together
address every failure mode the prior attempts exposed: host-process
disappearance, single price-source transport failure, and single safety-context
RPC transport failure. A future Attempt 5 launched through
`scripts/Start-V2-9-Proof.ps1` would exercise all three. **Attempt 5 remains
unauthorized** — it requires a separate, explicit operator approval and is out
of scope for this lane.

## Files changed

- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/operator_cli/safety_context_source_redundancy.py` (new)
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`
- `tests/test_v2_9_6_safety_context_source_redundancy.py` (new)
- `docs/printer-v1-v2-9-6-safety-context-source-redundancy-closeout.md` (this file)

## What was not touched

No cadence policy, window deadline, supervision, replay, isolation, one-proof
lock, GoPlus provider-risk logic, LP-lock policy, or composite conflict/blocking
logic changed. No live source was called. No persistent DB was touched. No
Attempt 5, V2-10, 12h, 24h, retrieval, paper decision, position, trade, audit,
or PnL work began.

## Next recommended phase

Hold. V2-9 remains BLOCKED pending a real audited 4h result. The three
capabilities that would make a further attempt worthwhile (durable supervision,
price-source redundancy, safety-context redundancy) are now all in place and
proven. Any Attempt 5, or the pre-existing-test cleanup, requires a new explicit
operator-approved lane.
