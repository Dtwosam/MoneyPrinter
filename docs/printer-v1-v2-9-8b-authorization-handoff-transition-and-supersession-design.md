# Printer V1 V2-9.8B Authorization Handoff-Transition and Supersession Design

Date: 2026-08-25

Starting HEAD: `ec59f29c79533a4b3612cce467ae604e70b5904b`

Verdict:

`V2_9_8B_AUTHORIZATION_HANDOFF_TRANSITION_AND_SUPERSESSION_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION`

This lane is design and specification only. It does not implement the
conditional chain, adopt a policy-map entry, independently review or start
`...17181afc`, create a replacement authorization, or create marker, child,
application, campaign, provider, Scheduler, or database evidence.

## Decision

The valid unconsumed package
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc` is permanently unusable
as execution authority. Independent review of that exact package is forbidden
even though its substantive package checks passed.

The blocker is a workflow/handoff-transition defect, not a package-byte,
schema, database, or runtime defect. Future review and start authority must be
encoded prospectively in the launch-bound tracked handoff **before**
authorization preparation. A tracked `CURRENT_HANDOFF.md` rewrite after
preparation changes HEAD and invalidates an exact-HEAD-bound package.

The existing canonical diagnostic for this blocked, unconsumed, marker-absent
package is `BLOCKED_UNCONSUMED_SUPERSEDED`. The existing canonical historical
owner is `_POLICY_TERMINAL_DISPOSITIONS`. No new vocabulary, classifier,
evidence class, package root, schema, database object, or runtime consumer is
justified.

## Blocker classification

`AUTHORIZATION_WORKFLOW_HANDOFF_TRANSITION_DEFECT`

This classification names the workflow defect. It is not a
`TERMINAL_DISPOSITION_VOCABULARY` value and must not be added as one.

## Bound blocked authorization

The create-once package remains:

- ID: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc`;
- path:
  `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc/final_authorization.json`;
- SHA-256:
  `99d2759e14da7d50ac301699a021d92bd3be0e024d36ec2a171ef23ff78a3f80`;
- size: `4344` bytes;
- mode: `0444`;
- bound branch:
  `agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit`;
- bound HEAD: `ec59f29c79533a4b3612cce467ae604e70b5904b`;
- bound authoritative DB SHA-256:
  `9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`;
- current migration execution: `MIGRATION_061_20260823T200709Z`;
- authorized at: `2026-08-24T22:26:38.079847+00:00`;
- expires at: `2026-08-25T10:26:38.079847+00:00`;
- independently reviewed: no;
- consumed: no;
- durable manifest, marker, child, campaign, and runtime ownership: absent.

The package is valid on substantive authorization, Git, DB, migration, and
historical-trust-root checks. Validity is not execution authority. The package
MUST NOT be independently reviewed as a start candidate, marked, applied, or
run. Historical adoption must not change any package byte or reinterpret the
package as reviewed or consumed.

## Current authority trace

1. Active Printer V1 source stack, including `AGENTS.md` and
   `docs/printer-v1-memory-growth-build-order-v2.md`, remains the higher
   authority.
2. Tracked `CURRENT_HANDOFF.md` at starting HEAD `ec59f29...` still names:

   `V2-9.8B FRESH EXACT-HEAD FOUR-TOKEN STANDARD-FOUR-HOUR 4/2/2 AUTHORIZATION PREPARATION ONLY`
3. The rereadiness checkpoint that produced that handoff is
   `docs/printer-v1-v2-9-8b-post-historical-disposition-repair-exact-head-worktree-db-rereadiness.md`.
   It granted preparation only. It did not prospectively encode independent
   review or operator start.
4. Authorization preparation then created `...17181afc` as an untracked
   create-once package bound to that same HEAD.
5. Independent review of that exact package is therefore blocked: the
   launch-bound tracked handoff still names preparation only, so review is not
   a permitted action at the bound HEAD.
6. Updating tracked `CURRENT_HANDOFF.md` after preparation would create a new
   commit, change HEAD, and invalidate the exact-HEAD package.
7. `_POLICY_TERMINAL_DISPOSITIONS` currently has no entry for `...17181afc`, so
   historical enumeration would emit only the default
   `DISPOSITION_NOT_AVAILABLE`.
8. No later authorization, marker, child, or campaign exists for this ID.

