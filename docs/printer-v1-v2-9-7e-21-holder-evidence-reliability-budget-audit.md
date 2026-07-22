# V2-9.7E.21 Holder Evidence Reliability and Campaign Budget Audit

**Verdict:** `V2_9_7E_21_HOLDER_RELIABILITY_BUDGET_AUDIT_PASS`

**Repair-lane readiness:** READY for a separately authorized combined
design-and-repair lane. NOT READY for another live cycle.

## Scope and evidence

- Baseline: `eb27d8b0e822cbf5d4930ef970920b6641c9e163`,
  `Close bounded live holder and snapshot readiness blocker`.
- Read-only DB:
  `C:\Users\dtwof\PrinterPilot\E20\printer-v1-e20-readiness.sqlite3`.
- Access used SQLite `mode=ro&immutable=1`, `PRAGMA query_only=ON`; integrity
  was `ok` and foreign-key check returned zero rows.
- Evidence was the active source stack, E.19/E.20 documents and owners, E20
  DB, and redacted report. No provider, DB, production code, or corpus was
  contacted or changed.

Failures lack a request foreign key and rows lack endpoint-host provenance.
Role is nevertheless recoverable from the deterministic request-key suffix,
committed fixed endpoints, serial ordering, and exact timestamps. The missing
durable linkage is a repair requirement.

## Exact E.20 holder-request timeline

UTC times are shown. Identities are redacted hashes. Age is finalized Pump
`block_time` to GoPlus request. `P` is primary
`api.mainnet-beta.solana.com`; `B` is backup
`solana-rpc.publicnode.com`.

| # | Identity | Age | GoPlus request/receipt | P request/failure | B request/failure |
|---:|---|---:|---|---|---|
| 1 | `sha256:5aaf3d6af9a6f60174d4` | 62.823045s | `16:44:16.823045` / `16:44:18.655774` | `16:44:18.655774` / `16:44:19.269861` 429 (0.614087s) | `16:44:19.269861` / `16:44:51.016511` timeout (31.746650s) |
| 2 | `sha256:a86478c295818a99b7bf` | 106.019974s | `16:44:51.019974` / `16:44:51.822631` | `16:44:51.822631` / `16:44:52.455219` 429 (0.632588s) | `16:44:52.455219` / `16:45:21.222842` 429 (28.767623s) |
| 3 | `sha256:921ea66a6dbe5a9416b9` | 122.222842s | `16:45:21.222842` / `16:45:21.935690` | `16:45:21.937698` / `16:45:22.555297` 429 (0.617599s) | `16:45:22.556740` / `16:45:52.972829` timeout (30.416089s) |
| 4 | `sha256:49b41e3849a4c79ae382` | 152.972829s | `16:45:52.972829` / `16:45:53.783494` | `16:45:53.785938` / `16:45:54.398733` 429 (0.612795s) | `16:45:54.398733` / `16:46:23.167292` 429 (28.768559s) |
| 5 | `sha256:4d9a091fae2a1f6d31f2` | 184.172651s | `16:46:23.172651` / `16:46:23.989505` | `16:46:23.989505` / `16:46:24.606028` 429 (0.616523s) | `16:46:24.606028` / `16:46:55.031167` timeout (30.425139s) |
| 6 | `sha256:09cf666f4c83a7939001` | 215.031773s | `16:46:55.031773` / `16:46:55.867184` | `16:46:55.868035` / `16:46:56.436159` 429 (0.568124s) | `16:46:56.438181` / `16:47:25.326844` 429 (28.888663s) |
| 7 | `sha256:b3089bb297bbcd2d1cf0` | 253.326844s | `16:47:25.326844` / `16:47:26.252566` | `16:47:26.252566` / `16:47:26.883213` 429 (0.630647s) | `16:47:26.883213` / `16:47:57.287531` timeout (30.404318s) |
| 8 | `sha256:3d54f8ee233259529d09` | 277.289557s | `16:47:57.289557` / `16:47:58.001882` | `16:47:58.001882` / `16:47:58.606571` 429 (0.604689s) | `16:47:58.606571` / `16:48:27.484148` 429 (28.877577s) |

### Concurrency, method, role, and spacing

- Concurrency was exactly one; the owner evaluated candidates synchronously.
- Order was GoPlus, primary, then one transient-eligible backup. Backup began
  immediately after primary failure; there was no intentional pacing.
- Every RPC attempt failed on the first HTTPS POST JSON-RPC method,
  `getTokenLargestAccounts`; `getTokenSupply` was never reached. Sixteen
  governed RPC requests therefore caused 16 underlying RPC operations.
