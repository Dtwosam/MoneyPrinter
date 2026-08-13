"""RED contract for the proof-only four-token canonical factory wiring.

This file is intentionally offline/static at this step. It must not start Printer,
perform source work, or mutate an authoritative database.
"""

from __future__ import annotations

import inspect
import unittest

from printer_v1.operator_cli import operational_memory_factory_command as command


class FourTokenCanonicalFactoryWiringContractTests(unittest.TestCase):
    def test_private_canonical_coordinator_has_optional_proof_controller_seam(self) -> None:
        parameter = inspect.signature(command._run_operational_campaign).parameters.get(
            "four_token_proof_controller"
        )
        self.assertIsNotNone(parameter)
        self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(parameter.default)

    def test_proof_controller_seam_is_not_public_runtime_authority(self) -> None:
        self.assertEqual(command.TOKEN_CAPACITY, 2)
        for public_runner in (
            command.run_operational_campaign,
            command.run_standard_four_hour_campaign,
            command.run_selective_1h_proof,
        ):
            with self.subTest(public_runner=public_runner.__name__):
                self.assertNotIn(
                    "four_token_proof_controller",
                    inspect.signature(public_runner).parameters,
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
