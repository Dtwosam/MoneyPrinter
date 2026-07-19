# V2-9.7D.7A Abstract Command Surface Closeout

## Status

PASS. V2-9.7D.7A adds an internal, non-shell command contract for one bounded
campaign or one zero-source report-only replay. It does not publish an
operational command and does not activate a campaign.

## What Was Built

- Frozen command, ceiling, lock-request, owner-port, and execution-result
  objects.
- Read-only preflight for exact campaign/configuration/run, DB target, policy,
  canonical migration ledger through 033, stored clean Git provenance,
  backup/restore references, report-directory identity, two-slot cycles,
  active/foreign leases, and locked capabilities.
- A bounded campaign handler that requires injected `SOURCE_GOVERNOR` and
  `CENTRAL_SCHEDULER` owner ports, acquires one operational lease, delegates
  once, validates all finite usage ceilings, supports idempotent cancellation,
  uses committed supervision cleanup, verifies zero locked-capability deltas,
  and persists the immutable final report.
- A report-only handler that delegates to the committed read-only replay API
  with exact campaign, configuration, report, and report-hash identities.
- Safe-stop behavior for an invalid or failed delegated execution after lease
  acquisition. No successor, resume, or automatic restart path exists.

The committed final-report contract requires released-lease evidence. The
handler therefore performs terminal child-work cleanup and lease release
through the single supervision cleanup call before final report assembly and
persistence.

## Money-Usefulness Contribution

This lane gives the completed evidence and campaign components one bounded,
fail-closed activation boundary. Exact budgets, ownership, provenance,
backup readiness, and terminal reporting reduce the risk that future memory
growth is attributed to an ambiguous run or collected outside governed source
and scheduler capacity. It makes later operator review more reliable without
claiming profit or enabling a financial action.

## Proof Completed

- Valid campaign configuration reached only the injected Source Governor and
  Central Scheduler owner ports.
- Invalid capacity, dirty provenance, configuration, DB target, policy,
  report-path, and ceiling inputs blocked before mutation.
- Every persisted cycle was required to contain exactly two slots and remain
  within the cycle ceiling.
- Active or foreign operational leases blocked the command preflight.
- Repeated cancellation preserved one reason and one supervision owner.
- Policy/owner bypass evidence triggered cleanup and lease release.
- Terminal handling preserved the first cause and ordered acquisition,
  delegated work, cancellation, cleanup/release, and report persistence.
- Report-only handling delegated exact identities while fixture DB bytes and
  row counts remained unchanged.
- Locked capability baseline/final deltas remained exactly zero.
- Focused lower-layer supervision, report, replay, and isolated Slice 6 tests
  were rerun as direct regressions.

## Remaining Locks

- No exact PowerShell or other public command is present.
- No persistent-target migration or operational campaign is authorized.
- No source fetch, live runtime loop, scheduler execution, memory generation,
  two-token pilot, or V2-9.7D closeout was performed.
- Retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets,
  signing, live execution, scoring, ranking, confidence, and weighted logic
  remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- This is an abstract dependency-injected surface. A later activation lane must
  bind real committed owners and independently prove the persistent target and
  operator-facing invocation without weakening preflight.
- Report persistence follows committed 6B.6 requirements and can succeed only
  after all authoritative campaign facts and released-lease evidence exist.
- Git provenance is accepted as an exact immutable input and validated against
  the stored configuration. The later operator binding remains responsible for
  using the committed bounded capture owner immediately before invocation.
- The initial focused run exposed only a test-fixture SQLite handle left open
  during teardown. Closing that handle repaired Windows cleanup; no production
  assertion or command behavior failed.
