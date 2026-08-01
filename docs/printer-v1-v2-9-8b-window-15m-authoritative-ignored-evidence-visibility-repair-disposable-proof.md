# Printer V1 V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Bounded Disposable Proof

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Bounded Disposable Proof`

Lane type: bounded disposable proof only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_DISPOSABLE_PROOF_PASS`

The committed ignored-evidence visibility repair passed bounded disposable verification against the exact implementation commit.

This proof does not authorize or execute a real `WINDOW_15M` campaign. It does not build the production wrapper, issue a new authorization, contact providers, run Source Governor or Central Scheduler, open or mutate the authoritative database, create memory, activate retrieval, or unlock paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## 2. Controlling baseline

| Item | Value |
| --- | --- |
| Proof branch | `agent/v2-9-8b-window-15m-ignored-evidence-visibility-repair-disposable-proof` |
| Proofed HEAD | `32ec6467d08165637015d5775d5ba6e2180a74af` |
| Implementation verdict | `V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_IMPLEMENTATION_PASS` |
| Design baseline | `cce78eae42a4e711439c0623fdadc1dde857cf2a` |
| Authoritative evidence shape | 19 files: 17 Git-visible plus 2 Git-ignored `.sqlite3` backups |

The active Printer V1 source stack remains:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## 3. External proof record identity

The operator supplied the immutable proof record:

`V2_9_8B_WINDOW_15M_IGNORED_EVIDENCE_DISPOSABLE_PROOF_20260801T231732Z`

Recorded local path:

`/Users/Dtwo1/PrinterOperations/v2-9-8/ignored-evidence-visibility-disposable-proof/V2_9_8B_WINDOW_15M_IGNORED_EVIDENCE_DISPOSABLE_PROOF_20260801T231732Z/disposable_proof_record.json`

Independent SHA-256 verification:

`33d2e42b640fd8cbef77af215491efc653bbf0c0ef6d6daf885770da8cf36705`

File size:

`172156` bytes.

Schema:

`PRINTER_V1_V2_9_8B_IGNORED_EVIDENCE_DISPOSABLE_PROOF_V1`

The independently calculated SHA-256 matched the operator-reported digest exactly.

## 4. Exact committed code and test identity

The proof record verified that all seven working files matched their committed Git blobs:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `src/printer_v1/operator_cli/git_provenance.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`
- `tests/test_v2_9_8b_window_15m_ignored_evidence_visibility.py`
- `tests/test_v2_9_7b_5_embedded_git_provenance.py`
- `tests/test_v2_9_8a_public_operational_command.py`

Every `working_blob` equaled its corresponding `committed_blob`.

## 5. Compilation and focused test proof

The proof used in-memory Python compilation with no bytecode output.

Compilation result:

- return code: `0`
- errors: none

The focused committed pytest command covered the original validator/integration suite, the new authoritative ignored-evidence suite, embedded Git provenance, and the public operational command boundary.

Result:

`94 passed in 6.51s`

Pytest return code:

`0`

Pytest stderr was empty.

The proof therefore covered both the repaired three-set reconciliation and its surrounding operational Git-provenance contracts.

## 6. Authoritative-shaped evidence invariance

The proof independently recorded the accepted evidence packages before and after execution.

Results:

- expected evidence files: `19`
- before count: `19`
- after count: `19`
- before/after dictionaries: exactly equal
- every path retained identical size, `mtime_ns`, and SHA-256
- the two ignored SQLite backups remained present and unchanged

The accepted evidence inventory included the exact migration package and failed one-shot authorization package already preserved by prior lanes.

No evidence was deleted, moved, renamed, rewritten, or rehashed into a different value.

## 7. Authoritative database invariance

The authoritative database was not opened through SQLite.

Before and after state matched exactly:

- path exists: true
- regular file: true
- symlink: false
- size: `65671168`
- `mtime_ns`: `1785617072867102156`
- `-wal`: absent
- `-shm`: absent
- `-journal`: absent

Disposable SQLite connections used by focused tests:

`22`

Authoritative SQLite connection attempts:

`0`

Unknown SQLite targets:

`0`

The 22 allowed connections were confined to disposable test databases.

## 8. Runtime guard results

| Guard | Count |
| --- | ---: |
| Network attempts | 0 |
| Authoritative SQLite attempts | 0 |
| Unknown SQLite targets | 0 |
| Forbidden launcher/campaign subprocess attempts | 0 |
| Allowed Git subprocesses | 954 |
| Other subprocesses | 1 |
| Guard log files | 1 |

