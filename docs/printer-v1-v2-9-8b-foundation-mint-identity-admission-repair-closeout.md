# Printer V1 V2-9.8B Foundation Mint-Identity Admission Repair Closeout

Date: 2026-07-29

Starting HEAD: `20c1f1bd3d9b334cd7c5a9dc767031ae63a050e1`

Lane: `V2-9.8B Foundation Mint-Identity and Chain-Mint Admission Audit and Repair`

## Verdict

`V2_9_8B_FOUNDATION_MINT_IDENTITY_ADMISSION_REPAIR_PASS`

The independent audit, complete design, canonical-owner repair, sanitized
live-shaped regression, public-path frozen N2/N7 proofs, precise negative
taxonomy, migration compatibility checks, and broad affected suite pass. The
authoritative DB remains byte-identical and all Printer locks remain intact.

This PASS authorizes only a separately explicit future N2-first bounded live
candidate-acquisition proof. It does not authorize that proof now, N7 live,
retry, campaign, tracking, lifecycle, snapshots, windows, memory, retrieval,
decisions, positions, trades, audits, PnL, or any financial capability.

## Confirmed, refined, and rejected findings

1. **Rejected as stated; refined.** Successful RPC transport was not itself
   accepted as mint evidence: all four certificates failed. The batch could be
   transport-complete while every candidate observation was unusable. The
   defect was decoder gating plus generic taxonomy.
2. **Rejected for the blocked execution.** The four cohort, request, normalized
   observation, and candidate identities reconcile exactly by redacted hashes.
3. **Confirmed as an auditability/fixture gap.** Positional association matched
   the Solana contract, but target and response slot were not retained and an
   address-asserted reordered fixture was not handled.
4. **Rejected for the blocked execution; confirmed as a guard gap.** The live
   observations used the same top-level merge key, but foundation did not
   independently compare the mint evidence request target to that key.
5. **Rejected for the blocked execution; refined as missing negative proof.**
   All four returned owners were Token-2022, not pair/pool/infrastructure
   owners. Final role/owner negatives were absent from the canonical proof.
6. **Confirmed; dominant root defect.** The live owner required exact total
   length 166 before invoking the adopted Token-2022 decoder, contrary to the
   pinned `>=166` plus structural TLV contract.
7. **Confirmed.** Missing/null, wrong owner, unsupported program, malformed
   layout, target mismatch, and merge mismatch collapsed into generic FAIL.
8. **Confirmed and refined.** The terminal identity family represented a
   separate missing exact quote identity and masked the earlier chain-mint
   rejection; no actual mint merge conflict was found.
9. **Confirmed.** The public-path fixture returned legacy 82-byte SPL mints
   only and did not reproduce the blocked all-Token-2022 extended-account path.

## Exact root cause

The canonical live mint-batch owner rejected extended Token-2022 mint accounts
before decoding them. Its exact-length precondition allowed only an
extensionless 166-byte account, while the already-adopted decoder and pinned
contract require a 166-byte minimum followed by structurally valid TLV data.
The frozen public-path fixture generated only legacy SPL mint accounts, so this
contract mismatch was not exercised offline.

Diagnosis was weakened by three secondary gaps: request target/response slot
was not durable evidence, distinct mint negatives shared one reason, and
terminal failure precedence could report identity incompleteness ahead of a
chain-mint decoder rejection.

## What was built

- exact ordered request-target and response-slot association for every mint
  account;
- safe exact-address association for reordered address-decorated frozen
  responses, with no adjacent-slot sliding;
- explicit account presence, owner/program, layout, association, and failure
  facts in the existing observation JSON;
- exact SPL Token validation through the adopted initialized 82-byte layout;
- exact Token-2022 validation through the adopted 166-byte minimum, padding,
  AccountType, and structural TLV decoder;
- separate categorical reasons:
  - `MINT_ACCOUNT_MISSING`;
  - `MINT_WRONG_PROGRAM_OWNER`;
  - `MINT_UNSUPPORTED_TOKEN_PROGRAM`;
  - `MINT_ACCOUNT_DATA_MALFORMED`;
  - `INFRASTRUCTURE_MINT_EXCLUDED`;
  - `MINT_TARGET_MISMATCH`;
  - `MINT_EVIDENCE_MERGE_KEY_MISMATCH`;
  - `MINT_EVIDENCE_REASON_CONFLICT`;
- foundation merge guards that require evidence target and optional asserted
  response address to match the exact candidate mint key;
- terminal-family precedence that keeps real merge mismatches separate while
  allowing decoder/presence/owner/program/layout failures to remain admission
  failures with their precise reason;
- mixed SPL/Token-2022 canonical public-path fixtures;
- a sanitized synthetic four-Token-2022 regression derived only from the
  persisted shape of the blocked execution, with no real identities or raw
  provider payloads.

Foundation ownership of certificates, reserve, exact-N manifest, and replay is
unchanged. Scheduler, Source Governor, budgets, active capacity, and stop
boundaries are unchanged.

