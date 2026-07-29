# Printer V1 V2-9.8B Foundation Mint-Identity and Chain-Mint Admission Audit

Date: 2026-07-29

Starting HEAD: `20c1f1bd3d9b334cd7c5a9dc767031ae63a050e1`

Lane: `V2-9.8B Foundation Mint-Identity and Chain-Mint Admission Audit and Repair`

Gate: independent audit before code change

## Baseline and boundaries

- tracked and untracked worktree: clean;
- authoritative DB: `data/printer_v1.sqlite3`;
- starting authoritative DB SHA-256:
  `08fb9d202bf60f258779041e85d79a5c65e789ea1bddb67745b218df588ba1db`;
- latest migration: `049_candidate_acquisition_integration.sql`;
- execution inspected read-only: `20260729T150849Z-acq-9de864deec62`;
- host-only artifacts inspected under the closeout-recorded path;
- no provider, RPC, N2, N7, campaign, tracking, lifecycle, snapshot, window,
  memory, retrieval, decision, position, trade, audit, or PnL path was run.

The authoritative DB was opened read-only. No raw provider payload, RPC URL,
secret, or mint address is reproduced here.

## Source-grounded blocker classification

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
EVIDENCE: all four cohort identities reached one completed
  candidate_mint_account_batch; their exact redacted identity hashes reconcile
  across market, mint, pool, holder, safety, candidate, and certificate rows;
  all four returned owners are the adopted Token-2022 program; all four were
  reduced to mint_status=FAIL; the live owner calls the adopted Token-2022
  decoder only when raw length is exactly 166; the decoder and pinned contract
  accept structurally valid Token-2022 mints of length at least 166 with TLV.
OFFICIAL-SOURCE COMPARISON: Solana getMultipleAccounts associates response value
  slots positionally with requested addresses; null is missing account evidence.
  SPL Token requires an initialized 82-byte mint. The pinned Token-2022 contract
  requires the adopted 166-byte base/account-type boundary plus a valid TLV walk,
  not exact total length 166.
PRINTER-CONTRACT COMPARISON: transport completion is not mint admission; exact
  mint, token-program owner, account layout, and exact candidate merge must all
  pass categorically. Infrastructure mints are not memecoin candidates.
ROOT CAUSE: the canonical live mint batch rejected every extended Token-2022
  mint before invoking its already-correct decoder because of an exact-length
  precondition. The public-path offline fixture generated only legacy 82-byte
  SPL mints. Positional association was used but not retained as auditable
  target/slot evidence, and mint failures were collapsed to generic FAIL.
CODE CHANGE JUSTIFIED: YES
MINIMUM SAFE RESPONSE: repair the existing live mint-batch decoder boundary,
  retain exact request-target/response-slot evidence, add precise categorical
  failures and exact merge guards, and extend frozen public-path fixtures.
FOCUSED PROOF: valid SPL, adopted Token-2022, mixed cohorts, null/missing,
  owner/program/layout/target/merge negatives, then public N2/N7 frozen transport.
UNTOUCHED SCOPE: migration/schema, authoritative DB, provider contracts, source
  budgets, runtime capacity, operational campaign and all memory/financial paths.
AUTHORIZATION STATUS: this operator-authorized audit/design/repair/offline-proof
  lane only; no live re-proof is authorized.
NEXT ROADMAP-COMPLIANT STEP: after PASS, only a separately explicit N2-first
  bounded live candidate-acquisition proof.
```

## Persisted execution reconstruction

The repaired cohort boundary worked exactly as previously closed out: 39 raw
unique nominations thinned to four, all four received cohort enrichment, the
mint batch completed once, and there were zero source-failure rows. One
`getMultipleAccounts` transport operation returned four value slots.

Redacted identity-hash joins establish:

- the four mint-batch top-level identities equal the four cohort/candidate
  identities;
- each has corresponding market, pool, holder, and safety enrichment;
- every returned mint-account owner hashes to the adopted Token-2022 program;
- no returned owner matches the legacy SPL Token program in this cohort;
- no pair/pool/infrastructure account entered these four live mint slots;
- every candidate failed `CHAIN_MINT_VALID` with generic
  `MINT_STATUS_FAILED`;
- every identity was separately incomplete because its exact quote-mint fact
  was absent from the present-pool evidence;
- `_failure_family` preferred that incomplete identity state, producing
  `IDENTITY_MERGE_FAILURE / IDENTITY_NOT_MERGED` and masking the earlier
  chain-mint decoder rejection in the terminal family.

The persisted normalized response intentionally does not retain raw account
bytes. The response byte count (3,012 bytes for four Token-2022 accounts), the
all-Token-2022 owner result, the exact-length code gate, and the absence of any
other route to `mint_status=FAIL` on a supported owner establish the committed
contract mismatch. The repair does not make a claim about any real address; it
proves the same shape with sanitized extended Token-2022 fixtures.

## Preliminary finding dispositions

1. **Rejected as stated; refined reporting gap.** RPC transport completion was
   recorded as `COMPLETE`, but foundation admission did not treat that alone as
   usable mint evidence: all four certificates were rejected. The defect is the
   decoder precondition and generic taxonomy, not transport success directly
   passing the gate.
2. **Rejected for the blocked execution.** Redacted hash joins show the four
   cohort identities exactly match the four requested/normalized mint-batch
   identities.
3. **Confirmed as an auditability and fixture gap, not the observed live root.**
   The code used positional `zip`, consistent with the RPC contract, but did not
   retain request target and response slot and could not validate an
   address-decorated reordered fixture.
4. **Rejected for the blocked execution; confirmed as an unguarded boundary.**
   All persisted observations merged on the same top-level mint values. The
   foundation did not independently compare mint evidence's request target to
   the candidate merge key.
5. **Rejected for the blocked execution; refined as a negative-proof gap.** All
   four account owners were Token-2022. Aggregator normalizers exclude known
   infrastructure base mints, but the mint-batch owner lacked final categorical
   role/owner tests for a pair or pool mistakenly supplied as a mint.
6. **Confirmed; dominant committed defect.** The live owner required
   `len(raw) == 166` before calling a decoder whose pinned contract is
   `len(raw) >= 166` plus valid padding, AccountType, and TLV structure.
7. **Confirmed.** Null account, wrong owner, unsupported program, malformed
   data, target mismatch, and merge mismatch all collapsed into generic
   `mint_status=FAIL`, then `MINT_STATUS_FAILED`.
8. **Confirmed and refined.** `IDENTITY_MERGE_FAILURE` represented missing exact
   quote identity, not a mint conflict. Its precedence masked the chain-mint
   decoding rejection; the decoder defect did not itself create a different
   merge key.
9. **Confirmed.** The canonical mock network created only initialized legacy
   82-byte SPL mint accounts. It did not reproduce the all-Token-2022 extended
   batch-to-foundation path from the blocked execution.

## Complete root cause

The primary failure is a narrow code-contract mismatch in the canonical live
mint-batch owner: extended Token-2022 mint accounts were rejected by an
extensionless-only exact-length guard before the adopted decoder could validate
their base state, padding, AccountType, and TLV structure. The nearest public
N2/N7 offline fixture could not catch this because it returned legacy SPL mints
only.

Three secondary observability/safety gaps made diagnosis and classification
weaker: response target/slot association was not durable, all mint negatives
shared one generic reason, and terminal identity precedence could mask a prior
chain-mint rejection. None requires a schema change; the existing observation
facts and report JSON can carry the categorical evidence.

## Audit verdict

The issue is code-justified and repairable inside the current canonical owners
without a migration or capability expansion. Proceed to the complete design.
