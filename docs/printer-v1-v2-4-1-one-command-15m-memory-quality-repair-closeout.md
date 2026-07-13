# Printer V1 V2-4.1 One-Command 15m Memory Quality Repair Closeout

## Status

Verdict: `V2_4_1_SAFE_BLOCK_WITH_CONTEXT_GAP`

V2-4.1 repaired the first-snapshot timing anchor, connected the existing
context-quality audit path, reconciled the stale Phase 28 readiness scanner,
integrated the shared six-area context resolver, corrected TRACK_NORMAL to six
snapshots without lowering coverage, and integrated bounded governed close-time
collection for market regime, Solana chain heat, exact-target safety, exact-
target ENTRY/EXIT realism, and side-aware trading flow. The final approved live
proof resolved those five requested areas from real governed responses for two
autonomously selected tokens. It still produced zero clean memories because the
legacy Lane Q safety-label gate disagrees with the shared 15m safety policy, and
one token also failed the existing chart gate. No second final proof was run.

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

The Solana Builder provider modules for CoinGecko, GoPlus, and Jupiter are not
yet authored in the repository. External endpoint/schema claims beyond the
current A6 implementation and this bounded proof remain
`UNKNOWN_REQUIRES_RESEARCH`. The existing DexScreener and Source Governor
modules were used only within their documented Printer roles.

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

## Final Governed Context Collection Integration And Proof

### Collection design and implementation

The Central Scheduler-owned close job now performs one fixed pre-close context
bundle per selected token before taking the exact close snapshot:

1. one governed CoinGecko `broad_market_context` request, consumed by both the
   market-regime and Solana-chain-heat recorders;
2. one governed GoPlus `safety_reference` request;
3. one governed Jupiter `paper_quote_realism` ENTRY request;
4. one governed Jupiter `paper_quote_realism` EXIT request.

The context budget is therefore four close-time requests per token and eight
for the two-token maximum. Each transport is an existing free/public,
explicitly injected, disabled-by-default adapter. Every request is recorded by
Source Governor. No retry, endpoint rotation, new provider, source loop, or
scheduler loop was added.

Collection precedes the close snapshot so the source response timestamps do
not look ahead of the evidence window. After the governed close snapshot is
persisted, the existing guarded insert helpers bind the stored responses to
that exact token, pair, and snapshot. GoPlus and Jupiter payloads now retain
their returned/requested mint identities, and the binder rejects a mismatch
without inserting evidence. E2M snapshot metadata now retains DexScreener
buy/sell counts for 5m, 1h, and 24h so the existing trading-flow parser can
derive direction and pressure.

The report now counts market, chain, safety, and quote evidence table deltas.
Report-only replay remains read-only and creates no calls, evidence, snapshots,
windows, episodes, or fingerprints.

### Focused verification

The one-command test module contains 14 methods. The aggregate Windows/Python
3.14 process remained unstable after several completed tests, so every method
was run individually with a normal `OK` summary and exit code `0`. The focused
coverage proves:

* four governed close-time requests and their response/failure trace;
* exact market and chain recorder handoff;
* exact-target safety and ENTRY/EXIT evidence insertion;
* fail-closed safety and quote mint mismatch behavior;
* side-aware flow direction and pressure from persisted E2M metadata;
* failure remaining dirty;
* six-snapshot TRACK_NORMAL coverage and 900-second timing;
* replay, exact identity, zero running jobs, and zero downstream deltas.

All eight shared-context tests also passed individually with normal summaries.
Additional stable pytest slices passed:

* GoPlus/Jupiter exact-mint normalization: `2 passed`;
* nearby GoPlus/Jupiter normalization and real-evidence orchestration:
  `4 passed`;
* flow normalization, direction/pressure, missing-side handling, and locks:
  `4 passed` with `5` subtests;
* broad-context recording/consumption and chain-heat classification:
  `4 passed`;
* E2M provenance/idempotency: `2 passed`;
* Lane Q context and retrieval/financial locks: `4 passed`.

`py_compile` and `git diff --check` passed. The only emitted warnings were the
known pytest-cache permission warning and Git line-ending notices.

### Final bounded live proof

Proof DB:

`data/printer_v1_v2_4_1_final_context_proof_20260713.sqlite3`

Backup:

`data/printer_v1_v2_4_1_final_context_proof_20260713.backup.sqlite3`

Run ID:

`42684711-e30e-493b-b1e0-d15028d0f176`

The copied operator DB was behind the V2-4 run-ledger migrations. The first
CLI invocation stopped in schema preflight before creating a run or making a
source request. Existing migrations were applied to the proof copy only. The
one actual live proof then completed with:

* two autonomous `TRACK_FAST` selections;
* two discovery requests;
* twenty exact-pair snapshots, ten per token;
* eight bounded close-time context requests;
* thirty total governed requests and thirty responses;
* zero source failures and zero automatic retries;
* two closed 15m windows;
* zero clean memories and two honest dirty windows;
* zero running jobs after stop.

