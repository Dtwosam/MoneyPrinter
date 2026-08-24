# Printer V1 V2-9.8B Latest Consumed Authorization Historical-Disposition Owner Design

Date: 2026-08-24

Starting HEAD: `f18408c7da6cad3147d653aef93b9950603ebb35`

## Verdict

`V2_9_8B_LATEST_CONSUMED_AUTHORIZATION_HISTORICAL_DISPOSITION_OWNER_DESIGN_PASS_READY_FOR_NEXT_LANE`

Design decision:

`A. EXACT_POLICY_ADOPTION_SUFFICIENT`

The current architecture already owns diagnostic-only historical dispositions
through exact authorization-ID registrations. The minimum truthful repair is
one exact entry in the existing `_POLICY_TERMINAL_DISPOSITIONS` map. No new
vocabulary, inference framework, evidence class, package root, schema, DB
object, runtime consumer, or authorization mechanism is justified.

## Baseline and authority

- Required HEAD: `f18408c7da6cad3147d653aef93b9950603ebb35`.
- Branch:
  `agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit`.
- Tracked worktree and index: clean at entry.
- Visible untracked paths are the already classified operator authorization,
  migration, and reconciliation evidence roots.
- `CURRENT_HANDOFF.md` names this exact design-only lane.
- This lane performs documentation only. It does not create an authorization,
  application, marker, child, campaign, provider call, Scheduler call, or DB
  write.

## Existing supported disposition

Result:

`EXISTING_SUPPORTED_DISPOSITION`

`git_provenance_authorization_manifest.py` already declares
`CONSUMED_CHILD_EXITED_NONZERO` in `TERMINAL_DISPOSITION_VOCABULARY`.
`_validate_historical_authorization_evidence(...)` accepts only values in that
vocabulary. `enumerate_historical_authorization_evidence(...)` obtains the
diagnostic value through `_terminal_disposition_for(...)`, whose approved exact
exceptions are owned by `_POLICY_TERMINAL_DISPOSITIONS` and whose fallback is
`DISPOSITION_NOT_AVAILABLE`.

The vocabulary is diagnostic only and explicitly creates no trust or reuse
authority. Existing history and closeouts already use
`CONSUMED_CHILD_EXITED_NONZERO` for consumed one-shot children that exited
nonzero. No new label is required.

## Exact immutable evidence

Authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd`

Read-only production validation and immutable readback prove:

- exactly one package and one application directory;
- package path:
  `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd/final_authorization.json`;
- package SHA-256:
  `d76470f33838f4d3d05a3ea865940a2d52e96597b30d61d2ef3c19a99ef50a32`;
- package size/mode: `4281` / `0444`;
- marker SHA-256:
  `1ecb94577b08a1ab7cb5546a2f09a65f81373a9b819a9b1d21756f80632993f4`;
- marker consumed at `2026-08-24T14:44:52.991489+00:00`;
- allowed invocation count exactly one;
- child start attempted and exact child terminal validated;
- child exit code `1`, success false, terminal category
  `OPERATIONAL_COMMAND_BLOCKED`;
- wrapper classification `CHILD_EXITED_NONZERO`;
- automatic retries, manual reruns, resumes, restarts, and successors all zero;
- marker flags for retry, rerun, resume, restart, and successor all false.

The existing canonical semantics therefore resolve exactly to
`CONSUMED_CHILD_EXITED_NONZERO`. This classification says only that the consumed
one-shot child exited nonzero. It does not infer campaign success or identify
the historical persistence subcause.

## Current production owner and consumer trace

The real future path is:

1. a future authorization document declares the complete sorted
   `prior_authorizations_non_reusable` trust root;
2. `extract_approved_historical_authorization_ids(...)` and
   `validate_prior_authorizations_non_reusable(...)` validate that root;
3. `four_token_standard_four_hour_one_shot_wrapper.build_manifest_bytes(...)`
   calls `enumerate_historical_authorization_evidence(...)` with the approved
   four-token package roots;
4. the enumerator inventories exact untracked package files and calls
   `_terminal_disposition_for(package_id)`;
5. `_terminal_disposition_for(...)` consults
   `_POLICY_TERMINAL_DISPOSITIONS` and otherwise returns
   `DISPOSITION_NOT_AVAILABLE`;
6. the enumerator emits exact path, SHA-256, size,
   `HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE`, authorization ID, and
   terminal disposition into the future manifest;
7. `_validate_historical_authorization_evidence(...)`,
   `_reconcile_evidence_sets(...)`, and
   `validate_git_provenance_manifest_pre_marker(...)` validate vocabulary,
   identity, bytes, disjoint evidence ownership, and complete inventory before
   any marker can exist;
8. audit/forensic readers may inspect the resulting diagnostic field.

At the current HEAD, step 5 has no entry for `...95dc47dd`, so its exact real
historical record contains `DISPOSITION_NOT_AVAILABLE` despite the immutable
application evidence above.

No production consumer reads `CONSUMED_CHILD_EXITED_NONZERO`,
`BLOCKED_UNCONSUMED_SUPERSEDED`, or `DISPOSITION_NOT_AVAILABLE` outside this Git
provenance owner. The same field name used by lifecycle/reporting modules is a
separate domain and none consumes historical authorization dispositions.

## Prior-history comparison

| Authorization | Package/application truth | Current historical disposition | Non-reuse truth |
| --- | --- | --- | --- |
| `...20260821T153458Z_512f2436` | Consumed marker; one child; child exit `0`; wrapper `CHILD_EXITED_ZERO`; campaign later `BLOCKED_UNSAFE` | `DISPOSITION_NOT_AVAILABLE` at current HEAD; no change in this lane | Permanently consumed through marker, one-shot flags, trust root, and obsolete Migration-059 binding |
| `...20260823T221645Z_6af1423a` | Unconsumed; no application/marker/child; expired and superseded | Exact policy adoption `BLOCKED_UNCONSUMED_SUPERSEDED` | Permanently historical and unconsumed; temporal expiry and trust root forbid reuse |
| `...20260824T123555Z_95dc47dd` | Consumed marker; one validated child; child exit `1`; wrapper `CHILD_EXITED_NONZERO` | Current default `DISPOSITION_NOT_AVAILABLE`; proposed exact adoption `CONSUMED_CHILD_EXITED_NONZERO` | Permanently consumed through marker, one-shot flags, and trust root regardless of temporal validity |

The comparison confirms exact-ID policy registration is the established
architecture for histories whose approved diagnostic is more specific than the
default. It also confirms that the three histories must not be collapsed.
This design does not opportunistically assign a new disposition to
`...512f2436`.

## Minimum production design

The later implementation may add only this exact registration to
`_POLICY_TERMINAL_DISPOSITIONS` in
`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`:

```text
V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd
    -> CONSUMED_CHILD_EXITED_NONZERO
