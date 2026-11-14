"""Read every exported STEP and STL back and compare it with the part it was written from.

The in-memory checks cannot see a bad file: OCCT once wrote base.step without the faces that
touched an offset curve, and the part in memory was still one sound solid.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import trimesh
from build123d import Shape, import_step
from OCP.BRep import BRep_Tool
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.ShapeAnalysis import ShapeAnalysis_Shell

VOLUME_SHARE = 0.001  # the file's volume must lie within 0.1 % of the part's
SLIVER_FACE = 0.05  # mm^2; a smaller face in a milled part trips CAM feature recognition
SHORT_EDGE = 0.01  # mm


@dataclass(frozen=True)
class Exported:
    """One exported file set: the STEP, the part it came from, and its STL when it has one."""

    step: Path
    part: Shape
    solids: int = 1
    stl: Path | None = None
    milled: bool = False


def verify(files: list[Exported]) -> int:
    """Print one line per file and every fault found; return the number of faults."""
    faults = 0
    for exported in files:
        found = step_faults(exported) + (stl_faults(exported) if exported.stl else [])
        name = f"{exported.step.parent.name}/{exported.step.name}"
        print(f"re-read {name}: {'ok' if not found else 'FAIL ' + '; '.join(found)}")
        faults += len(found)
    return faults


def step_faults(exported: Exported) -> list[str]:
    shape = import_step(exported.step)
    solids = shape.solids()
    faults = []
    if len(solids) != exported.solids:
        faults.append(f"{len(solids)} solids, expected {exported.solids}")
    faults += [f"solid {index + 1} is not valid" for index, solid in enumerate(solids)
               if not BRepCheck_Analyzer(solid.wrapped).IsValid()]
    open_shells = sum(not BRep_Tool.IsClosed_s(shell.wrapped) for shell in shape.shells())
    if open_shells:
        faults.append(f"{open_shells} open shells")
    if free := free_edges(shape):
        faults.append(f"{free} free edges")
    faults += _volume_fault("STEP", _solid_volume(shape), _solid_volume(exported.part))
    if not _names_product(exported.step, exported.part.label):
        faults.append(f"product is not named {exported.part.label!r}")
    if exported.milled:
        faults += sliver_faults(shape)
    return faults


def free_edges(shape: Shape) -> int:
    """Edges that belong to only one face: an open seam in what should be a closed body."""
    analysis = ShapeAnalysis_Shell()
    analysis.LoadShells(shape.wrapped)
    analysis.CheckOrientedShells(shape.wrapped, True)
    return len(Shape.cast(analysis.FreeEdges()).edges()) if analysis.HasFreeEdges() else 0


def sliver_faults(shape: Shape) -> list[str]:
    slivers = sum(face.area < SLIVER_FACE for face in shape.faces())
    short = sum(edge.length < SHORT_EDGE for edge in shape.edges())
    return ([f"{slivers} faces under {SLIVER_FACE} mm^2"] if slivers else []) + (
        [f"{short} edges under {SHORT_EDGE} mm"] if short else [])


def stl_faults(exported: Exported) -> list[str]:
    mesh = trimesh.load_mesh(exported.stl)
    faults = [] if mesh.is_watertight else [f"{exported.stl.name} is not watertight"]
    return faults + _volume_fault(exported.stl.name, mesh.volume, _solid_volume(exported.part))


def _solid_volume(shape: Shape) -> float:
    """Sum over the solids. The assembly compound's own `volume` came out 0.25 % below this sum, and the
    sum is what the file holds."""
    return sum(solid.volume for solid in shape.solids())


def _volume_fault(what: str, volume: float, expected: float) -> list[str]:
    share = abs(volume - expected) / expected
    return [] if share <= VOLUME_SHARE else [f"{what} volume {volume:.1f} mm^3 against {expected:.1f} in memory"]


def _names_product(step: Path, label: str) -> bool:
    return bool(label) and re.search(rf"PRODUCT\('{re.escape(label)}'", step.read_text()) is not None