| Mint | Pair | First snapshot | Close due | Final snapshot | Span | Snapshots |
| --- | --- | --- | --- | --- | ---: | ---: |
| `6baGyq4HLbUn93MQUGFqBktpXP8BRjpoxSsAap4ppump` | `EqMxjt3vQvFuWamr5DUYajMALRKHogF4N3Yxaa7RGZak` | `2026-07-13T14:43:24.613928+00:00` | `2026-07-13T14:58:24.613928+00:00` | `2026-07-13T14:58:29.025711+00:00` | `904s` | 10 |
| `7mki412wXATW1T3m9YVw6Msxu1JcJtDuT72Ft4Qfpump` | `FHT4RPAw3Ktas2sb3jZQDph37T3fFY4F5P7cLTMBe2nf` | `2026-07-13T14:43:25.260729+00:00` | `2026-07-13T14:58:25.260729+00:00` | `2026-07-13T14:58:33.517380+00:00` | `908s` | 10 |

Interior spacing was approximately 100 seconds for both TRACK_FAST targets.
The close jobs began approximately `0.069s` and `5.083s` after their due times;
both persisted spans exceeded 900 seconds.

### Real context results

For both tokens, all four close-time requests returned
`COMPLETE / CLEAN_DATA` with separate request and response IDs. The shared
resolver reported:

| Area | Token 1 | Token 2 |
| --- | --- | --- |
| Market Regime | `READY`, `NEUTRAL`, clean | `READY`, `NEUTRAL`, clean |
| Solana Chain Heat | `READY`, `SOLANA_WARM`, clean | `READY`, `SOLANA_WARM`, clean |
| Safety / Rug | `READY` under 15m policy | `READY` under 15m policy |
| ENTRY/EXIT realism | both exact-target routes ready | both exact-target routes ready |
| Trading Flow | `FLOW_CHOPPY / PRESSURE_BALANCED` | `FLOW_CHOPPY / PRESSURE_MODERATE_INFLOW` |
| Chart / Volatility | `READY` | `CHART_VOLATILITY_UNKNOWN` |

The two GoPlus rows proved mint authority renounced, freeze authority disabled,
metadata immutable, positive supply, and a supported token program. The free
response did not resolve holder concentration, liquidity lock/burn, or known
risk flags. Storage therefore honestly retained `SAFETY_UNKNOWN` and inserted
the rows as audit-only. The shared 15m policy considered these source-coverage
gaps acceptable because all hard safety fields passed, but the legacy first-
memory/Lane Q classifier still treated `safety_status_label=SAFETY_UNKNOWN` as
a blocker. This policy handoff mismatch kept both windows dirty.

The second token also produced `CHART_CONTEXT_DO_NOT_TRAIN` from its natural
round-trip path. That chart blocker is expected evidence behavior and must not
be weakened.

All four Jupiter rows were exact-target, clean-eligible evidence with an
available route and acceptable slippage/price impact. All market, chain,
safety, quote, and flow provenance remained linked to governed request and
response rows.

### Final proof DB deltas

| Table | Delta |
| --- | ---: |
| source requests / responses / failures | `+30 / +30 / 0` |
| discovery candidates | `+2` |
| selection batches / items | `+1 / +29` |
| tracking queue | `+2` |
| scheduler jobs | `+22` |
| token snapshots | `+20` |
| market / chain rows | `+4 / +4` |
| safety / quote evidence | `+2 / +4` |
| memory windows | `+2` |
| memories / fingerprints | `0 / 0` |
| retrieval queries / matches | `0 / 0` |
| paper decisions / positions | `0 / 0` |
| trade events / trade audits / paper audit reports | `0 / 0 / 0` |

The report-only replay produced zero new source calls and zero evidence rows;
all inspected proof counts remained unchanged.

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
2. Governed market, chain, exact-target safety, exact-target ENTRY/EXIT, and
   side-aware flow collection are integrated and live-proven. They no longer
   constitute a missing collection-path blocker.
3. The shared 15m resolver accepts `SAFETY_UNKNOWN` when every hard safety
   field passes and only optional free-source coverage remains unknown. The
   legacy first-memory/Lane Q classifier still blocks the same label. This
   policy handoff mismatch is the primary clean-promotion blocker.
4. One live token naturally produced `CHART_CONTEXT_DO_NOT_TRAIN`. This is an
   honest evidence outcome, not a collection defect, and must remain blocking.
5. The Solana Builder source stack does not yet contain provider-specific
   CoinGecko, GoPlus, or Jupiter modules. External endpoint and schema claims
   beyond the verified Printer adapters remain `UNKNOWN_REQUIRES_RESEARCH`.
6. Lane K's report includes historical copied windows; correctness is
   preserved, but run-local reporting remains noisy.
7. Clean promotion is structurally supported, but the final live proof did not
   produce a clean memory because the safety-policy handoff blocked both
   windows and chart quality independently blocked one.
8. The aggregate Windows/Python 3.14 test process remains unstable. Focused
   methods and stable nearby slices passed with normal summaries and exit code
   `0`; the instability was not hidden by skipping a failing assertion.
