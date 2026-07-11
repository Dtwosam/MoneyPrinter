# Printer V1 V2-2AL.4 T3 Page-Cap Provenance Readiness Review

Status: AUDIT / READINESS ONLY
Lane: V2-2AL.4 - T3 Page-Cap Blocker and Failure-Provenance Readiness Review
Executor/model: Codex, standard/balanced mode
Anchor: `f0935f0 Add V2-2AL.3 bounded live T3 proof retry`
Verdict: `READINESS_COMPLETE_WITH_REPAIR_BLOCKER`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

This lane did not run live RPC, discovery, source fetching, runtime, scheduler,
memory generation, retrieval, paper decisions, or paper-trading work. It did not
change code, tests, migrations, or any DB rows. It inspected only local
documents, local source code, local test files, and existing local DB artifacts
in read-only mode.

The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.
A3 remains locked.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2aj-t3-solana-rpc-token-age-evidence-design.md`
- `docs/printer-v1-v2-2al-3-bounded-live-t3-proof-retry.md`

Supporting local artifacts inspected:

- `docs/printer-v1-v2-2ad-bounded-live-pumpportal-smoke-proof.md`
- `docs/printer-v1-v2-2ae-pumpportal-live-event-diagnostics.md`
- `docs/printer-v1-v2-2af-pumpportal-launch-timestamp-evidence-design-update.md`
- `docs/printer-v1-v2-2ag-observed-live-launch-tier-implementation.md`
- `docs/printer-v1-v2-2ah-observed-live-launch-live-proof.md`
- `data/printer_v1_v2_2ae_pumpportal_event_diagnostics.sqlite3` read-only
- `data/printer_v1_v2_2ad_pumpportal_live_smoke.sqlite3` read-only
- `data/printer_v1_v2_2ah_observed_live_launch_live_proof.sqlite3` read-only
- `data/printer_v1.sqlite3` read-only
- `src/printer_v1/sources/solana_rpc_token_age.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`

## Lane Boundary Confirmation

This readiness review is not a live proof and not an implementation lane.

It does not:

- expand the 3-page cap
- add endpoint rotation
- add paid/archive RPC
- retry the failed AL.3 mint
- select a new mint through live discovery
- use pair age, `captured_at`, migration time, first trade, or
  `OBSERVED_LIVE_LAUNCH` as token creation time
- unlock A3
- unlock V2-3
- create memory, retrieval, paper decisions, positions, trades, audits, or PnL

## Question 1 - Approved Retry-Mint Readiness

The failed V2-2AL.3 mint
`pumpgrWRAztPTe9HpqUUj23hWDcz1qvkbMRiDM6wint` is rejected for the next retry
because it exhausted the approved 3-signature-page cap before reaching the mint
history start. The retry confirmed the Token-2022 byte-82 layout repair, but it
did not prove T3 creation-time evidence.

The best local source for a fresher retry mint is the V2-2AE PumpPortal
event-level diagnostics proof DB. That proof recorded one clean governed
PumpPortal `pumpfun_launch_stream` response with four mint-bearing launch
events observed during `subscribeNewToken`. The events had no explicit
`tokenCreatedAt`, `createdTimestamp`, or `timestamp`, so they did not satisfy
T2, but they are local evidence of mint-bearing launch-stream observations.

No live discovery or new source fetching was run for this review.

## Candidate Mint Table

| Mint | Local artifact source | Observed timestamp | Source channel | Evidence it was near launch | Expected page-cap suitability | Rejection reason |
| --- | --- | --- | --- | --- | --- | --- |
| `6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump` | `data/printer_v1_v2_2ae_pumpportal_event_diagnostics.sqlite3`, `printer_source_responses.id=1072` | `2026-07-10T08:21:26.045788+00:00` | `pumpfun_launch_stream` / `subscribeNewToken` | Mint-bearing event from PumpPortal launch stream; `dex=pumpfun`; `poolSource=pumpportal`; liquidity about 4650 USD at observation | Best available local candidate: observed directly in the launch stream and likely lower-history than the previously failed high-history mint | None for readiness; still requires bounded T3 proof after provenance repair |
| `GDNjfwVEZ8qHdjdm3JHwYzA2SMwaVc9jSuxdp75Tpump` | `data/printer_v1_v2_2ae_pumpportal_event_diagnostics.sqlite3`, `printer_source_responses.id=1072` | `2026-07-10T08:21:26.045788+00:00` | `pumpfun_launch_stream` / `subscribeNewToken` | Mint-bearing event from PumpPortal launch stream; `dex=pumpfun`; `poolSource=pumpportal`; liquidity about 4515 USD at observation | Suitable fallback candidate, but not selected because the first acceptable AE mint is enough for a single retry | Not selected; avoid multiple retry targets |
| `5aU5MqsjLxZsqsQLURxmPTWUa6U8CvmXNyRQd8i8pump` | `data/printer_v1_v2_2ae_pumpportal_event_diagnostics.sqlite3`, `printer_source_responses.id=1072` | `2026-07-10T08:21:26.045788+00:00` | `pumpfun_launch_stream` / `subscribeNewToken` | Mint-bearing event from PumpPortal launch stream; `dex=pumpfun`; `poolSource=pumpportal`; liquidity about 4500 USD at observation | Suitable fallback candidate, but not selected because the first acceptable AE mint is enough for a single retry | Not selected; avoid multiple retry targets |
| `6qoof98YdCmSNyNciLM8GuYQnmwQ66TwKqux38bLpump` | `data/printer_v1_v2_2ae_pumpportal_event_diagnostics.sqlite3`, `printer_source_responses.id=1072` | `2026-07-10T08:21:26.045788+00:00` | `pumpfun_launch_stream` / `subscribeNewToken` | Mint-bearing event from PumpPortal launch stream; `dex=pumpfun`; `poolSource=pumpportal`; liquidity about 4500 USD at observation | Suitable fallback candidate, but not selected because the first acceptable AE mint is enough for a single retry | Not selected; avoid multiple retry targets |
| `pumpgrWRAztPTe9HpqUUj23hWDcz1qvkbMRiDM6wint` | `docs/printer-v1-v2-2al-3-bounded-live-t3-proof-retry.md` | Prior AL/AL.3 approved proof mint; not a fresh AE launch-stream artifact | Solana RPC T3 proof target | Mint account validation passed after Token-2022 layout repair | Poor for next retry under current cap: 3 signature pages exhausted before reaching mint history start | Rejected for AL.5 retry candidate due page-cap exhaustion |

## Approved Retry Mint

Approved retry mint for the next bounded T3 live proof after provenance repair:

`6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`

Reason:

- It came from a local governed PumpPortal `pumpfun_launch_stream` artifact.
- It was observed in a `subscribeNewToken` launch-stream response.
- It is a valid Solana-shaped mint string.
- It is not the previously failed high-history mint.
- It is the first acceptable mint in the clean AE response, which avoids any
  ranking, scoring, confidence, or weighted selection.

This approval does not mean the mint will pass T3. It only means it is a better
bounded retry target than the AL.3 high-history mint because it was locally
observed close to launch time.

## Page-Cap Suitability Finding

Finding: `SUITABLE_CANDIDATE_EXISTS_WITH_BOUNDARY_RISK`

The AE candidate is more suitable than the AL.3 failed mint because it was
captured from a PumpPortal launch stream rather than reused from a later
high-history proof target. A near-launch mint is more likely to have its
initialization transaction reachable within the current approved cap:

- max 8 total RPC operations
- max 3 `getSignaturesForAddress` pages
- max 3 `getTransaction` calls
- max 1 `getBlockTime` call
- 10-second timeout
- zero retries

However, the suitability is not a guarantee. The next proof must still fail
honestly on page-cap exhaustion, pruning, rate limiting, missing transaction,
mint mismatch, null/future block time, or any other bounded failure.

No page-cap increase, endpoint rotation, paid/archive RPC, or fallback timestamp
substitution is approved by this review.

## Question 2 - Failure-Provenance Readiness

Current failure provenance is not strong enough for another live retry.

Static inspection shows:

- `_fetch_token_age_data()` tracks `request_ids`, `methods_attempted`, and
  `pages_fetched` internally.
- The T3 success path emits all 15 `t3_*` provenance fields.
- The T3 failure path returns `fixture_status`, `failure_type`, and
  `failure_message`.
- `_t3_failure_result()` records a failed normalized result with source name,
  request kind, source status, data quality, failure type, and failure message.
- Failed T3 normalization intentionally emits no `t3_*` fields.

Fail-closed token-age behavior is correct: failures must not populate
`token_created_at`, `token_age_seconds`, or `token_age_evidence_tier`, and must
not unlock A3.

The auditability gap is different: a bounded failure currently loses safe
partial trace fields that are needed to understand exactly where a live proof
stopped.

## Safe Partial Failure Fields Needed

A future repair should preserve safe, non-age-producing failure provenance such
as:

- requested mint
- redacted RPC host
- RPC methods attempted
- request IDs
- signature pages fetched
- transaction calls attempted
- block-time calls attempted
- failure stage

These fields must remain audit/provenance only. They must not become
`token_created_at`, `token_age_seconds`, `token_age_evidence_tier`, A3 evidence,
retrieval evidence, memory evidence, paper decision evidence, or trading
evidence.

## Failure-Provenance Decision

Decision: `HARD_AUDITABILITY_BLOCKER_REQUIRING_REPAIR_FIRST`

The absence of partial failure provenance is not acceptable for the next bounded
retry. V2-2AL.3 already required the operator report to infer method progress
from the failure message. A second live retry should not repeat that weakness.

The next lane should repair failure provenance before V2-2AL.5. The repair must
preserve all current limits:

- max 8 operations
- max 3 signature pages
- max 3 transaction calls
- max 1 `getBlockTime`
- 10-second timeout
- zero retries
- no page-cap increase
- no paid/archive node dependency
- no endpoint rotation
- no token-age fallback from pair age, `captured_at`, migration time, first
  trade, or observed-live status

## Safety Confirmations

- No live Solana RPC was called.
- No PumpPortal call was made.
- No discovery or source fetching was run.
- No persistent DB rows were mutated.
- Existing DB artifacts were inspected read-only.
- No code, tests, migrations, or command paths were changed.
- No memory windows were created.
- Retrieval remained paused.
- Paper decisions remained paused.
- BUY/SELL/HOLD remained locked.
- Positions, trades, audits, and PnL remained locked.
- No wallet, private key, signing, live execution, paid API, score, ranking,
  confidence, weighted logic, embedding, or vector path was added.
- A3 remains locked.
- V2-3 remains paused.

## Readiness Verdict

`READINESS_COMPLETE_WITH_REPAIR_BLOCKER`

This review found a suitable local retry mint from an existing governed
PumpPortal launch-stream artifact:

`6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`

But the next live proof should not run yet. Failure-provenance repair is needed
first so bounded failures preserve enough safe audit trace without creating
token-age evidence or loosening any V1 lock.

## Exact Next Lane

`V2-2AL.4A - T3 Failure-Provenance Repair`

After V2-2AL.4A is implemented and independently verified, the next live proof
lane can be:

`V2-2AL.5 - Bounded Live T3 Proof With Approved Recent Mint`

using:

`6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`
