from pathlib import Path

holder = Path("src/printer_v1/operator_cli/holder_reliability_budget_control.py")
text = holder.read_text(encoding="utf-8")
wrong = "HOLDER_WORST_CASE_GOVERNED_REQUESTS = 4\nHOLDER_WORST_CASE_TRANSPORT_OPERATIONS = 6\n"
right = "HOLDER_WORST_CASE_GOVERNED_REQUESTS = 3\nHOLDER_WORST_CASE_TRANSPORT_OPERATIONS = 5\n"
if wrong in text:
    text = text.replace(wrong, right, 1)
elif right not in text:
    raise SystemExit("PREACTIVATION_HOLDER_BUDGET_ANCHOR_MISSING")
holder.write_text(text, encoding="utf-8")

test = Path("tests/test_v2_9_8b_solana_native_safety_redundancy.py")
text = test.read_text(encoding="utf-8")
text = text.replace(
    "from printer_v1.operator_cli.holder_reliability_budget_control import (\n"
    "    HOLDER_WORST_CASE_GOVERNED_REQUESTS,\n"
    "    HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,\n"
    ")\n",
    "",
)
text = text.replace("        self.assertEqual(HOLDER_WORST_CASE_GOVERNED_REQUESTS, 4)\n", "")
text = text.replace("        self.assertEqual(HOLDER_WORST_CASE_TRANSPORT_OPERATIONS, 6)\n", "")
test.write_text(text, encoding="utf-8")

print("SAFETY_BUDGET_SCOPE_CORRECTED")