```

No other production semantic change is required. In-memory prospective
enumeration with only that exact registration changes the one `...95dc47dd`
record to the required disposition while preserving its path, SHA-256, size,
evidence class, trust root, and all other authorization records. A nearby
lookalike ID continues to return `DISPOSITION_NOT_AVAILABLE`.

Rejected alternatives:

- Generic scanning or inference from arbitrary application directories would
  create a new trust input and broaden disposition ownership.
- Inferring every future disposition from child exit codes would conflate
  application evidence with historical package enumeration and create an
  unapproved global classifier.
- Leaving the default unchanged would preserve non-reuse but would not satisfy
  the canonical evidence requirement established by rereadiness.

## Historical evidence and reconciliation invariants

The adopted record remains only:

`HISTORICAL_WINDOW_15M_AUTHORIZATION_EVIDENCE`

This existing class name is shared by approved authorization-package roots and
must not be renamed. `...95dc47dd` never becomes current authorization evidence,
current Migration-061 evidence, application authority, or execution-ready
authority.

The exact adoption changes only a diagnostic string. It does not change:

- current Migration-061 files or identity;
- historical migration or reconciliation inventories;
- package path, bytes, SHA-256, size, or mode;
- allowed package roots or evidence classes;
- current-versus-historical disjointness;
- `F = T ∪ M ∪ Ha ∪ Hm ∪ Hr` reconciliation;
- undeclared-path or symlink/non-regular-file failure behavior;
- pre-marker SHA/size validation or allowed-file-set binding.

## Future trust-root and temporal behavior

The next real preparation must derive the complete trust root mechanically. At
this design baseline the prospective result is `43` sorted unique IDs with
duplicate count zero and independent membership for:

- `...20260821T153458Z_512f2436`;
- `...20260823T221645Z_6af1423a`;
- `...20260824T123555Z_95dc47dd`.

The count is an observed baseline, not a constant. Implementation proof must
derive it from the current production inventory.

Removing only `...95dc47dd` from that root continues to fail closed because its
exact untracked package becomes unapproved historical evidence. The policy map
does not create directory trust and cannot compensate for omission.

Consumption permanently beats temporal validity. Neither enumeration nor the
policy registration may call `TEMPORALLY_VALID` or use an unelapsed expiration
as execution authority. The consumed marker makes `...95dc47dd` non-reusable
even if its original expiration had not elapsed.

## Integrity and tamper behavior

The policy entry is diagnostic metadata, not an integrity bypass:

- historical manifest construction continues to bind exact package path,
  SHA-256, and size;
- `_validate_historical_authorization_evidence(...)` continues to reject bytes
  changed after enumeration;
- full marker validation continues to bind authorization SHA, manifest SHA,
  allowed-file-set SHA, branch, HEAD, command, and one-shot flags;
- `read_child_terminal_envelope(...)` continues to bind the exact sibling
  marker path/SHA, authorization ID, mode, and exit code;
- a package, manifest, marker, or child-terminal mismatch remains a failure in
  its existing owner.

The implementation must not make historical enumeration depend dynamically on
external application directories. Tests may use the immutable evidence to prove
the approved policy fact and disposable copies to prove the existing tamper
boundaries.

## Focused TDD matrix for the next lane

| Case | Underlying proof boundary | Required result |
| --- | --- | --- |
| A. RED exact enumeration | Real immutable `...95dc47dd` package, prospective trust root including its ID, current production enumerator | Exact record currently has `DISPOSITION_NOT_AVAILABLE` |
| B. GREEN exact adoption | Same real package and enumerator after the one exact policy registration | One exact historical record has authorization ID `...95dc47dd`, disposition `CONSUMED_CHILD_EXITED_NONZERO`, path above, SHA `d76470...50a32`, size `4281`, and unchanged historical class |
| C. Omission fail-closed | Remove only `...95dc47dd` from the derived prospective trust root | Enumeration/pre-marker reconciliation rejects the undeclared historical package; no directory-discovery trust |
| D. Wrong-ID negative | Disposable nearby/lookalike ID with identical-looking bytes or terminal shape | It does not inherit the mapping and remains default/unapproved |
| E. Evidence tamper | Disposable package copy changed after enumeration; separately tampered manifest/marker/child binding through existing validators | Existing SHA/size/marker/child validation fails; policy registration grants no bypass |
| F. Historical distinctions | Enumerate `...512f2436`, `...6af1423a`, and `...95dc47dd` together | First retains its separate consumed history/current default, second remains `BLOCKED_UNCONSUMED_SUPERSEDED`, third becomes `CONSUMED_CHILD_EXITED_NONZERO` |
| G. Current versus historical | Reconcile full derived evidence sets | `...95dc47dd` appears only in `Ha`; never current `M`, current authorization, or execution authority; no overlaps or undeclared paths |
| H. Runtime isolation | Static production search for exact vocabulary and historical field consumers | Only provenance/evidence validation and audit paths consume it; no Scheduler, provider, budget, admission, retry, memory, retrieval, decision, or financial authority |

Tests must use disposable mutation boundaries. They must not modify the real
package/application evidence or authoritative DB. The expected focused test
owner is
`tests/test_v2_9_8b_four_token_historical_migration_provenance.py`, with only a
separate directly focused module if keeping the proof isolated genuinely
requires it.

## Schema and implementation surface

Schema verdict:

`NO_SCHEMA_CHANGE_REQUIRED`

Expected production surface:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` — one
  exact map entry only.

