# Printer V1 V2-9.8B WINDOW_15M Current-vs-Historical operator-runs Trust Boundary Repair Implementation

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Current-vs-Historical operator-runs Trust Boundary Repair Implementation`

Lane type: narrow implementation and focused disposable verification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_VS_HISTORICAL_OPERATOR_RUNS_TRUST_BOUNDARY_REPAIR_IMPLEMENTATION_PASS`

The approved current-vs-historical `operator-runs/` trust-boundary design is implemented in the production Git-provenance authorization manifest validator.

The implementation replaces the incorrect whole-namespace rule `F == M` with the approved exact-HEAD model:

`F == T union M`

where committed historical files are bound by the authorized Git HEAD and current visible/ignored untracked evidence remains bound by the external manifest.

No wrapper or marker was built, no authorization was issued, no provider or source was contacted, no Source Governor or Central Scheduler runtime ran, no campaign executed, no authoritative database was opened or mutated, and no memory, retrieval, decision, position, trade, audit, or PnL capability changed.

## 2. Controlling source stack

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order remains part of this stack and is not the sole source of truth.

## 3. Exact baseline

| Item | Value |
| --- | --- |
| Implementation branch | `agent/v2-9-8b-window-15m-current-vs-historical-operator-runs-trust-boundary-implementation` |
| Starting HEAD | `7b2ca06d6904ac237a17fb03a43630b85540e1a5` |
| Approved design verdict | `V2_9_8B_WINDOW_15M_CURRENT_VS_HISTORICAL_OPERATOR_RUNS_TRUST_BOUNDARY_REPAIR_DESIGN_PASS` |
| Authoritative target shape | 11 tracked historical + 17 visible current + 2 ignored current = 30 files |

## 4. Exact files changed

1. Modified:
   `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
2. Modified:
   `tests/test_v2_9_8b_window_15m_ignored_evidence_visibility.py`
3. Added:
   `docs/printer-v1-v2-9-8b-window-15m-current-vs-historical-operator-runs-trust-boundary-repair-implementation.md`

No ignore rule, public command, wrapper, authorization, migration, database, Scheduler, source, memory, retrieval, or paper-trading file changed.

## 5. Implemented set model

The production validator now derives:

- `M`: current manifest paths;
- `V`: Git-visible untracked paths;
- `I`: scoped Git-ignored untracked paths under `operator-runs/`;
- `T`: exact-HEAD tracked paths under `operator-runs/`, obtained with `git ls-tree -r --name-only -z HEAD -- operator-runs/`;
- `F`: complete no-follow filesystem inventory under `operator-runs/`.

The validator requires:

- `F == T union M`;
- current package inventory equals `M`;
- `M` contains no tracked path;
- `T`, effective `V`, and `I` are pairwise disjoint;
- every manifest path is visible-untracked or ignored-untracked;
- visible untracked paths outside `M` block;
- ignored untracked `operator-runs/` paths outside `M` block;
- tracked files inside either current package root block;
- filesystem paths belonging to neither exact HEAD nor current manifest block;
- symlinks and non-regular entries anywhere under `operator-runs/` block.

The returned allowlist still contains only the current manifest paths, never tracked historical paths.

## 6. Compatibility preserved

Unchanged:

- `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1`;
- `PRINTER_V1_APPLICATION_MARKER_V1`;
- allowed-file-set digest;
- `ValidatedGitProvenanceAuthorization` public fields;
- bounded filename-free summary;
- canonical six-field Git-provenance payload;
- `capture_git_provenance()` semantics;
- operational command shape;
- `WINDOW_15M` and one-attempt/no-retry law;
- Source Governor and Central Scheduler ownership;
- all memory, retrieval, decision, position, trade, audit, and PnL locks.

## 7. Focused verification

Result:

`113 passed`

Pytest return code: `0`.

The focused suites prove the full authoritative-shaped `30 = 11 tracked + 19 current` model and surrounding manifest, marker, embedded provenance, and public operational-command contracts.

## 8. Money-usefulness contribution

This implementation removes the deterministic pre-marker blocker created by conflating committed historical evidence with current authorization evidence.

It preserves both historical audit continuity and exact current evidence safety, reducing the chance of consuming another scarce one-shot authorization before useful paper-only `WINDOW_15M` collection begins.

It creates no market signal, memory, retrieval result, paper decision, position, trade, or profit claim.

## 9. What improved

- exact Git HEAD now binds historical `operator-runs/` artifacts;
- the current manifest binds only current untracked evidence;
- the complete namespace remains inventoried;
- unexpected visible, ignored, tracked-in-current-root, symlink, and special-file states remain fail-closed;
- the real 30-file repository shape is represented in focused tests;
- no evidence deletion, relocation, ignore mutation, or manifest inflation is needed.

## 10. What remains locked

- bounded disposable proof;
- independent repair closeout;
- repeated authoritative readiness audit;
- wrapper construction;
- marker creation;
- fresh authorization;
- providers, source fetching, Source Governor, Scheduler, and campaign runtime;
- memory generation or promotion;
- retrieval;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- wallets, private keys, real funds, live execution, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer V1 remains Solana-only, Solana memecoin-only, and paper-only.

## 11. Proof required next

The bounded proof must execute the committed implementation and focused suites against a disposable repository reproducing the full authoritative shape:

- 30 total `operator-runs/` files;
- 11 tracked historical files;
- 17 visible current files;
- 2 ignored current SQLite files;
- exactly 19 returned current allowlist paths;
- no historical path in the allowlist;
- required negative cases;
- zero protected capability activity;
- unchanged authoritative evidence and database state.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Control |
| --- | --- |
| Historical files become a broad exemption | Only exact paths in the authorized HEAD enter `T` |
| New untracked file resembles history | It remains visible/ignored untracked and blocks |
| Tracked file appears in current package | Explicitly blocks |
| Historical file is modified or deleted | Clean-tree checks and inventory reconciliation block |
| Hidden ignored extra appears | Scoped ignored enumeration and manifest equality block |
| Namespace contains symlink or special file | Complete no-follow inventory blocks |
| Historical paths leak into current allowlist | Result remains exactly `M`; focused test proves exclusion |
| Public schemas drift | No schema or public-field change |
| Runtime capability expands | No operational/runtime file changed |
| Authoritative readiness is overclaimed | Proof, closeout, and repeated audit remain mandatory |

## 13. Exact next lane

`V2-9.8B WINDOW_15M Current-vs-Historical operator-runs Trust Boundary Repair Bounded Disposable Proof`

Type: bounded disposable proof only.

It may not build the real wrapper, create a marker, issue authorization, contact providers, run Source Governor or Central Scheduler, execute a campaign, mutate the authoritative database, generate memory, activate retrieval, or unlock paper trading.
