# Printer V1 V2-9.8B Post-Rollover-2 Frozen Secondary Discovery Contract Implementation

Date: 2026-08-03

Baseline: `63799afa600ed490de2d74fbe1c331efb7d23774`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_FROZEN_SECONDARY_CONTRACT_IMPLEMENTATION_PASS`

The complete confirmed producer/consumer drift was repaired inside the
approved boundary. Claimed-stage evidence, Scheduler claim/ownership law,
strict accounting, Source Governor, schema, migrations, retries, and downstream
capabilities were not changed.

## Implemented contract

`printer_v1.sources.secondary_discovery` now exports the adopted
`SECONDARY_DISCOVERY_CONTRACT_VERSION = "V2-9.7D.7B.4B"`. The authoritative
operational owner records that version in combined discovery provenance.

Trending continues to accept an object containing a `data` list, including the
lawful empty list. Active continues to require exactly one matching pool object
with exact JSON:API identities and positive integer m5 activity. Neither
normalizer was weakened.

## Complete bounded repair

1. A requested exact active pool now requires an explicit fixture operation in
   `run_geckoterminal_fixture_lane`; absence becomes `UNAVAILABLE` instead of
   silent `SUCCEEDED_EMPTY`.
2. The combined executor now catches only canonical `SecondaryDiscoveryError`
   around normalization.
3. A canonical secondary response error is persisted as a provider failure
   using its exact error code. The malformed body is not persisted as a clean
   response.
4. The affected provider work and its real Scheduler job terminalize failed
   through the existing parity owner. Other provider/direct observations remain
   available, with no retry or endpoint rotation.
5. Shared DB, ownership, Scheduler, ceiling, and unexpected exceptions remain
   outside the narrow catch and retain shared-failure behavior.
6. The frozen test transport raises `MISSING_FROZEN_FIXTURE` for an unmatched
   URL instead of returning `{}` as a successful body.
7. A frozen builder now emits explicit trending, every supplied active-pool,
   and Dex bodies derived from the real frozen Pump mint/pool identities.
8. The builder rejects stale contract versions before transport.
9. The exact public-composition success fixture uses that builder and still
   crosses `LiveSecondaryDiscoveryAdapter` and the real combined normalizers.

## Claimed-stage evidence disposition

No implementation change was made. Existing transaction-local evidence already
records real enqueue/claim IDs, lock owner, rollback and non-durability labels.
Rolled-back rows are not reconstructed, no Scheduler terminal is injected, and
strict accounting still blocks a claimed stage without real sealed evidence.

The repaired success fixture is expected to let real work terminalize and seal
normally; that result must be proven only by the one exact composition after the
focused gate and repair commit.

## Files changed

| File | Purpose |
| --- | --- |
| `src/printer_v1/sources/secondary_discovery.py` | Contract version and required planned-active operation |
| `src/printer_v1/discovery/combined_executor.py` | Narrow provider-local canonical normalization failure handling |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | Secondary contract-version provenance |
| `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py` | Lawful frozen active builder and strict unmatched transport |
| `tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py` | Missing-active negative proof |
| `tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py` | Provider-local failure/Scheduler-terminal proof |
| `tests/test_v2_9_8b_frozen_secondary_discovery_contract.py` | Consolidated envelope, version, transport, adapter and setup proof |
| `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py` | Lawful exact success fixture wiring |
| audit/design/implementation/focused reports | Consolidated lane record |

## Money-usefulness contribution

Printer now retains healthy direct-origin acquisition when optional secondary
data is malformed, while still rejecting the bad data itself. That reduces
false full-campaign failures and keeps future memory inputs tied to exact
provider identities rather than accidental fixture defaults.

## What improves

- Exact fixture completeness and deterministic missing-fixture classification.
- Provider-local malformed-response isolation.
- Real Scheduler terminal parity for failed secondary work.
- Explicit secondary contract provenance.

## What remains locked

Six-unit accounting, Scheduler ownership/claim law, Source Governor,
schema/migrations, live providers/authorization, retries/restarts/successors,
retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets,
signing, funds, paid APIs, scoring/ranking/confidence/weights, embeddings, and
vectors remain unchanged and locked.

## Proof performed / required

Contract-specific implementation checks passed before the final focused gate.
The final focused proof must include the complete affected adapter, combined,
authoritative, pre-lifecycle, claim-at-work-start, evidence-capture, accounting,
full-run and Scheduler regression set. The exact node remains unexecuted until
that proof, compilation, diff check, changed-file review, and commit pass.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Disposition |
| --- | --- |
| Failed provider work has no PARTIAL DB enum | Work terminalizes failed; independently valid observations remain factual |
| Malformed raw body is not a clean response row | Exact failure code is persisted; no dirty body is mislabeled clean |
| Provider schema changes | Pinned contract fails closed; future drift requires a new lane |
| Fixture helper remains test code | It imports the production-owned version and feeds the real adapter/parser |
| Claimed rollback evidence | Intentionally unchanged; attempt diagnostics cannot satisfy six-unit law |
