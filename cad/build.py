"""Build the case: `python cad/build.py check | export | render | draw | all`."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from macropad_case import checks, drawings, export, render  # noqa: E402

EXPORTS = Path(__file__).resolve().parent / "exports"
IMAGES = Path(__file__).resolve().parents[1] / "docs" / "images" / "cad"


def check() -> int:
    report = checks.run_all()
    EXPORTS.mkdir(exist_ok=True)
    (EXPORTS / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    detected = sum(item["ok"] for item in report["self_test"])
    print(f"self-test: {detected} of {len(report['self_test'])} known faults and sound shapes judged right")
    for result in report["interference"]:
        print(f"{result['variant']}: {result['pairs']} pairs checked, {len(result['clashes'])} clashes")
    for item in report["clearances"]:
        print(f"  {item['name']}: {item['value_mm']} mm (min {item['minimum_mm']})")
    for item in report["measurements"]:
        note = f"; {item['note']}" if "note" in item else ""
        print(f"  measured {item['name']}: {item['value']} {item['unit']} ({item['kind']} {item['limit']}){note}")
    for item in report["printability"]:
        print(f"  print {item['part']}: widest unsupported span {item['widest_span_mm']} mm (limit {item['limit_mm']}), "
              f"{item['bed_contact_mm2']} mm^2 on the bed (min {item['minimum_contact_mm2']}), "
              f"{item['height_over_narrow_side']} times taller than its narrow side; layer by layer: "
              f"longest bridge {item['longest_bridge_mm']} mm (limit {item['limit_mm']}), "
              f"deepest cantilever {item['deepest_cantilever_mm']} mm (limit {item['cantilever_limit_mm']})")
    problems = checks.failures(report)
    for problem in problems:
        print(f"FAIL {problem}")
    return 1 if problems else 0


COMMANDS = {
    "check": check,
    "export": lambda: export.export_all(EXPORTS),
    "render": lambda: render.render_all(IMAGES),
    "draw": lambda: drawings.write_drawings(EXPORTS / "drawings", IMAGES),
}


def main(arguments: list[str]) -> int:
    command = arguments[0] if arguments else "all"
    if command == "all":
        return next((code for code in (run() for run in COMMANDS.values()) if code), 0)
    if command not in COMMANDS:
        print(f"usage: build.py [{' | '.join([*COMMANDS, 'all'])}]", file=sys.stderr)
        return 2
    return COMMANDS[command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
