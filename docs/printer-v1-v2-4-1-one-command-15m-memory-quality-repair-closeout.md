# Printer V1 V2-4.1 One-Command 15m Memory Quality Repair Closeout

## Status

Verdict: `V2_4_1_SAFE_BLOCK_WITH_CONTEXT_GAP`

V2-4.1 repaired the first-snapshot timing anchor, connected the existing
context-quality audit path, reconciled the stale Phase 28 readiness scanner,
integrated the shared six-area context resolver, corrected TRACK_NORMAL to six
snapshots without lowering coverage, and completed the approved bounded live
proofs. The latest proof met the real 900-second timing and six-snapshot
requirements for both selected tokens and stopped safely, but it produced zero
clean memories because required governed context and evidence were absent. No
second integration proof was run.

This closeout does not approve V2-5.

## Source Stack And Scope

The active Printer V1 source stack, V2-3 design, V2-4 closeout, existing
scheduler/context/memory audit code, and relevant Solana Builder GeckoTerminal
and Source Governor documents were reviewed together.

Unverified external source behavior remains `UNKNOWN_REQUIRES_RESEARCH`. This
lane added no source adapter, source loop, provider, or external-data claim.

The implementation remained limited to `WINDOW_15M`, proof mode, at most two
autonomously selected tokens, Source Governor requests, Central Scheduler jobs,
memory-quality gating, and report-only replay.

## Audit Findings

### Timing defect

The original V2-4 orchestration scheduled token close jobs from orchestration
start. Discovery and opening-snapshot latency therefore reduced persisted
evidence duration below 900 seconds. The original live proof measured about
897 seconds for both windows.

### Context-quality gap

The original one-command close path invoked E2O window close, E2Q audit, and
Lane K promotion wiring, but it did not run the comprehensive existing context
review before promotion. The clean-memory review contract requires honest
evaluation of:

- market regime;
- Solana chain heat;
- safety and rug state;
- liquidity plus entry/exit realism;
- trading flow;
- chart and volatility;
- support-only 5m micro-event evidence;
- completed-window outcome evidence.

Unknown, partial, stale, mismatched, or missing critical context must block
clean promotion. `WINDOW_5M_MICRO_EVENT` cannot replace the main 15m window.

### Readiness-scanner contract drift

The Phase 28 readiness test expected `READY_CONTROLLED_CONTEXT`, but the old
hardening scanner performed raw substring searches across all production
Python. It treated lock-report strings such as `private_key`, `embedding`, and
`vector` as executable capabilities, and treated every `while True` as
unbounded even when an adopted runner had explicit duration/cycle limits and a
terminating branch.

No prohibited capability was found. The scanner scope and the duplicate Phase
21 raw-text assertion were stale relative to the approved bounded,
scheduler-owned, paper-only architecture.

## Adopted Repair

### First-snapshot anchor

Each token now receives one immediate scheduler-owned opening snapshot job.
Only after that snapshot is valid and persisted does the orchestrator schedule
the token's remaining snapshots and close job from:

```text
first valid persisted snapshot captured_at + 900 seconds
```

Each token has an independent anchor. Missing opening evidence fails closed.
At close, the actual persisted first-to-final snapshot duration must be at
least 900 seconds before the memory audit continues.

Replay does not duplicate opening jobs, anchored jobs, snapshots, windows,
episodes, fingerprints, or source calls.

### Existing context engines and gates

The close path reuses the established context insertion, context targeting,
freshness, memory-label, snapshot-derived 15m chart/micro/outcome, controlled
safety/quote overlay, and first-memory-review helpers. It writes the resulting
context row IDs, labels, evidence overlays, derived context, outcome, and
remaining blockers into the exact memory window's supporting context.

Lane K remains the only clean-promotion owner. A context-clean candidate stays
`PARTIAL_MEMORY` until Lane K evaluates it. Any context failure is marked
audit-only or dirty with `do_not_train=1` before Lane K runs.

### Readiness hardening

The raw source scan was replaced with an AST-based capability scan:

- comments and audit/report strings are not executable capabilities;
- executable wallet, key, live-trade, scoring, confidence, embedding, and
  vector identifiers remain forbidden;
