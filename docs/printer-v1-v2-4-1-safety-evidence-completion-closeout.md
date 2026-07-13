# Printer V1 V2-4.1 Safety Evidence Completion Closeout

Status: `BLOCKED`

Verdict: `V2_4_1_SAFETY_EVIDENCE_COMPLETION_BLOCKED`

This closeout audits holder concentration, exact-pool LP lock/burn state, and
provider-known risk flags only. It does not change Lane Q policy, start V2-5,
or unlock memory, retrieval, decisions, or financial activity.

## Scope And Sources Inspected

The audit used the active Printer source stack and inspected:

* `src/printer_v1/sources/goplus.py`;
* `src/printer_v1/safety/goplus_normalizer.py`;
* `src/printer_v1/sources/solana_rpc_holder.py`;
* `src/printer_v1/evidence_fill/real.py`;
* `src/printer_v1/operator_cli/one_command_15m_factory.py`;
* `src/printer_v1/safety/evidence.py`;
* `src/printer_v1/context_evidence/window_15m.py`;
* `migrations/001_database_foundation.sql` and
  `migrations/022_solana_safety_evidence.sql`;
* focused safety tests in `tests/test_post_rc_real_evidence_collection.py`;
* the isolated final-context proof DB, opened read-only.

No source call or persistent DB write was performed.

## Field Audit

| Field | Existing governed evidence | Current handoff | Finding |
| --- | --- | --- | --- |
| Holder concentration | Solana RPC `getTokenLargestAccounts` plus `getTokenSupply`; some GoPlus responses also contain `holders`, balances, percentages, and total supply | The controlled real-evidence path can merge the governed RPC result. The one-command path does not invoke that fallback. The GoPlus evidence normalizer reads `top_10_holders`, not the live `holders` shape. | Genuine evidence exists. A parser and one-command wiring gap remains. Unknown, stale, failed, mismatched, and rate-limited results already fail closed. |
| LP lock/burn | GoPlus may expose token-level `dex`, `burn_percent`, `lp_holders`, or fixture-oriented explicit `lp_info.locked` / `lp_lock` fields | The current normalizer accepts only explicit lock booleans. The live proof response did not provide an adopted exact-pool lock contract, and its `dex` pool IDs did not reliably identify the selected pair. | Not reliably establishable for the exact target with the current approved, locally contracted path. `UNKNOWN` is correct. |
| Provider-known risk flags | The normalizer preserves and maps explicit `risky_flags`, `risk_flags`, or `risks` fields | The live proof responses contained none of those fields. Absence remains `KNOWN_RISK_FLAGS_UNKNOWN`; explicit empty and non-empty lists already map to no-known-risk and risk-present respectively. | No dropped live flag was found. Other authority and token-program fields must not be relabeled as a generic provider risk list. |

## Read-Only Proof Evidence

The final-context proof DB was inspected using SQLite URI `mode=ro`. Its two
latest GoPlus responses retained the provider payload in
`normalized_payload_json` with exact requested mint provenance.

One response contained `holders`, `holder_count`, `total_supply`, a `dex`
array, and `lp_holders`. The holder balances can support a categorical top-ten
share calculation. The current evidence normalizer drops that live `holders`
shape because it only recognizes `top_10_holders`.

The same response did not prove lock or burn for the exact selected pair. The
provider's `dex` entries used different pool IDs, included concentrated pool
types, and exposed nullable or zero `burn_percent` values without an adopted
local semantic contract. Treating zero as unlocked, or a nonzero value as
locked/burned, would be unsupported pool-specific inference. The other live
response contained no holder or pool data.

The source response table stores the full normalized provider object and its
response hash, while the safety evidence row stores categorical labels and
request/response/failure IDs. This preserves the available governed evidence
and trace without pretending missing semantics are known.

## Existing Fail-Closed Controls

The audit confirmed:

* exact GoPlus requested-mint mismatch fails before evidence insertion;
* RPC holder mint mismatch is rejected;
* RPC rate limits, transport failure, stale data, missing supply, and missing
  largest-account data leave concentration unknown and cannot create clean
  evidence;
* explicit unlocked LP evidence and explicit provider risk flags prevent
  `SAFETY_CLEAN`;
* missing LP or risk evidence remains unknown;
* evidence insertion is target-bound by token, pair, snapshot, and governed
  request/response trace;
* no evidence collection helper unlocks retrieval or financial tables.

The shared 15m resolver and the legacy Lane Q classifier were inspected only.
Their safety policy was not changed in this lane.

## Why Implementation Stopped

The task explicitly requires a stop when LP state or holder evidence cannot be
established reliably from existing approved paths. Holder evidence is
recoverable, but exact-pool LP lock/burn is not currently supported by an
adopted provider contract or a validated pool-specific parser. Implementing
only the holder fix would leave the requested safety bundle incomplete, while
guessing LP semantics would weaken safety. Therefore no parser, persistence,
source-budget, or one-command code was changed.

## Verification

A focused unittest command covered GoPlus normalization, the Solana RPC holder
fallback, conservative LP handling, known-risk flags, effective safety merge,
and failure reporting. It printed passing results through the holder suite,
including exact-mint mismatch, HTTP 429, stale/missing data, redaction, and
zero-downstream-unlock cases. The Windows/Python 3.14 process then ended during
the holder suite without a final unittest summary or reliable exit code and
without printing an assertion failure. The command was not repeatedly retried
or weakened.

Static inspection and the read-only proof-DB audit passed. No test, source,
migration, or database file was changed.

## Preserved Locks

This audit created no source requests, scheduler jobs, snapshots, memories,
retrieval rows, paper decisions, BUY/SELL/HOLD actions, positions, trades,
audits, or PnL. It added no provider, paid dependency, wallet, key, execution,
score, rank, confidence, or weighted logic. Unknown evidence remains unknown,
and known dangerous evidence remains blocking.

## Remaining Blocker And Next Step

The blocker is an exact-pool LP lock/burn evidence contract. Before any safety
policy reconciliation, an operator-approved V2-4.1 design lane must choose one
of these fail-closed paths:

* adopt and pin authoritative semantics for an already approved provider's
  exact pool identifier and lock/burn fields; or
* approve a pool-program-specific read-only parser that validates the selected
  pair structure and ownership on Solana.

That design must define supported pool types, exact pair attribution, burn and
lock proof conditions, unsupported cases, freshness, and Source Governor
recording. It may then include the already proven holder parser/fallback wiring
and direct provider-risk preservation. Until that contract exists, safety
evidence completion is blocked and V2-5 remains unavailable.
