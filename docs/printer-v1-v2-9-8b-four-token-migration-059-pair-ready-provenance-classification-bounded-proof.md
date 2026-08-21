# Printer V1 V2-9.8B Four-Token Migration-059 / PAIR_READY Provenance Classification Bounded Proof

Date: 2026-08-21

## Verdict

`V2_9_8B_FOUR_TOKEN_MIGRATION_059_PAIR_READY_PROVENANCE_CLASSIFICATION_BOUNDED_PROOF_PASS`

This is a bounded deterministic/disposable proof of the committed provenance
classification implementation. It created only temporary Git repositories,
fixture authorizations, fixture manifests, fixture markers and fake child
terminal evidence. It did not create a production manifest or marker, apply an
authorization, launch a real child, run Printer, contact a provider, start
Source Governor or Central Scheduler runtime, or mutate authoritative state.

## Commit and scope proof

- design commit:
  `148c8d808b88ad836ca00d21fc0d8185c61b3096`
- implementation commit:
  `a89d1f602065fc856ae43e264cc5389666a2288d`
- proof starting HEAD:
  `a89d1f602065fc856ae43e264cc5389666a2288d`
- branch:
  `agent/v2-9-8b-pair-ready-parent-terminal-cancellation-repair`
- production provenance source SHA-256 before and after proof:
  `c5bf63e5cfeba9467b977eb053e6f7735641bafd4c5697870dd8583a13627a53`
- `_reconcile_evidence_sets()` source SHA-256:
  `d6193bc38336deb3085a038be7853ed70f992a1491c45d5732f465b1bc373eea`

The design commit is an ancestor of the implementation commit. Inspection of
the exact implementation commit found only the approved provenance owner,
seven directly affected tests, the implementation closeout and handoff. The
production diff rotates both four-token profiles to Migration 059, demotes 058
to exact historical migration evidence, adds the exact PAIR_READY historical
reconciliation declaration, extends only the required closed vocabulary, and
adds the diagnostic supersession mapping. The canonical reconciler itself was
not changed.

This proof commit contains only this report and one proof-only deterministic
test file. No production source, migration, authorization, database or
`operator-runs` evidence is changed.

## Committed identity proof

### Current Migration 059

- package root:
  `operator-runs/v2-9-8b-migration-059-application`
- package kind: `MIGRATION_059_EVIDENCE`
- real preserved execution inspected read-only:
  `MIGRATION_059_20260821T095456Z`
- real preserved file count: `5`

The execution identity and files remain authorization/preparation-time current
evidence. Production source does not hard-code the observed execution or its
member list as historical evidence.

### Historical Migration 058

- execution: `MIGRATION_058_20260818T082552Z`
- evidence class: `HISTORICAL_MIGRATION_058_EVIDENCE`
- exact file count: `11`
- committed and independently recomputed inventory SHA-256:
  `d6dc1431a3a99a8c2f521a3033948d11bbdd4e7151ddabc1127c7fb3b9138fa8`

The production enumerator read every preserved regular file and reproduced the
committed count and digest. No symlink, non-regular member or unexplained
sibling was present.

### Historical PAIR_READY residual reconciliation

- execution: `RECONCILIATION_20260821T110736Z`
- evidence class:
  `HISTORICAL_PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE`
- exact file count: `5`
- committed and independently recomputed inventory SHA-256:
  `94cb775d8f1a0d095669c3a1285b8484d7bfbae62c50bf327669516d942285d7`

| Exact member under the declared root/execution | Bytes | SHA-256 |
| --- | ---: | --- |
| `backup_and_disposable_rehearsal.json` | 306712 | `a74406aec8e240d6627a04cf0299bbc95b35a45f2fd98261f60c040e3eb48cf0` |
| `post_reconciliation_snapshot.json` | 92014 | `633424430f850c70a58cd03a6fa4f73b6b89c8baab570946ad7bb79e899aa76c` |
| `pre_reconciliation_snapshot.json` | 92083 | `1f5a2b4b7ba16ec4f4378259bfe863f0bac5c4cd0ff5594c3154e3356b9e26e6` |
| `reconcile_pair_ready_residual.py` | 33379 | `64da79ef2cf1cae93f6fe4acb48f2c4f0c5d22214fc04ed05898776775c8c31a` |
| `reconciliation_receipt.json` | 29684 | `cbdd06a2cd33d1f1917c1b26210f9c27dc4a8b8384004cdb6462eca476544022` |

All five real path, size and SHA-256 records matched the committed production
declaration exactly.

## Production enumeration and profile scope

Read-only enumeration against the untouched real repository returned:

