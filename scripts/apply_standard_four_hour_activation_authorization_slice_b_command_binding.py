from pathlib import Path

path = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"expected command-binding anchor missing: {old[:120]!r}")
    text = text.replace(old, new, 1)


replace_once(
'''        if args.mode == "run" and not any(provenance_binding_values):
            raise OperationalMemoryFactoryError(
                "ordinary run requires external one-shot wrapper authorization"
            )
        if args.mode == "run" and all(provenance_binding_values):
            child_terminal_binding = resolve_child_terminal_binding(os.environ)
        elif args.mode != "run" and os.environ.get(CHILD_TERMINAL_ENV_VAR):
            raise OperationalMemoryFactoryError(
                "child terminal binding is accepted only for ordinary run"
            )
''',
'''        wrapper_bound_modes = {"run", STANDARD_FOUR_HOUR_MODE}
        if args.mode in wrapper_bound_modes and not any(provenance_binding_values):
            label = "ordinary run" if args.mode == "run" else "standard four-hour run"
            raise OperationalMemoryFactoryError(
                f"{label} requires external one-shot wrapper authorization"
            )
        if args.mode in wrapper_bound_modes and all(provenance_binding_values):
            child_terminal_binding = resolve_child_terminal_binding(os.environ)
        elif args.mode not in wrapper_bound_modes and os.environ.get(CHILD_TERMINAL_ENV_VAR):
            raise OperationalMemoryFactoryError(
                "child terminal binding is accepted only for one-shot wrapper run modes"
            )
''',
)
replace_once(
'''        if args.mode == "run" and git_provenance_authorization is None:
            raise OperationalMemoryFactoryError(
                "ordinary run requires external one-shot wrapper authorization"
            )
        if args.mode == "run" and child_terminal_binding is None:
            raise OperationalMemoryFactoryError(
                "ordinary run child terminal binding requires complete wrapper provenance"
            )
''',
'''        if args.mode in wrapper_bound_modes and git_provenance_authorization is None:
            label = "ordinary run" if args.mode == "run" else "standard four-hour run"
            raise OperationalMemoryFactoryError(
                f"{label} requires external one-shot wrapper authorization"
            )
        if args.mode in wrapper_bound_modes and child_terminal_binding is None:
            label = "ordinary run" if args.mode == "run" else "standard four-hour run"
            raise OperationalMemoryFactoryError(
                f"{label} child terminal binding requires complete wrapper provenance"
            )
''',
)
replace_once(
'''        if args.mode == "run" and child_terminal_binding is not None:
            write_child_terminal_envelope(
                binding=child_terminal_binding,
                source=result,
                mode="run",
                exit_code=0,
                success=True,
            )
''',
'''        if args.mode in wrapper_bound_modes and child_terminal_binding is not None:
            write_child_terminal_envelope(
                binding=child_terminal_binding,
                source=result,
                mode=args.mode,
                exit_code=0,
                success=True,
            )
''',
)
replace_once(
'''        campaign_modes = {"run", SELECTIVE_1H_MODE}
''',
'''        campaign_modes = {"run", SELECTIVE_1H_MODE, STANDARD_FOUR_HOUR_MODE}
''',
)
replace_once(
'''        if args.mode == "run" and child_terminal_binding is not None:
            try:
                write_child_terminal_envelope(
                    binding=child_terminal_binding,
                    source=envelope,
                    mode="run",
                    exit_code=1,
                    success=False,
                )
''',
'''        if args.mode in {"run", STANDARD_FOUR_HOUR_MODE} and child_terminal_binding is not None:
            try:
                write_child_terminal_envelope(
                    binding=child_terminal_binding,
                    source=envelope,
                    mode=args.mode,
                    exit_code=1,
                    success=False,
                )
''',
)
path.write_text(text, encoding="utf-8")