The source stack wins any conflict with this design. This design does not
create execution authority.

## Why tracked post-preparation handoff mutation is incompatible

An exact-HEAD authorization binds the launch branch and the exact commit that
exists when the package is created. Independent review and later operator start
must re-derive that same HEAD.

`CURRENT_HANDOFF.md` is a tracked file. Any post-preparation rewrite that
changes "next permitted action" from preparation to independent review, or from
independent review to operator start, is a tracked mutation. That mutation:

- requires a new commit on the launch branch;
- changes `HEAD`;
- makes `repository.head` in the already-created package false;
- fails closed at provenance / pre-marker validation.

Leaving the handoff at `AUTHORIZATION PREPARATION ONLY` after a valid package
exists blocks independent review even when every substantive package check
passes. That is the present defect.

The only compatible owner of the next two permissions is prospective encoding
in the launch-bound tracked handoff **before** the package exists.

Independent-review evidence may later exist as untracked operator evidence or
on a non-launch branch. It must not move the bound launch HEAD. A separate
review-branch closeout does not repair a launch-HEAD handoff that still names
preparation only.

## Prospective encoding requirement

Future authority must be written into the launch-bound `CURRENT_HANDOFF.md`
before authorization preparation, as conditional clauses that do not require a
later tracked mutation of that same HEAD.

The required prospective chain is exactly:

```text
preparation PASS + unchanged exact bindings
  -> INDEPENDENT REVIEW ONLY permitted without tracked mutation

independent review PASS + unchanged exact bindings
  -> SEPARATE OPERATOR START OF THAT EXACT AUTHORIZATION
     permitted without tracked mutation

any BLOCKED result, HEAD drift, package drift, DB drift, evidence drift,
host blocker, zero-state blocker, schema blocker, or expiry
  -> operator start forbidden
```

"Unchanged exact bindings" means the launch-bound branch, HEAD, authorization
bytes and SHA-256, authoritative DB SHA-256, current Migration-061 provenance,
historical non-reuse trust root, evidence inventory, and host / zero-state /
schema readiness remain the bindings recorded at preparation.

"Without tracked mutation" means no tracked file on the launch-bound tree may
be rewritten to confer the next permission. The immediate next-action line at
preparation remains `AUTHORIZATION PREPARATION ONLY`. Transitions A and B are
conditional permissions already present at that HEAD.

This design document is the durable contract. `CURRENT_HANDOFF.md` is the
operational owner of the live clauses. No production parser, runtime state
machine, or generic classifier may be introduced to own the chain.

## Conditional Transition A

Name: `TRANSITION_A_INDEPENDENT_REVIEW_ONLY`

Trigger, all required:

- one create-once authorization package exists;
- preparation closed PASS for that exact package;
- the package is bound to the current launch HEAD;
- that launch HEAD already contains this prospective chain;
- exact Git, DB, migration, evidence, host, zero-state, and schema bindings
  are unchanged;
- the package remains unconsumed, temporally valid, marker-absent, and
  child-absent;
- no BLOCK condition below is true.

Effect:

`INDEPENDENT REVIEW ONLY` of that exact authorization is permitted without
tracked mutation of the launch HEAD.

Transition A does not consume the authorization, create a marker, start a
child, or permit operator start.

## Conditional Transition B

Name: `TRANSITION_B_SEPARATE_OPERATOR_START_ONLY`

Trigger, all required:

- Transition A already permitted independent review of that exact package;
- independent review of that exact package closed PASS;
- exact bindings remain unchanged from the package and from the review;
- the package remains unconsumed, temporally valid, marker-absent, and
  child-absent;
- no BLOCK condition below is true.

Effect:

one separately operator-started invocation of **that exact authorization** is
permitted without tracked mutation of the launch HEAD.

Transition B does not create a successor, retry, rerun, resume, or restart. It
does not authorize a different authorization ID, a refreshed package, or a
tracked handoff rewrite.

## Fail-closed BLOCK transition

Name: `TRANSITION_BLOCK_OPERATOR_START_FORBIDDEN`

Any one of the following forbids operator start, forbids Transition B, and
forbids treating the package as executable authority:

- any BLOCKED result from preparation, independent review, rereadiness, schema
  admission, zero-state, host safety, or provenance validation;