- Primary starts were about 31.6-33.6 seconds apart and backup starts about
  30.8-32.3 seconds apart. This was incidental backup latency, not Scheduler
  pacing. The next candidate began 0-5.4ms after backup terminalization.
- All eight primaries returned 429. Backups produced four timeouts and four
  429s. No `Retry-After` was preserved.

## Burst and endpoint-independence verdicts

Printer did not create concurrent or same-endpoint burst traffic. Each endpoint
saw roughly one holder request every 30 seconds, below the official primary
limit of 40 requests per method per 10 seconds. The primary failures are
therefore consistent with external shared-IP/service limiting, blocking, or an
unpublished dynamic restriction, not E20 exceeding that published ceiling.
Printer still lacks deliberate pacing, `Retry-After` provenance, and
operation/connection-wide accounting.

The fixed hostnames provide only syntactic diversity. Meaningful independent
redundancy is **NOT PROVEN**: neither succeeded; PublicNode's cost/auth/limits
and service contract remain unknown; infrastructure independence is unknown;
and host/role is not durably linked to each failure. The backup needs its own
adopted provider contract before Printer can rely on it as effective redundancy.

## Provider freshness

Candidates were only 62.823045-277.289557 seconds old. GoPlus returned HTTP 200
and locally normalized `COMPLETE / CLEAN_DATA` for all eight, but no usable
holder rows. This makes provider indexing maturity a likely contributor, not a
proven cause. GoPlus exposes no provider capture time, slot, cache age, or
guaranteed indexing delay. Its 300-second registry TTL is local receipt-age
policy, not provider-freshness proof. E20 also received complete envelopes, not
the documented code-2 partial state associated with a suggested later request.

A maturation delay is campaign-compatible only as Scheduler `scheduled_for`
work: zero requests while waiting, fixed deadline enforcement, and an honest
block when time is insufficient. E20 cannot justify a threshold because even
the 277-second candidate lacked holder evidence. A design must freeze the value
from a provider contract or offline fixture proof.

## Campaign-budget breakdown

| Phase | Governed | Transport | Result |
|---|---:|---:|---|
| Pump acquisition | 12 | 12 | 3 signature pages + 9 decodes |
| GoPlus | 8 | 8 | holder unknown |
| Primary RPC | 8 | 8 | eight 429s |
| Backup RPC | 8 | 8 | four timeouts + four 429s |
| Combined validation | 9 | 0 new | reused acquired proofs |
| DexScreener readiness | 0 | 0 | not reached |
| **Total** | **45** | **36** | exact ceiling consumed |

Separate owners were bounded locally but had no shared advance reservation.
E.19 budgeted at most 9 Pump plus 5 discovery/enrichment plus 24 holder calls.
E20 actually composed 12 Pump, 9 combined-validation, and 24 holder operations:
45 before reserving either required snapshot.

Without raising the ceiling, Printer can freeze proofs, run zero-source gates
first, reserve two snapshots, derive the candidate cap from remaining worst-case
cost, and stop at two eligible candidates. Under the observed 12 + 9 shape,
seven three-call candidates plus two snapshots total 44. Validation of an
already acquired proof may be classified as Scheduler/storage work rather than
a second provider operation only through explicit design and tests; its audit
provenance must remain.

## Exact-target evidence reuse

Fresh holder evidence can be reused with zero transport only when it preserves:

- exact lowercased mint and exact request purpose;
- original source, endpoint role/redacted host, request/response IDs,
  capture/receipt time, parser/policy version, and lineage;
- `COMPLETE / CLEAN_DATA`, exact-target, known holder label, and no malformed,
  stale, or conflicting condition; and
- source TTL at eligibility time: currently GoPlus 300s, Solana RPC 120s.

Receipt TTL must not be called provider-time proof. Source/parser-policy change
invalidates reuse. Reuse records lineage to the original response, creates no
fabricated response, and cannot bypass the Governor. Different mint/source,
failed/mismatched/unknown evidence, or stale evidence is never reusable.

## Reporting defect

`_holder_execution_fact` compares returned mint before checking failed status
or response absence. A transport failure has an empty payload, so it becomes
`HOLDER_EVIDENCE_TARGET_MISMATCH`.

Correct precedence is:

1. missing execution;
2. governor/provider/rate-limit/transport/parser failure or no response,
   preserving subtype;
3. stale/conflicting response;
4. malformed/incomplete quality;
5. target mismatch on a received parseable response;
6. exact-target unknown concentration; then
7. exact-target known concentration.