9. The AST scanner is intentionally conservative: new executable capability
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
result, governed context collection, exact-target persistence, replay, and lock
gates passed. Autonomous clean promotion remains blocked because the shared
15m safety policy and legacy first-memory/Lane Q safety-label gate disagree on
otherwise hard-field-complete `SAFETY_UNKNOWN` evidence. One token also had an
independent chart-quality blocker. V2-5 is not recommended.

The next operator-approved task must remain inside V2-4.1 and reconcile the
15m safety-policy handoff with the legacy first-memory/Lane Q classifier using
one explicit fail-closed contract. It must not make optional unknown fields
look known, weaken hard safety requirements, add providers, or force clean
memory. Any later proof must remain single-run, isolated, bounded, and honest;
zero clean memory remains valid when real evidence fails.

## Consolidated Context Mini-Sprint Gate 1 Closeout

The final consolidated V2-4.1 audit stopped at Gate 1. Static inspection
confirmed two unresolved evidence-contract boundaries that cannot be repaired
honestly by parser or handoff changes alone.

### Explicit fail-closed safety contract

The shared `WINDOW_15M` contract remains:

- mandatory evidence must be fresh, complete, traceable, and exact-target;
- mint authority, freeze authority, metadata mutability, supply validation,
  and token-program validation must pass;
- missing, stale, failed, mismatched, or untraceable mandatory evidence blocks;
- explicit unlocked-liquidity evidence and explicit provider risk flags block;
- holder concentration, LP state, and provider-risk coverage may remain
  honestly unknown only when all mandatory evidence passes and no known danger
  is present;
- optional unknown values must never be relabeled as known-safe values;
- unsupported or unmatched pool evidence remains `LP_STATE_UNKNOWN`;
- genuine `CHART_CONTEXT_DO_NOT_TRAIN` remains an independent blocker.

The shared resolver currently implements the optional-coverage policy through
`SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY`, while its emitted
`safety_status_label` still carries stored `SAFETY_UNKNOWN`. The first-memory
review consequently blocks the label before E2Q and Lane K can promote the
window. E2Q and Lane K consume the upstream window quality; neither provides a
separate safety-policy repair. This is a real shared-contract mismatch, not a
Lane Q quota or Lane K promotion defect.

### Holder concentration boundary

The existing governed sources can produce genuine concentration evidence:
GoPlus responses may include `holders` plus `total_supply`, and the governed
Solana RPC fallback uses `getTokenLargestAccounts` plus `getTokenSupply` with
exact-mint validation. The GoPlus normalizer still recognizes only its older
`top_10_holders` shape, and the one-command path does not invoke the RPC
fallback.

Those parser and invocation gaps are mechanically repairable. They were not
changed in this mini-sprint because the current safety evidence row has one
primary source-request/response trace. Copying GoPlus authority and token
fields into a row whose primary trace points only to Solana RPC would not
preserve complete cross-source provenance. A bounded composite-provenance
contract is required before that merge can satisfy the task's traceability
rule.

### Exact-pool LP boundary

No adopted local source contract currently proves `LOCKED`, `BURNED`, or
`UNLOCKED` for the exact selected pool types. The PumpSwap contract verifies
program ownership and the base mint at the known offset, but explicitly marks
the full pool layout, including LP-mint and reserve offsets, as
`UNKNOWN_REQUIRES_RESEARCH`. The inspected GoPlus live shape exposes
token-level pool and burn fields without an adopted exact-pair lock/burn
semantic contract. Raydium and Orca exact-pool lock/burn semantics are likewise
not established by the approved source stack.

Interpreting those fields would invent unsupported pool-specific behavior.
Accordingly unmatched and unsupported evidence remains `LP_STATE_UNKNOWN`.
Focused locked, burned, and unlocked regression cases cannot be implemented
truthfully until at least one supported pool layout and proof rule is adopted.

### Chart contract result

No shared Chart/Volatility policy defect was found. The resolver derives chart
context from exact-window snapshots and independently blocks unknown trend,
unknown volatility, audit-only chart context, and
`CHART_CONTEXT_DO_NOT_TRAIN`. The prior live chart block was a genuine data-
quality result and remains correctly blocking.

### Gate result

Because Gate 1 remained unresolved, this mini-sprint made no production-code,
test, migration, scheduler, source, or database changes. Gates 2 and 3 were
not entered. The single final isolated proof was not run, so there was no
second proof and no persistent database mutation.

The smallest safe next task remains inside V2-4.1: adopt one bounded composite
safety-provenance representation and one authoritative exact-pool LP
lock/burn contract for a specifically supported pool type. Only then should
the GoPlus holder parser, governed RPC fallback, unified safety label, and
exact-pool LP normalization be implemented and verified together. Provider
and pool semantics not covered by that contract remain
`UNKNOWN_REQUIRES_RESEARCH`.

The consolidated verdict remains
`V2_4_1_SAFE_BLOCK_WITH_CONTEXT_GAP`. V2-5 remains blocked.