- HEAD drift from the package's bound commit;
- branch drift from the package's bound branch;
- package-byte or package-SHA drift;
- authoritative DB drift;
- Migration-061 / current-evidence drift;
- historical-trust-root or operator-evidence inventory drift;
- host blocker;
- zero-state blocker;
- schema blocker;
- expiry or other loss of temporal validity;
- any consumption, marker, child, or application evidence for that ID;
- any retry, rerun, resume, restart, or successor request.

BLOCK is fail-closed and non-repairable for that exact authorization identity.
The package remains historical evidence. A later campaign, if any, requires the
full later sequence in this design, including a completely new authorization
bound to a later HEAD that already contains the prospective chain.

## Why `...17181afc` cannot use Transition A or B

`...17181afc` is bound to `ec59f29...`. That HEAD's tracked handoff does not
contain Transitions A or B. Retrofitting those clauses onto `ec59f29...`
requires a tracked mutation and would invalidate the package. Therefore
`...17181afc` is not a Transition A or Transition B candidate.

The correct terminal handling is supersession, not delayed independent review.

## `...17181afc` supersession design

Adopt the exact ID as historical, diagnostic-only, permanently non-reusable
evidence:

```text
V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc
    -> BLOCKED_UNCONSUMED_SUPERSEDED
```

Keep the package at its current path with unchanged bytes, SHA-256, size, and
mode. Do not create marker, child, application, or campaign evidence. Do not
relocate the package. Do not independently review it as a start candidate.

`BLOCKED_UNCONSUMED_SUPERSEDED` is already in
`TERMINAL_DISPOSITION_VOCABULARY` and is already used for other blocked
unconsumed marker-absent packages. No new label is required. The more specific
historical truth — valid package, independent review blocked by missing
prospective handoff encoding — remains in this design and later closeout. The
diagnostic field does not have to restate that narrative.

This design does not treat later expiry as the primary cause. Expiry, if it
occurs, is an additional fail-closed fact. It does not revive the package and
does not justify a different vocabulary value.

## Exact historical owner

The only approved production owner is the existing exact-ID map:

`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
`_POLICY_TERMINAL_DISPOSITIONS`

The existing consumer path remains:

1. a future authorization document declares the complete sorted
   `prior_authorizations_non_reusable` trust root;
2. `extract_approved_historical_authorization_ids(...)` and
   `validate_prior_authorizations_non_reusable(...)` validate that root;
3. four-token Standard-4H manifest construction calls
   `enumerate_historical_authorization_evidence(...)`;
4. the enumerator inventories exact untracked package files and calls
   `_terminal_disposition_for(package_id)`;
5. `_terminal_disposition_for(...)` consults `_POLICY_TERMINAL_DISPOSITIONS`
   and otherwise returns `DISPOSITION_NOT_AVAILABLE`;
6. the enumerator emits path, SHA-256, size,
   `HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE`, authorization ID, and
   terminal disposition;
7. historical validation, evidence-set reconciliation, and pre-marker
   validation continue to bind vocabulary, identity, bytes, and disjoint
   ownership before any marker can exist.

Directory discovery never creates trust. The policy map never creates trust.
Omission of `...17181afc` from a future trust root must continue to fail closed
against the immutable untracked package.

No production consumer may read `BLOCKED_UNCONSUMED_SUPERSEDED` as Scheduler,
provider, admission, retry, memory, retrieval, decision, or financial
authority. Same-named `terminal_disposition` fields in other modules remain
separate lifecycle domains.

## Distinct prior history

| Authorization | Package/application truth | Required diagnostic | Non-reuse truth |
| --- | --- | --- | --- |
| `...20260821T153458Z_512f2436` | Consumed marker; child exit `0` | Keep current default `DISPOSITION_NOT_AVAILABLE` | Permanently consumed; not in this lane |
| `...20260823T221645Z_6af1423a` | Unconsumed; expired; no marker | Keep `BLOCKED_UNCONSUMED_SUPERSEDED` | Permanently historical; not collapsed with `...17181afc` |
| `...20260824T123555Z_95dc47dd` | Consumed marker; child exit `1` | Keep `CONSUMED_CHILD_EXITED_NONZERO` | Permanently consumed |
| `...20260824T222638Z_17181afc` | Valid unconsumed package; no marker/child; review blocked by missing prospective handoff encoding | Adopt `BLOCKED_UNCONSUMED_SUPERSEDED` | Permanently historical and unconsumed |

Sharing the diagnostic `BLOCKED_UNCONSUMED_SUPERSEDED` with `...6af1423a` does
not merge the two histories. Exact IDs, bytes, dates, and causes remain
distinct. This lane must not opportunistically reclassify `...512f2436`.

## Future trust-root behavior

The next real replacement authorization, after the later rereadiness PASS, must
derive the complete sorted unique `prior_authorizations_non_reusable` list from
production evidence. That list must include `...17181afc`.

At this design baseline the prospective derived root is 44 unique IDs, with
duplicate count zero. The 44 count is an observation from the immutable
`...17181afc` prior list (43) plus `...17181afc` itself. It is not a production
constant and must not be hard-coded.

Removing only `...17181afc` from a future root must fail closed. Temporal
validity of `...17181afc` cannot create reuse authority. Policy registration
cannot compensate for omission.

## No generic classifier

Forbidden:

- inferring `BLOCKED_UNCONSUMED_SUPERSEDED` from "unconsumed and not
  independently reviewed";
- scanning application directories or wrapper terminals to assign
  dispositions;
- prefix, glob, or regular-expression matching of authorization IDs;
- a CURRENT_HANDOFF parser in production code;
- a runtime state machine for Transitions A and B;
- collapsing distinct IDs that share a diagnostic string.

The only approved disposition change is one exact-ID map entry. The only
approved handoff-transition change is explicit prospective text in
`CURRENT_HANDOFF.md` according to this contract.

## No schema, database, or runtime change

Schema verdict:

`NO_SCHEMA_CHANGE_REQUIRED`

This sequence must not add, alter, or apply a migration; must not write the
authoritative database; must not change Source Governor, Central Scheduler,
wrapper, marker, child, campaign, or provider runtime; and must not create
`ValidatedGitProvenanceAuthorization` except inside later separately authorized
preparation of a replacement package.

The authoritative DB identity remains
`9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5` for this
design baseline. This lane does not re-hash or mutate it.

## Narrow implementation surface

Expected production surface:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` — one
  exact `_POLICY_TERMINAL_DISPOSITIONS` entry for `...17181afc`.

