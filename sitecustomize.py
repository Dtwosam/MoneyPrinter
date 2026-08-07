"""Temporary Checkpoint 8 offline fixture-order repair hook.

This file is used only to let the already-proven offline C8 repair workflow apply
one exact proof-only patch before its tests. It performs no network, campaign,
proof, database, scheduler, memory, or provider work. Remove after GREEN.
"""

from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent
HARNESS = ROOT / "scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py"
COMPAT = ROOT / "src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py"
TEST = ROOT / "tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py"


def _replace_once(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return False
    if text.count(old) != 1:
        raise RuntimeError(f"CHECKPOINT8_REPAIR_ANCHOR_MISMATCH:{path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def _apply() -> None:
    if not (HARNESS.is_file() and COMPAT.is_file() and TEST.is_file()):
        return

    harness_old = '''            expected_mint = ""
            if len(args) >= 2:
                expected_mint = str(args[1] or "")
            elif kwargs.get("expected_mint"):
                expected_mint = str(kwargs["expected_mint"])
            candidate = _checkpoint8_candidate_for_mint(expected_mint)
            if candidate is None:
                raise Checkpoint8ControllingProofError(
                    "CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING"
                )
            return self._nested_transport(
'''
    harness_new = '''            expected_mint = ""
            expected_signature = ""
            if len(args) >= 2:
                expected_mint = str(args[0] or "")
                expected_signature = str(args[1] or "")
            elif kwargs.get("expected_mint"):
                expected_mint = str(kwargs["expected_mint"])
                expected_signature = str(kwargs.get("migration_signature") or "")
            candidate = _checkpoint8_candidate_for_mint(expected_mint)
            if candidate is None:
                raise Checkpoint8ControllingProofError(
                    "CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING"
                )
            if (
                expected_signature
                and str(candidate.get("migration_signature") or "")
                != expected_signature
            ):
                raise Checkpoint8ControllingProofError(
                    "CHECKPOINT8_PUMPSWAP_FIXTURE_SIGNATURE_MISMATCH"
                )
            return self._nested_transport(
'''
    _replace_once(HARNESS, harness_old, harness_new)

    compat_old = '            transport = verifier(first_signature, first_mint)\n'
    compat_new = '            transport = verifier(first_mint, first_signature)\n'
    _replace_once(COMPAT, compat_old, compat_new)

    test_text = TEST.read_text(encoding="utf-8")
    test_name = (
        "test_checkpoint8_pumpswap_verifier_factory_matches_canonical_"
        "mint_signature_order"
    )
    if test_name not in test_text:
        import_anchor = '''from pathlib import Path

from printer_v1.operator_cli.window_15m_concrete_composition import (
'''
        import_replacement = '''from pathlib import Path

import pytest

from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.operator_cli.checkpoint8_real_consumer_compatibility import (
    _accepted_source_result,
    _context,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
'''
        if test_text.count(import_anchor) != 1:
            raise RuntimeError("CHECKPOINT8_REPAIR_TEST_IMPORT_ANCHOR_MISMATCH")
        test_text = test_text.replace(import_anchor, import_replacement, 1)

        source_anchor = ''')


ROOT = Path(__file__).resolve().parents[1]
'''
        source_replacement = ''')
from printer_v1.sources.pumpswap import build_pumpswap_adapter


ROOT = Path(__file__).resolve().parents[1]
'''
        if test_text.count(source_anchor) != 1:
            raise RuntimeError("CHECKPOINT8_REPAIR_TEST_SOURCE_ANCHOR_MISMATCH")
        test_text = test_text.replace(source_anchor, source_replacement, 1)

        addition = '''


def test_checkpoint8_pumpswap_verifier_factory_matches_canonical_mint_signature_order(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_verifier_factory_order")
    prepared = _prepared(harness, tmp_path)
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    verifier = materialized.outputs_by_label[
        "exact_pump_pumpswap_graduation_verifier_transport"
    ]
    candidate = harness._checkpoint8_candidate_records()[0]
    mint = candidate["mint"]
    signature = candidate["migration_signature"]
    pool = candidate["pumpswap_pool"]

    transport = verifier(mint, signature)
    adapter = build_pumpswap_adapter(enabled=True, fixture_transport=transport)
    result = adapter.execute(
        _context(
            "pumpswap",
            "pumpswap_onchain_pool_confirmation",
            payload={"expected_mint": mint, "pool_address": pool},
            ordinal=77,
        )
    )
    assert _accepted_source_result(result)

    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING",
    ):
        verifier(signature, mint)
'''
        TEST.write_text(test_text.rstrip() + addition + "\n", encoding="utf-8")

    # The proven repair workflow stages the harness itself before commit. Stage
    # the two directly affected companion files here so that the same GREEN-only
    # commit also carries the compatibility fix and regression.
    subprocess.run(
        ["git", "add", str(COMPAT.relative_to(ROOT)), str(TEST.relative_to(ROOT))],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


_apply()
