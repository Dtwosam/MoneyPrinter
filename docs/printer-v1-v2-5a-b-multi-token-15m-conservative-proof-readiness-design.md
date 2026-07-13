# Printer V1 V2-5A/B Multi-Token 15m Conservative Proof Readiness and Design

## Status

Lane: `V2-5A/B - Multi-Token 15m Conservative Proof Readiness and Design`

Verdict: `V2_5_CONSERVATIVE_PROOF_DESIGN_BLOCKED`

This lane is audit and design only. No discovery, source request, scheduler job,
snapshot, memory window, live proof, or database mutation was performed.

The V2-4.1 one-command factory is safe and bounded for its proven two-token
scope, but it is not yet ready for the first conservative scale proof. The
smallest meaningful V2-5 scale is three autonomously selected tokens. The
current command rejects more than two tokens, and any failed token step sets a
run-wide source-failure stop that cancels every other token's pending work.
Those two implementation boundaries must be repaired and tested before V2-5C.

## Source Stack Reviewed

The following active Printer documents were reviewed together:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-v2-3-one-command-memory-factory-design.md`;
- `docs/printer-v1-v2-4-1-one-command-15m-memory-quality-repair-closeout.md`;
- the one-command runner, CLI, scheduler, selection, context, safety, replay,
  reporting, and focused test paths.

Applicable Solana Builder material was limited to:

- `docs/solana-builder-source-of-truth/README.md`;
- `docs/solana-builder-source-of-truth/source-governor-evidence-rules.md`;
- `docs/solana-builder-source-of-truth/dexscreener-api-contract.md`;
- `docs/solana-builder-source-of-truth/solana-core-rpc-reference.md`.

The repository has no adopted provider-specific Solana Builder modules for
GeckoTerminal, CoinGecko, GoPlus, or Jupiter. Claims beyond the current Printer
adapters and prior governed proofs remain `UNKNOWN_REQUIRES_RESEARCH`.

## V2-5A Readiness Audit

### Current one-command boundary

The production command remains
`printer-run-one-command-15m-memory-factory`. It is proof-mode-only, accepts no
manual token list, invokes governed GeckoTerminal discovery and qualified
seeded random selection, schedules exact-pair DexScreener snapshots, collects a
bounded close-time context bundle, closes `WINDOW_15M`, runs the shared context
review and memory audit, and emits a terminal report.

The implementation currently enforces:

- one or two selected tokens only;
- one or two discovery requests only;
- five-second source timeout;
- zero automatic retries;
- 1,200-second total-duration cap;
- ten snapshots for `TRACK_FAST` and six for `TRACK_NORMAL`;
- one independent close anchor per token at first valid persisted snapshot plus
  900 seconds;
- five close-time context requests per token at most, including one conditional
  Solana RPC holder fallback.

The V2-4.1 final proof exercised two tokens, not conservative scale. It proved
independent anchors, cadence, exact identity, context gating, honest dirty
outcomes, report-only replay, zero running jobs, and all downstream locks. It
did not prove behavior above two tokens or continuation after one token fails.

### Safest token cap

The smallest conservative scale beyond the proven V2-4.1 boundary is exactly
three autonomous selections. Three is large enough to expose scheduler
interleaving, per-token budget accounting, failure isolation, and report
separation without jumping to the historical five-token runner scale.

The current validation `1 <= max_selected_tokens <= 2` blocks this proof shape.
The first V2-5 proof must use exactly three selected tokens after a narrow
implementation repair. The default production value should remain two; only an
explicit operator-approved V2-5 proof mode may permit three.

### Source budgets

The conservative three-token ceiling is:

| Budget area | Per-token maximum | Run maximum |
|---|---:|---:|
| GeckoTerminal discovery | not per token | 2 requests |
| DexScreener snapshots, `TRACK_FAST` | 10 | 30 |
| DexScreener snapshots, `TRACK_NORMAL` | 6 | 18 |
| Close-time context without RPC fallback | 4 | 12 |
| Conditional Solana RPC holder fallback | 1 | 3 |
| All close-time context | 5 | 15 |
| Worst-case governed requests | 15 | 47 |

The worst case is two discovery requests plus three `TRACK_FAST` tokens at ten
snapshot requests and five context requests each. Mixed or all-`TRACK_NORMAL`
runs consume less. These must be hard ceilings, not targets.

Source accounting must be both run-wide and per token. A token may not borrow
another token's unused request allowance to exceed its own snapshot or context
cap. No source request may occur after either relevant ceiling is exhausted.

### Public RPC fallback and rate limiting

The holder fallback is conditional: GoPlus holder evidence is attempted first,
and a governed read-only Solana RPC request is made only when concentration
remains unknown. The V2-4.1 proof recorded two public RPC rate-limit failures.
Public RPC availability and numeric limits remain operationally unstable; any
unverified behavior is `UNKNOWN_REQUIRES_RESEARCH`.

The V2-5 contract must therefore retain:

- at most one holder fallback per selected token;
- at most three holder fallbacks in the run;
- zero retries and zero endpoint rotation;
- no paid or archive endpoint;
- redacted host-only reporting;
- a rate-limited token remains honestly safety-blocked or dirty;
- a rate limit on one token does not consume another token's holder allowance
  and does not terminate unrelated token work.

### Scheduler volume and terminal guarantees

One selected token creates one cancelled discovery handoff job plus six or ten
factory jobs. The maximum for three `TRACK_FAST` selections is therefore 33
scheduler rows: three cancelled discovery handoffs and 30 run-step jobs.

Every run-owned scheduler row must finish `SUCCEEDED`, `FAILED`, or `CANCELLED`.
The terminal report must show zero `RUNNING` jobs, zero locks, and zero pending
run-owned jobs. Any ambiguous claim, unreleased lock, or terminal-state mismatch
is a global safe-stop failure.

### Cadence and independent anchors

The cadence contract is suitable for V2-5:

- `TRACK_FAST`: ten observations including opening and close, nominally 100
  seconds apart over the full 900-second window;
- `TRACK_NORMAL`: six observations including opening and close, nominally 180
  seconds apart over the full 900-second window;
- every close is anchored independently to that token's first valid persisted
  snapshot plus 900 seconds;
- no valid opening snapshot means that token fails closed;
- actual first-to-close persisted evidence must span at least 900 seconds.

The current tests prove two independent anchors. Three-token interleaving and
one-token failure continuation are not yet proven.

### Token and pair isolation

The current runner stores exact token ID, pair ID, mint, pair address, tracking
lane, source request IDs, snapshot IDs, and memory-window IDs on run steps.
Selection reads only `SELECTED` active-tracking items. Snapshot persistence and
the shared context resolver enforce exact target matching. STNP, deduplication,
cooldown, rotation, source quality, and audit-only isolation remain upstream
selection gates.

This is a strong identity boundary. V2-5 still requires a three-token fixture
proving that no request, snapshot, context row, safety contribution, quote,
window, episode, or fingerprint crosses token/pair boundaries.

### Rotation and candidate diversity

Qualified random active-token selection is seeded and reproducible. Eligible
identity is stably ordered before uniform seeded selection. Existing outcome
categories remain diagnostic and do not force the initial sample. `WATCH_ONLY`,
D1, and inactive candidates remain audit-only and cannot create active jobs.

The proof must report lane, source channel, initial classification, and any
available trajectory label for all three selections. A homogeneous natural
sample is not a reason to retry. Diversity is observed, not manufactured.

### Starvation blocker

The current execution loop processes the earliest pending run step. If any
snapshot or close step returns `ok=false`, or raises an exception, the runner
sets `SAFE_STOP_SOURCE_FAILURE`. Its finalizer then cancels every pending step
for the run. A target-specific failure on token A can therefore prevent tokens
B and C from reaching their windows.

This is fail-safe but does not satisfy V2-5's token-starvation gate. It is the
primary readiness blocker.

The narrow repair must distinguish:

- **token-local terminal failure:** exact-pair source failure, invalid opening
  snapshot, target mismatch, insufficient token evidence, or token-local close
  blocker; mark that token terminal-blocked, cancel only its pending jobs, and
  continue other tokens within their own budgets;
- **global safe stop:** Source Governor bypass or accounting failure, Central
  Scheduler integrity failure, database integrity or identity contamination,
  total-duration exhaustion, operator interruption, ambiguous job state, or an
  unexpected downstream delta; cancel all remaining run work.

No retry is introduced. Continuing unrelated tokens is not a retry of the
failed token.

### Reporting and copied-window noise

The terminal report's `memory_windows` query is run-local because it follows
memory-window IDs recorded on the current run's steps. Table deltas are also
before/after values for the proof run. However, each close result embeds Lane
K/E2Z pipeline output that can include historical windows copied into the proof
DB. This is known report noise, not evidence identity corruption.

Before V2-5C, the report must make current-run results authoritative by
`run_id`, step ID, selected exact target, and attached memory-window ID.
Historical copied-window summaries must be labeled separately and must not
affect per-token yield, completion, blockers, or verdict.

### Replay and database protection

Report-only replay reads the stored terminal JSON and adds a replay marker. It
does not execute sources or scheduler work. V2-4.1 proved zero new calls and
zero new evidence rows.

The proof must use a fresh isolated copy of the persistent database, a separate
verified backup of that proof copy, and all current migrations applied only to
the proof copy. The command must reject the canonical persistent path. The
persistent database SHA-256 and critical table counts must be captured before
and after and remain identical.

Replay acceptance requires unchanged proof-DB counts for requests, responses,
failures, scheduler jobs, snapshots, context rows, safety composites and
contributions, quotes, windows, episodes, memories, and fingerprints.

### Retrieval and financial locks

The final report already checks zero deltas for retrieval queries and matches,
paper decisions, paper positions, trade events, trade audits, and paper audit
reports. V2-5 must also explicitly report any PnL-like table if present, or
state that none exists. Any nonzero downstream delta is a global proof failure.

## Readiness Gate Decision

Caps and budgets can be defined conservatively, identity and replay boundaries
are strong, and terminal cleanup is fail-safe. Readiness does not pass because:

1. the one-command factory rejects the required three-token proof cap;
2. token-local failure currently cancels unrelated tokens;
3. three-token source, scheduler, isolation, and terminal reporting tests do not
   yet exist;
4. run-local reporting does not fully separate embedded historical Lane K
   summaries from authoritative current-run results.

V2-5C must not run until these narrow prerequisites are implemented and their
focused tests pass.

## V2-5B Conservative Proof Design

The following is the exact proof plan to use only after the blockers above are
repaired and verified.

### Run shape

- Command: `printer-run-one-command-15m-memory-factory`.
- Mode: explicit operator-approved V2-5 proof mode.
- Database: fresh isolated proof copy plus separate proof-copy backup.
- Main window: `WINDOW_15M` only.
- Autonomous selections: exactly three qualified active tokens.
- Manual token list or candidate insertion: prohibited.
- Minimum useful completion: at least two independently terminal window results
  among the three selected targets.
- Clean-memory quota: none.
- Discovery requests: maximum two.
- Source timeout: five seconds per request.
- Automatic retries: zero.
- Endpoint rotation: zero.
- Total run duration: exactly 1,200-second hard cap.
- Maximum scheduler rows: 33.
- Maximum governed source requests: 47.

If fewer than three eligible active tokens are autonomously selected, the proof
safe-stops as insufficient multi-token scale. It is not rerun to obtain a more
favorable sample.

### Per-token expectations

Each selected target must report:

- token ID, pair ID, mint, pair address, lane, source channel, and selection
  reason;
- selection seed and eligible-pool size;
- opening snapshot ID and timestamp;
- every scheduled and actual snapshot time;
- expected and actual snapshot count;
- spacing and evidence duration;
- close due time and actual close time;
- per-source request, response, and failure IDs;
- snapshot and context freshness, quality, and exact-target checks;
- market, chain, safety, holder, LP, provider-risk, ENTRY/EXIT, flow,
  chart/volatility, support-only 5m, and outcome labels;
- safety composite and contribution IDs;
- Lane Q/E2Q result, memory quality, `do_not_train`, and exact blockers;
- episode and fingerprint IDs if legitimately created;
- terminal status: clean, dirty, blocked, or token-local failed.

Six snapshots are required for `TRACK_NORMAL`; ten are expected for
`TRACK_FAST`. Every auditable window requires at least 900 seconds of persisted
evidence. A natural dirty or blocked result is valid and must not trigger a
retry.

### Failure handling

- A source failure is recorded through Source Governor with exact token and
  request trace.
- A token-local hard failure terminates only that token and cancels only its
  pending jobs.
- Other tokens continue unless a global stop condition occurs.
- A public RPC rate limit leaves holder concentration unknown and safety
  blocked for that token; it does not rotate endpoints or retry.
- Context failures may produce honest dirty memory when the close path remains
  structurally valid.
- No token may exceed its request, snapshot, context, or scheduler allowance.

### Starvation and contamination stop conditions

The proof fails and stops globally on:

- any Source Governor or Central Scheduler bypass;
- total governed requests above 47;
- scheduler rows above 33;
- any token consuming another token's budget;
- source request, snapshot, context, or memory target mismatch;
- same-token/new-pair ambiguity reaching a clean result;
- any cross-token or cross-pair evidence attachment;
- evidence duration below 900 seconds being accepted for clean review;
- a dirty, stale, incomplete, failed, or conflicting window promoted clean;
- fewer than two independent terminal window outcomes;
- any running or locked scheduler job at stop;
- persistent database hash or count change;
- any retrieval or financial delta.

### Required artifacts

V2-5C must preserve but not commit:

- isolated proof DB;
- proof-copy backup;
- persistent DB before/after hash and count manifest;
- command invocation and terminal JSON;
- run-local source-budget report;
- run-local scheduler/step report;
- per-token snapshot spacing and context report;
- per-token memory-quality/blocker report;
- proof-DB before/after delta manifest;
- report-only replay output and unchanged-count proof.

Only the V2-5 proof/closeout document may be committed unless a separately
approved implementation repair is required first.

## Required Verification Before V2-5C

Focused deterministic tests must prove:

1. three-token proof mode is accepted while ordinary defaults stay at two;
2. four selected tokens are rejected;
3. two discovery requests, 47 total requests, 15 per-token requests, three RPC
   fallbacks, 33 scheduler rows, zero retries, and 1,200 seconds are hard caps;
4. three tokens keep independent first-snapshot anchors and exact identities;
5. token A snapshot failure does not cancel token B or C;
6. token-local cancellation leaves no pending or running jobs for token A;
7. a global budget, scheduler, governor, identity, DB, or lock failure cancels
   every pending job;
8. public RPC rate limiting blocks only the affected token's safety result;
9. `TRACK_NORMAL` and `TRACK_FAST` coverage remains six and ten observations;
10. current-run reports exclude historical copied-window noise from yield;
11. report-only replay creates no calls, jobs, evidence, snapshots, windows,
    episodes, memories, or fingerprints;
12. retrieval and every financial table remain zero-delta.

## Money-Usefulness Contribution

This design moves the factory from a two-token implementation demonstration to
a minimally scaled, failure-isolated proof. It improves the credibility of
future memory growth by ensuring one unavailable token or public RPC response
cannot bias the run by silently preventing other selected tokens from reaching
their natural 15-minute outcomes.

The proof does not require clean yield. Honest dirty and blocked windows remain
useful operational evidence because they identify source, safety, chart, or
quality constraints without polluting the clean corpus.

## What V2-5 Still Does Not Unlock

This lane does not unlock or execute:

- V2-5C or any live proof;
- `WINDOW_1H`, 4h, 12h, or 24h;
- main-window use of `WINDOW_5M_MICRO_EVENT`;
- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- positions, trades, audits, or PnL;
- wallets, keys, funds, signing, or execution;
- paid APIs;
- scoring, ranking, confidence, or weighted logic;
- embeddings or vectors;
- Source Governor or Central Scheduler bypass;
- persistent database mutation.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk or blocker | Current result | Required response |
|---|---|---|
| Two-token hard cap | Blocking | Permit exactly three only in explicit V2-5 proof mode |
| Token-local failure causes run-wide cancellation | Blocking | Add token-local terminal failure and per-token cancellation |
| Public RPC rate limiting | Expected operational risk | One bounded call per token, no retry/rotation, honest safety block |
| Worst-case request pressure | Bounded at 47 by design | Enforce run-wide and per-token counters before every call |
| Scheduler pileup | Bounded at 33 by design | Enforce cap and zero pending/running/locked jobs at stop |
| Historical Lane K report noise | Reporting blocker | Make run-ID-local results authoritative and label history separately |
| Natural sample lacks category diversity | Non-blocking | Report honestly; do not retry or force category composition |
| Low or zero clean yield | Non-blocking when explained | Preserve exact per-token blockers and zero-clean validity |
| Cross-token evidence contamination | Hard stop | Exact identity assertions across every persisted artifact |
| Persistent DB mutation | Hard stop | Hash/count verification and isolated proof copy only |

## Final Verdict And Next Step

Final verdict: `V2_5_CONSERVATIVE_PROOF_DESIGN_BLOCKED`.

The conservative proof shape is fully specified, but the current one-command
implementation cannot execute it safely because it is capped at two tokens and
does not isolate token-local failures. The next operator-approved lane should be
a narrow V2-5 readiness repair that adds explicit three-token proof mode,
token-local terminal failure handling, hard per-token/run budgets, and run-local
report separation with focused tests.

Only after that repair passes may the operator authorize `V2-5C - Run bounded
proof`. No proof was run in V2-5A/B, and V2-5C does not start automatically.
