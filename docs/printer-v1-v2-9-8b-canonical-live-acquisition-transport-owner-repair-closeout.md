# Printer V1 V2-9.8B Canonical Live Acquisition Transport Owner Repair Closeout

Date: 2026-07-29
Lane: V2-9.8B — canonical live candidate-acquisition transport owner repair
Baseline: `f68d743ea854bc647073cb2152075f513240d348`
Verdict: `V2_9_8B_CANONICAL_LIVE_ACQUISITION_TRANSPORT_OWNER_REPAIR_PASS`

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| 1 — audit/readiness | PASS | Root cause classified `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`; no provider drift, schema gap, or migration need found. |
| 2 — complete design | PASS | One public construction boundary, one repository-owned owner, finite source plan, exact accounting, redaction, and cleanup contracts frozen. |
| 3 — implementation | PASS | `LiveCandidateAcquisitionTransportOwner` is built after approval/config validation and passed to the existing integration; the internal non-null guard remains. |
| 4 — canonical offline proof | PASS | Normal public N2/N7 parsing and dispatch built the concrete live owner and ran its real operation plan against frozen HTTP/RPC responses on disposable migration-049 databases. |

## Root cause and repair

The existing shell modes reached `run_candidate_acquisition_only` with
`acquisition_transport_owner=None`. The integration correctly stopped with
`APPROVED_ACQUISITION_TRANSPORT_OWNER_REQUIRED`, but the repository had no
approved live implementation or public constructor.

The repair adds one `LiveCandidateAcquisitionTransportOwner` and one one-shot
urllib transport. The existing public command now performs:

```text
parse N2/N7 -> explicit operator approval -> validate configuration
-> construct canonical live owner -> existing preflight/integration
-> Central Scheduler -> Source Governor -> foundation -> terminal report
```

The direct integration guard is unchanged. No proof launcher, second command,
operation-plan injector, private provider loop, retry, reconnect, endpoint
rotation, or successor path was added.

## Source and transport architecture

Included:

- DexScreener latest-profile nomination and supported market batch;
- GeckoTerminal Solana new-pool nomination and supported market facts;
- approved read-only Solana RPC exact mint, Pump, PumpSwap, pool, and holder work;
- direct pinned Pump create and migration transaction decoding;
- pinned PumpSwap Pool decoding and exact Pump graduation verification;
- optional GoPlus safety reference.

Excluded: DEXTools, PumpPortal, Birdeye, Helius, paid sources, WebSockets,
persistent connections, wallets, signing, and transaction submission.

Every declared acquisition operation owns one Scheduler job and one governed
request. Signature pages, Pump transaction slots, and per-candidate optional
work are separately declared. The two fixed composites—Dex profiles/market and
holder largest-accounts/supply—have no provider loop and durably record both
underlying calls. Actual call count, operation kind/state, redacted endpoint
role, raw response bytes, rows, and cursor range are checked before evidence is
accepted. Cancellation and lease state are checked before and after transport.
DexScreener and GeckoTerminal are first collected, then materialized for one
shared deterministic candidate-bound mint set through separately attributed
zero-transport operations; provider order therefore does not decide preference
or admission.

## Configuration and redaction

`PRINTER_SOLANA_RPC_URL` is required only for explicitly approved N2/N7 live
construction. It must be a parseable HTTPS URL with a hostname, no URL
username/password, no fragment, and no non-default port. Missing, malformed,
unsupported, or unresolved configuration stops before activation preflight,
execution identity, lease, Scheduler, Governor, or source work.

The full RPC URL is excluded from dataclass representation and all durable
records. Exceptions contain only categorical codes and fixed endpoint roles;
chained provider exceptions are suppressed. HTTP error bodies are counted and
closed but never surfaced. Tests used query credentials and provider-body
secrets and proved they did not appear in command output, reports, errors, or
configuration representation.

## Canonical offline results

### N2

