from __future__ import annotations

import inspect

from printer_v1.operator_cli import campaign_supervision as cs
from printer_v1.operator_cli import four_token_factory_adapter as fa
from printer_v1.operator_cli import operational_memory_factory_command as omfc
from printer_v1.operator_cli import unified_terminal_closure as utc

names = [
    (fa, "reconcile_parent_interrupted_open_pre_admission_attempts"),
    (fa, "finalize_four_token_shared_terminal"),
    (cs, "cleanup_campaign_supervision"),
    (utc, "reconcile_campaign_terminal"),
]
for module, name in names:
    fn = getattr(module, name, None)
    print(f"=== {module.__name__}.{name} ===")
    print("FOUND", fn is not None)
    if fn is not None:
        print("SIGNATURE", inspect.signature(fn))
        print(inspect.getsource(fn))

for name in dir(omfc):
    if "four_token" in name.lower() and ("terminal" in name.lower() or "reconcile" in name.lower()):
        obj = getattr(omfc, name)
        if callable(obj):
            print(f"=== OMFC {name} ===")
            try:
                print("SIGNATURE", inspect.signature(obj))
                print(inspect.getsource(obj))
            except Exception as exc:
                print("INSPECT_ERROR", repr(exc))