- direct network imports outside `src/printer_v1/sources/` remain forbidden;
- approved source adapters may contain transport imports, while Source
  Governor enforcement remains independently tested;
- runtime frameworks remain forbidden;
- `while True` remains forbidden unless it contains explicit duration/cycle
  bounds and terminating control flow.

Focused negative tests prove that executable private-key code, direct network
bypass imports, and unbounded loops still fail.

## Tests And Regression Gates

All required gates produced normal pytest summaries and exit code `0`:

- focused Phase 28 plus scanner contract checks: `4 passed`;
- Phase 20 hardening and Phase 21 operator readiness: `26 passed`;
- focused V2-4.1 suite: `10 passed`;
- exact affected regression slice:
  `79 passed` across Lane E2M snapshot persistence and Phase 28 controlled
  context collection;
- `git diff --check`: passed, with only working-tree line-ending warnings.

The focused V2-4.1 tests cover delayed first-snapshot anchoring, 899-second
blocking, 900-second acceptance for further audit, independent token anchors,
replay/interruption idempotency, exact window attachment, critical-context
blocking, support-only 5m behavior, and locked retrieval/financial tables.

## Bounded Live Proof

### Setup

- Run ID: `027a8c24-5ca0-42c6-a0c2-1e57a3210c63`
- Proof DB: `data/printer_v1_v2_4_1_proof_20260713.sqlite3`
- Backup: `data/printer_v1_v2_4_1_proof_20260713.backup.sqlite3`
- DB mode: `PROOF_ONLY`
- Main window: `WINDOW_15M`
- Started: `2026-07-13T11:50:35.308897+00:00`
- Finished: `2026-07-13T12:05:43.680529+00:00`
- Total elapsed: about `908.372s`
- Maximum selected tokens: `2`
- Maximum discovery requests: `2`
- Source timeout: `5s`
- Total-duration cap: `1200s`
- Automatic retries: `0`
- Selection seed: `705225129131dd22df74198bb8bfaa1b`
- Eligible active pool: `30`

Printer selected both targets autonomously with no token list, fixture,
manual candidate insertion, threshold change, retry, or post-start code change.

| Lane | Token mint | Pair address |
|---|---|---|
| `TRACK_NORMAL` | `5tnYQAcWi62gQhan2Efk1rCHvPnvfX3qqJ7x42Smpump` | `3H8jVeeLjr4JYXB7BMXtKhzgtxzTtTUjsCrYJ6DNtdiC` |
| `TRACK_FAST` | `7mki412wXATW1T3m9YVw6Msxu1JcJtDuT72Ft4Qfpump` | `FHT4RPAw3Ktas2sb3jZQDph37T3fFY4F5P7cLTMBe2nf` |

### Source and scheduler results

- governed source requests: `17`;
- governed source responses: `17`;
- source failures: `0`;
- discovery requests: `2`;
- exact-pair snapshot requests: `15`;
- run steps: `15`, all succeeded;
- scheduler jobs created in the proof DB: `17`;
- running jobs after stop: `0`.

The original two discovery handoff jobs were cancelled rather than executed.
All timed snapshot and close actions remained Central Scheduler-owned.

### Per-token timing and quality

| Token | First valid snapshot | Scheduled close | Actual final snapshot | Evidence duration | Snapshots | Result |
|---|---|---|---|---:|---:|---|
| `5tnY...pump` | `2026-07-13T11:50:40.779474+00:00` | `2026-07-13T12:05:40.779474+00:00` | `2026-07-13T12:05:41.726819+00:00` | `900.947345s` | `5` | `DIRTY_MEMORY`, `do_not_train=1` |
| `7mki...pump` | `2026-07-13T11:50:41.492321+00:00` | `2026-07-13T12:05:41.492321+00:00` | `2026-07-13T12:05:43.144494+00:00` | `901.652173s` | `10` | `AUDIT_ONLY_MEMORY`, `do_not_train=1` |

