# Printer V1 V2-9.8B WINDOW_15M Pre-Lifecycle Git-Provenance Block Audit

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Pre-Lifecycle Git-Provenance Block Audit`

Review type: audit-only, read-only, documentation-only.

## Verdict

`V2_9_8B_WINDOW_15M_PRE_LIFECYCLE_GIT_PROVENANCE_BLOCK_AUDIT_PASS`

The consumed invocation did not enter the campaign lifecycle. It was blocked by
a deterministic incompatibility between the one-shot wrapper's required
repository-local immutable evidence files and the production Git-provenance
helper's no-allowlist launch call.

The block was not caused by an unrelated or unsafe repository file.

A fresh authorization is eligible only after a separate wrapper-provenance design,
implementation, bounded proof, and closeout. No rerun is authorized by this audit.

## Controlling evidence

- Consumed authorization:
  `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z`
- Final-authorization commit:
  `ffb7e4581833ee4ee77763a2bfcff0c98f8087a1`
- Terminal-evidence result:
  `V2_9_8B_WINDOW_15M_TERMINAL_EVIDENCE_CAPTURED_SAFE`
- Command result:
  `OPERATIONAL_COMMAND_BLOCKED`
- Command error:
  `operational preflight blocked: gate=git_provenance: launch Git tree contains an arbitrary untracked file`
- Classifier result:
  `FRESH_AUTHORIZATION_ELIGIBLE_AFTER_WRAPPER_PROVENANCE_DESIGN_REPAIR`
- Authoritative post-050 DB SHA-256:
  `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5`
- Migration ledger:
  `50 / 050_campaign_scheduler_ownership_scope.sql`

## What happened

The wrapper correctly completed its fresh pre-run gates and then wrote the
required immutable files before invoking the authorized command:

- `pre_run_evidence.json`;
- `application_started.json`.

Those files were intentionally stored under the untracked repository-local
`operator-runs/` authorization package.

The production command then called Git provenance without an exact untracked-file
allowlist. Its helper therefore reported `git_untracked_present=true`, and the
operational preflight failed closed before creating any new campaign identity,
artifact directory, source request, Scheduler work, or database row.

## Classifier findings

The read-only classifier inspected all 17 repository-visible untracked files:

- 13 existed before command start;
- 4 were written only after the command returned;
- 0 were unrelated or unapproved;
- 0 known hashes mismatched;
- every file belonged to one of two approved immutable evidence roots:
  - the accepted migration-050 execution package;
  - the consumed WINDOW_15M authorization package.

The production helper reproduced the block with no allowlist:

- tracked tree clean: `true`;
- staged changes: `false`;
- unstaged changes: `false`;
- untracked present: `true`.

The same production helper passed when given the exact 17-file allowlist:

- tracked tree clean: `true`;
- staged changes: `false`;
- unstaged changes: `false`;
- untracked present: `false`.

The helper supports exact repository-relative file paths only. It does not accept
directories, globs, absolute paths, or traversal.

## Pre-lifecycle safety result

The attempted invocation produced:

- one consumed authorization marker;
- one command invocation;
- exit code `1`;
- zero source calls;
- zero Scheduler-runtime calls;
- zero database writes;
- zero table deltas;
- zero new Printer campaign artifact directories;
- zero active campaign, discovery, Scheduler, factory, or proof residue;
- zero locked Scheduler jobs;
- zero stale or incomplete leases;
- zero retrieval or paper-capability deltas;
- no restart, resume, successor, report-only replay, or orphan recovery;
- integrity `ok`;
- zero foreign-key violations;
- exact pre/post authoritative DB hash, size, and mtime equality;
- no SQLite sidecars.

The latest supervision row remained the prior completed campaign. No new
supervision row was created by this attempt.

## Root cause

`DETERMINISTIC_WRAPPER_PROVENANCE_SELF_BLOCK`

The wrapper and production command enforced individually valid rules that were
not composed correctly:

1. the wrapper had to create durable pre-run and consumption evidence before
   launch;
2. the production command rejected every non-allowlisted untracked path;
3. the wrapper did not supply the exact approved file allowlist to the production
   Git-provenance capture;
4. therefore the wrapper guaranteed its own pre-lifecycle rejection.

This is a wrapper/provenance integration defect. It is not evidence that the
production Git-provenance safety rule should be weakened.

## Roadmap decision

A direct rerun or fresh authorization now would skip required design,
implementation, proof, and closeout steps. It is not allowed.

The correct next work is a narrowly scoped wrapper-provenance repair section:

1. design the exact provenance-compatible one-shot wrapper contract;
2. implement only the approved integration change;
3. prove it on a disposable/non-campaign path with no provider calls and no
   authoritative DB mutation;
4. close the repair with exact hashes and negative tests;
5. repeat post-repair readiness and final authorization before any new campaign
   attempt.

## Required repair design properties

The next design must preserve all existing Git-provenance safety and add only a
bounded exact-file integration:

- no `.gitignore`, `.git/info/exclude`, or global-ignore mutation;
- no directory or glob allowlisting;
- no broad `operator-runs/` exemption;
- no deletion, relocation, or rewriting of accepted evidence packages;
- no bypass of `capture_git_provenance()` or `validate_launch_provenance()`;
- exact repository-relative paths only;
- exact path set derived before launch;
- each allowed path must be inside an approved immutable evidence package;
- every allowed file must have an expected hash or a just-created immutable hash
  bound into the wrapper marker;
- any extra untracked file must block;
- any missing, changed, renamed, duplicated, or post-hoc-added allowed file must
  block;
- tracked-tree cleanliness remains mandatory;
- the final production provenance payload remains the canonical six-field
  validated object;
- no provider, source, Scheduler, campaign, memory, retrieval, or financial work
  may occur during repair proof.

## Money-usefulness contribution

This audit prevents wasting another scarce one-shot campaign authorization on a
wrapper that is guaranteed to fail before useful collection begins. It preserves
the stronger Git safety boundary while making future evidence collection capable
of reaching the real bounded paper-only campaign path.

It creates no market signal, memory, decision, position, trade, or profit claim.

## What this lane improves

- identifies the exact pre-lifecycle failure mode;
- proves no unrelated untracked file caused the block;
- proves the authoritative DB and protected capabilities were untouched;
- distinguishes wrapper integration failure from campaign/runtime failure;
- establishes the minimum safe repair boundary;
- prevents an unjustified rerun or broad ignore-rule workaround.

## What this lane still does not unlock

This audit does not authorize:

- another wrapper or campaign invocation;
- providers, RPC, WebSockets, source fetching, discovery, or Scheduler runtime;
- memory generation or promotion;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof required before repair completion

Minimum sufficient proof:

1. exact-path allowlist generation is deterministic;
2. no-allowlist reproduces `git_untracked_present=true` on the disposable fixture;
3. exact approved-file allowlist produces `git_untracked_present=false`;
4. one unrelated untracked file blocks;
5. one hash-mismatched allowed file blocks;
6. a directory, glob, absolute path, or traversal entry blocks;
7. tracked staged or unstaged changes block;
8. no repository ignore configuration changes;
9. no authoritative DB mutation;
10. zero provider, source, Scheduler, campaign, memory, retrieval, or financial
    calls;
11. focused tests only, followed by closeout review.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition | Required control |
| --- | --- | --- |
| Broad allowlist could hide unrelated files | Not allowed | Exact file paths only |
| Wrapper-created files change after binding | Must block | Bind hash before launch and recheck |
| Existing migration evidence is large and untracked | Accepted evidence requirement | Exact manifest and hashes, no directory exemption |
| Production helper payload omits file names by design | Preserve privacy/simplicity | Wrapper retains separate hashed manifest |
| Moving evidence outside repo could break accepted paths | Not approved | Keep packages intact unless separately designed |
| Ignoring `operator-runs/` would weaken safety | Rejected | No ignore-rule changes |
| Fresh authorization could be mistaken as already available | Not yet | Repair closeout, readiness, and authorization must repeat |
| Another collector bug could waste time | Known efficiency risk | Focused deterministic proof before operator use |

## Exact next permitted lane

`V2-9.8B WINDOW_15M One-Shot Wrapper Git-Provenance Compatibility Design`

Type: design/specification only.

It may inspect code and write design documentation. It may not implement the
repair, run the campaign, call providers, mutate the authoritative DB, or issue a
fresh campaign authorization.