## Canonical offline proof totals

Both proofs used the normal public `acquisition-only-n2` / `acquisition-only-n7`
dispatch, disposable migration-049 DBs, and frozen one-shot low-level
transports. There was no network access.

| Measure | N2 | N7 |
| --- | ---: | ---: |
| terminal status | `COMPLETED` | `COMPLETED` |
| certificates issued | 2 | 7 |
| certificates admitted | 2 | 7 |
| manifest count | 1 | 1 |
| manifest items | 2 | 7 |
| legacy projection | 2 | 0 |
| Scheduler jobs | 20 | 44 |
| governed requests | 20 | 44 |
| underlying transport operations | 13 | 28 |
| normalized rows | 23 | 62 |
| response bytes | 3,064 | 9,504 |
| active leases after terminal | 0 | 0 |
| active Scheduler residue | 0 | 0 |
| protected-table deltas | all zero | all zero |
| replay | identical; zero-source | identical; zero-source |

The N7 manifest is runtime-neutral. The legacy two-token adapter rejects it
with `LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO`. Active runtime capacity remains
exactly two.

Additional negative proofs establish valid SPL, valid extended Token-2022,
mixed cohorts, missing and null account slots, wrong owner, unsupported program,
malformed data, pair/pool/infrastructure targets, reordered and partially null
responses, exact target/slot association, target mismatch without slot sliding,
and exact merge-key mismatch.

## Tests and checks

- baseline nearest suites before repair: `60 passed`;
- focused canonical/migration proof subset after repair: `9 passed`;
- broad affected closeout suite:
  `208 passed in 26.56s` across foundation, post-foundation integration/public
  CLI, and Solana RPC SPL/Token-2022 decoder regressions;
- Python compilation: PASS for changed owners and directly affected tests;
- `git diff --check`: PASS;
- migration compatibility: fresh disposable DBs applied through exact migration
  049 throughout the proof; canonical latest migration assertion PASS;
- authoritative DB read-only integrity: `ok`;
- authoritative DB foreign-key check: zero rows;
- authoritative active acquisition leases: zero;
- authoritative active/locked Scheduler residue: zero;
- authoritative SQLite sidecars: none;
- authoritative DB final SHA-256:
  `08fb9d202bf60f258779041e85d79a5c65e789ea1bddb67745b218df588ba1db`.

## Files changed

- `src/printer_v1/operator_cli/live_candidate_acquisition_transport.py`
- `src/printer_v1/discovery/candidate_acquisition.py`
- `tests/test_v2_9_8b_candidate_acquisition_post_foundation_integration.py`
- `tests/fixtures/candidate_mint_admission_blocked_stage_a_sanitized_v1.json`
- `docs/printer-v1-v2-9-8b-foundation-mint-identity-admission-audit.md`
- `docs/printer-v1-v2-9-8b-foundation-mint-identity-admission-design.md`
- `docs/printer-v1-v2-9-8b-foundation-mint-identity-admission-repair-closeout.md`

## What was not touched

- no schema or migration file;
- no authoritative DB write;
- no source registry, Source Governor policy, Scheduler policy, cadence, budget,
  selection capacity, or runtime-capacity change;
- no live provider/RPC request or proof;
- no live N2/N7 operational invocation;
- no campaign, tracking, lifecycle, snapshot, window, or memory work;
- no retrieval, paper decision, BUY/SELL/HOLD, position, trade event, paper
  audit, or PnL work;
- no wallet, private key, signing, transaction submission, fund movement, paid
  source, score, rank, confidence, weight, embedding, or vector work.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Standard Solana batch responses are positional and do not carry the account
   address inside each value. Printer now preserves exact target and slot; an
   explicit response-address assertion is available for frozen proof, but live
   correctness still relies on the pinned RPC positional contract.
2. Token-2022 extension bodies are structurally walked but not semantically
   interpreted. This repair proves mint layout, not extension safety. Authority
   safety remains a separate fail-closed gate.
3. The blocked sample also lacked exact quote identity for its present-pool
   evidence. This mint repair does not broaden supported pool programs or claim
   that a future live cohort will pass every later foundation gate.
4. The sanitized regression preserves only the persisted failure shape because
   raw live account payloads were intentionally not retained. It cannot prove
   any historical address's current state.
5. Lexicographic source-neutral cohort thinning, public-source availability,
   freshness, pool identity, holder evidence, safety, liquidity, and
   tradeability may still honestly block a future proof.
6. One future N2 sample cannot establish general live reliability.

## Exact next permitted task

Only a separately operator-authorized, bounded, **N2-first live
candidate-acquisition proof** through the canonical public command is permitted.
It must preserve the current ceilings, stop after N2 unless its explicit future
prompt says otherwise, and re-prove exact target/slot mint evidence, admission,
accounting, replay, cleanup, protected-table isolation, and DB integrity.

No live proof, retry, N7, campaign, tracking, memory, retrieval, or financial
work is authorized by this closeout itself.
