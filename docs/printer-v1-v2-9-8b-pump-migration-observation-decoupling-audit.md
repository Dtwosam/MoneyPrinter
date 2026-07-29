# Printer V1 V2-9.8B Pump Migration Observation Decoupling Audit

Date: 2026-07-29

Lane: `V2-9.8B Pump Migration Observation Decoupling Audit and Design`

Audit classification: `DESIGN_GAP`

## 1. Scope, baseline, and non-authorization

This is a documentation and design lane only. It performs no provider, RPC,
WebSocket, recovery, N2, N7, campaign, or database operation.

| Baseline gate | Result |
| --- | --- |
| Required HEAD | `90f80d85d99c994a762a47b98fcbb41c5beef63c` - exact |
| Branch | `master` |
| Worktree/index/untracked inventory before work | clean |
| Authoritative DB | `data/printer_v1.sqlite3` |
| Required DB SHA-256 | `36cf157b74a28fe93695f7c29ffee143a3d7ed6453bdcec5ad74ea666284fa09` - exact |
| Live/source authorization | none |
| Mutation authorization | the three lane documents only |

No Python, configuration, schema, migration, cursor, recovery bound, source
budget, database, or active pointer is changed by this lane.

## 2. Authorities read

The audit used the active source stack named by `AGENTS.md`, including the Clean
Master Spec, Post-RC Build Order, Memory Factory Guide, post-Lane-10 architecture
and build order, V2 memory-growth build order and audits, V2-9 closeout, active
assistant anchor, and Python Builder Guide.

The closest evidence records were:

- the cursor-continuity recovery audit, design, and closeout;
- the end-to-end candidate-admission audit, design, and closeout;
- the post-cursor-repair live N2 closeout;
- the candidate-acquisition foundation combined audit, complete design,
  implementation closeout, and post-foundation integration design;
- the pinned direct Pump creation and bonding-curve contracts;
- the pinned Pump `migrate` and PumpSwap Pool contract material;
- the Solana core RPC and transaction-instruction parsing references; and
- the Source Governor evidence rules.

The exact Pump/PumpSwap authority remains the official Pump repository at commit
`9c82f61cb711b044a17f770ab8ce9f9bdf78f333` with:

| Artifact | SHA-256 |
| --- | --- |
| `idl/pump.json` | `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49` |
| `idl/pump_amm.json` | `6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56` |

Pinned identities used by this audit are:

- Pump program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`;
- PumpSwap program `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`;
- Pump `migrate` discriminator `9beae792ec9ea21e`;
- PumpSwap Pool discriminator `f19a6d0411b16dbc`;
- legacy and version-0 transactions only;
- finalized successful transactions only;
- canonical Pump migration Pool index `0`; and
- legacy SPL base mint with wrapped-SOL quote under the adopted migration pin.

## 3. Mandatory source-grounded blocker investigation

```text
BLOCKER CLASSIFICATION: DESIGN_GAP
EVIDENCE: The current integration declares the Pump Program address migration
  namespace as required. A GAPPED, UNKNOWN, or BLOCKED_CONTRACT result enters
  required_failures and stops the whole acquisition before foundation. The
  PumpSwap/current-pool batch also carries that global cursor range. The closed
  recovery lane inspected 11,000 Pump-program signatures across 44 migration
  pages, moved only 40 slots from the frozen tip, did not encounter the prior
  boundary, and added about 47 MB of immutable page evidence.
OFFICIAL-SOURCE COMPARISON: getSignaturesForAddress is an address-scoped,
  newest-first locator; before pages older and public history can be pruned.
  The pinned migrate instruction places the candidate mint at account 2, the
  bonding curve at account 3, and the PumpSwap Pool at account 9. Each exact
  candidate address can therefore locate candidate-referencing transactions,
  after which finalized getTransaction decoding supplies proof. A bounded or
  empty address history never proves nonexistence.
PRINTER-CONTRACT COMPARISON: Multi-source nomination and the superseding
  foundation clarification allow non-Pump and UNKNOWN_ORIGIN candidates through
  exact-present-pool admission. Exact Pump migration plus exact PumpSwap proof
  is mandatory only for a Pump graduation claim. PumpSwap presence alone does
  not prove graduation. Global observation may supply coverage or discovery but
  cannot substitute for candidate-specific proof.
ROOT CAUSE: Program-wide Pump migration continuity, candidate-specific Pump
  graduation verification, and unrelated exact-present-pool admission are
  coupled through one required cursor state even though they prove different
  facts.
CODE CHANGE JUSTIFIED: NO in this documentation/design lane. A later explicit
  implementation lane is justified only after this design PASS and must remain
  inside its minimum boundary.
MINIMUM SAFE RESPONSE: Separate the four channels and retire the global Pump
  migration cursor from universal candidate gating without resetting, advancing,
  deleting, or fabricating its history.
FOCUSED PROOF: Offline fixtures for every lineage branch, candidate locator,
  exact migrate/Pool join, optional global gap, restart/pruning/provider failure,
  compact storage, accounting, replay, N2/N7 mechanics, and zero forbidden
  deltas before any live work.