Expected operational surface:

- `CURRENT_HANDOFF.md` — durable prospective Transition A / Transition B /
  fail-closed BLOCK clauses specified by this contract. Those clauses must be
  installed by the implementation lane and preserved through later independent
  proof, closeout, and rereadiness. They must not authorize review or start of
  `...17181afc`. They become live only for a later replacement authorization
  whose bound HEAD already contains them.

Expected non-production surface:

- focused historical-authorization tests for the exact policy adoption;
- static proof that the handoff contract forbids post-preparation tracked
  mutation of a launch HEAD that already binds a candidate package;
- later closeout documentation.

If implementation requires another production subsystem, new evidence class,
new root, marker inference, enumeration refactor, CURRENT_HANDOFF parser, or
runtime transition engine, it must stop for design amendment.

This design lane must not implement that surface.

## Focused proof matrix

Tests and inspection must use disposable mutation boundaries. They must not
modify the real `...17181afc` package, create application evidence for it, or
open the authoritative database for write.

| Case | Underlying proof boundary | Required result |
| --- | --- | --- |
| A. RED exact enumeration | Real immutable `...17181afc` package, prospective trust root including its ID, current production enumerator | Exact record currently has `DISPOSITION_NOT_AVAILABLE` |
| B. GREEN exact adoption | Same real package and enumerator after the one exact policy registration | One exact historical record has authorization ID `...17181afc`, disposition `BLOCKED_UNCONSUMED_SUPERSEDED`, path above, SHA `99d2759e...3f80`, size `4344`, mode `0444`, class `HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE` |
| C. Omission fail-closed | Remove only `...17181afc` from the derived prospective trust root | Enumeration/pre-marker reconciliation rejects the undeclared historical package; no directory-discovery trust |
| D. Wrong-ID negative | Disposable nearby/lookalike ID with identical-looking bytes | It does not inherit the mapping and remains default/unapproved |
| E. Evidence tamper | Disposable package copy changed after enumeration | Existing SHA/size validation fails; policy registration grants no bypass |
| F. Historical distinctions | Enumerate `...512f2436`, `...6af1423a`, `...95dc47dd`, and `...17181afc` together | First keeps its current default, second stays `BLOCKED_UNCONSUMED_SUPERSEDED`, third stays `CONSUMED_CHILD_EXITED_NONZERO`, fourth becomes `BLOCKED_UNCONSUMED_SUPERSEDED` without collapsing identities |
| G. Current versus historical | Reconcile derived evidence sets | `...17181afc` appears only in `Ha`; never current `M`, current authorization, or execution authority |
| H. Unconsumed isolation | Real package directory and application namespace | No marker, child, or application directory for `...17181afc`; implementation creates none |
| I. Prospective chain encoding | Implementation and later rereadiness `CURRENT_HANDOFF.md` | Transition A, Transition B, and fail-closed BLOCK are present before any replacement authorization is created |
| J. Post-preparation mutation incompatibility | Launch HEAD that already binds a candidate package | Tracked `CURRENT_HANDOFF.md` rewrite to confer review or start is treated as HEAD drift / BLOCK, not as a repair |
| K. `...17181afc` exclusion | Bound HEAD `ec59f29...` lacks the prospective chain | Transitions A and B do not apply; independent review and operator start remain forbidden |
| L. Derived trust-root observation | Production prior-ID derivation including `...17181afc` | Sorted unique count is derived, currently observed `44`, never pinned as a constant |
| M. Runtime isolation | Static production search | Only provenance/evidence validation and audit paths consume the new exact map entry; no Scheduler, provider, budget, admission, retry, memory, retrieval, decision, or financial authority |

