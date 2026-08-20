# Printer V1 V2-9.8B Solana-Native Core Safety Redundancy Repair Closeout

Date: 2026-08-20

## Verdict

`V2_9_8B_SOLANA_NATIVE_CORE_SAFETY_REDUNDANCY_REPAIR_CLOSEOUT_GREEN`

The bounded safety-redundancy repair is implemented and offline-proved against the accepted cooperative later-cycle repair base.

Accepted base:

`3f982ce97f30d99fabc384bfbf790b02b2049bdf`

Clean committed-state proof anchor:

`3d9388fa7cb382450e026de0f2dc2d0d3140429f`

Post-proof cleanup anchor:

`7abca8cfa24638b6f9272818b2c2645bdbae2491`

Proof workflow run:

`32382911612`

## What changed

Product scope is bounded to:

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/safety/composite.py`
- `src/printer_v1/safety/goplus_normalizer.py`
- `src/printer_v1/sources/measured_transport.py`
- `src/printer_v1/sources/solana_rpc_token_safety.py`

The existing scheduled safety collection now performs one additional Source-Governed Solana RPC mint-account read. It derives only chain-provable core facts: mint authority, freeze authority, supply sanity, and SPL Token / Token-2022 program identity.

GoPlus remains complementary for provider-specific or non-chain safety context, but is no longer a structural single point of failure for those four core facts when independent approved Solana evidence is usable. Missing required facts still fail closed. If usable GoPlus and Solana core evidence disagree, the disputed field becomes `UNKNOWN` with an explicit source-conflict label and remains blocked.

`METADATA_UNKNOWN` is optional source coverage for 15m memory; explicit mutable metadata remains blocking. Holder-condition absence or disagreement remains visible/descriptive under the existing E.48 separation law and does not independently dirty otherwise trustworthy memory evidence.

No new Scheduler job, independent provider loop, cadence increase, migration, paid API, or capacity mechanism was added.

## Budget ownership

The repair adds exactly one governed lifecycle safety request per token. Scheduler ceilings are unchanged.

Current lifecycle safety accounting includes:

- `PRECLOSE_CONTEXT_REQUEST_COUNT = 6`
- `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 4`
- `WINDOW_CLOSE` reserved operations = `7`
- `CONTINUATION_CLOSE` reserved operations = `5`

The separate pre-activation holder-admission budget remains unchanged; it is not the owner of this lifecycle safety read.

## Bounded proof

A frozen RED contract was established first: the seven new safety-redundancy tests failed before implementation for the missing behavior.

The final committed-state proof ran read-only with no patching and passed:

- new Solana-native safety redundancy contract
- composite and holder-source regressions
- first-hour and timeframe safety regressions
- lifecycle request-accounting regressions
- cooperative D4/D5 later-cycle coordinator regression
- Python compilation of touched production modules
- `git diff --check`

No live providers, Printer campaign, authorization, wallet, real funds, live execution, retrieval, paper-trade activation, or paid service were used by this proof.

## Pre-existing baseline debt kept out of scope

The repair did not rewrite unrelated stale fixtures merely to make the branch green.

- `tests/test_v2_8_1_one_token_4h_runtime.py` still contains an older assertion that WINDOW_4H real collection is disabled, while the accepted base cadence policy already enables it only through standard-four-hour operational authority.
- selected legacy V2-9.2 / V2-9.3 final-report fixtures omit required launch Git provenance even though the accepted base `_final_report()` already validates it. Those malformed fixtures were excluded from this bounded repair proof rather than weakening provenance enforcement.

These are not evidence that the safety repair regressed runtime behavior.

## Locks preserved

Printer V1 remains Solana-only, Solana-memecoin-only and paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval and financial capabilities remain locked until their explicit lanes.

## Authorization posture

`NOT READY FOR NEW 4/2/2 AUTHORIZATION`

This closeout proves the bounded code repair only. It is not operational re-readiness and does not authorize a campaign.

All prior authorizations remain non-reusable.

## Exact next permitted action

`V2-9.8B Post-Safety-Repair Operational Re-Readiness Audit`

That audit should be read-only/offline first and must reconcile the repaired safety path with the current authoritative repository/database identity and any remaining readiness blockers before a fresh 4/2/2 authorization can be considered.

Do not create or reuse an authorization from this closeout. Do not run Printer from this closeout.
