# Printer V1 V2-9.7E.24 Holder Source Reliability and Reporting Repair

## Verdict

`V2_9_7E_24_HOLDER_SOURCE_REPORTING_REPAIR_PASS`

## Stage 1 frozen design

Baseline: `7616a23baa991c24737982ea5882c307de5c084f` (`Prove post-repair holder and snapshot readiness`). This lane is offline-only. It does not authorize a provider request, an E.23 rerun, a live readiness cycle, or a pilot.

E.23 proved that GoPlus frequently returned an exact target without a usable holder field, the public Solana primary returned HTTP 429 for every candidate, and the PublicNode backup returned only rate-limit or transport failures. The backup therefore did not demonstrate meaningful independent reliability. The minimum frozen repair replaces PublicNode with exactly one fixed `helius_free` backup. GoPlus remains the primary provider-risk source and the public Solana RPC remains the primary holder-concentration source.

The backup contract is:

| Contract item | Frozen value |
|---|---|
| Product / endpoint | Helius standard Solana RPC, fixed host `mainnet.helius-rpc.com`; beta and other hosts forbidden |
| Authorization | Operator-owned Helius API key supplied at runtime; never stored, logged, included in evidence, or accepted from discovery data |
| Cost | Helius Free plan only, $0/month; no automatic upgrade or paid fallback |
| Published free quota | 1,000,000 credits/month and 10 RPC requests/second |
| Unit cost | Standard RPC methods cost one credit each; one complete holder fact uses two credits/transport operations |
| Methods | `getTokenLargestAccounts` followed once by `getTokenSupply`, both for the exact mint and explicit `finalized` commitment |
| Schema / units | raw base-unit integer strings (`amount`) plus `decimals`; top 20 token accounts maximum, no pagination; concentration uses the first ten accounts divided by exact-mint raw total supply |
| Freshness | provider context slot plus local capture/receipt time; Printer TTL remains 120 seconds; both method results must be complete, coherent, exact-target, and finalized |
| Errors | HTTP/auth/rate-limit/server/timeout, JSON-RPC error, malformed/missing fields, target mismatch, stale evidence, and unknown concentration all fail closed |
| Provenance | `helius_free`, `BACKUP`, redacted fixed host, exact mint hash/identity in the existing protected evidence row, methods, commitment, context slot, capture/receipt time, response/failure lineage, and underlying operation count |