Both windows passed the 900-second timing boundary and exact mint/pair
attachment. Window `157` had only five snapshots against the existing
six-snapshot 15m coverage policy, so snapshot-derived chart/outcome context
failed closed. Window `158` had ten snapshots and derived chart, volatility,
liquidity, micro-event, and held-outcome context successfully.

Both windows still lacked required clean governed context/evidence:

- market regime remained `UNKNOWN`;
- Solana chain heat remained `SOLANA_UNKNOWN`;
- safety and rug labels remained unknown;
- entry and exit realism remained unknown;
- valid target-matched safety evidence was absent;
- valid target-matched entry and exit quote evidence was absent;
- flow direction and pressure remained unknown.

Window `157` also retained unknown chart, volatility, micro-event, and outcome
labels because its snapshot coverage was insufficient. Window `158` recorded
`HELD_TO_15M_FADED`, `TREND_CHOPPY`, and `VOLATILITY_EXTREME`, but these labels
could not compensate for missing critical context. Its outcome therefore
remained `OUTCOME_UNKNOWN` for clean-memory purposes.

The 5m context was explicitly stored as
`SUPPORT_ONLY_NOT_MAIN_EVIDENCE` and did not replace 15m evidence.

### Memory result

- clean memories: `0`;
- dirty or audit-only windows: `2`;
- new memory fingerprints: `0`;
- clean promotion forced: no;
- zero clean memories treated as valid: yes.

## DB Deltas And Replay

Allowed proof DB deltas:

| Table | Delta |
|---|---:|
| source requests | +17 |
| source responses | +17 |
| source failures | 0 |
| discovery candidates | +2 |
| selection batches | +1 |
| selection batch items | +30 |
| tracking queue | +2 |
| scheduler jobs | +17 |
| token snapshots | +15 |
| memory windows | +2 |
| run ledger | +1 |
| run-step ledger | +15 |
| memory fingerprints | 0 |

Required zero downstream deltas:

- retrieval queries: `0`;
- retrieval matches: `0`;
- paper decisions: `0`;
- paper positions: `0`;
- paper trade events: `0`;
- paper trade audits: `0`;
- paper audit reports: `0`;
- PnL/memory-action rows: `0`.

The completed run received one report-only replay. Proof DB SHA-256 remained:

`82303F4376B16CBFABF78F961D0FC8AB32F39D5A382D6EDE6F3A880FFF59A596`

All inspected counts were unchanged; replay reported zero new source calls and
zero new evidence rows.

## Shared Resolver Integration And Bounded Proof

The one-command close handler now invokes
`build_window_15m_context_evidence()` with the exact token, pair, opening
snapshot, close snapshot, first valid snapshot time, and close snapshot time.
The resolver runs before E2Q. Its blockers are merged into the memory review,
persisted in `supporting_context_json`, and cause `MISSING_CRITICAL_DATA`,
`do_not_train=1`, and an E2Q dirty result before Lane Q/E2Z eligibility.

The TRACK_NORMAL schedule was corrected from five total attempts to six:
opening, four interior observations at nominal 180-second spacing, and the
close observation at first valid snapshot plus 900 seconds. TRACK_FAST remains
unchanged. The existing six-snapshot coverage rule was not lowered.

Proof DB:

`data/printer_v1_v2_4_1_context_integration_proof_20260713.sqlite3`

Run ID:

`62c363c3-08ed-473b-aa4c-4f5635c2e338`

The copied operator DB was behind migrations 027/028. The first CLI preflight
stopped before creating a run or making a live call. Existing migrations were
then applied to the proof copy only, after which the one actual bounded live
run completed. No source retry or second live proof occurred.

Autonomous selections:

| Mint | Pair | Lane | Snapshots | Evidence span | Spacing seconds |
| --- | --- | --- | ---: | ---: | --- |
| `5y8yv5z7L7tAYUWzznxq1RPRNmk6w9jNVUcYh4ewpump` | `72SHPB95Hqf6GJisp28oaLumaYsrxMsBwrwLCDQnMAyi` | TRACK_NORMAL | 6 | 900 | 180.723, 180.288, 179.708, 180.348, 179.681 |
| `Ch1vdFT6dVmkVLbJkBXGBv8iyhWv9ik1C45cYNsFpump` | `323MZ6ovqVfNhZUgFTPjzxXRovGZ6fdy4bCd5ZuUmjJS` | TRACK_NORMAL | 6 | 901 | 180.887, 180.432, 179.526, 180.508, 180.017 |

