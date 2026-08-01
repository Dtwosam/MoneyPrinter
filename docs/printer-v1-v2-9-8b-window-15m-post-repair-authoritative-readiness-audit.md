# Printer V1 V2-9.8B WINDOW_15M Post-Repair Authoritative Readiness Audit

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Post-Repair Authoritative Readiness Audit`

Lane type: audit-only, read-only, documentation-only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_POST_REPAIR_AUTHORITATIVE_READINESS_BLOCKED_IGNORED_EVIDENCE_VISIBILITY`

The Git-provenance compatibility implementation and its bounded disposable proof remain valid for the disposable repository conditions that were tested. However, authoritative readiness is not established.

The real repository contains two accepted migration-evidence `.sqlite3` files that are hidden by the repository's standard Git ignore rules. The production validator obtains its observed untracked set with `git ls-files --others --exclude-standard -z` and requires every manifest-listed path to appear in that set. A future exact manifest that includes the complete accepted evidence package will therefore fail before marker creation because the two ignored files are absent from the observed set.

No wrapper, fresh authorization, provider access, source fetching, discovery, Scheduler runtime, campaign, memory generation, retrieval, decision, position, trade, audit, or PnL capability is authorized by this audit.

## 2. Controlling baseline

| Item | Value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-window-15m-post-repair-authoritative-readiness-audit` |
| Starting HEAD | `eeb7345bb1f0ef0ac87d39ee4c5cbcfcc1307a13` |
| Independent repair closeout | `V2_9_8B_WINDOW_15M_GIT_PROVENANCE_COMPATIBILITY_INDEPENDENT_REPAIR_CLOSEOUT_PASS` |
| Implementation commit | `9a22d0de9e1a001b9c508a80c0b50d9ceda12b4c` |
| Disposable proof commit | `ada3376a09abcd6fe291d309889c1fb91d5d73ec` |
| Closeout commit | `eeb7345bb1f0ef0ac87d39ee4c5cbcfcc1307a13` |
| Authoritative DB SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| Authoritative DB size | `65671168` bytes |
| Accepted evidence files | 19 |

The tracked repository state was clean during the independent closeout evidence collection. No SQLite sidecar existed. All 19 accepted evidence files matched the disposable-proof record's pre and post hashes and sizes.

## 3. Authoritative evidence visibility finding

The accepted migration evidence package contains two nested SQLite backup files:

1. `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3`
2. `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3`

Both are regular, non-symlink files. Each is `65654784` bytes with SHA-256:

`e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`

The repository `.gitignore` includes broad SQLite patterns:

- `*.sqlite`
- `*.sqlite3`
- `data/*.sqlite`
- `data/*.sqlite3`

As a result:

- a recursive approved-root inventory sees all 19 accepted evidence files;
- `git ls-files --others --exclude-standard -z` sees only 17;
- the two nested `.sqlite3` files are hidden from the production validator's observed-untracked set.

This difference is deterministic and was independently reproduced during closeout collection. It is not evidence drift and not a missing-file problem.

## 4. Design and implementation conflict

The approved design requires the wrapper to:

1. enumerate all current repository evidence files;
2. prove each belongs to an approved immutable package;
3. re-enumerate the complete repository evidence set;
4. hash every file and build the exact manifest;
5. validate exact equality between observed untracked paths and manifest paths.

The production validator currently obtains `observed` using:

`git ls-files --others --exclude-standard -z`

It then computes:

- `missing_from_repo = manifest_paths - effective_observed`;
- `extra_in_repo = effective_observed - manifest_paths`.

Any `missing_from_repo` path blocks with:

`manifest file is not present in the observed untracked set`

Therefore the authoritative package cannot currently satisfy both requirements:

### Case A: include all 19 accepted evidence files

This preserves full package integrity, but the two ignored `.sqlite3` paths are manifest-listed and absent from `effective_observed`. Validation blocks before marker creation.

### Case B: include only the 17 Git-visible files

This can satisfy current observed-set equality, but it omits two accepted repository evidence files and violates the design's complete-evidence enumeration and exact-manifest requirement. It would weaken audit continuity and is not an approved workaround.

Neither case is readiness-safe.

## 5. Why the disposable proof did not catch this

The bounded disposable proof used temporary repositories and disposable fixtures. The proof correctly demonstrated the validator's logic and fail-closed behavior, including a nested SQLite evidence fixture.

However, the disposable repository did not reproduce the authoritative repository's broad `*.sqlite3` ignore behavior for that nested fixture. The nested file was visible to the test repository's standard untracked query, so exact equality passed there.

The disposable proof is not invalidated. It proved the implemented contract under its stated fixture conditions. The post-repair authoritative audit exists specifically to test whether those conditions match the real repository. They do not yet match in this one material respect.

## 6. Rejected shortcuts

The following are not acceptable remedies:

- deleting or relocating the two accepted backup files;
- omitting them from the manifest;
- adding broad `operator-runs/` ignore or allow rules;
- changing global or local Git exclude configuration;
- disabling standard excludes for all repository files without a bounded design;
- accepting directories or globs instead of exact files;
- bypassing `capture_git_provenance()`;
- creating the irreversible marker before this issue is resolved;
- issuing a fresh authorization to test the current state.

These would weaken provenance, damage audit continuity, or consume authorization without readiness.

## 7. Required design decision

The next lane must design a narrow, fail-closed way to reconcile:

1. Git-visible untracked evidence;
2. explicitly validated ignored evidence under the two exact approved package identities; and
3. complete package inventory.

The design must preserve:

- exact files only;
- no directory or glob exemption;
- no general ignored-file bypass;
- no `.gitignore`, `.git/info/exclude`, or global Git configuration mutation;
- exact path, package identity, size, SHA-256, regular-file, and non-symlink checks;
- detection of extra ignored files both inside and outside approved package roots;
- unchanged six-field Git-provenance payload;
- existing Source Governor and Central Scheduler ownership;
- one-attempt/no-retry law;
- external manifest and marker ordering;
- ordinary `WINDOW_15M` only.

A likely design space is a separate, explicit ignored-evidence inventory that is recursively enumerated only within exact approved package identities and then reconciled with both the manifest and Git-visible set. This is not approved implementation; the design lane must decide the exact trust boundary and failure law.

## 8. Money-usefulness contribution

This audit prevents another scarce one-shot authorization from being consumed by a second deterministic pre-lifecycle provenance mismatch. It improves the chance that the next authorized paper-only `WINDOW_15M` run reaches useful collection while retaining full evidence integrity.

It creates no market signal, clean memory, decision, position, trade, or profit claim.

## 9. What this lane improves

- proves that the repaired code is not yet authoritative-ready despite disposable proof success;
- identifies the exact two files and exact Git-ignore mechanism causing the mismatch;
- separates implementation validity from authoritative-environment compatibility;
- prevents an unsafe shortcut that would omit accepted evidence;
- preserves all existing campaign, memory, retrieval, and paper-trading locks.

## 10. What remains locked

- external one-shot wrapper construction;
- any fresh campaign authorization;
- providers, RPC, WebSockets, and source fetching;
- discovery and Scheduler runtime;
- campaign execution;
- memory generation or promotion;
- retrieval and dirty-memory use;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- wallets, private keys, signing, real funds, live execution, and paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Solana-only, memecoin-only, and paper-only V1 restrictions remain unchanged.

## 11. Proof required after repair

Before authoritative readiness can pass, the later repair sequence must include:

1. design/specification of ignored-evidence reconciliation;
2. approved narrow implementation;
3. focused tests using a repository with the real `*.sqlite3` ignore semantics;
4. positive proof with all 19 authoritative-shaped evidence files represented;
5. negative proof for an extra ignored SQLite file under an approved root;
6. negative proof for an ignored file outside approved roots;
7. proof that visible and ignored evidence cannot be double-counted or omitted;
8. bounded disposable proof with no network, DB mutation, Scheduler, or campaign;
9. independent closeout;
10. repeated post-repair authoritative readiness audit.

Only after that sequence may a fresh final authorization be considered.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current disposition |
| --- | --- |
| Full 19-file manifest blocks because two files are ignored | Confirmed authoritative blocker |
| 17-file manifest omits accepted evidence | Rejected |
| Broad ignored-file enumeration exposes unrelated files | Must be prevented by exact-root design |
| Extra ignored file inside approved root goes unseen | Must become a required negative test |
| Extra ignored file outside approved roots goes unseen | Must become a required negative test |
| Duplicate file appears in visible and ignored inventories | Must fail or canonicalize without ambiguity |
| Changing `.gitignore` weakens repository safety | Rejected |
| Deleting accepted backups damages audit continuity | Rejected |
| Another authorization is consumed before repair | Prohibited |
| Disposable proof fixture differs from authoritative ignore semantics | Confirmed efficiency setback; fixture must be corrected later |

## 13. Exact next lane

`V2-9.8B WINDOW_15M Authoritative Ignored-Evidence Visibility Repair Design`

Type: design/specification only.

The next lane may inspect code and evidence and define the exact reconciliation contract. It may not implement code, modify ignore rules, build the real wrapper, issue authorization, contact providers, run Scheduler, execute a campaign, generate memory, activate retrieval, or unlock paper trading.