- public mode: `acquisition-only-n2 --operator-approved`;
- constructed class: `LiveCandidateAcquisitionTransportOwner`;
- policy: exact `ACQUISITION_ONLY_N2`, capacity two;
- Scheduler jobs / governed requests: 16 / 16;
- exact mocked HTTP/RPC calls durably accounted: 13;
- manifest items / legacy projection: 2 / 2;
- runtime handoff / lifecycle started: 0 / false;
- deterministic public replay made zero additional transport calls;
- lease released; active lease and active Scheduler residue: 0 / 0;
- all protected tracking, snapshot, window, memory, retrieval, and financial
  table deltas: zero.

### N7

- public mode: `acquisition-only-n7 --operator-approved`;
- same concrete owner class and exact `ACQUISITION_ONLY_N7` policy;
- Scheduler jobs / governed requests: 38 / 38;
- exact mocked HTTP/RPC calls durably accounted: 28;
- runtime-neutral manifest items / projection: 7 / 0;
- legacy adapter: categorically rejected N7 with
  `LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO`;
- deterministic public replay made zero additional transport calls;
- runtime handoff and lifecycle work: zero;
- lease released; active lease and active Scheduler residue: 0 / 0;
- all protected-table deltas: zero.

The valid public calls no longer return
`APPROVED_ACQUISITION_TRANSPORT_OWNER_REQUIRED`. Invalid direct internal calls
still do. Offline failures cover missing/malformed/unsupported RPC config,
unresolved transport, authentication, required nomination group, optional
source, timeout, malformed response, operation/byte/row budgets, cursor gap,
unsupported Pump contract, cancellation, lease renewal, redaction, and replay.
All terminal paths retain zero retry, reconnect, rotation, restart, or successor.

## Verification

- focused foundation/integration/live-owner/public-CLI suite: 54 passed;
- canonical N2/N7 public-path subset: 2 passed;
- broad directly affected suite: 421 passed and 132 subtests passed;
- disposable migration tests: canonical migrations include 048 and end at 049;
  fresh and copied disposable databases pass integrity and foreign-key checks;
- Python compilation: PASS;
- `git diff --check`: PASS;
- authoritative DB: migration ledger row 49 is
  `049_candidate_acquisition_integration.sql`, integrity `ok`, zero foreign-key
  violations, no sidecar residue;
- authoritative DB SHA-256 remained
  `e6748de305800fc65ce287ef00e72be0ba7910ae7766f8331280f35da4aa07df`.

No live provider, RPC, WebSocket, acquisition, backfill, campaign, tracking,
lifecycle, snapshot, window, or memory operation ran.

## Schema and capability locks

No schema or migration changed. Active Memory Factory capacity remains exactly
two. The repair created no campaign, tracking, lifecycle, snapshot, window,
memory, selective-1h, retrieval, decision, BUY/SELL/HOLD, position, trade,
audit, PnL, wallet, private-key, signing, transaction, real-fund, paid-source,
score, rank, confidence, weighted, embedding, or vector capability.

## Functionality Risks / Setbacks / Efficiency Blockers

- Live reliability remains unproven because this repair was deliberately
  transport-free; public/free provider limits, pruning, latency, and retention
  can still block the future proof.
- A full bounded signature page can require later cursor continuation; gaps or
  unsupported Pump/PumpSwap contracts fail closed rather than claim absence.
- Aggregator nomination is not lineage or pool proof. Unsupported non-Pump pool
  programs remain identity-incomplete; only the pinned PumpSwap relationship is
  currently decoded by this owner.
- Holder evidence retains wallet-authenticity limitations of
  `getTokenLargestAccounts`; GoPlus remains optional and absence is not safety.
- No automatic retry, fallback, or endpoint rotation can mask a transient
  outage; this is intentional but can reduce acquisition yield.

## Next permitted task

The exact next permitted task is a new, separately explicit bounded live
candidate-acquisition proof: Stage A `ACQUISITION_ONLY_N2` first. Stage B
`ACQUISITION_ONLY_N7` is permitted only after terminal N2 PASS. This closeout
does not authorize running either proof now and does not authorize the
operational Memory Factory campaign.