- `Hm = 40` files;
- Migration-058 contribution to `Hm = 11` files;
- `Hr = 12` files;
- PAIR_READY contribution to `Hr = 5` files.

Both four-token profiles have exactly:

- current migration root/kind = Migration 059;
- historical migrations `050, 055, 056, 057, 058`;
- the same exact three historical reconciliation packages, including
  PAIR_READY, because both complete-inventory preparations inspect the same
  `operator-runs` namespace.

The ordinary WINDOW_15M and two-token Standard-4H profiles remain at their
existing current Migration-050 authority and carry neither historical migration
nor historical reconciliation declarations.

## Trust-model proof

The committed implementation still enforces:

```text
F = T ∪ M ∪ Ha ∪ Hm ∪ Hr
C == M
```

The disposable proof uses the real production profile dataclass, wrapper
manifest builder, historical authorization/migration/reconciliation
enumerators, inventory digest functions, Git visible/ignored/tracked owners,
canonical pre-marker validator and `_reconcile_evidence_sets()`. The reconciler
was not mocked or patched.

Trusted historical identities originate only from exact committed profile
declarations. Filesystem discovery can prove equality or fail closed; it cannot
create an identity. Current evidence originates only from the exact
authorization-bound current execution and manifest. Historical migration,
historical authorization and historical reconciliation sets remain disjoint
from current `M` and cannot satisfy current-package equality.

## Disposable full-shape positive proof

The proof constructed a disposable Git repository with:

- current Migration-059 evidence: `1` file;
- current fresh four-token authorization evidence: `1` file;
- approved historical authorization evidence: `1` file;
- historical migrations `050/055/056/057/058`: `40` files with production
  count shape `12/5/6/6/11`;
- historical reconciliation packages, including five-member PAIR_READY:
  `12` files with production count shape `3/4/5`.

Canonical manifest preparation and pre-marker validation passed with exactly
`55` lawful untracked files. The returned allowlist equalled
`M ∪ Ha ∪ Hm ∪ Hr`; Migration 059 entered current `M`, Migration 058
entered `Hm`, PAIR_READY entered `Hr`, and neither historical class appeared as
current evidence.

## Required negative proof matrix

Every case below failed closed in the production owners.

### Current Migration 059

- current file missing;
- current byte modified;
- unexpected extra current file;
- wrong current execution ID;
- historical Migration 058 substituted for Migration 059;
- current inventory contains 058 instead of 059;
- manifest claims 059 while the inventory contains only 058;
- historical reconciliation content copied inside the current package.

### Historical Migration 058

- one of the exact eleven members absent;
- member byte modified;
- extra member;
- wrong execution directory;
- unexplained sibling execution;
- expected member substituted as tracked;
- symlink entry;
- non-regular entry;
- immutable digest mismatch;
- historical path attempts to satisfy current `M`.

### Historical PAIR_READY reconciliation

- any exact member absent;
- member byte changed;
- member size changed;
- member path renamed;
- extra sixth member;
- sibling execution directory;
- evidence-class mismatch;
- execution-ID mismatch;
- symlink;
- non-regular entry;
- tracked/untracked substitution;
- `Hr` overlap with `M`;
- `Hr` overlap with `Ha`;
- `Hr` overlap with `Hm`.

PAIR_READY remained outside the non-reconciliation vocabulary and carried no
current migration, authorization, runtime or reuse authority.

### Global namespace and equality

- unrelated visible file;
- unrelated ignored file;
- unknown/sibling prefix file;
- duplicate path across evidence classes;
- tracked/current overlap;
- expected path absent from complete inventory;
- filesystem path absent from the expected union;
- current inventory not equal to manifest `M`;
- symlink and special-file inventory;
- arbitrary prefix and directory discovery cannot create trust.

## Superseded authorization proof

