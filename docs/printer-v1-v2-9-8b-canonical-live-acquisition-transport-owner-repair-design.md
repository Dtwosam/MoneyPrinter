# Printer V1 V2-9.8B Canonical Live Acquisition Transport Owner Repair Design

Date: 2026-07-29
Gate: 2 of 4 — complete design
Depends on: canonical live-owner repair audit
Verdict: `V2_9_8B_CANONICAL_LIVE_ACQUISITION_TRANSPORT_OWNER_REPAIR_GATE_2_PASS`

## Owner and construction boundary

`LiveCandidateAcquisitionTransportOwner` is the sole repository-owned concrete
live owner for both `ACQUISITION_ONLY_N2` and `ACQUISITION_ONLY_N7`. It implements
the existing `AcquisitionTransportOwner` protocol and returns only finite
`AcquisitionSourceOperation` values. It does not admit, schedule, persist,
select, qualify, or hand off a candidate.

The existing public command constructs it only after explicit approval and
valid configuration. `run_candidate_acquisition_only` retains its non-null owner
guard for internal invalid calls. No other public command or launcher is added.

## Source plan

The fixed plan is:

1. DexScreener latest-profile nomination plus its supported current market batch;
2. GeckoTerminal page-1 new-pool nomination and supported market facts;
3. bounded finalized direct Pump create signature pages and transaction decodes;
4. bounded finalized Pump migration pages and transaction decodes;
5. one exact mint-account batch for supported SPL Token/Token-2022 identity;
6. one PumpSwap Pool-account batch and strict migration/Pool/PDA/vault verification;
7. bounded holder evidence through finalized Solana RPC;
8. optional GoPlus risk evidence.

DexScreener/GeckoTerminal nominate without preference. Direct Pump/PumpSwap is
mandatory for Pump lineage claims, not for every nominated mint. Unknown origin
remains categorical. The foundation alone merges identities, applies gates,
creates certificates/reserve/manifest, and selects exact N. DEXTools,
PumpPortal, Birdeye, Helius, Jupiter, paid sources, ranking, scoring,
confidence, weighting, embeddings, and vectors are absent.

Both nomination responses are collected before candidate-bound market rows are
materialized. Their union is bounded by the policy's deterministic mint identity
order, independent of provider execution order; each provider then emits only
its own supported rows for that shared bounded set. These zero-transport
materialization operations retain source attribution and exact zero-call
accounting. They do not admit, prefer, rank, or select a candidate.

## Transport contract

`UrllibCandidateAcquisitionOneShotTransport` owns one response per call and:

- uses only committed HTTPS endpoints or the validated RPC URL;
- sets a finite timeout and per-response byte ceiling;
- reads at most ceiling plus one byte;
- closes normal and HTTP-error responses;
- decodes one JSON body;
- returns raw response-byte count, categorical operation kind, and redacted role;
- raises only categorical errors without URL, host path/query, payload, or secret;
- has zero retry, reconnect, persistent session, endpoint rotation, or fallback.

Each high-level source operation remains one Scheduler job and one governed
request. Every underlying HTTP/RPC attempt is returned individually. Dynamic
page/transaction/holder counts must be no greater than their predeclared policy
ceiling; their exact count and byte sum must equal the durable operation ledger.
Failure attempts are ledgered with zero or observed response bytes and `FAILED`.
Signature pages, Pump transactions, and per-candidate GoPlus work are separate
declared operations. Holder work is the adopted fixed two-call
largest-accounts/supply composite, and Dex nomination is the fixed two-call
profiles/market composite. Neither composite contains a provider loop. No
operation plan exceeds the Source Governor's committed per-source rate ceiling.

## Decoding and evidence

Provider responses use existing DexScreener, GeckoTerminal, holder, and GoPlus
normalizers. `pump_contracts.py` exposes transaction-level wrappers around the
existing pinned instruction decoders so transport composition does not duplicate
layout rules. Unknown program, discriminator, account order, version, mint,
Pool layout, quote, extension, PDA, LP, or vault remains unsupported/failed.

Mint verification accepts only exact SPL Token or Token-2022 ownership and
reuses the adopted mint-state decoders. The first live boundary treats only an
initialized exact 82-byte legacy Mint or initialized exact 166-byte
extensionless Token-2022 Mint with disabled mint and freeze authorities as
on-chain safety PASS; every Token-2022 TLV extension fails closed. Holder PASS
requires the existing healthy categorical label.
GoPlus never supplies safety from absence; explicit adopted risk may fail a
candidate. Aggregator pool identity never replaces exact on-chain PumpSwap proof.

## Failure and cleanup

Configuration blockers occur before preflight or database work. During an
execution, provider/auth/rate/timeout/transport/malformed/contract/budget/byte/
row/cursor/cancellation/lease failures retain separate categorical evidence.
The first terminal cause remains immutable. The integration checks lease and
cancellation before and after every transport, terminalizes every Scheduler
residue with `max_retries=0`, releases the acquisition lease, creates no
successor, and persists one replayable terminal report.

Required provider-group behavior is unchanged: one of DexScreener or
GeckoTerminal must nominate successfully; required Solana/Pump work failure
blocks; optional source failure is report-visible and non-terminal unless the
remaining evidence cannot satisfy admission.

## Proof design

The canonical offline proof invokes `main([mode, "--operator-approved"])` with:

- a disposable DB migrated through 049;
- valid fake process configuration;
- frozen HTTP/RPC responses injected only at the concrete live owner's
  one-shot transport boundary, with the real live source plan retained;
- the existing public preflight override solely to represent the disposable,
  intentionally uncommitted test DB.

N2 must produce two selected items, projection two, handoff zero, no lifecycle,
deterministic replay, released lease, and zero active jobs. N7 must produce seven
neutral items, projection zero, strict legacy rejection, deterministic replay,
and the same cleanup. Negative proof covers approval/configuration, unresolved
transport, required/optional providers, timeout, malformed data, budgets,
bytes, rows, cursor, unsupported contract, cancellation, renewal, redaction,
and idempotence. Migration 048/049 compatibility and protected-table zero deltas
remain mandatory.

## No-unlock and schema boundary

No migration is added. Active capacity stays two. The owner cannot create
campaign, tracking, lifecycle, snapshot, window, memory, retrieval, decision,
position, trade, audit, PnL, wallet, signing, transaction-submission, or fund
movement work. PASS authorizes only a separately explicit future N2-first live
proof; it does not run or authorize that proof here.
