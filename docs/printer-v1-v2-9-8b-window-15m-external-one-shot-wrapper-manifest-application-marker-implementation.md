# Printer V1 V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Implementation

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Implementation`

## 1. Verdict

`V2_9_8B_WINDOW_15M_EXTERNAL_ONE_SHOT_WRAPPER_MANIFEST_APPLICATION_MARKER_IMPLEMENTATION_PASS`

The approved one-shot launch boundary is implemented and verified with disposable fixtures only.

No authoritative manifest, marker, authorization, provider call, Source Governor runtime, Scheduler runtime, campaign, authoritative database connection, memory, retrieval, decision, position, trade, audit, or PnL action occurred.

## 2. Exact baseline

- starting commit: `8773831d8b3f246e86821b0c20165fd441f47226`;
- design verdict:
  `V2_9_8B_WINDOW_15M_EXTERNAL_ONE_SHOT_WRAPPER_MANIFEST_APPLICATION_MARKER_DESIGN_PASS`;
- preserved authoritative evidence directories remained untracked and untouched.

## 3. Implemented scope

1. Added canonical Python owner:
   `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`.
2. Added thin PowerShell entrypoint:
   `scripts/Start-PrinterV1-Window15M-OneShot.ps1`.
3. Refactored the validator into reusable pre-marker preparation plus complete validation.
4. Added a CLI-level ordinary-run guard requiring complete wrapper bindings.
5. Added focused disposable tests.
6. Added this implementation report.

## 4. Implemented contracts

- deterministic exact-package manifest construction;
- approved manifest and marker schemas unchanged;
- existing allowed-file-set digest owner reused;
- five-set current/historical reconciliation reused before marker creation;
- fixed external application root;
- create-once canonical application directory;
- create-once marker as durable consumption;
- complete post-marker revalidation;
- one child maximum;
- child-only four-variable environment injection;
- direct ordinary CLI run blocked without bindings;
- no retry, rerun, resume, restart, or successor;
- safe terminal process record that does not claim campaign success;
- macOS `/var` and `/private/var` parent aliases canonicalized without accepting an internal repository symlink alias.

## 5. Implementation-time blockers and repairs

### 5.1 Canonical parent-path alias

The first focused run reported 17 failures and 101 passes. All failures shared one root cause: macOS represented the same temporary repository as `/private/var/...` while the supplied authorization path used `/var/...`.

The production repair:

- compares canonical filesystem identities for containment;
- discovers the supplied lexical repository boundary;
- requires lexical and canonical repository-relative paths to be identical;
- continues to reject symlinks or aliases introduced below the repository boundary;
- adds a parent-alias acceptance and internal-alias rejection regression test.

### 5.2 Lexical test assertion

The second focused run reported 1 failure and 118 passes.

The production repair had correctly passed the canonical repository path to the child, but one disposable test still compared `/private/var/...` and `/var/...` lexically.

The test was corrected to use filesystem identity via `os.path.samefile()`. No production behavior or scope changed.

## 6. Focused verification

Command:

```text
/Users/Dtwo1/Developer/MoneyPrinter/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v2_9_8b_window_15m_one_shot_wrapper.py tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py tests/test_v2_9_8b_window_15m_ignored_evidence_visibility.py
```

Result:

```text
........................................................................ [ 60%]
...............................................                          [100%]
119 passed in 9.36s
```

Additional checks:

- in-memory source compilation: PASS;
- `git diff --check`: PASS;
- exact implementation scope: PASS;
- bytecode and pytest cache disabled.

## 7. Money-usefulness contribution

The implementation prevents the next one-shot authorization from depending on manual manifest creation, manual environment setup, or an unguarded direct run.

It improves the chance that a later separately approved `WINDOW_15M` attempt reaches useful paper-only collection without weakening evidence or one-attempt safety.

It creates no memory or profit claim.

## 8. What this implementation improves

- one canonical production application owner;
- no validator-logic duplication;
- exact pre-marker gate;
- explicit durable consumption boundary;
- child environment isolation;
- direct-run bypass closure;
- deterministic evidence artifacts;
- filesystem-alias-safe path containment;
- one-attempt terminal truth.

## 9. What remains locked

- authoritative application;
- current-evidence rollover;
- fresh readiness and authorization;
- providers and source fetching;
- Source Governor and Scheduler runtime;
- campaign execution;
- authoritative DB access or mutation;
- memory and retrieval;
- decisions, positions, trades, audits, and PnL;
- longer windows;
- wallets, private keys, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors.

## 10. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current disposition |
| --- | --- |
| Wrapper implementation has only disposable evidence | Requires bounded disposable proof next |
| Consumed authorization evidence remains current untracked | Separate rollover prerequisite remains |
| Marker exists but terminal record is absent after host loss | Later read-only audit must classify; no rerun |
| Child exits zero but campaign evidence is incomplete | Wrapper never declares campaign PASS |
| Platform permission/fsync behavior differs | Bounded proof must exercise supported local semantics |
| Broad runtime regression remains unrun | Reserved for later closeout/readiness per risk-based policy |

## 11. Exact next lane

`V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Bounded Disposable Proof`

No authoritative application or campaign is authorized.