The expected focused test owner is a directly focused historical-disposition
module, or an additive exact-ID section in the existing latest-consumed
disposition tests, if keeping the proof isolated does not require a broader
refactor. Do not overload unrelated migration-provenance tests unless that is
the minimum sufficient owner.

## Runtime-authority isolation and permanent locks

Historical disposition and handoff-transition text may support only evidence
reconciliation, provenance validation, audit/forensics, non-reuse trust-root
proof, and the prospective review/start permission chain. They cannot drive
Scheduler selection, provider selection, source budget, admission,
retry/rerun/resume/restart/successor, memory quality, retrieval, decisions,
positions, trades, audits, PnL, or any other runtime action.

All V1 locks remain unchanged: Solana-only, Solana memecoin-only, paper-only;
no wallet/private key/signing/real funds/live execution; no paid API, scoring,
ranking, confidence, weighted logic, embedding, or vector; Source Governor and
Central Scheduler remain mandatory; dirty memory remains excluded; 5m remains
support-only; Cycle 3, 12h/24h, retrieval, BUY/SELL/HOLD, positions, trades,
audits, PnL, and V2-10 remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Installing Transition A/B in `CURRENT_HANDOFF.md` during implementation must
  not be misread as permission to review or start `...17181afc`.
- Later closeout and rereadiness updates must preserve the prospective clauses
  while changing only the immediate next-action line. Dropping the clauses
  would recreate this defect.
- A generic unconsumed-package classifier would create a second historical
  trust mechanism and is forbidden.
- The observed trust-root count may grow before replacement preparation;
  derive it and never pin `44` as policy.
- Temporal expiry of `...17181afc` is not a reason to run it and not a reason
  to invent a second diagnostic.
- Independent-review evidence placed on the launch branch would recreate HEAD
  drift; review evidence must stay off the bound launch HEAD.
- Known stale fixtures remain debt and are outside this lane.

## Exact sequencing

Exact next permitted action after this design:

```text
V2-9.8B AUTHORIZATION HANDOFF-TRANSITION AND SUPERSESSION
NARROW IMPLEMENTATION
```

Required sequence afterward:

1. narrow implementation of the exact policy-map entry and the durable
   prospective CURRENT_HANDOFF chain;
2. independent bounded proof / actual patch inspection;
3. implementation closeout;
4. exact-HEAD / worktree / DB rereadiness, with Transitions A/B/BLOCK already
   present in the launch-bound handoff;
5. replacement authorization preparation bound to that later HEAD;
6. independent review of that replacement authorization under Transition A,
   without tracked launch-HEAD mutation;
7. one separately operator-started campaign of that replacement authorization
   under Transition B, only if every gate still passes.

Stop after this docs-only design. No implementation. No replacement
authorization. No marker. No campaign.
