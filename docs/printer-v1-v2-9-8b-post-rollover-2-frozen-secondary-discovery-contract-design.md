# Printer V1 V2-9.8B Post-Rollover-2 Frozen Secondary Discovery Contract Design

Date: 2026-08-03

Baseline: `63799afa600ed490de2d74fbe1c331efb7d23774`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_FROZEN_SECONDARY_CONTRACT_DESIGN_PASS`

## Contract owner and version

`printer_v1.sources.secondary_discovery` is the authoritative owner of the
secondary discovery response contract. It owns the request kinds, endpoints,
parameters, response normalizers, error vocabulary, and the pinned contract
version `V2-9.7D.7B.4B`.

The live/frozen composition records that version in
`CombinedDiscoveryFixtures.provider_contract_versions`. A frozen fixture
builder must reject any requested version other than the source-owned version.
The provider response itself does not invent a version field.

## Canonical response contract

### Trending response

```json
{
  "data": [
    {
      "id": "solana_<pool>",
      "type": "pool",
      "attributes": {"address": "<pool>"},
      "relationships": {
        "base_token": {"data": {"id": "solana_<mint>", "type": "token"}},
        "quote_token": {"data": {"id": "solana_<quote>", "type": "token"}},
        "dex": {"data": {"id": "<venue>", "type": "dex"}}
      }
    }
  ]
}
```

Required envelope: object with list `data`. Required resource fields are exact
pool type/ID/address and base-token, quote-token, and DEX relationships.
Optional attributes are ignored unless already adopted. Rank, score, ordering,
price, liquidity, and marketing fields never gain authority.

`{"data": []}` is the only canonical lawful empty Gecko result in this slice.
It produces zero trending observations without failure.

### Active response

```json
{
  "data": {
    "id": "solana_<requested_pool>",
    "type": "pool",
    "attributes": {
      "address": "<requested_pool>",
      "transactions": {"m5": {"buys": 1, "sells": 1}}
    },
    "relationships": {
      "base_token": {"data": {"id": "solana_<mint>", "type": "token"}},
      "quote_token": {"data": {"id": "solana_<quote>", "type": "token"}},
      "dex": {"data": {"id": "pump-fun", "type": "dex"}}
    }
  }
}
```

Active `data` must be exactly one pool object. The pool must match the requested
pool, and `m5` buys/sells must be non-negative integers with a positive sum.
There is no fabricated or empty active observation.

## Malformed and provider-failure behavior

- Missing/wrong envelope or pool fields: `MALFORMED_RESPONSE` or exact existing
  identity code.
- Wrong requested pool: `AMBIGUOUS_IDENTITY`.
- Zero activity: `NOT_ACTIVE`.
- Stale receipt: `STALE_OR_UNKNOWN`.
- Contract version mismatch: fixture generation fails before transport with a
  named stale-contract error.
- Missing frozen URL: `LiveTransportError` with a named missing-fixture code.
- Non-2xx/transport provider failure: existing failure `FixtureSourceFact`.

At the combined consumer boundary, canonical `SecondaryDiscoveryError` is
provider-local. The consumer persists the governed request and provider failure,
does not label the malformed body clean, terminalizes the affected discovery
work through the existing Scheduler terminal owner, and continues independent
lanes. It does not retry, rotate endpoints, fabricate observations, or catch
shared database/owner/ceiling faults.

## Normalization output

Successful rows retain only exact factual identity and provenance:

- provider and channel;
- Solana network;
- mint, pool, quote mint, and venue;
- receipt time as observed time;
- provider-label-unverified Pump.fun status;
- for active only, `activity_interval=m5` and categorical activity count;
- raw payload hash and non-multiplying provenance count.

No scoring, ranking, confidence, weighting, or provider order enters selection.

## Fixture-generation contract

The exact success harness must:

1. use the source-owned contract version;
2. create explicit trending, each planned active-pool, and Dex bodies;
3. derive active pool/mint identity from the same frozen Pump acquisition used
   by the composition;
4. include positive fixed m5 activity;
5. pass the bodies through `LiveSecondaryDiscoveryAdapter` and the real combined
   normalizer boundary;
6. raise on any unplanned URL instead of returning `{}`.

Intentionally malformed bodies remain isolated in explicitly named negative
tests and never feed the success proof.

## Claimed-stage evidence design

No production change is required. Attempt diagnostics remain separate from
durable stage evidence:

```text
real transaction-local ENQUEUE + CLAIM + rollback
  -> preserve pre-rollback IDs, owner, transition labels and rollback status
  -> label rows not proven durable
  -> do not create a stage-evidence object
  -> keep strict accounting blocked
  -> preserve the original operational failure as primary
```

A successful repaired fixture instead allows the provider work to reach the
real Scheduler terminal transition and normal stage sealing. No transition is
injected by the fixture.

## Bounded implementation owners

| Owner | Change |
| --- | --- |
| `secondary_discovery.py` | Export canonical contract version; require a requested active fixture when active work was planned |
| `combined_executor.py` | Translate only canonical secondary response errors into provider-local persisted failures |
| authoritative operational owner | Record the source-owned Gecko contract version in combined fixture provenance |
| frozen secondary test transport/builder | Generate lawful exact active bodies, reject stale versions, and fail unmatched URLs |
| focused tests | Prove envelopes, wrapping, translation, isolation, claim/rollback and accounting invariants |

No claimed-stage evidence, Scheduler, six-unit, Source Governor, schema,
migration, retry, or downstream capability owner changes.

## Money-usefulness contribution

The design preserves healthy factual acquisition when one optional secondary
response is bad, while ensuring malformed data never enters selection. That
improves corpus reliability without turning provider popularity or test
fixtures into money-bearing authority.

## What improves

- Frozen proof data and production parsing share one exact contract.
- Empty and malformed responses are unambiguous.
- Provider failures stay isolated and auditable.
- Contract provenance prevents silent fixture drift.

## What remains locked

Strict accounting, Scheduler/Source Governor ownership, schema/migrations,
live authorization and providers, retries/restarts/successors, longer windows,
retrieval, decisions, financial actions, wallets, scoring/ranking/confidence,
embeddings, and vectors remain locked.

## Proof required

The focused gate must pass all nineteen requested contract and regression cases,
changed-file compilation, `git diff --check`, and exact changed-file review.
Only then may the exact node execute once.

## Proof performed

The design was checked against the adopted `V2-9.7D.7B.4B` fixture manifest,
the production normalizer functions, the live decoded-body adapter, combined
provider-isolation law, and the preserved transaction-local rollback evidence.
That review proved the design needs neither schema changes nor synthetic stage
evidence and can be implemented by the bounded owners listed above.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Control |
| --- | --- |
| Catch is too broad | Catch only `SecondaryDiscoveryError` |
| Fixture bypasses parser | Feed decoded bodies through real live adapter and combined normalizer |
| Empty trending confused with missing active | Separate list-empty success from required active object |
| Failed lane hides valid rows | Retain already-normalized rows but terminalize work failed |
| Synthetic post-rollback evidence | No change to attempt/stage evidence path |
| Future provider schema drift | Fail closed under pinned contract; require a new governed contract lane |