Expected non-production surface:

- focused historical-authorization tests;
- minimal `CURRENT_HANDOFF.md` update and later closeout documentation.

If implementation requires another production subsystem, new evidence class,
new root, marker inference, or enumeration refactor, it must stop for design
amendment.

The authoritative DB remains byte-identical at
`9962fc4fe9e47c785e0732450102d0b2f5cd62fff6081b8517102b04a2a9efc5`.
No migration or DB write belongs to this sequence.

## Runtime-authority isolation and permanent locks

Historical disposition may support only evidence reconciliation, provenance
validation, audit/forensics, and non-reuse trust-root proof. It cannot drive
Scheduler selection/priority/cooldown, provider selection, source budget,
admission, retry/rerun/resume/restart/successor, memory quality, retrieval,
decisions, positions, trades, audits, PnL, or any other runtime action.

All V1 locks remain unchanged: Solana-only, Solana memecoin-only, paper-only;
no wallet/private key/signing/real funds/live execution; no paid API, scoring,
ranking, confidence, weighted logic, embedding, or vector; Source Governor and
Central Scheduler remain mandatory; dirty memory remains excluded; 5m remains
support-only; Cycle 3, 12h/24h, retrieval, BUY/SELL/HOLD, positions, trades,
audits, PnL, and V2-10 remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- A generic application-directory classifier would create a second historical
  trust mechanism and is forbidden.
- `...512f2436` also has specific consumed evidence but currently carries the
  default disposition; changing it is outside this blocker and must not be
  smuggled into the narrow implementation.
- The historical evidence validator checks disposition vocabulary and exact
  file bytes; the implementation must not weaken either boundary merely to make
  the new expected record pass.
- The observed trust-root count may grow before implementation; derive it and
  never pin `43` as policy.
- The old incident's exact persistence subcause remains irrecoverable and is
  unrelated to this diagnostic-only adoption.

## Exact sequencing

Next permitted action:

`V2-9.8B LATEST-CONSUMED AUTHORIZATION HISTORICAL-DISPOSITION NARROW TDD IMPLEMENTATION`

Required sequence afterward:

1. narrow TDD implementation;
2. independent bounded proof / actual patch inspection;
3. implementation closeout;
4. repeat post-repair exact-HEAD/worktree/DB rereadiness;
5. only after that rereadiness PASS, fresh authorization preparation.

Stop after this docs-only design. No implementation, authorization, or campaign.
