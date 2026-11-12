"""Build the case: `python cad/build.py check | export | render | all`."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from macropad_case import checks, export, render  # noqa: E402

EXPORTS = Path(__file__).resolve().parent / "exports"
IMAGES = Path(__file__).resolve().parents[1] / "docs" / "images" / "cad"


def check() -> int:
    report = checks.run_all()
    EXPORTS.mkdir(exist_ok=True)
    (EXPORTS / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    for result in report["interference"]:
        print(f"{result['variant']}: {result['pairs']} pairs checked, {len(result['clashes'])} clashes")
    for item in report["clearances"]:
        print(f"  {item['name']}: {item['value_mm']} mm (min {item['minimum_mm']})")
    for item in report["printability"]:
        print(f"  print {item['part']}: widest unsupported span {item['widest_span_mm']} mm (limit {item['limit_mm']})")
    problems = checks.failures(report)
    for problem in problems:
        print(f"FAIL {problem}")
    return 1 if problems else 0


COMMANDS = {
    "check": check,
    "export": lambda: export.export_all(EXPORTS),
    "render": lambda: render.render_all(IMAGES),
}


def main(arguments: list[str]) -> int:
    command = arguments[0] if arguments else "all"
    if command == "all":
        return check() or export.export_all(EXPORTS) or render.render_all(IMAGES)
    if command not in COMMANDS:
        print(f"usage: build.py [{' | '.join([*COMMANDS, 'all'])}]", file=sys.stderr)
        return 2
    return COMMANDS[command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
