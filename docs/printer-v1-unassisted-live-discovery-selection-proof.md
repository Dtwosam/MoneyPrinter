# Printer V1 Unassisted Live Discovery And Selection Proof

Status: `UNASSISTED_PIPELINE_PASS_COMPOSITION_BLOCKED`

Date: 2026-07-13

Commit under proof: `698d64a Repair and prove Group A quota`

## Setup

Printer's existing `printer-discover-candidates-once` entry function was run
exactly once against a fresh isolated schema-only database:

`data/printer_v1_unassisted_discovery_selection_698d64a.sqlite3`

The stale `.venv` executable could not start because it referenced a removed
Python 3.12 interpreter. No live request occurred from that failed launcher.
The same production CLI entry function was therefore invoked through the active
Python interpreter with:

- operator approval: true;
- chain: `solana`;
- source: `geckoterminal`;
- max candidates: 10;
- max source requests: 2;
- timeout: 5 seconds per transport;
- no fixtures, candidate list, mint list, enrichment, retry, or scheduler run.

Wall time for the one production run was 10.45 seconds.

## Governed Source Requests

| Request | Kind/channel | Requested | Response | Result |
|---|---|---|---|---|
| 1 | `geckoterminal_new_pool_discovery` / `GECKOTERMINAL_NEW_POOL` | 00:11:24.065515Z | response 1 at 00:11:31.708908Z | `COMPLETE / CLEAN_DATA`, 20 candidates |
| 2 | `geckoterminal_trending_pool_reference` / `GECKOTERMINAL_TRENDING_POOL` | 00:11:31.724762Z | response 2 at 00:11:32.183066Z | `COMPLETE / CLEAN_DATA`, 20 candidates |

Source Governor recorded two requests and two responses, with zero failures.
Both planned READY channels were sampled. No direct source call bypassed the
governor.

## Every Candidate

Outcome vocabulary: `ACTIVE` means persisted with tracking/scheduler handoff;
`AUDIT` means retained only in the audit-only pool; `CAP` means rejected after
the ten-candidate persistence cap; `STNP` means rejected before persistence as
unresolved same-token/new-pair evidence.