Mismatch remains blocking; it cannot outrank a response that never existed.

## Repair-option comparison

| Option | Decision | Why |
|---|---|---|
| Scheduler pacing without retry | Hygiene, not main fix | E20 was serial/sparse; fixed pacing improves determinism but cannot cure observed shared-endpoint limits |
| Maturation delay | Include conditionally | Freshness is plausible; delay must be scheduled, bounded, and based on a frozen evidence-backed threshold |
| Exact-target reuse | Include | Reduces calls safely under strict identity, provenance, TTL, and version gates |
| Fixed free-source redundancy | Defer for contract | Current backup independence is unproven; any addition must be one fixed governed provider |
| Tighter eligibility | Include | Apply zero-source gates first, budget-derived cap, and stop at two without score/rank |
| Safety-contract change | Reject | Weaker holder evidence would create dirty safety and false readiness |

Paid APIs, endpoint rotation, hidden retry loops, scoring/ranking/confidence,
weighted logic, and weaker safety evidence are rejected.

## Recommended minimum repair design

Build one deterministic **mature/reuse/reserve/pace** stage owned by the Central
Scheduler and Source Governor:

1. Freeze finalized proofs and apply all zero-source gates.
2. Use one ledger for actual underlying operations, governed calls, validation,
   fixed deadline, and two reserved snapshots. Refuse work that consumes the
   reservation.
3. Reuse only exact fresh evidence under the contract above.
4. Otherwise schedule a design-frozen maturation boundary; never sleep inside
   the source owner or restart automatically.
5. Evaluate sequentially with fixed pacing: one GoPlus, one primary only when
   needed, and at most the existing fixed backup after an eligible transient
   failure. No retry or rotation.
6. Persist endpoint role, redacted host, RPC method, underlying count, explicit
   commitment/context, request-failure linkage, and `Retry-After`.
7. Stop at exactly two eligible candidates or block with snapshot capacity
   intact; apply corrected reporting precedence without weakening eligibility.

An additional free/public source is not yet proven necessary. If the repaired
fixed path still fails offline reliability gates, a later adoption must pin one
provider's cost/auth/free quota, exact-mint request, documented holder schema,
commitment/context, units, capture/TTL, limits, errors/nulls, fixed endpoint
role, provenance, operation accounting, zero retry/rotation, and conflict rules.
An allowed general source name does not itself authorize that role.

## Focused proof before another live cycle

The design-and-repair lane must prove offline:

1. fake-clock spacing, sequentiality, zero overlap/retry/rotation;
2. worst-case ledger reservation for two snapshots;
3. exact reuse acceptance plus stale/mismatch/source/version rejection;
4. maturation due-time, deadline refusal, cancellation, replay, and zero calls
   while waiting;
5. endpoint/method/commitment/operation/failure/`Retry-After` provenance;
6. factual failure precedence and genuine mismatch blocking;
7. deterministic two-or-none, no scoring/ranking;
8. cleanup, integrity/FKs, zero forbidden deltas, and zero-source replay.

Only after this passes may an operator separately authorize one new live
readiness cycle. E20 must not be rerun implicitly.

## Money-usefulness contribution

This audit separates provider scarcity from avoidable budget composition. The
repair can reserve the market evidence needed for a future clean 15m judgment,
reduce duplicate calls through exact reuse, and avoid spending a whole campaign
on immature candidates without weakening safety or buying data.

## Functionality Risks / Setbacks / Efficiency Blockers

- Shared public primary capacity failed despite sparse traffic.
- Backup calls consumed 29-32 seconds each and yielded no evidence; its service
  contract and independence are unknown.
- Failure rows lack request linkage and endpoint-role provenance.
- GoPlus local completeness does not prove holder completeness/freshness.
- No evidence-derived maturation threshold exists.
- Registry TTL is local policy, not upstream capture proof.
- Top-level Governor counts can hide two-method success-path RPC consumption.
- Acquisition, eligibility, and validation lack one advance budget reservation.
- Reuse can contaminate tokens or bypass governance if not centrally enforced.
- A lower candidate cap may reduce discovery yield, but preserves mandatory
  snapshot capacity and honest learning value.

## Readiness and remaining locks

Evidence is sufficient for a combined design-and-repair lane, not for live
readiness or a full pilot. Retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, wallets, keys, signing, real funds, live execution, paid
APIs, scores, ranks, confidence, weighting, embeddings, vectors, V2-9.7F, and
V2-9.8 remain locked.

Do not implement repairs, contact providers, rerun readiness, or run the pilot
in E.21.
