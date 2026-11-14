"""STEP and STL files for every part, plus one assembly STEP. Every file is read back afterwards."""

from pathlib import Path

import trimesh
from build123d import Compound, Part, Shape, export_step, export_stl

from .checks import PRINT_POSES
from .components import components
from .parts import top_chairs
from .roundtrip import Exported, verify
from .small_parts import case_parts
from .spec import CNC, PRINT, VARIANTS, part_label

# The two light bars are the same part turned around; the two knobs and the two foot strips are identical.
EXPORT_NAMES = {
    "base": "base", "top": "top", "diffuser_left": "diffuser", "knob_left": "knob", "foot_strip_back": "foot_strip",
    "centre_pad": "centre_pad", "tilt_bar": "tilt_bar", "lens": "lens",
}
VARIANT_PARTS = ("base", "top")


def export_all(exports: Path) -> int:
    written = []
    for variant in VARIANTS:
        parts = case_parts(variant)
        for name, file_name in EXPORT_NAMES.items():
            if name in VARIANT_PARTS:
                written.append(_export_part(parts[name], name, variant, exports / variant / file_name))
            elif variant == PRINT:
                written.append(_export_part(parts[name], name, variant, exports / file_name))
    # The break-away chairs print with the top, in the same pose: load both files together.
    _write_stl(PRINT_POSES["top"] * top_chairs(), exports / PRINT / "top_chairs.stl")
    assembly = _assembly()
    export_step(assembly, exports / "assembly.step")
    written.append(Exported(exports / "assembly.step", assembly, solids=len(assembly.solids())))
    print(f"exported to {exports}")
    faults = verify(written)
    if faults:
        print(f"FAIL {faults} faults in the exported files")
    return 1 if faults else 0


def _export_part(part: Part, name: str, variant: str, stem: Path) -> Exported:
    """STEP keeps the assembled position. STL lies the way it prints, when the part is printed.
    The lens is cut from sheet: it gets a STEP here and its outline as DXF with the drawings."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    part.label = part_label(stem.name, variant)
    step = stem.with_suffix(".step")
    export_step(part, step)
    if name not in PRINT_POSES:
        return Exported(step, part, milled=variant == CNC)
    _write_stl(PRINT_POSES[name] * part if variant == PRINT else part, stem.with_suffix(".stl"))
    return Exported(step, part, stl=stem.with_suffix(".stl"), milled=variant == CNC)


def _write_stl(shape: Shape, path: Path) -> None:
    """The mesher leaves zero-area triangles where a cone ends in a point (the tap drill points),
    and a mesh with them is not watertight. They are dropped before the file is written."""
    export_stl(shape, path)
    mesh = trimesh.load_mesh(path)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.export(path)


def _assembly() -> Compound:
    labelled = []
    for name, solid in (case_parts(PRINT) | components(PRINT)).items():
        solid.label = name
        labelled.append(solid)
    return Compound(label="macropad", children=labelled)