| # | Channel | Mint / pair | Classification | Bucket | Outcome and reason |
|---:|---|---|---|---|---|
| 1 | new | `47a28a8LJ1jNySg7iifoXockKLWfbEsmy79em21zQTFB` / `K1jxMJCQJtLBSXKT18T5pwbcUfHAVuhcKpGLnHa79ki` | WATCH_ONLY | B3 | AUDIT: not eligible for active 15m tracking |
| 2 | new | `GvRFLmbNif1gs4cAXew1fKWNtGj7fbEiDgEGp7iTpump` / `DdYc7Z1Sv14yM7fTyDdfQ3aY3n32PP7jNzPXTyLZ9sb4` | WATCH_ONLY | C1 | AUDIT: not eligible for active 15m tracking |
| 3 | new | `KJc4GNsZrzqmCjZrDupSgsCFu4FGwJYimMBaSaRpump` / `Fr4bgwdxiAuVhLnUX6DNq75VwByYzyTXWtRdt6A4jynG` | TRACK_NORMAL | C2 | ACTIVE |
| 4 | new | `Gj18fzx4F7nqTGNUhgMKqWFiEayzcXDcPvz1MDAupump` / `8CaWUBAFrMLFFdWoSM3Kjq5fJdc1y9rVKdcqCG2HNqUd` | TRACK_NORMAL | C1 | ACTIVE |
| 5 | new | `7VEwW6vZrRdUSE7Jmv5JDbHNsVGs9p7BBzvkrC6gYV5v` / `DXFAWbBeNp3V8kTZnc1S5T7V94VbUS2F5wv7Enq2EhHC` | TRACK_NORMAL | C1 | ACTIVE |
| 6 | new | `91VE9ZqwdnEG7i8xstRRPzW5s7Qy3SBR68UWxA34pump` / `GUvMxvgpqtUGUCNnsaYqeHbsijtiDWAf78RAQNBEnZau` | TRACK_NORMAL | C2 | ACTIVE |
| 7 | new | `4Vdh2u8tArbbCxH3QuBbHftS7eqhtzkvW1X1HsKsXYut` / `6peEZ9FFFzHVHu832czEHkRce9XPeBSVmSkNJQdC8Z9U` | TRACK_NORMAL | C2 | ACTIVE |
| 8 | new | `Cc4z4gmzjUHLW7md7SszdCggEa63rNrXx9mzN4Ctu59c` / `3YFWU2cJhf8RYtmwXU7SgLQYeCtx3K2nByjZt3VHAg68` | TRACK_FAST | A1 | ACTIVE; final quota view selected |
| 9 | new | `4wknFzJKuFA4SKCir6iRippNSL3csq6PxKyVNVY8pump` / `5XAQaKJh338b3KxWGa93u2gzghY6aJJSaHg8PSBiRkGo` | TRACK_NORMAL | C1 | ACTIVE |
| 10 | new | `CENcjQHKRkGyBaNrCSYgSCy2ZjvNymZDu9HvkNt3pump` / `Hj4YxXUbsLT5gvh5UCyM91EK574ZUYCPrnSCKHrFnjzS` | WATCH_ONLY | B5 | AUDIT |
| 11 | new | `EGbUNh4bz84G3FX8jPyhRu6zRZzaKpRFsjbBAuvjpump` / `6k16prCSpiTxJvQbspLkefdnpKWDwjJDZwAAdW1PKsJn` | TRACK_NORMAL | C1 | ACTIVE |
| 12 | new | `8BS8uDcztRfQVEbDsZEQtV6sTLzxFB7v3LNqUvicpump` / `4FfibrdyUaQtE5UP363p9cda9V89hfBF1N84yVJ9sxm4` | WATCH_ONLY | B5 | AUDIT |
| 13 | new | `7hZwCx9YgfV8PhnfcWGy3XjuwtU77xc9SEjW8NJppump` / `J89Y54tBJ5tNKVpr4BGyg61wth3QUX2bn1eN8kHtMUJS` | TRACK_NORMAL | C1 | ACTIVE |
| 14 | new | `55NSfdh797d8ULGUQUBsbz8cwJZjw6B7L4Cd3drypump` / `5hpsD42oJfXrRqWuaPRebGZJ9pUzS4Rn1Ln4L1mMLnvZ` | WATCH_ONLY | B1 | AUDIT |
| 15 | new | `DzGmnquGBLoV1r9FQ6Uh5d8QpLMaVkA4NY3gjNFMpump` / `4yMfk4nU7qz9aYKEr58kCZEmZbmipsu6xtFHDjt7V58w` | WATCH_ONLY | B1 | AUDIT |
| 16 | new | `HgtiPU5oRnzaFFtSK8caJErvSgaZTdVPmtLyzYuuvfuA` / `Bq4NtQ6SLmpTkUGxUFC2y8eFWWnkzpx5RVRm9mcLqPgy` | TRACK_FAST | A1 | ACTIVE; rejected from final quota view by A1 cap |
| 17 | new | `HgtiPU5oRnzaFFtSK8caJErvSgaZTdVPmtLyzYuuvfuA` / `yBPRZhd8DzyyRrB4Jyptw6Hg8gufkZcmm8QmyAV153M` | WATCH_ONLY | B5 | STNP: duplicate mint, unresolved new pair |
| 18 | new | `8EcTVYuLBS9bXmK1S1mDC7zedHzN8KRAGGscL6frpump` / `C3oVxPYm8rVMHVSYeUzfWdAN1U6waAHAuqD3S52ZNunq` | TRACK_NORMAL | B1 | CAP |
| 19 | new | `GbLAYWQ8ESvh2UjkKo45xYwd7BFq1cpjTwZcuW68pump` / `2asokD1ci7bhnSroWU3tTMWzXBZoSuM3MNJJKhCnQP7E` | TRACK_NORMAL | B1 | CAP |
| 20 | new | `9QYswfqreUmiMLNpTiKwFC4m5PxtthXXAbBUoCEApump` / `3Nn2m5cnUDnNqgoXvXh7cXGsCR3dMqDSHYELNMBAibeY` | TRACK_NORMAL | C2 | CAP |
| 21 | trending | `4ko5tSr5o3H4v1sFtjTSd9MPUW7yx5AFCpkNPoL6pump` / `68nVMrVPyxGJGbGH2P92E93SYhJcbe6QociZrqoqdjcB` | TRACK_FAST | A1 | CAP |
| 22 | trending | `9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump` / `6e7V9eegCHw997T72MxgwwJipZ6GJyZF8NvjkzT1rvpN` | TRACK_FAST | A1 | CAP |
| 23 | trending | `6AVAUKa9uxQpruHZUinFECpXEh1usRVtzQWK8N2wpump` / `B5K3qfft5ALRJBskL7qJPDzbbW76TXLkfKSd1mP4MtgN` | TRACK_FAST | A1 | CAP |
| 24 | trending | `gsoZaYPVioFi9GRaehCnvNqUSNWYNZNVKT9oyoJpump` / `34hC1UWpc1gTnM9W3zvhesimRE1GpQxq9CWWFohB31Rd` | TRACK_FAST | A1 | CAP |
| 25 | trending | `DpqGBmkc6SrY2vA1Yb5KuH571WW1oQJjJdD3d2kupump` / `QRViw782g3LnUd2pL9ug9dbpneY6MdxfvKuQ4uaeAGx` | TRACK_FAST | A1 | CAP |
| 26 | trending | `D4pi5eJNqT5mCzQcxAGfMavgVYLspfYkAQKKvQ8Xpump` / `7p1LD2vWkRCDBXNHWAk3fKDJ7fcAKUbSZmeAuCgivNgQ` | TRACK_NORMAL | B1 | CAP |
| 27 | trending | `9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump` / `FnzKY6x7entQ1eR3D225dQyT7ybfka4PskBMQhb8L3CC` | TRACK_FAST | A1 | STNP: duplicate mint, unresolved new pair |
| 28 | trending | `FrtbBAaSZksfh4oV46E7Pvb43QiiUmYLD3dcGS6gpump` / `Ak9J6xqrsdPXGMQrscv67yrJYbbvhjqu6TWePikc6N6o` | TRACK_FAST | A1 | CAP |
| 29 | trending | `DUYw2p3NC6zDdsSrazV4JdDFKtRk2K4mw764EWs2pump` / `AoXFMDQMaevMEJgKuMTHbptoeoCjW8bDYKniXMhkNDpc` | TRACK_FAST | A1 | CAP |
| 30 | trending | `6NwarBvDkXhByqVp2Qkq5i9XbtA2B3Bwe8SWGu9vpump` / `DPzKoJVewaH1wpchD3gWKeeGm7G2mXkBW48uRniAgbVx` | TRACK_FAST | A1 | CAP |
| 31 | trending | `BCdwQBAn8dYB5YjTsoB6TdHAWokxv28k2oZUodERpump` / `2DVbU5h8JCd37gaXAJUZ4t77HsjJW22LLduTZk7GSa43` | TRACK_FAST | A1 | CAP |
| 32 | trending | `CTdVAK1wZ5wgJiMqm41CGF323QTr1ZwAtnJ3MwKDpump` / `Hxokv1hk53qa1pDmfxb2p4PHukm6nS43foa5EEiTUguz` | TRACK_FAST | A1 | CAP |
| 33 | trending | `h3c8Kyoj4pnpeZCGqtWqyK6z8WbzroYRD1Wi68Jpump` / `Hk3y3mJce15piKW23rC4Xd1BSitJT6PxrgcYV4StDQQd` | TRACK_NORMAL | C1 | CAP |
| 34 | trending | `4YpANZ4urF4DW2QtCMP54kZQkhsisypsstJbasQapump` / `6wLSrSbJQdJqYoxQqujVCg2qLKx4HYC6wb3GAh5o3zEb` | TRACK_NORMAL | C2 | CAP |
| 35 | trending | `Tqj8yFmagrg7oorpQkVGYR52r96RFTamvWfth9bpump` / `F42tZnKPavq1VUcrL6ymhc6YqVpt84fWwgzbNTv2wb3W` | TRACK_FAST | A1 | CAP |
| 36 | trending | `6MJEQQB6wC6wpRrjni15Q7By9DrbdbRFeJU3xqV1pump` / `ak3U4AkfzqqFqTHjsNDbAViCiC8QwzXb9CfkCQeAUx6` | TRACK_FAST | A1 | CAP |
| 37 | trending | `CARDSccUMFKoPRZxt5vt3ksUbxEFEcnZ3H2pd3dKxYjp` / `HnhpJPJgBG2KwniMTNW8cVBHvk1hFog3RC3kjnyc23tD` | TRACK_FAST | A1 | CAP |
| 38 | trending | `5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2` / `4w2cysotX6czaUGmmWg13hDpY4QEMG2CzeKYEQyK9Ama` | TRACK_NORMAL | B1 | CAP |
| 39 | trending | `4MrsXQzaosYNyFd4wKDvgnC5xRtRqgXRrijFTGj9pump` / `8N544CG9j44dkzu4CjSWHxpwekxHQPTR4R17Kw9y5FBk` | TRACK_FAST | A1 | CAP |
| 40 | trending | `BcHEaaTCvycPwwsJ9yQTXdHP9X2gCLkznDbZ8VySpump` / `EDeuGoVFTEUvWZvNGQH6UvSs5uk6RLgKTvr3MgY32ouw` | TRACK_FAST | A1 | CAP |