Authorization:
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T124505Z_8cf7ee5d`

- SHA-256 PRE/POST:
  `644a7b16c7055334e59ab5aa4e820f712b055f8fa4e902d3b9810389fe2724b7`
- mode: `four-token-standard-four-hour-run`
- exact authorized HEAD:
  `e639fb0f43338f231165b8873849f452e0a5c146`
- diagnostic disposition: `BLOCKED_UNCONSUMED_SUPERSEDED`
- production manifest: absent;
- production marker: absent;
- application directory: absent;
- consumption: absent;
- reuse authority: none.

The implementation/proof ancestry is beyond `e639fb0f...`, so the immutable
authorization cannot bind it. The focused exact-HEAD regression committed a
disposable drift after authorization creation and the canonical pre-marker path
rejected it before any fake child call or marker.

## Wrapper and consumption regression proof

Disposable tests proved:

- one canonical four-token Standard-4H wrapper application owner;
- pre-marker/zero-state validation occurs while the marker is absent;
- marker create-once and irreversible consumption remain intact;
- exactly one fake child-launch call site;
- automatic retry, manual rerun, resume, restart and successor counts remain
  zero;
- a non-zero fake child exit remains an honest failure after consumption;
- a second invocation is rejected without a second child call;
- direct operational invocation without complete wrapper bindings fails closed;
- direct failure causes no database, provider or Scheduler side effect.

No real child process was launched.

## Focused verification

Green proof gate:

```text
181 passed, 82 subtests passed
```

This includes the seven implementation-modified test files, the new bounded
proof suite, canonical Standard-4H wrapper tests, exact-HEAD and existing-wrapper
regression locks, strict zero-state tests, profile/schema coherence, selected
operational command ownership tests and direct-command fail-closed tests.

The bounded-proof-specific suite alone passed:

```text
12 passed, 42 subtests passed
```

`py_compile` and `git diff --check` are required again immediately before the
proof commit.

## Unrelated stale fixture classification

Two diagnostic probes intentionally outside the final trust-path gate exposed
pre-existing fixture drift:

1. `test_v2_9_8b_four_token_proof_integrated_disposable_wrapper.py`:
   two failures and one pass. The legacy fixture materializes one Migration-050
   member while the immutable production declaration requires twelve. Primary
   classification: `TEST_HARNESS_DEFECT`.
2. Full `test_v2_9_8b_four_token_standard_four_hour_operational_command.py`:
   184 passes, 82 subtests and two failures. The stale assertions expect
   `lifecycle_requests_per_token = 117`; committed policy is `118`. Primary
   classification: `TEST_HARNESS_DEFECT`.

Neither failure reaches or contradicts Migration-059 current enumeration,
Migration-058 historical enumeration, PAIR_READY reconciliation, complete
inventory equality, exact-HEAD validation, the current Standard-4H wrapper or
direct fail-closed behavior. This proof does not repair or weaken either legacy
fixture.

## Authoritative PRE/POST invariance

| Identity | PRE | POST |
| --- | --- | --- |
| authoritative DB SHA-256 | `87dac0d15ee32940f7dda30d0704dc252ff540c9d6f1ff6a3857e8f598c9f2fa` | same |
| migration count/head | `59 / 059_pair_ready_parent_terminal_cancellation_transition.sql` | same |
| integrity / foreign-key rows | `ok / 0` | same |
| journal mode / sidecars | `delete / none` | same |
| strict zero-state domains | all 12 equal `0` | same |
| active Printer runtime PIDs | none | none |
| production source SHA-256 | `c5bf63e5cfeba9467b977eb053e6f7735641bafd4c5697870dd8583a13627a53` | same |
| operator-runs identity SHA-256 | `67a8989ac8ad8144b2705c138756a3c3a634ab489e7e23c5be06e6c7508946c9` | same |
| operator-runs shape | `86 directories / 167 files / 0 symlinks / 0 special` | same |
| superseded authorization SHA-256 | `644a7b16c7055334e59ab5aa4e820f712b055f8fa4e902d3b9810389fe2724b7` | same |

The operator-runs identity is a canonical SHA-256 over every repository-relative
path, object kind, permission mode, byte size and regular-file content SHA-256.

## Protected capability and activity delta

Actual activity/delta is zero for:

- providers, RPC and WebSockets;
- Source Governor and Central Scheduler runtime;
- real child launch and Printer runtime;
- memory collection;
- retrieval and paper decisions;
- BUY/SELL/HOLD, positions, trades, audits and PnL;
- wallet, private key, signing and live execution;
- paid APIs;
- scoring, ranking, confidence and weighted logic;
- embeddings/vectors;
- 12h/24h.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- The proof depends on exact preserved local evidence; any future byte, path,
  mode or sibling drift must block and require a new classified lane.
- The superseded authorization remains unusable. This proof does not authorize
  a replacement or readiness work.
- Two legacy fixture families remain stale and separately scoped. They must not
  be mistaken for provenance product defects or weakened as part of this lane.
- Production wrapper comments that predate the 059 rotation remain documentary
  drift only; the committed executable profiles and proof results are the
  authority. This proof lane does not permit a production comment edit.

## Exact next permitted lane

`V2-9.8B Four-Token Migration-059 / PAIR_READY Provenance Classification Independent Closeout`

Do not run authorization readiness and do not construct another authorization.