The single non-Git subprocess belonged to the bounded test environment and did not invoke PowerShell, the one-shot wrapper, the operational launcher, providers, Scheduler, or a campaign.

## 9. Repository write and cleanliness proof

The proof recorded:

- tracked status before: clean
- tracked status after: clean
- repository files written: false
- bytecode writes disabled: true
- pytest cache disabled: true
- ignored source/test inventory before and after: exactly equal

The two visible `operator-runs/` directories remained the already accepted evidence packages. Their presence was expected and their contents were separately proven unchanged.

## 10. Protected capability counters

Every protected capability counter remained zero:

- provider calls
- Source Governor calls
- Scheduler calls
- campaign calls
- real campaign invocations
- memory calls
- retrieval calls
- decision calls
- position calls
- trade calls
- paper trade audit calls
- PnL calls

No wallet, private key, signing, real funds, live execution, paid API, scoring, ranking, confidence, weighting, embedding, or vector capability was introduced or exercised.

## 11. Harness blockers preceding PASS

Three earlier local invocations stopped because of proof-runner defects rather than Printer implementation failures:

1. missing `textwrap` import before test execution;
2. an over-broad socket monkeypatch that broke Python standard-library SSL imports during collection;
3. an over-broad SQLite guard that blocked disposable test databases after 82 tests had passed.

Each stopped fail-closed. The successful path-aware runner preserved Python's socket class, blocked outbound connections, allowed only disposable SQLite targets, and blocked the authoritative database path.

These harness corrections did not modify Printer source, tests, accepted evidence, the authoritative database, or operational runtime state.

## 12. Money-usefulness contribution

This proof removes the implementation uncertainty behind the prior 19-file-versus-17-visible evidence blocker.

It shows that Printer can preserve the full audit package, including the two ignored SQLite backups, while still rejecting unmanifested visible or ignored evidence. That reduces the chance of consuming another scarce one-shot authorization on a deterministic pre-runtime provenance failure.

It does not create a market signal, favorable memory, retrieval result, paper decision, position, trade, or profit claim.

## 13. What the lane improves

- proves the repaired validator against real `*.sqlite3` ignore semantics;
- proves all 19 authoritative-shaped files can coexist in one exact manifest boundary;
- proves extra visible and ignored evidence remains fail-closed through focused tests;
- preserves the original manifest and marker schemas;
- preserves the canonical six-field Git-provenance payload;
- preserves ordinary `WINDOW_15M` mode and one-attempt ownership boundaries;
- preserves the authoritative DB and accepted evidence packages unchanged.

## 14. What remains locked

This proof does not unlock:

- independent repair closeout;
- repeated authoritative readiness audit;
- production one-shot wrapper construction;
- a fresh authorization;
- provider or source fetching;
- discovery or Scheduler runtime;
- a `WINDOW_15M` campaign;
- memory generation or promotion;
- retrieval;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL.

`WINDOW_5M_MICRO_EVENT` remains support-only. Solana-only, Solana memecoin-only, and paper-only restrictions remain unchanged.

## 15. Proof still required before readiness

The roadmap still requires:

1. independent repair closeout;
2. repeated post-repair authoritative readiness audit against the preserved 19-file evidence packages;
3. only after readiness PASS, a separate fresh final authorization lane.

No campaign may run before those steps pass.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current control |
| --- | --- |
| General ignored-file bypass | Ignored enumeration remains scoped to `operator-runs/` |
| Extra ignored evidence | Focused negative tests passed |
| Evidence drift | Exact 19-file before/after equality and SHA preservation passed |
| Authoritative DB mutation | No authoritative connection; exact stat and sidecar equality passed |
| Hidden tracked changes | Tracked state clean before and after |
| Test cache or bytecode residue | Disabled; ignored source/test inventories matched |
| Harness overblocking | Corrected to path-aware authoritative DB and network guards |
| Runtime or campaign drift | No launcher, Scheduler, provider, or campaign invocation occurred |
| Readiness overclaim | Independent closeout and repeated authoritative audit remain mandatory |

## 17. Exact next lane

`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Independent Closeout`

Type: independent audit/closeout documentation and read-only verification only.

It may not build the wrapper, issue authorization, contact providers, run Scheduler, execute a campaign, mutate the authoritative database, generate memory, activate retrieval, or unlock paper trading.