Totals: 40 seen and normalized; 2 STNP rejections; 6 WATCH_ONLY audit-only
candidates; 10 active candidates persisted; 22 additional valid candidates
rejected by the cap. The command's candidate-stage report records 30 rejected
before persistence, including the audit-only and cap outcomes.

## Final Selection And Quota

The classifier quota view selected ten entries: nine active and one audit-only.

| Mint | Bucket | Mode | Selection reason |
|---|---|---|---|
| `47a28a...QTFB` | B3 | AUDIT_ONLY / WATCH_ONLY | bounded WATCH_ONLY supplement |
| `Cc4z4g...u59c` | A1 | ACTIVE_TRACKING | Group A winner slot |
| `KJc4GN...pump` | C2 | ACTIVE_TRACKING | non-A bounded fill |
| `Gj18fz...pump` | C1 | ACTIVE_TRACKING | non-A bounded fill |
| `7VEwW6...YV5v` | C1 | ACTIVE_TRACKING | non-A bounded fill |
| `91VE9Z...pump` | C2 | ACTIVE_TRACKING | non-A bounded fill |
| `4Vdh2u...XYut` | C2 | ACTIVE_TRACKING | non-A bounded fill |
| `4wknFz...pump` | C1 | ACTIVE_TRACKING | non-A bounded fill |
| `EGbUNh...pump` | C1 | ACTIVE_TRACKING | non-A bounded fill |
| `7hZwCx...pump` | C1 | ACTIVE_TRACKING | non-A bounded fill |

