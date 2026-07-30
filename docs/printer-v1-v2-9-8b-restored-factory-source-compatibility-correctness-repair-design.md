# Printer V1 V2-9.8B Restored Factory Source Compatibility Correctness Repair Design

Date: 2026-07-30

Lane: `V2-9.8B Restored Factory Source Compatibility Correctness Repair`

Status: `BLOCKED_AT_PREIMPLEMENTATION_OPERATION_BUDGET_GATE`

## Work gate

- Baseline branch / HEAD: `master` /
  `da9ad61a0be696e1ddae7e19c83649360d49f832`
- Direct parent: `e54ce92aef59d0c9edd2266f69e3572d4b084c97`
- Authoritative database: `data/printer_v1.sqlite3`
- Required database SHA-256:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Active lane: one cohesive correction of the five operator-review
  discrepancies.
- Allowed if the preimplementation gate passes: exact design, implementation,
  frozen offline proof on disposable migration-049 databases, closeout, and one
  PASS commit.
- Forbidden: provider, RPC, WebSocket, live probe, Memory Factory, N2, N7,
  recovery, tracking, snapshot, window or memory execution against the
  authoritative database; retrieval or financial capability activation.
- Required stop rule: if the legitimate worst-case active path does not fit the
  unchanged operation ceilings, return BLOCKED with exact arithmetic. Do not
  raise a ceiling merely to obtain PASS.

No provider request or live authorization was consumed during this
investigation.

## Mandatory source-grounded blocker investigation

```text
BLOCKER CLASSIFICATION:
DESIGN_GAP

EVIDENCE:
The five operator-review discrepancies are reproducible committed defects, but
the cohesive repair cannot proceed under the lane's unchanged-ceiling rule.
Exact measured accounting exposes a legitimate current active-path worst case
above the operation ceiling before implementation can safely authorize the
path.

OFFICIAL-SOURCE COMPARISON:
Solana's official transaction constants cap transaction account indices at 256.
The official getMultipleAccounts contract permits at most 100 addresses per
request. Therefore a supported v0 transaction can require three actual account
batches. The pinned Pump IDL defines the exact 25-role migrate account order.

PRINTER-CONTRACT COMPARISON:
The active direct locator permits one signature page, twelve finalized
transaction reads and five PumpSwap verifications. PumpSwap verification reads
one transaction and batches all transaction account keys in groups of 100.
Printer's admission ceiling remains 45, its zero-transport validation charge
remains 9, and its readiness snapshot reservations remain 2 + 4 = 6.

ROOT CAUSE:
The reset charged governed request count as though it were transport-operation
count. It therefore adopted source breadth whose real predeclared worst case is
larger than the unchanged admission budget.

CODE CHANGE JUSTIFIED:
NO for this lane under the supplied constraints. The individual defects justify
future correction, but a partial implementation is prohibited and the complete
current source plan cannot pass the mandatory unchanged-ceiling gate.

MINIMUM SAFE RESPONSE:
Stop before Python or active-authority documentation changes, preserve all
ceilings and locks, record this design blocker and close the lane BLOCKED.

FOCUSED PROOF:
Static owner/call-path inspection, official contract comparison, exact integer
budget arithmetic, clean-tree checks, and immutable authoritative-database
checks only.

UNTOUCHED SCOPE:
All runtime Python, tests, active source-stack documents, schema, migrations,
authoritative database, provider state, candidate acquisition, cursors,
recovery, tracking, lifecycle, memory, retrieval and financial capabilities.

AUTHORIZATION STATUS:
The correctness-repair implementation was conditionally authorized, but the
lane's own preimplementation budget stop condition fired. No implementation,
proof run or PASS commit is authorized.

NEXT ROADMAP-COMPLIANT STEP:
Operator review of the exact budget/design blocker only.
```

## Confirmed five-discrepancy repair model

The source-grounded design confirms that a future complete correction would
need all five changes together. They must not be applied partially while this
lane is blocked.

### 1. Exact measured transport-operation accounting

The canonical future model is:

```text
predeclared worst-case identities
-> one record for every attempted HTTP/RPC call
-> exact actual identity reconciliation
-> durable source evidence
-> campaign ledger
-> terminal report
-> zero-source replay
```

An operation identity must include:

- source name;
- governed source-request identity;
- method or endpoint kind;
- within-request ordinal;
- target category.

Only a real transport call counts. Parsing, decoding, validation and
normalization count as zero. Failure retains the attempted operation identity,
bytes, rows and categorical cause. Missing, duplicate, undeclared or
over-ceiling identities must stop before candidate persistence or lifecycle
continuation.

The current code does not implement this model:

- direct migration discovery hardcodes two operations per PumpSwap verification;
- eligible supply and the campaign ledger consume source-request totals;
- PumpSwap verification may perform one, two or three account batches;
- DexScreener fresh profiles performs two HTTP calls inside one governed
  request.

### 2. Complete Pump migrate account-role contract

The pinned Pump IDL at
`9c82f61cb711b044a17f770ab8ce9f9bdf78f333` defines these ordered roles:

| Position | Official role |
|---:|---|
| 0 | `global` |
| 1 | `withdraw_authority` |
| 2 | `mint` |
| 3 | `bonding_curve` |
| 4 | `associated_bonding_curve` |
| 5 | `user` |
| 6 | `system_program` |
| 7 | `token_program` |
| 8 | `pump_amm` |
| 9 | `pool` |
| 10 | `pool_authority` |
| 11 | `pool_authority_mint_account` |
| 12 | `pool_authority_wsol_account` |
| 13 | `amm_global_config` |
| 14 | `wsol_mint` |
| 15 | `lp_mint` |
| 16 | `user_pool_token_account` |
| 17 | `pool_base_token_account` |
| 18 | `pool_quote_token_account` |
| 19 | `token_2022_program` |
| 20 | `associated_token_program` |
| 21 | `pump_amm_event_authority` |
| 22 | `event_authority` |
| 23 | `program` |
| 24 | `rent` |

