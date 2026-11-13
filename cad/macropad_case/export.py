"""STEP and STL files for every part, plus one assembly STEP."""

from pathlib import Path

from build123d import Compound, Part, export_step, export_stl

from .checks import PRINT_POSES
from .components import components
from .small_parts import case_parts
from .spec import PRINT, VARIANTS

# The two diffusers are the same part turned around, and the two knobs are identical.
EXPORT_NAMES = {"base": "base", "top": "top", "diffuser_left": "diffuser", "knob_left": "knob", "tilt_bar": "tilt_bar"}
VARIANT_PARTS = ("base", "top")


def export_all(exports: Path) -> int:
    for variant in VARIANTS:
        parts = case_parts(variant)
        for name, file_name in EXPORT_NAMES.items():
            if name in VARIANT_PARTS:
                _export_part(parts[name], name, exports / variant / file_name, lie_on_bed=variant == PRINT)
            elif variant == PRINT:
                _export_part(parts[name], name, exports / file_name, lie_on_bed=True)
    export_step(_assembly(), exports / "assembly.step")
    print(f"exported to {exports}")
    return 0


def _export_part(part: Part, name: str, stem: Path, lie_on_bed: bool) -> None:
    """STEP keeps the assembled position. STL lies the way it prints, when the part is printed."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    export_step(part, stem.with_suffix(".step"))
    export_stl(PRINT_POSES[name] * part if lie_on_bed else part, stem.with_suffix(".stl"))


def _assembly() -> Compound:
    labelled = []
    for name, solid in (case_parts(PRINT) | components()).items():
        solid.label = name
        labelled.append(solid)
    return Compound(label="macropad", children=labelled)
