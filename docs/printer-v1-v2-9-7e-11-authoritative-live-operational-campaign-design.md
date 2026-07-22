# V2-9.7E.11 Authoritative Live Operational Campaign Design

**Status:** FROZEN AFTER INTERNAL REVIEW

**Baseline:** `75b22c51791d619dfb2f1746932743db082d544f`

## Todo / Checklist

- [x] Audit the complete fixture/live boundary.
- [x] Separate reusable domain owners from missing transports and composition.
- [x] Select one internal live architecture.
- [x] Review governance, identity, budget, lifecycle, and stop boundaries.
- [ ] Implement the frozen design.
- [ ] Prove natural dispositions offline.
- [ ] Run one bounded live readiness cycle.

## Capability Audit

The durable Pump origin decoder, cursor, registry, combined discovery gates,
uniform selection, atomic handoff, lifecycle collectors, promotion, report,
replay, cleanup, Source Governor, and Central Scheduler are reusable domain
owners. Four operational boundaries remain at the baseline:

1. `pumpfun_origin.run_acquisition_cycle` accepts only ownership-tagged
   `FixtureOperation` values; the proven live JSON-RPC code exists only in
   proof harnesses.
2. `CombinedPumpfunCampaignExecutor` accepts `CombinedDiscoveryFixtures`; the
   provider normalizers are reusable, but no production adapter builds its
   input from bounded live transports.
3. `OriginToLifecycleCampaignDriver` has no live caller and requires the
   fixture-backed combined executor.
4. Exact two-token continuation is exposed only through E.9's compressed
   fixture plan, which predeclares the continuation mint and 5m trigger. The
   ordinary continuous path assumes one token and captures support
   unconditionally. Neither is an operational natural-evidence owner.

The legacy GeckoTerminal-discovering factory front end, retired whole-program
Pump polling, historical mint archaeology, and the E.9 compressed plan remain
proof/historical surfaces and cannot become operational authority.

## Frozen Architecture

`AuthoritativeLiveOperationalCampaignOwner` is the sole new internal entry
point. It has no CLI and accepts narrow dependency-injected ports:

```text
AbstractCampaignCommand
  -> LivePumpOriginAdapter (one free-public RPC endpoint, bounded JSON-RPC)
  -> LiveSecondaryDiscoveryAdapter (bounded GeckoTerminal, DexScreener,
     optional authenticated free Solana Tracker)
  -> existing run_acquisition_cycle / provider normalizers
  -> CombinedPumpfunCampaignExecutor
  -> exact two-slot activation
  -> OriginToLifecycleCampaignDriver handoff
  -> existing two-token lifecycle in operational-natural mode
  -> NaturalEvidenceDispositionOwner
  -> existing continuation and support-only 5m policies
  -> promotion / final report / report-only replay / cleanup
```

### Live ports and governance

The transport port exposes one-shot `json_get` and `json_rpc` methods only.
The adapters admit every operation through the Source Governor before the
transport and require the Central Scheduler owner to be present. Each call has
a stable request kind, Scheduler work type, timeout, response-byte ceiling,
and separate governed-request and underlying-operation counters. There is no
retry, reconnect, endpoint rotation, wallet, signing, or paid endpoint.

Pump uses only `getSignaturesForAddress` on the create-exclusive mint-authority
index and `getTransaction` with finalized commitment and transaction version
0 support. The adapter creates the existing operation envelope and delegates
all admission, decoding, cursor, and continuity semantics to
`run_acquisition_cycle`; it does not reopen the Pump contract.

Secondary HTTP responses are converted to the existing factual input shape and
validated by the existing provider normalizers inside the combined executor.
Rank, score, response position, promotion, and risk labels never enter gates.
Solana Tracker is optional and only callable when an existing free-tier secret
reference resolves; missing auth is a factual unavailable lane, never a paid
fallback.

### Natural evidence disposition

Operational mode contains no continuation mint or trigger-family input. After
both terminal 15m closes, a pure owner reads the exact current-run governed
snapshot streams and canonical context labels. It uses the existing micro-event
parser/classifier to derive categorical movement, held-to-15m, exit, and memory
gate labels. Those observed labels map only to the already-adopted continuation
learning-need and support-trigger vocabularies, then pass through the existing
token-local continuation and support-only 5m policies.

Ordinary/consolidated movement yields no learning need and a valid no-capture.
Observed transition/collapse/survival evidence may yield a categorical learning
need. A support trigger exists only when the canonical micro-event evidence is
eligible and maps to an adopted trigger family. Unknown, stale, incomplete,
dirty, mismatched, or ungoverned evidence blocks rather than guesses.

The same owner evaluates the selected token's terminal 1h evidence for a
categorical 1h-to-4h need. Support-only 5m never supplies continuation
authority. No numeric score, weight, rank, confidence, or new threshold is
introduced; quantitative thresholds remain solely inside the existing
canonical micro-event classifier.

