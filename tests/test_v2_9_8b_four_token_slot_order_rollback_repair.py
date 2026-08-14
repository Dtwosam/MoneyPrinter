import inspect
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.four_token_factory_adapter import (
    reconcile_four_token_cycle_terminal,
)


class FourTokenSlotOrderRollbackRepairTests(unittest.TestCase):
    def test_cycle1_four_token_planning_reloads_authoritative_campaign_slot_order(self):
        source = inspect.getsource(factory.run_one_command_15m_factory)

        anchor_call = source.index("opening_anchor_by_target = _capture_opening_anchors(")
        plan_call = source.index("_plan_opening_jobs(", anchor_call)
        between = source[anchor_call:plan_call]
        plan_block = source[plan_call : plan_call + 900]

        self.assertIn("targets=targets,", between)
        self.assertIn("planning_targets = targets", between)
        self.assertIn("if four_token_proof_controller is not None:", between)
        self.assertIn("planning_targets = _cycle_targets_for_factory(", between)
        self.assertIn("cycle_id=str(cycle_id)", between)
        self.assertIn("targets=planning_targets,", plan_block)

    def test_outer_exception_rolls_back_before_terminal_reconciliation(self):
        source = inspect.getsource(factory.run_one_command_15m_factory)
        except_index = source.rindex("except Exception as exc:")
        finally_index = source.index("finally:", except_index)
        handler = source[except_index:finally_index]

        rollback_index = handler.index("if conn.in_transaction:")
        self.assertIn("conn.rollback()", handler[rollback_index:])
        self.assertLess(
            rollback_index,
            handler.index('if getattr(exc, "post_handoff_proof_fault", False):'),
        )

    def test_generic_selected_target_order_remains_lexical(self):
        source = inspect.getsource(factory._selected_targets)
        self.assertIn(
            "ORDER BY lower(i.token_mint), lower(i.pair_address)",
            source,
        )

    def test_terminal_reconciliation_keeps_fresh_transaction_guard(self):
        source = inspect.getsource(reconcile_four_token_cycle_terminal)
        self.assertIn("if connection.in_transaction:", source)
        self.assertIn(
            "cycle terminal reconciliation requires a fresh transaction",
            source,
        )


if __name__ == "__main__":
    unittest.main()
