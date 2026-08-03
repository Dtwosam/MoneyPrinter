# Printer V1 V2-9.8B Post-Rollover-2 Frozen Secondary Discovery Contract Audit

Date: 2026-08-03

Baseline: `63799afa600ed490de2d74fbe1c331efb7d23774`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_FROZEN_SECONDARY_CONTRACT_AUDIT_PASS`

Primary classification: `PRODUCER_AND_CONSUMER_CONTRACT_DRIFT`.

Every confirmed repair remains inside the frozen fixture/test harness,
secondary response contract, directly affected combined consumer, and tests.
No Scheduler-law, six-unit-law, Source Governor, schema, migration, retry, or
broader discovery redesign is required.

## Source-grounded blocker investigation

```text
BLOCKER CLASSIFICATION: PRODUCER_AND_CONSUMER_CONTRACT_DRIFT
EVIDENCE: exact failure JSON/database, exact fixture, frozen transport,
LiveSecondaryDiscoveryAdapter, adopted Gecko normalizers, fixture lane,
combined executor, secondary closeouts, and focused tests
OFFICIAL/ADOPTED CONTRACT: trending data is a list; active data is one exact
pool object with exact identity and positive integer m5 buys+sells
PRODUCER DEFECT: the exact success fixture planned an active request but supplied
no active response; the fake transport returned {} as a successful decoded body
CONSUMER DEFECT: the combined executor allowed SecondaryDiscoveryError to escape
the provider-lane isolation boundary and roll back the shared transaction
ROOT CAUSE: missing frozen active payload plus drift from adopted provider-local
malformed-response handling
CLAIMED-STAGE VERDICT: existing attempt evidence and strict blocking are correct;
no durable evidence or Scheduler transition may be reconstructed
CODE CHANGE JUSTIFIED: YES, bounded
```

## Authoritative producer / consumer contract

| Boundary | Producer output | Consumer expectation | Current result |
| --- | --- | --- | --- |
| Exact proof setup | Mapping of URL discriminator to decoded JSON body | Every planned trending, active, and Dex request has an explicit frozen result | Active-pool mapping absent |
| `_FakeSecondaryTransport.json_get` | Decoded body or transport exception | Unplanned URL is a named fixture failure, never an HTTP-200-shaped body | Returns `{}` and therefore claims success |
| `OneShotUrllibSecondaryTransport.json_get` | Directly decoded provider JSON | No wrapper beyond the provider envelope | Correct |
| `LiveSecondaryDiscoveryAdapter._get` | `FixtureSourceFact.body` is the decoded provider body | Normalizer receives the provider envelope exactly once | Correct; no duplicate wrapper |
| Gecko trending normalizer | `{"data": [...]}` | `data` list, maximum 20; each item is a JSON:API pool resource | Correct |
| Gecko active normalizer | `{"data": {...}}` | One exact JSON:API pool resource with positive `transactions.m5` | Correct |
| Fixture Gecko lane | Operations plus optional requested active pool | Missing planned active operation is `UNAVAILABLE` | Silently skips it when no operation remains |
| Combined secondary lane | `FixtureSourceFact` sequence | Malformed provider response becomes a provider-local failure; other lanes continue | `SecondaryDiscoveryError` escapes and becomes shared rollback |
| Discovery batch provenance | provider contract-version mapping | Records the adopted secondary contract version used by the frozen plan | Live composition records only the direct contract |

## Exact envelope and pool-object contract

### Trending

The exact body is a JSON object with `data` as a list. `{"data": []}` is a
lawful empty result and normalizes to zero observations with no failure. A
missing `data`, non-list `data`, non-object pool item, or over-20 page is
malformed or schema drift, not empty success.

Every non-empty pool resource requires:

- `type == "pool"`;
- `id == "solana_" + attributes.address`;
- non-empty `attributes.address`;
- `relationships.base_token.data.id` with `solana_` prefix;
- `relationships.quote_token.data.id` with `solana_` prefix;
- non-empty `relationships.dex.data.id`.

### Active

The exact body is a JSON object with `data` as one pool object, not a list.
That pool has the same exact identity fields as trending plus:

- `attributes.transactions` as an object;
- `transactions.m5` as an object;
- integer, non-negative `buys` and `sells`;
- `buys + sells > 0`;
- `attributes.address` equal to the requested pool.

An absent/non-object `data` is `MALFORMED_RESPONSE: missing pool object`.
Zero m5 activity is `NOT_ACTIVE`. A mismatched pool is
`AMBIGUOUS_IDENTITY`. Active has no lawful empty-object success: absence must
be an explicit provider/transport failure or a malformed response.

## Exact failure reconstruction

The exact proof created two real Pump pools and asked the secondary adapter for:

1. Gecko trending;
2. one exact Gecko active pool;
3. DexScreener profiles.

Its frozen body map contained only:

```python
{"trending_pools": {"data": []}, "token-profiles": []}
```

The unplanned active URL was:

`https://api.geckoterminal.com/api/v2/networks/solana/pools/2ZNhPJSXQKsnayAerTiUU8XeBaTY93g6BcPc7TF1uVnS`

The fake transport returned `{}` with fixture status `success`. The active
normalizer then deterministically raised exactly:

`SecondaryDiscoveryError: MALFORMED_RESPONSE: missing pool object`.