A future implementation must validate every fixed program/sysvar address, every
documented Pump/PumpSwap/ATA PDA, the `withdraw_authority` relation to the
decoded Global account, mint/pool/vault/LP relationships, and the documented
signer/writable contract. Candidate-specific roles cannot be treated as global
constants. Undocumented aliasing or role substitution must fail closed.

The current implementation validates the account count and only selected fixed
and relationship positions. It does not establish the complete role contract.

### 3. One Solana endpoint owner

The shared owner must resolve `PRINTER_SOLANA_RPC_URL` once and inject the same
immutable resolved object into:

- direct Pump signature and transaction transport;
- Pump/PumpSwap transaction/account verification;
- ordinary holder evidence;
- active token/account verification;
- readiness preflight.

The current holder composition can still construct its transport from the
module-level fallback rather than the resolved runtime object. A future repair
must remove independent environment reads and static fallback selection from
active adapters while preserving redacted diagnostics and conditional Helius
backup only.

### 4. Typed prohibited-capability enforcement

Every shared source profile must explicitly carry:

- wallet required;
- private key required;
- signing required;
- funding required;
- paid dependency;
- metered account/trade stream;
- transaction submission;
- execution endpoint;
- credential requirement;
- permitted credential category.

The current schema has only combined wallet/private-key and paid-dependency
booleans. Its recursive protection is incomplete because the text scan covers
only authentication, endpoints and required environment. A future repair must
validate typed fields and recursively scan every serialized active profile
field.

### 5. Active documentation alignment

The current assistant anchor and Clean Master Spec still describe PumpPortal as
the active restored locator and direct Pump/PumpSwap as deferred for ordinary
operation. A future cohesive implementation must update current-authority
sections to state:

- direct bounded Pump/PumpSwap verification is the ordinary restored locator;
- PumpPortal is deferred and has no ordinary runtime authority;
- the locator is one-page, stateless and explicitly incomplete;
- insufficient eligible supply safe-stops;
- no cursor, recovery or backfill is active.

Historical closeouts and clearly historical candidate-acquisition material must
remain historical.

### Baseline-test debt

The legacy Solana-host expectation directly intersects the reset and must be
updated only as part of a future cohesive implementation. The holder-report
wording and GoPlus forbidden-term failures remain unrelated baseline debt:
their producer blobs are unchanged from the parent and they must not be repaired
in this lane.

## Mandatory unchanged-ceiling feasibility gate

### Adopted constants

| Item | Bound |
|---|---:|
| Admission operation ceiling | 45 |
| Zero-transport validation charge | 9 |
| Snapshot reservations | 2 + 4 = 6 |
| Direct Pump signature pages | 1 |
| Direct Pump transaction lookups | at most 12 |
| PumpSwap candidates verified | at most 5 |
| Transaction account-key ceiling | 256 |
| `getMultipleAccounts` batch size | at most 100 |
| Account batches per verification | `ceil(256 / 100) = 3` |

### Direct Pump/PumpSwap plan alone

```text
signature page                                      1
finalized migration transaction lookups            12
five PumpSwap verifications:
  getTransaction                         5 * 1 =    5
  getMultipleAccounts batches            5 * 3 =   15
                                                    --
direct Pump/PumpSwap transport total                33

zero-transport validation charge                     9
snapshot reservations                                6
                                                    --
subtotal before DexScreener or holder work           48
admission ceiling                                    45
minimum overage                                       3
```

This minimum direct-plan overage is sufficient to block implementation.

### Complete current active source plan

The current request-count supply budget can additionally authorize:

- two real DexScreener fresh-profile HTTP calls inside one governed request;
- up to eleven exact-pair HTTP calls after the locator/discovery request-count
  assumptions consume nineteen of the thirty-unit discovery budget;
- up to ten holder transport operations for the required two candidates.

```text
direct Pump/PumpSwap transport total                33
DexScreener fresh-profile operations                 2
exact-pair operations                                11
zero-transport validations                            9
snapshot reservations                                 6
two-candidate holder worst case                      10
                                                    --
complete legitimate worst case                       71
admission ceiling                                    45
overage                                              26
```

The authoritative database currently contains enough historical graduated
inventory for the multi-round exact-pair path to be legitimate; the calculation
does not depend on inventing candidates.

Changing the 45 ceiling is explicitly prohibited. Silently shrinking source
coverage, candidate verification depth or evidence evaluation to manufacture a
PASS would be an unapproved behavioral redesign, not this correctness repair.

## Design verdict

`V2_9_8B_RESTORED_FACTORY_SOURCE_COMPATIBILITY_CORRECTNESS_REPAIR_BLOCKED`

No Python, test, active-authority documentation, migration or database change
is permitted after this gate. The frozen offline proof cannot truthfully begin
because its required predeclared active plan fails before transport.

## Functionality Risks / Setbacks / Efficiency Blockers

- Request-count budgeting understates real transport cost and can admit work
  that the campaign ledger cannot lawfully complete.
- The stateless one-page locator may need a narrower explicitly approved source
  plan or a different reserved-budget design; neither is authorized here.
- Public Solana account batching is variable, so assuming one batch is not a
  safe budget contract.
- Partial repair would leave operator preflight and reports internally
  contradictory and is prohibited.
- Until a later operator-approved design resolves the arithmetic, no bounded
  live source-contract probe or Memory Factory campaign is authorized.

