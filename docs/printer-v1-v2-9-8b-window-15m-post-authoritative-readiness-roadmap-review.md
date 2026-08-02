# Printer V1 V2-9.8B WINDOW_15M Post-Authoritative-Readiness Roadmap Review

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Post-Authoritative-Readiness Roadmap Review`

Lane type: audit/readiness review and documentation-only roadmap reconciliation.

## 1. Verdict

`V2_9_8B_WINDOW_15M_POST_AUTHORITATIVE_READINESS_ROADMAP_REVIEW_PASS`

The authoritative current-vs-historical reconciliation is PASS, but Printer is
not yet ready for another authorization or ordinary `WINDOW_15M` attempt.

The missing capability is not validation. The strict production validator and
operational-command consumer already exist.

The missing capability is a real external one-shot wrapper that constructs the
fresh manifest, atomically creates the authorization-consumption marker, injects
the four exact bindings only into one child process, and prevents retry,
rerun, resume, restart, successor, or environment leakage.

## 2. Controlling source stack

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active build order is used inside this stack and is not the sole source of
truth.

## 3. Exact baseline

| Item | Value |
| --- | --- |
| Review branch | `agent/v2-9-8b-window-15m-post-authoritative-readiness-roadmap-review` |
| Starting HEAD | `21262837322b31301cbfc495f814d7f84f149774` |
| Readiness verdict | `V2_9_8B_WINDOW_15M_REPEATED_POST_TRUST_BOUNDARY_REPAIR_AUTHORITATIVE_READINESS_AUDIT_PASS` |
| Preserved repository shape | 11 tracked historical + 19 current untracked = 30 |
| Current evidence split | 17 visible + 2 ignored SQLite |
| Consumed authorization | historical-only, not reusable |

All required repair, proof, closeout, and readiness commits are ancestral.

## 4. Static capability inventory

### Already built

- strict `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` validation;
- strict `PRINTER_V1_APPLICATION_MARKER_V1` validation;
- exact current/historical reconciliation;
- operational Python consumption of all four external path/hash bindings;
- fail-closed partial-variable rejection;
- ordinary `preflight-only`/`run` mode restriction;
- exact current allowlist return;
- Source Governor and Central Scheduler ownership preservation.

### Missing

- production manifest construction;
- production application-marker construction;
- atomic external artifact publication;
- exact authorization-consumption timing;
- one-child environment injection and parent cleanup;
- one-shot launch ownership;
- interruption/partial-artifact recovery law;
- proofed prevention of retry, rerun, resume, restart, and successor.

The public PowerShell command is a direct Python launcher and does not provide
these missing capabilities.

The only manifest/marker constructors are inside the disposable test fixture and
must not be promoted directly into production.

## 5. Roadmap decision

The project must not proceed directly to fresh authorization.

The exact next lane is:

```text
V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Design
```

This is the design stage required by the active V2 completion pattern.

## 6. Minimum compliant future sequence

1. **Design/specification**
   - define the wrapper, artifact, consumption, failure, and proof contracts.
2. **Narrow implementation**
   - only after design approval; no campaign execution.
3. **Bounded disposable proof**
   - disposable Git repo/artifacts/child only; no providers or authoritative DB.
4. **Independent closeout**
   - verify implementation and proof identities.
5. **Fresh authoritative readiness audit**
   - read-only real repository/evidence/DB checks.
6. **Fresh exact-HEAD one-shot authorization**
   - separate operator approval; one invocation, no retry or successor.
7. **One ordinary `WINDOW_15M` attempt**
   - only through the approved wrapper and existing operational command.
8. **Independent campaign closeout**
   - truthful terminal evidence and lock preservation.

## 7. Required design boundaries

The design must settle:

- whether the committed owner is a new PowerShell wrapper, Python helper, or a
  minimal composition of both;
- one external artifact root under the operator-controlled operations directory;
- manifest schema creation without changing the approved schema;
- current package enumeration and tracked-history exclusion;
- exact branch/HEAD, authorization-document, file-set, and digest binding;
- atomic file creation, permissions, and immutability;
- marker creation as the single authorization-consumption event;
- behavior when failure occurs before marker creation;
- behavior when failure occurs after marker creation but before child start;
- behavior when the child exits nonzero or the host disappears;
- explicit prohibition of retry, rerun, resume, restart, and successor;
- child-only environment injection and guaranteed parent cleanup;
- no secret values in artifacts or logs;
- no network or SQLite work in construction;
- disposable proof cases and minimum sufficient regression scope.

## 8. Money-usefulness contribution

This review prevents another scarce one-shot authorization from being consumed
before the provenance artifacts and atomic launch boundary actually exist.

That improves the probability that a later approved `WINDOW_15M` attempt reaches
useful paper-only collection instead of failing at process launch.

It creates no market signal, memory, retrieval result, decision, position,
trade, or profit claim.

## 9. What this lane improves

- removes ambiguity after authoritative readiness PASS;
- distinguishes validation from construction;
- prevents test-only builders from becoming accidental production authority;
- establishes the required V2 design-first sequence;
- preserves historical evidence and consumed-authorization truth;
- gives the next lane one narrow capability target.

## 10. What remains locked

- wrapper implementation;
- real manifest or marker creation;
- authorization issuance;
- provider, RPC, WebSocket, or source contact;
- Source Governor or Scheduler runtime;
- campaign execution;
- authoritative DB connection or mutation;
- memory generation or promotion;
- retrieval;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana memecoin-only, and paper-only.

## 11. Proof/test required before completion of the next major capability

The wrapper capability will not be complete until it passes:

1. approved design;
2. narrow implementation;
3. bounded disposable positive and negative proof;
4. independent closeout;
5. repeated authoritative readiness;
6. separate operator authorization.

Minimum proof cases must include:

- exact valid manifest/marker/child PASS;
- extra visible and ignored evidence block;
- tracked file in current package blocks;
- historical mutation blocks;
- partial environment set blocks;
- wrong path/hash/digest/branch/HEAD/authorization ID blocks;
- duplicate or pre-existing artifact blocks;
- crash before marker does not consume authorization;
- crash after marker consumes authorization and forbids another child;
- child nonzero exit cannot create retry or successor;
- parent environment is clean after launch;
- network and authoritative SQLite access remain zero.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition |
| --- | --- |
| Direct jump to authorization | Reject; wrapper construction is missing |
| Existing validator is treated as full wrapper | Reject; it only validates/consumes |
| Test fixture is copied into production | Reject; design and ownership required |
| Marker timing is ambiguous | Design must define one atomic consumption point |
| Failure before/after marker is conflated | Separate fail-closed laws required |
| Environment survives beyond child | Child-only injection and cleanup required |
| Artifact is mutable after launch | Immutable create-once identity required |
| Existing consumed authorization is reused | Prohibited |
| Broad implementation or runtime tests are requested | Use minimum sufficient static/design checks now |
| Scope reaches providers, DB, memory, or trading | Stop immediately |

## 13. Exact next lane

`V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Design`

Type: design/specification only.

No implementation or operational action is authorized by this roadmap review.