Official contract sources: [Helius getTokenLargestAccounts guide](https://www.helius.dev/docs/rpc/guides/gettokenlargestaccounts), [getTokenLargestAccounts reference](https://www.helius.dev/docs/api-reference/rpc/http/gettokenlargestaccounts), [getTokenSupply reference](https://www.helius.dev/docs/api-reference/rpc/http/gettokensupply), [authentication](https://www.helius.dev/docs/api-reference/authentication), [endpoints](https://www.helius.dev/docs/api-reference/endpoints), [plans](https://www.helius.dev/docs/billing/plans), [credits](https://www.helius.dev/docs/billing/credits), [rate limits](https://www.helius.dev/docs/billing/rate-limits), and [error codes](https://www.helius.dev/docs/faqs/error-codes).

Source Governor owns every Helius request record and decision. The Central Scheduler-owned campaign invokes it only in the existing holder-eligibility step, only after an eligible transient failure from the primary RPC, and at most once per candidate. There is no retry, endpoint rotation, reconnection loop, or second backup. A response from two complete exact-target sources that yields different concentration categories is a blocking conflict; failure or absence never overrides a clean fact. Transport/auth/rate-limit/provider failures take precedence over target mismatch unless a response actually returned a different target.

The E.22 arithmetic counted governed adapter calls, but a Solana holder adapter can consume two transport operations. The corrected conservative per-candidate maximum is five: one GoPlus operation, two primary-RPC operations, and two Helius operations. With the worst Pump acquisition (12), combined zero-transport validation (9), and two reserved DexScreener snapshots, the derived candidate cap is four: `floor((45-12-9-2)/5)=4`. Worst case is 43, leaving two operations of slack. The ceiling stays 45 and both snapshot operations remain reserved.

The reporting repair adds durable start/finish evidence for every external Pump RPC operation before discovery normalization. Report-only replay reads that evidence from SQLite, not process memory. Cleanup queries use the real `printer_tracking_queue.queue_status` column. No request secrets or raw target parameters enter the operation log.

## Stage 2 implementation and proof

Implemented the frozen design without contacting Helius, GoPlus, Solana RPC,
DexScreener, or any other provider. All proof transports and DBs were isolated
fixtures.

### Production repair

- Registered `holder_concentration_reference` for the existing optional
  `helius_free` source and set its retry allowance to zero.
- Added a governor-only Helius holder adapter. Its production builder accepts
  only an operator-supplied key and constructs only the fixed mainnet host. It
  issues the two exact-mint finalized methods once each. There is no endpoint
  parameter, fallback host, retry, rotation, reconnect, session, paid path, or
  secret-bearing evidence field.
- Replaced the live default PublicNode backup with Helius Free. The historical
  factory key remains fixture-compatible for older offline tests, but the live
  default can no longer build or reach PublicNode.
- Preserved primary transient-failure admission. Missing Helius authorization
  fails closed as `helius_auth_missing` without a transport call. A future live
  preflight must require the operator-owned free-plan key before authorization
  consumption.
- Added exact-source Helius evidence reuse under the existing exact mint,
  purpose, role, parser/policy version, clean status, lineage, capture/receipt,
  and 120-second TTL gates.
- Added deterministic conflict resolution: multiple usable exact-target facts
  must agree on the categorical concentration label or eligibility blocks with
  `HOLDER_EVIDENCE_CONFLICT`. No vote, score, rank, weight, or confidence is
  used.
- Changed campaign charging to actual underlying transport operations. The
  governed-request count remains separately durable. Four candidates at five
  worst-case operations each, plus 12 Pump, 9 zero-transport validation, and 2
  reserved snapshots totals 43 of 45.
- Added migration 038 and a one-shot Pump transport decorator. Each operation
  writes a durable `STARTED` row before delegation and a terminal `COMPLETE` or
  `FAILED` row with start/finish time, ordinal, redacted host, method,
  commitment, role, and failure subtype. Raw params, signatures, mint targets,
  URLs, and credentials are not stored.
- Added a read-only canonical report projection. It queries
  `printer_tracking_queue.queue_status`, includes durable Pump and holder
  evidence, performs integrity/FK/forbidden-delta checks, and always records
  zero replay source requests. Replay has no dependency on process memory.

### Focused offline proof results

| Gate | Result |
|---|---|
| Exact target success and mismatch rejection | PASS |
| Stale, malformed, failed, unknown and conflicting evidence rejection | PASS |
| Helius governor request, quota unit and two-operation accounting | PASS |
| Fixed mainnet host, secret redaction, one adapter call, zero retry/rotation | PASS |
| Four-candidate cap and two-snapshot reservation within 45 | PASS |
| Transport/rate-limit/auth precedence over synthetic mismatch | PASS |
| Durable Pump success/failure timing and deterministic DB-only replay | PASS |
| Correct `queue_status` cleanup query | PASS |
| Integrity, foreign keys and forbidden-capability counts | PASS |

Verification: 26 tests plus 7 parameterized subtests passed across E.24, E.22,
E.19 and the nearest source-redundancy owner; 41 authoritative-live/reporting
regressions passed. Python compilation and cached diff hygiene passed. No live
source test or full suite was run.

### Readiness

The repair is ready only for consideration of one separately authorized bounded
live readiness cycle. It is not authorization for that cycle or a full pilot.

## Money-usefulness contribution

The design protects scarce readiness budget and prevents unavailable shared endpoints, incomplete holder data, or misleading failure labels from activating candidates. It does not claim that token accounts are beneficial owners and does not turn holder concentration into a score or trade signal.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Helius is an operator-approved free-tier dependency and is unavailable until a key is explicitly configured.
2. The two RPC methods describe token accounts, not deduplicated beneficial owners.
3. The four-candidate conservative cap may reduce pool breadth, but it is necessary to charge actual transport operations without raising the ceiling.
4. Live reliability and snapshot readiness remain unproven; this lane is deliberately offline.

## Locks and next authorization

Lifecycle windows, memory, retrieval, decisions, BUY/SELL/HOLD, positions, trades, PnL, wallets, keys in evidence, paid APIs, scoring/ranking, V2-9.7F, and V2-9.8 remain locked. A PASS may authorize only consideration of one separately approved bounded live readiness cycle.