The second active A1 (`HgtiPU...vfuA`) was excluded from the quota view by the
winner cap. The remaining five audit-only candidates were excluded by the
bounded batch cap.

Quota result: **FAIL**.

Violations:

- `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET`;
- `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH`;
- `GROUP_B_SHARE_BELOW_MIN_30_PERCENT`;
- `MISSING_GROUP_B_DECAY_REQUIRED_FOR_6PLUS_BATCH`.

Selected buckets were `{A1: 1, B3: 1, C1: 5, C2: 3}`. No classifier-generated
A2/A3/A4, D1, or B2/B4 appeared in this live sample. The command reported the
failure honestly and did not force quota success.

## Handoffs And Database Deltas

The proof DB began schema-only. Deltas were:

| Table | Delta |
|---|---:|
| source requests / responses / failures | +2 / +2 / 0 |
| tokens / pairs / discovery candidates | +10 / +10 / +10 |
| tracking queue | +10 (8 TRACK_NORMAL, 2 TRACK_FAST) |
| scheduler jobs | +10 pending handoff rows (8 normal, 2 fast) |
| selection batches / items / rotation state | 0 / 0 / 0 |
| snapshots / memory windows / fingerprints | 0 / 0 / 0 |
| retrieval queries / matches | 0 / 0 |
| paper decisions / positions | 0 / 0 |
| trade events / paper audits / paper audit reports | 0 / 0 / 0 |
| PnL | no PnL table present; no financial rows created |

No scheduler job was executed. Audit-only candidates created no token, pair,
tracking, scheduler, or rotation rows. However, all ten accepted active
candidates received tracking and pending scheduler handoffs even though the
separate final quota view failed. This proves quota is still informational at
this production front door rather than a persistence gate.

Static call-path inspection also found that this production command does not
invoke `apply_selection_cooldown_gates()` or `persist_selection_batch()`.
Consequently it did not record or evaluate cross-batch selection rotation state.
The fresh proof DB had no prior selections, so a cooldown check would not have
rejected this sample, but the missing wiring means this front door did not prove
the requested cooldown/rotation stage.

The persistent DB SHA-256 was unchanged before and after:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

## Required Answers

1. **Did Printer complete discovery and selection without manual intervention?**
   Yes. After command setup, Printer independently fetched, normalized,
   classified, deduplicated, composed a quota view, persisted active handoffs,
   and returned once.
2. **Did any stage require external candidate selection, data patching, or
   operator judgment?** No. The operator supplied only bounded command approval
   and source limits. No candidate or mint was selected manually.
3. **Did it preserve Source Governor, quota, and safety rules?** Source Governor,
   source trace, STNP rejection, audit-only isolation, and downstream locks were
   preserved. Quota rules were evaluated and reported accurately, but the failed
   quota did not prevent active tracking/scheduler handoff. Cross-batch cooldown
   and rotation were not invoked by this command.
4. **Did it stop safely?** Yes. The command exited successfully after one run;
   no scheduler execution or downstream memory/financial work occurred.
5. **Is the front door ready for later one-command automation lanes?** No. The
   front door is operational, but an invalid final quota can coexist with active
   handoff rows, and the command does not run the selection cooldown/rotation
   path. Those boundaries must be resolved or explicitly accepted before later
   automation.

## Verdict

`UNASSISTED_PIPELINE_PASS_COMPOSITION_BLOCKED`

Discovery and classification ran unassisted and safely, but the live sample did
not satisfy the required quota and the production command persisted active
handoffs despite that failure. No retry or repair was performed. V2-3 remains
paused.
