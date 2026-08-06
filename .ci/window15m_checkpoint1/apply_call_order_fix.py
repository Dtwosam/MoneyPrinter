from pathlib import Path

path = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")
text = path.read_text(encoding="utf-8")
old = '''        # Read the four external manifest/marker bindings once and all-or-none.\n        # Ordinary run is application-wrapper-only; auxiliary modes preserve\n        # their existing no-binding behavior.\n        git_provenance_authorization = _resolve_git_provenance_authorization(args.mode)\n        if args.mode == "run" and git_provenance_authorization is None:\n            raise OperationalMemoryFactoryError(\n                "ordinary run requires external one-shot wrapper authorization"\n            )\n        if args.mode == "run":\n            child_terminal_binding = resolve_child_terminal_binding(os.environ)\n        elif os.environ.get(CHILD_TERMINAL_ENV_VAR):\n            raise OperationalMemoryFactoryError(\n                "child terminal binding is accepted only for ordinary run"\n            )\n'''
new = '''        # Establish the child-owned reporting binding before provenance\n        # validation. This does not authorize execution; it only ensures a\n        # handled provenance/preflight failure can be reported structurally.\n        if args.mode == "run":\n            child_terminal_binding = resolve_child_terminal_binding(os.environ)\n        elif os.environ.get(CHILD_TERMINAL_ENV_VAR):\n            raise OperationalMemoryFactoryError(\n                "child terminal binding is accepted only for ordinary run"\n            )\n        # Read the four external manifest/marker bindings once and all-or-none.\n        # Ordinary run is application-wrapper-only; auxiliary modes preserve\n        # their existing no-binding behavior.\n        git_provenance_authorization = _resolve_git_provenance_authorization(args.mode)\n        if args.mode == "run" and git_provenance_authorization is None:\n            raise OperationalMemoryFactoryError(\n                "ordinary run requires external one-shot wrapper authorization"\n            )\n'''
if text.count(old) != 1:
    raise SystemExit(
        f"provenance/binding call-order anchor mismatch: {text.count(old)}"
    )
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("provenance reporting-binding call order repaired")