Both close jobs were anchored independently to their first valid persisted
snapshot. Each close observation occurred after its due time and met the
minimum duration. Exact mint/pair identity and all snapshot source traces were
preserved.

Both windows honestly resolved dirty with E2Q status `E2Q_AUDIT_DIRTY`.
Shared blockers were:

* no clean governed market context at or before close;
* no clean governed Solana chain context at or before close;
* no exact-target valid safety evidence;
* no exact-target valid ENTRY or EXIT quote evidence;
* flow direction/pressure unavailable from the stored source shape;
* chart/volatility not clean under the existing gate;
* one token also had a missing critical snapshot field.

Proof DB deltas included 12 snapshots, 12 run steps, 14 governed source
requests, 14 responses, zero failures, two memory windows, and 14 scheduler
jobs. There were zero deltas for memories/fingerprints, retrieval queries or
matches, paper decisions, positions, trade events, trade audits, paper audit
reports, and PnL-related activity. Running jobs after stop: `0`.

The report-only replay created zero source calls and zero evidence rows.

## Persistent DB Safety

Persistent DB: `data/printer_v1.sqlite3`.

SHA-256 before and after:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

The hash and all inspected source, snapshot, memory, retrieval, paper,
position, trade, audit, and PnL counts were unchanged. Only the isolated proof
DB and its backup were used for the proof.

## Money-Usefulness Contribution

The repaired anchor prevents sub-15m evidence from being mislabeled as a full
15m observation. The context gate prevents apparently complete price windows
from becoming training memory when market, chain, safety, flow, or realistic
entry/exit evidence is missing. Together these changes reduce false learning
and make zero-clean outcomes informative rather than something Printer must
hide or force.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The TRACK_NORMAL five-versus-six mismatch is resolved and live-proven. The
   integration proof produced six snapshots for each selected token.
2. The one-command proof source plan did not collect governed market-regime or
   chain-heat evidence. These remain clean-memory blockers.
3. The selected tokens had no target-matched valid safety, entry quote, or exit
   quote evidence in the copied operator DB. Evidence must never be fabricated.
4. End-snapshot-derived trading-flow rows were clean and target-matched, but
   direction and pressure remained unknown for this source payload.
5. Lane K's report includes historical copied windows; correctness is
   preserved, but run-local reporting remains noisy.
6. Clean promotion is structurally supported by the resolver and downstream
   gates, but autonomous clean promotion is not yet demonstrated because the
   one-command source plan does not assemble a complete governed bundle.
7. The AST scanner is intentionally conservative: new executable capability
   names, direct network clients outside source adapters, runtime frameworks,
   or unbounded loops fail readiness and require explicit architecture review.

## Preserved Locks

V2-4.1 did not activate or create:

- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- wallets, keys, funds, signing, or live execution;
- paid APIs;
- scoring, ranking, confidence, or weighted logic;
- embeddings or vectors;
- 1h, 4h, 12h, or 24h operation;
- dirty-memory training or decisions.

Source Governor and Central Scheduler boundaries remained mandatory. Solana-
only, Solana memecoin-only, paper-only V1 restrictions remain unchanged.

## Final Verdict And Next Step

Verdict: `V2_4_1_SAFE_BLOCK_WITH_CONTEXT_GAP`.

The timing, six-snapshot cadence, shared resolver handoff, fail-closed E2Q
result, replay, and lock gates passed. Autonomous clean promotion remains
blocked because the one-command source plan does not collect the complete
governed market, chain, safety, quote, and side-aware flow bundle. V2-5 is not
recommended.

The next operator-approved task must remain inside V2-4.1 and design the
smallest Source-Governor/Central-Scheduler-owned context collection plan for
the existing one-command run. It must not add providers or weaken any clean
gate. A later proof must remain single-run, isolated, bounded, and honest; zero
clean memory remains valid when real evidence fails.