UNTOUCHED SCOPE: Python, configuration, schema, migrations, cursors, recovery
  bounds, source budgets, authoritative DB, campaigns, memory, retrieval, and
  all financial capabilities.
AUTHORIZATION STATUS: Audit and design only; no implementation or live work.
NEXT ROADMAP-COMPLIANT STEP: If this design passes, a separately explicit
  V2-9.8B Pump Migration Observation Decoupling Implementation and Offline Proof
  lane.
```

## 4. Current coupling traced

The current canonical live owner declares two `FORWARD` namespaces:

1. the create-exclusive index address; and
2. the entire Pump Program address for migration discovery.

The migration namespace is not migrate-exclusive. It enumerates transactions
that reference the busy Pump Program and then spends bounded transaction reads
to find exact `migrate` instructions. The program-wide range is marked required.
Any unresolved required range enters the integration's terminal failure list,
even when DexScreener or GeckoTerminal already nominated an unrelated candidate
whose exact current pool could be verified without a Pump claim.

The current pool-account batch also carries the migration cursor range. That
makes a global coverage property appear to be a prerequisite of generic pool
evidence. It is not an evidence relationship: the cursor says what portion of
program-wide activity was observed, while the pool account says what exact
current account exists for one candidate.

## 5. Source-grounded facts

### 5.1 What candidate nomination proves

DexScreener and GeckoTerminal may directly nominate exact Solana mints and
contribute their supported pair, orientation, market, liquidity, activity,
pair-age, and freshness facts. Nomination does not prove Pump origin, migration,
canonical PumpSwap identity, safety, or admission.

Direct Pump creation or optional migration observation may also nominate. A
nomination channel never creates selection preference, quota, score, rank,
confidence, or weight.

### 5.2 What candidate-specific migration verification can prove

The pinned 25-account `migrate` instruction contains:

- expected mint at account 2;
- expected Pump bonding curve at account 3;
- exact PumpSwap program at account 8;
- exact PumpSwap Pool at account 9;
- Pump pool-authority creator at account 10;
- wrapped SOL at account 14;
- exact fixed programs at the other adopted positions; and
- exact Pool/vault/LP relationships that can be joined to the pinned PumpSwap
  account.

Therefore a known exact signature, mint, bonding curve, or PumpSwap pool can be
used as a bounded locator:

1. a known signature goes directly to finalized `getTransaction`;
2. a known pool uses bounded finalized `getSignaturesForAddress(pool)`;
3. a verified bonding curve uses bounded finalized
   `getSignaturesForAddress(bonding_curve)`; or
4. a candidate mint uses bounded finalized `getSignaturesForAddress(mint)`.

The returned signatures remain locators. Only an exact finalized transaction
decode and exact PumpSwap Pool verification establish the claim. A bounded scan
that finds no match is incomplete/unknown, not proof that migration never
happened.

### 5.3 What the PumpSwap Pool proves

An exact PumpSwap-owned Pool with the pinned discriminator, layout, base mint,
quote mint, PDA, index, creator, LP mint, and vault relationships proves exact
current Pool state. It does not alone prove that Pump `migrate` created or
referenced the Pool. A Pump graduation claim requires the same pool identity at
`migrate` account 9 and in the independently read Pool account.

### 5.4 What global observation proves

A contiguous global observer range can state that its declared, bounded
program-address range was completely reconciled under one pin and decoder. An
individual decoded exact migration inside a gapped range can remain a valid
positive fact. Global observation does not prove every candidate's lineage and
does not replace the exact candidate join.

A global gap proves only incomplete coverage. It cannot block a candidate with
no Pump graduation claim and cannot be translated into `not Pump`, `not
migrated`, or market shortage.

## 6. Existing global cursor and historical gap

The closed recovery lane froze these exact categorical facts:

| Field | Existing evidence |
| --- | --- |
| authoritative migration head slot | `435985595` |
| frozen recovery tip slot | `435999023` |
| last committed recovery continuation slot | `435998983` |
| inspected signatures | `11,000` across `44` pages |
| exact prior boundary encountered | no |
| terminal category | `CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED` |
| authoritative head advanced | no |

That state remains `GAPPED` and historically unresolved. The authoritative
head, frozen tip, continuation, immutable work rows, and hashes must remain
unchanged. Decoupling changes how future admission interprets this state; it
does not reset, erase, compact, advance, or silently adopt any checkpoint.

## 7. Narrower global-locator feasibility

No currently pinned migrate-exclusive global HTTP index is established.

- The Pump Program address is exact but too broad: it includes high-volume
  non-migration program activity.
- The PumpSwap Program address is also program-wide and includes Pool/swapping
  activity; the source stack does not prove it is a migration-exclusive or
  materially bounded index.
- The pinned contract does not adopt a fixed withdraw-authority,
  event-authority, or other address as a unique migrate-only index.
- A guessed account offset, guessed PDA, third-party label, log string, or
  provider category is prohibited.

Candidate mint, bonding-curve, and pool indexing is viable but is
candidate-specific, not a narrower global observer.

A bounded `logsSubscribe` session mentioning the Pump Program is viable only as
a lossy live locator after a later explicit contract/implementation lane. It has
no replay guarantee and cannot establish finality or continuity. Every located
signature must be re-read over approved finalized HTTP RPC and pass the exact
candidate migration and Pool join. Disconnect, lag, malformed logs, or missing
notifications affect optional coverage only.

Conclusion: no narrower global historical locator is adopted by this audit.
Future research may establish one, but this design does not depend on it.

## 8. Branch findings

| Candidate branch | Exact Pump migration required? | Global migration continuity required? | Maximum allowed lineage |
| --- | --- | --- | --- |
| explicit Pump graduation claim | yes | no | `PUMP_GRADUATION_CONFIRMED` only after exact join |
| exact Pump origin plus completed bonding curve/current PumpSwap graduation claim | yes | no | same exact graduation branch; no fallback |
| exact active Pump bonding curve with `complete=false` | no | no | `PUMP_ORIGIN_CONFIRMED` |
| optional global observer migration nomination | yes, using the nominated signature as locator | no | exact graduation only after candidate verification |
| exact PumpSwap Pool present but no Pump claim | no | no | `UNKNOWN_ORIGIN`; never graduation from presence alone |
| exact generic current pool with independently known non-Pump origin | no | no | `NON_PUMP_POOL_CONFIRMED` |
| exact generic current pool with unknown origin | no | no | `UNKNOWN_ORIGIN` |
| conflicting/failed Pump claim | required claim fails closed | no | cannot downgrade to generic/unknown to evade failure |

## 9. Confirmed findings

1. Program-wide Pump migration continuity is currently a universal required
   source gate even though the active source stack allows unrelated exact-present
   pool branches.
2. The current global migration namespace is extraordinarily dense and is not
   a migrate-exclusive index.
3. The unresolved 11,000-signature gap is valid historical coverage evidence
   but not candidate-lineage evidence.
4. The pinned migrate account layout makes exact candidate mint, bonding curve,
   and PumpSwap Pool viable bounded locator addresses.
5. A direct exact migration signature is the narrowest locator, but it remains
   non-authoritative until finalized HTTP verification.
6. Exact Pump `migrate` and exact PumpSwap Pool evidence must join on the same
   mint and pool and pass all pinned canonical relationships.
7. PumpSwap presence alone cannot establish graduation.
8. Generic/non-Pump admission can be exact and fail-closed without global Pump
   migration continuity.
9. A lossy live log stream can add discovery/coverage only; it cannot establish
   finality, completeness, or candidate graduation by itself.
10. Compact page summaries plus hashes and positive decoded facts are sufficient
    because a negative bounded scan is never promoted into evidence of absence.

## 10. Rejected findings

- reset or advance the existing global cursor to the current tip;
- treat the last recovery continuation as a new authoritative checkpoint;
- increase the recovery or ordinary page bounds;
- require global continuity for every nomination or exact-present pool;
- infer a Pump migration from PumpSwap ownership, venue label, pool address, or
  program presence alone;
- infer non-Pump origin from a failed or incomplete Pump search;
- use a candidate-specific positive proof as a claim of global completeness;
- retire global discovery entirely on the assumption that aggregators or
  candidate lookups will find every migration;
- adopt PumpSwap-program history as a migration-exclusive index without a
  source-grounded contract;
- use logs as finalized or complete evidence;
- persist another unbounded program-wide raw-signature ledger; or
- add scores, ranks, confidence, weights, quotas, or source preference.

## 11. Audit conclusion

The architecture has a real `DESIGN_GAP`: one global coverage cursor currently
controls branches that do not depend on its evidence. The pinned contracts are
sufficient to resolve the design without a new provider or guessed identity.

The safe resolution is to keep global observation as optional coverage and
diagnostic/audit evidence, retire it from active universal candidate gating,
and add a candidate-specific exact migration proof channel for only the branches
that claim Pump graduation. Candidate-specific verification complements rather
than replaces optional global discovery.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

1. Candidate-address history can still be pruned, unavailable, or longer than a
   bounded lookup. The required Pump claim must then fail unknown/incomplete.
2. A known Pool or mint may participate in many transactions; candidate-specific
   indexing is narrower, not guaranteed cheap or complete.
3. The current pinned migration layout supports legacy SPL/WSOL graduation only;
   Token-2022 or another quote/layout remains unsupported.
4. Optional global observation loses completeness value while its historical gap
   stays open; reporting must make that limitation visible.
5. A future logs locator can miss events during disconnect or lag and therefore
   cannot be a correctness dependency.
6. Existing recovery evidence has a large immutable footprint. This lane cannot
   delete or compact it; future storage policy prevents repetition only.
7. Candidate-specific source work consumes real Scheduler/Governor capacity and
   must be frozen inside existing or separately approved budgets before code.
