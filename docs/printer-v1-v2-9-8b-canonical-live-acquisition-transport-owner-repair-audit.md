# Printer V1 V2-9.8B Canonical Live Acquisition Transport Owner Repair Audit

Date: 2026-07-29
Gate: 1 of 4 — audit/readiness
Baseline: `f68d743ea854bc647073cb2152075f513240d348`
Verdict: `V2_9_8B_CANONICAL_LIVE_ACQUISITION_TRANSPORT_OWNER_REPAIR_GATE_1_PASS`

## Blocker classification

```text
BLOCKER CLASSIFICATION: MISSING_APPROVED_IMPLEMENTATION_BOUNDARY
EVIDENCE: the public N2/N7 modes pass None to run_candidate_acquisition_only;
  only FrozenAcquisitionTransportOwner is concrete; the canonical proof stopped
  with APPROVED_ACQUISITION_TRANSPORT_OWNER_REQUIRED before preflight or work.
OFFICIAL-SOURCE COMPARISON: no provider response occurred and no contract drift
  is evidenced; committed provider contracts and Pump/PumpSwap pins remain usable.
PRINTER-CONTRACT COMPARISON: one public command and one Scheduler/Governor-owned
  acquisition integration exist, but normal shell construction is missing.
ROOT CAUSE: post-foundation integration intentionally left the live transport
  port unimplemented.
CODE CHANGE JUSTIFIED: YES
MINIMUM SAFE RESPONSE: construct one finite repository-owned live owner in the
  existing public N2/N7 dispatch after approval and configuration validation.
FOCUSED PROOF: same CLI parse/dispatch with frozen low-level behavior for N2/N7,
  configuration failures, accounting, cleanup, redaction, and capability locks.
UNTOUCHED SCOPE: schema, authoritative DB, campaign, tracking, lifecycle,
  snapshots, windows, memory, retrieval, decisions, and financial owners.
AUTHORIZATION STATUS: offline repair/proof only; zero live calls.
NEXT ROADMAP-COMPLIANT STEP: Gate 2 complete design.
```

## Exact protocol and frozen owner

`AcquisitionTransportOwner` has one method:

```python
operations(*, mode: str, policy: Mapping[str, Any], execution_id: str)
    -> Sequence[AcquisitionSourceOperation]
```

Each operation declares source, governed request kind, adapter, required versus
optional status, round mode, payload, expected/maximum underlying operations,
and optional cursor range. `FrozenAcquisitionTransportOwner` proves that the
integration can execute a prebuilt finite sequence through one Scheduler job and
one governed request per operation, persist exact manifests and reports, release
its lease, replay deterministically, and stop before runtime. It intentionally
lacks environment ownership, URL validation, sockets, provider timeouts,
response-byte measurement, live decoding composition, and public construction.

## Reusable transport and decoder inventory

| Surface | Existing behavior | Adoption result |
|---|---|---|
| DexScreener fresh profiles | two finite keyless GETs; existing Solana/memecoin normalizer | reuse endpoints and normalizer; acquisition owner exposes both calls in underlying-operation accounting |
| DexScreener exact token/pair | one finite GET | retained for supported targeted evidence; no independent origin/pool-lineage claim |
| GeckoTerminal new pools | one finite keyless GET with page-1 bound | reuse endpoint, version header, and normalizer |
| GeckoTerminal exact pool/OHLCV/trades | one-shot builders; readiness composition may make multiple calls | exact-pool builder is reusable only when a target exists; no OHLCV/trade work in acquisition-only |
| public Solana RPC holder | two read-only calls, finite timeout, no internal retry; reports actual count on second-call failure | reuse holder normalizer; canonical owner declares both calls separately in its underlying ledger |
| Helius holder | fixed authenticated free-tier host and two calls | not required; absent from the required plan and no secret required |
| GoPlus | one keyless finite GET and existing normalizer | optional only; missing fields never become safety and explicit risk can fail admission |
| Pump create decoders | strict pinned create/create_v2 decoders; primary live campaign owner has a finite internal acquisition loop | reuse strict decoders, not the campaign owner/loop |
| Pump migration/PumpSwap | strict pinned migration and Pool/PDA/vault decoders; older builders contain composite direct RPC behavior | reuse strict transport-free decoders; do not adopt old orchestration unchanged |
| campaign one-shot urllib transports | finite timeout/read/close and no retry | useful behavioral precedent, but decoded-body return loses exact raw-byte accounting and campaign ownership is wrong for acquisition-only |

The existing campaign `LiveSecondaryDiscoveryAdapter` contains a private
multi-provider loop and campaign-owner admission. The Pump live adapter drives a
private finite page/transaction loop whose individual calls are not durable
acquisition Scheduler/Governor work. The older token-age path contains bounded
pagination loops under a different evidence contract. None is adopted unchanged.
There is no automatic retry or endpoint rotation in the new owner.

## Configuration and redaction contract

Required configuration is process-scoped `PRINTER_SOLANA_RPC_URL`. The value:

- must be a parseable HTTPS URL with a hostname;
- must contain no URL username/password or fragment;
- may use only the default HTTPS port;
- is never printed, persisted, logged, included in an exception, fixture, or report;
- is represented only by a host-only redacted field inside the in-memory config.

DexScreener, GeckoTerminal, and GoPlus use fixed committed HTTPS endpoints and
need no secret. Birdeye is optional and absent. Helius is optional and absent.
DEXTools and PumpPortal remain excluded. Missing/malformed/unsupported RPC
configuration and unresolved transport construction block before activation
preflight, execution identity, lease, Scheduler, Governor, or source work.

## Ownership, accounting, and continuity

- The existing integration remains the only finite orchestration owner.
- Every declared source operation creates exactly one `DISCOVERY_REFRESH`
  Scheduler job and one Source Governor request.
- A composite operation returns every actual HTTP/RPC call as an ordered,
  redacted underlying-operation record with state and raw response bytes.
- Declared ceilings are checked before work; actual count and byte sums are
  checked after transport and before evidence acceptance.
- Cancellation/lease state is checked before and immediately after transport.
- Every socket response is context-managed; timeout is finite; retry,
  reconnect, endpoint rotation, and successor count remain zero.
- Pump create and migration ranges preserve indexed address, pin, decoder,
  direction, exact terminal boundary, and categorical continuity. Gapped,
  unknown, or blocked-contract evidence cannot advance a cursor.
- DexScreener and GeckoTerminal are an either/or required nomination group.
  Solana exact verification and both direct Pump lanes are required operations.
  GoPlus is optional and its absence never becomes safety.

## Public construction and offline proof seam

Normal dispatch is:

```text
parse N2/N7 -> explicit approval -> validate process configuration
-> construct LiveCandidateAcquisitionTransportOwner
-> activation preflight -> existing integration owner
```

The internal `APPROVED_ACQUISITION_TRANSPORT_OWNER_REQUIRED` guard remains for
invalid direct calls. Offline tests inject frozen HTTP/RPC responses only at the
concrete live owner's one-shot transport boundary while using its real source
plan and the same public parser, builder, dispatch, integration, Scheduler,
Governor, foundation, report, and cleanup path. There is no operation-plan
injector, proof launcher, or second product command.

## Schema decision and Gate 1 result

Migration 049 already stores work, exact underlying operations, byte counts,
cursor ranges, leases, reports, and replay identity. No schema or migration is
required. No new external contract is required. Gate 1 passes.