### Structural separation from E.9

Operational mode and `CompressedTwoTokenProofPlan` are mutually exclusive at
factory preflight and at the live owner boundary. The live owner never accepts
fixtures, fixture operations, a continuation identity, a learning need, or a
trigger family. Offline tests inject transport-shaped raw responses, not
dispositions.

### Lifecycle and identity

The combined executor runs once. The E.8 bridge mirrors only the two activated
slot identities into the lifecycle batch. There is no rediscovery or
reselection. Both tokens receive independently scheduled 15m streams. Natural
dispositions are evaluated only after both 15m closes are present, ensuring no
first-close ordering bias. One token may continue while the other stops;
token-local failures cancel only that token. Shared first faults terminate the
campaign with no restart or successor.

### Readiness mode

The same owner exposes an internal `readiness_only` mode. It runs live adapters,
domain acquisition, combined merge/gates, and disposable atomic handoff, then
stops before lifecycle scheduling is consumed. It terminally cancels dry-run
handoff jobs, persists a redacted summary, and performs zero-source deterministic
replay. It cannot invoke the E.9 plan or any 15m/1h/4h collector.

## Frozen Ceilings

One campaign/cycle; Pump: 3 signature pages, 12 transaction decodes, 15 normal
maximum operations (45 absolute inherited guard); secondary: one Gecko trending,
one exact-pool enrichment when available, two Solana Tracker calls when free
auth exists, and two DexScreener calls; 30-second HTTP/RPC timeout per call;
1.5 MiB per response; 8 MiB readiness storage; 360-second readiness duration;
zero retries, rotations, reconnects, successors, and restarts. Lifecycle
ceilings remain policy-derived from the existing factory and are not raised.

## Schema Decision

No migration. Existing campaign, discovery, origin-registry, cursor, selection,
lifecycle, source, Scheduler, report, and replay tables already hold every
required identity and accounting fact. The new owners are composition and
transport boundaries only.

## Internal Design Review

- Authority is singular: only the new internal owner composes live intake with
  E.8; the legacy front end remains rejected.
- Every external operation is admitted before transport and represented in
  the existing domain envelope; every lifecycle unit remains Scheduler-owned.
- Exact mint/pair/slot identities flow from decoded origin through activation
  and lifecycle without copying a loosely related row.
- Fixture plans are type- and preflight-excluded from operational mode.
- Natural disposition uses existing categorical classifiers/policies and
  observed evidence only.
- Readiness cannot start lifecycle windows.
- No schema or financial/retrieval surface is necessary.

**Review verdict:** approved for implementation.

## Locks

All Printer V1 Solana-only, paper-only, free/public-source, governance,
two-or-none, clean-memory, support-only 5m, and financial/retrieval locks remain
unchanged. This lane does not run the multi-hour pilot or publish a command.

## Fail-closed refinements — 2026-07-22

Four fail-closed defects were repaired without changing the approved
architecture:

1. **Per-request Governor admission before secondary transport.**
   `_admit_source_request(...)` runs immediately before every
   `SecondaryHttpTransport.json_get`. It re-validates canonical Source Governor
   availability and Central Scheduler ownership and, when the injected Governor
   exposes an `admit(source_name, request_kind)` hook, consults it and fails
   closed on denial. Zero HTTP occurs when admission is denied or an owner is
   unavailable. Accounting and the zero-retry/rotation/reconnect/successor/
   restart guarantees are unchanged.

2. **Memory-quality gate before outcome.** The natural-evidence disposition owner
   admits only `CLEAN_MEMORY` / `PARTIAL_MEMORY`. Any other quality is
   `INELIGIBLE_15M_MEMORY_QUALITY` — no continuation, support-only 5m, trigger
   family or promotion authority — even when the outcome maps to a meaningful
   transition. No score, weight, rank, confidence or threshold added.

3. **Fail-closed readiness.** `run_readiness_only` starts `NOT_READY` and reaches
   `READY` only after the complete fixed-gate set (finalized origin accepted,
   activation complete, exactly two atomic `SELECTED` slots, activated identities
   ⊆ finalized origin identities, disposable handoff cancelled, zero lifecycle
   windows after cleanup, identical zero-source replay). Any shortfall stays
   non-ready with the exact failing gate names.

4. **Two-terminal-15m-close barrier.** Operational-natural disposition defers the
   first terminal 15m close (`DEFERRED_PENDING_PEER_15M_CLOSE`, no scheduling)
   and only once every activated token has terminal 15m close evidence evaluates
   each token from its own governed window, enqueues only the permitted
   continuation, preserves token identity and token-local results, rewrites the
   earlier deferred close, and produces identical, close-order-independent
   decisions. The E.9 compressed proof path is untouched.