This was not a lawful provider response rejected by production parsing. The
adopted fixture manifests contain the required active `data` object and pass
the same normalizer.

## Error and isolation audit

`LiveTransportError` is already converted into a failure `FixtureSourceFact`.
The combined executor persists that as a provider failure and continues.
However, it stores a response and calls `_normalize_op` without catching
`SecondaryDiscoveryError`. The adopted secondary adapter contract explicitly
requires malformed, missing, stale, ambiguous, and inactive results to become
provider-lane failures without erasing healthy independent observations.

Therefore the exact malformed body crossed a consumer boundary that had drifted
from the adopted provider-local isolation contract. It became a generic shared
exception, causing rollback and the captured `SHARED_FAILURE`. The repair must
catch only the canonical secondary contract error at that boundary, persist its
exact code as a provider failure, terminalize the affected work truthfully, and
continue without retry or fallback. Shared database/ownership/ceiling faults
must continue to escape.

## Complete confirmed defect inventory

1. The exact success fixture omitted the planned active-pool response.
2. The frozen fake transport converted an unmatched URL into successful `{}`
   instead of an explicit missing-fixture transport failure.
3. The fixture Gecko lane silently accepted a requested active pool with no
   active operation as `SUCCEEDED_EMPTY`.
4. The combined secondary consumer did not translate canonical
   `SecondaryDiscoveryError` into a provider-local failure, violating adopted
   failure isolation and rolling back otherwise healthy discovery work.
5. The live combined fixture provenance omitted the adopted Gecko secondary
   contract version, so a frozen plan was not tied to its parser contract.

No duplicate body wrapping, lawful-response rejection, rank/score leak, Source
Governor bypass, Scheduler claim defect, or normalizer identity defect was
found.

## Claimed-stage evidence audit

The failed exact attempt truthfully preserved, before rollback:

- discovery batch/work IDs;
- Scheduler job ID `2`;
- real `SCHEDULER_ENQUEUE` and `SCHEDULER_CLAIM` transitions;
- exact expected/observed lock owner;
- request work type `DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`;
- transaction visibility label;
- `new_attempt_rows_proven_durable=false`;
- rollback started/completed;
- original `SecondaryDiscoveryError` classification and message.

After rollback there was no durable Scheduler row, terminal transition, or
sealed stage evidence. Six-unit accounting requires real sealed evidence, not
attempt diagnostics. The public finalizer therefore correctly retained the
original operational failure as primary and marked strict accounting blocked.

No lawful durable evidence object is being discarded. Attempt diagnostics are
already preserved with accurate transaction-local labels. Production
claimed-stage evidence behavior requires no change. Reconstructing the rows or
injecting a terminal transition would be synthetic and is forbidden.

## Audit gate

PASS. The repair is bounded to:

- authoritative secondary contract-version identity;
- provider-local canonical error handling in the combined consumer;
- missing-active fixture enforcement;
- exact frozen fixture generation and unmatched-request behavior;
- directly affected tests and reports.

## Money-usefulness contribution

The audit separates a bad frozen response from a real provider contract failure
and prevents one secondary parser fault from erasing healthy direct-origin
evidence. That makes future memory-growth acceptance depend on factual provider
inputs and truthful failure isolation rather than accidental test transport
defaults.

## What improves

- One explicit frozen response contract for trending and active requests.
- Missing fixtures cannot masquerade as HTTP-200 empty objects.
- Malformed secondary data remains fail-closed but provider-local.
- Contract version and failure classification become auditable.

## What remains locked

Scheduler law, Source Governor, six-unit accounting, schema/migrations,
authoritative/live execution, retries, restarts, successors, retrieval,
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing,
funds, paid APIs, scoring/ranking/confidence/weights, embeddings, and vectors
remain unchanged and locked.

## Proof required

Focused proof must cover both envelopes, empty versus malformed semantics,
contract version, fixture wrapping, provider-local translation, exact claim and
rollback diagnostics, strict missing-evidence accounting, pre-lifecycle
regressions, compilation, diff checking, and exact fixture setup without
executing the exact node.

## Proof performed

- Replayed the exact frozen setup through `LiveSecondaryDiscoveryAdapter`
  without executing the public composition and observed active body `{}` with
  fixture status `success`.
- Passed that body to the adopted active normalizer and reproduced exact
  `MALFORMED_RESPONSE: missing pool object`.
- Ran the fixture Gecko lane with a requested active pool but no active
  operation and observed incorrect `SUCCEEDED_EMPTY` with zero failures.
- Compared the exact producer, decoded-body wrapper, adopted fixture manifests,
  both normalizers, combined consumer, prior failure JSON/database, and
  provider-isolation design.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Control |
| --- | --- |
| Provider-local catch hides shared failures | Catch only `SecondaryDiscoveryError`; DB/owner/ceiling exceptions still escape |
| Missing fixture becomes empty success | Frozen transport raises an explicit named failure on unmatched requests |
| Raw malformed response mislabeled clean | Normalize before persisting a clean response; persist failure classification instead |
| Partial provider work lacks partial DB enum | Terminalize affected work failed while retaining any independently valid observations |
| Rolled-back attempt called durable | Keep existing transaction-local labels and strict accounting block |
| Fixture/parser contract drifts again | Pin one source-owned version and validate frozen builders against it |
