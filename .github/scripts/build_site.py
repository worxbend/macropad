#!/usr/bin/env python3
"""Builds the microsite in _site/ and checks it.

    build_site.py               build once; exit 1 when any check fails
    build_site.py --serve 8000  build, serve _site on 127.0.0.1:8000, rebuild when a source changes

What goes into _site/:
- the .html, .css, .js and .svg files of site/ (site/README.md and shots.sh stay behind);
- every picture a page names as images/<group>/<file>, copied from docs/images/<group>/<file>;
- images/signature.svg, drawn from the Bezier chains in cad/macropad_case/signature.py, and the
  same drawing inlined where index.html has the comment <!-- signature:svg -->;
- resized WebP copies of the renders when Pillow is installed. Without Pillow the
  <source type="image/webp"> lines are dropped and the pages fall back to the PNGs.

The build fails when a page names a picture that does not exist, when a render in docs/images is
neither shown nor listed in SKIP, when a local link or #anchor does not resolve, when an image lacks
its size or alt text, when headings skip a level, or when the signature cannot be drawn.
The site is built in a staging folder and moved into place only when every check passes.
"""
import argparse
import ast
import re
import shutil
import struct
import sys
import threading
import time
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE = REPO_ROOT / "site"
IMAGES = REPO_ROOT / "docs" / "images"
OUTPUT = REPO_ROOT / "_site"
STAGING = REPO_ROOT / "_site.staging"
WEBP_CACHE = REPO_ROOT / ".build" / "site-webp"
SIGNATURE_SOURCE = REPO_ROOT / "cad" / "macropad_case" / "signature.py"
README = REPO_ROOT / "README.md"

PUBLISHED_SUFFIXES = {".html", ".css", ".js", ".svg"}
# Renders that may stay off the page, each with a one-line reason. Every other PNG under
# docs/images/cad and docs/images/pcb, and every PNG and GIF under docs/images/ui, must be shown.
SKIP: dict[str, str] = {}
CHECKED_RENDERS = (("cad", "*.png"), ("pcb", "*.png"), ("ui", "*.png"), ("ui", "*.gif"))

SIGNATURE_FILE = "images/signature.svg"
SIGNATURE_PLACEHOLDER = "<!-- signature:svg -->"
SIGNATURE_TITLE = "Signature: Oleksandr B"
SIGNATURE_NAMES = ("_LETTER_O", "_LEKSANDR_B", "SCALE", "LINE_WIDTH", "CAPTION")
BEZIER_SAMPLES = 64

WEBP_QUALITY = 82
# One authored pattern: a <source> for WebP copies on a line of its own. Without Pillow it is removed.
WEBP_SOURCE_LINE = re.compile(r'^[ \t]*<source type="image/webp"[^>]*>[ \t]*\n', re.MULTILINE)
LINK_ATTRIBUTES = {"src", "href", "srcset", "poster"}
# Attributes that may name a picture without being a link: <meta content>, data-gif and the like.
PICTURE_ATTRIBUTES = LINK_ATTRIBUTES | {"content"}
REPOSITORY = "https://github.com/worxbend/macropad"
REPOSITORY_LINK = re.compile(re.escape(REPOSITORY) + r"(?:/(blob|tree)/main/([^#?]+?))?/?(?:#(.*))?$")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)
VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


# ---------------------------------------------------------------- reading pages

class PageScan(HTMLParser):
    """What the checks need from one page: references, ids, images and headings, in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []  # href, src, srcset and poster values: must resolve
        self.references: list[str] = []  # every value that names images/...: must exist
        self.ids: list[str] = []
        self.images: list[tuple[int, dict[str, str], bool]] = []  # line, attributes, inside aria-hidden
        self.headings: list[tuple[int, int]] = []  # line, level
        self._hidden_stack: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        hidden = attributes.get("aria-hidden") == "true" or bool(self._hidden_stack and self._hidden_stack[-1][1])
        line = self.getpos()[0]
        for name, value in attributes.items():
            values = srcset_urls(value) if name == "srcset" else [value]
            if name in LINK_ATTRIBUTES:
                self.links += values
            if name in PICTURE_ATTRIBUTES or name.startswith("data-"):
                self.references += [v for v in values if v.startswith("images/")]
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag == "img":
            self.images.append((line, attributes, hidden))
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append((line, int(tag[1])))
        if tag not in VOID_ELEMENTS:
            self._hidden_stack.append((tag, hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self._hidden_stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for depth in range(len(self._hidden_stack) - 1, -1, -1):
            if self._hidden_stack[depth][0] == tag:
                del self._hidden_stack[depth:]
                return


def scan(html: str) -> PageScan:
    page = PageScan()
    page.feed(html)
    page.close()
    return page


def srcset_urls(srcset: str) -> list[str]:
    return [candidate.split()[0] for candidate in srcset.split(",") if candidate.strip()]


def picture_references(page: PageScan) -> set[str]:
    return set(page.references)


def webp_source(reference: str) -> tuple[str, int] | None:
    """images/cad/hero-800.webp -> (images/cad/hero.png, 800). None for anything else."""
    if not reference.endswith(".webp"):
        return None
    stem, _, width = reference.removesuffix(".webp").rpartition("-")
    return (f"{stem}.png", int(width)) if width.isdigit() else None


def source_of(reference: str) -> str | None:
    """The docs/images picture a reference comes from, or None for a file the build writes itself."""
    if reference == SIGNATURE_FILE:
        return None
    resized = webp_source(reference)
    return resized[0] if resized else reference


def picture_width(path: Path) -> int:
    header = path.read_bytes()[:24]
    if header.startswith(b"\x89PNG"):
        return struct.unpack(">I", header[16:20])[0]
    if header.startswith(b"GIF"):
        return struct.unpack("<H", header[6:8])[0]
    raise ValueError(f"{path}: not a PNG or GIF")


# ---------------------------------------------------------------- picture checks

def missing_pictures(references: set[str]) -> list[str]:
    problems = []
    for reference in sorted(references):
        source = source_of(reference)
        if source is None:
            continue
        path = IMAGES / source.removeprefix("images/")
        if not path.is_file():
            problems.append(f"{reference} does not exist under docs/images")
            continue
        resized = webp_source(reference)
        if resized and resized[1] > picture_width(path):
            problems.append(f"{reference} is wider than {source} ({picture_width(path)} px); never upscale")
    return problems


def all_renders() -> set[str]:
    return {f"{group}/{path.name}" for group, pattern in CHECKED_RENDERS for path in (IMAGES / group).glob(pattern)}


def unused_renders(references: set[str]) -> list[str]:
    shown = {source.removeprefix("images/") for source in map(source_of, references) if source}
    renders = all_renders()
    problems = [f"docs/images/{name} is not on any page; show it or add it to SKIP with a reason"
                for name in sorted(renders - shown - SKIP.keys())]
    for name, reason in SKIP.items():
        if name not in renders:
            problems.append(f"SKIP names {name}, which is not under docs/images")
        if name in shown:
            problems.append(f"SKIP names {name}, but a page shows it; remove it from SKIP")
        if not reason.strip() or "\n" in reason:
            problems.append(f"SKIP reason for {name} must be one non-empty line")
    return problems


# ---------------------------------------------------------------- signature

def read_signature(source: Path) -> dict:
    """The module-level literals of signature.py, read with ast so build123d is never imported."""
    values = {}
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in SIGNATURE_NAMES:
                values[name] = ast.literal_eval(node.value)
    missing = [name for name in SIGNATURE_NAMES if name not in values]
    if missing:
        raise ValueError(f"{source.relative_to(REPO_ROOT)} has no literal {', '.join(missing)}")
    for name in ("_LETTER_O", "_LEKSANDR_B"):
        chain = values[name]
        if len(chain) < 4 or (len(chain) - 1) % 3:
            raise ValueError(f"{name} must be a start point plus three points per curve, has {len(chain)}")
        if not all(len(point) == 2 and all(isinstance(c, (int, float)) for c in point) for point in chain):
            raise ValueError(f"{name} must hold only (x, y) number pairs")
    if not (values["SCALE"] > 0 and values["LINE_WIDTH"] > 0 and isinstance(values["CAPTION"], str)):
        raise ValueError("SCALE and LINE_WIDTH must be positive and CAPTION a string")
    return values


def bezier_points(chain: list[tuple[float, float]]) -> list[tuple[float, float]]:
    points = [chain[0]]
    for first in range(0, len(chain) - 1, 3):
        p0, p1, p2, p3 = chain[first:first + 4]
        for step in range(1, BEZIER_SAMPLES + 1):
            t = step / BEZIER_SAMPLES
            weights = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3)
            points.append(tuple(sum(w * p[axis] for w, p in zip(weights, (p0, p1, p2, p3))) for axis in (0, 1)))
    return points


def path_data(chain: list[tuple[float, float]]) -> str:
    def pair(point: tuple[float, float]) -> str:
        return f"{point[0]:g} {point[1]:g}"
    curves = [" ".join(pair(p) for p in chain[i:i + 3]) for i in range(1, len(chain), 3)]
    return f"M{pair(chain[0])} C" + " ".join(curves)


def stroke_length_mm(signature: dict) -> float:
    def length(points: list[tuple[float, float]]) -> float:
        return sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(points, points[1:]))
    return sum(length(bezier_points(signature[name])) for name in ("_LETTER_O", "_LEKSANDR_B")) * signature["SCALE"]


def signature_svg(signature: dict) -> str:
    """The signature as drawn by the laser, in drawing units (y down, as SVG is)."""
    stroke = signature["LINE_WIDTH"] / signature["SCALE"]
    points = [p for name in ("_LETTER_O", "_LEKSANDR_B") for p in bezier_points(signature[name])]
    half = stroke / 2
    ink = (min(x for x, _ in points) - half, min(y for _, y in points) - half,
           max(x for x, _ in points) + half, max(y for _, y in points) + half)
    pad = 0.5
    view = (ink[0] - pad, ink[1] - pad, ink[2] - ink[0] + 2 * pad, ink[3] - ink[1] + 2 * pad)
    ink_box = (ink[0], ink[1], ink[2] - ink[0], ink[3] - ink[1])

    def numbers(values: tuple[float, ...]) -> str:
        return " ".join(f"{v:.3f}".rstrip("0").rstrip(".") for v in values)
    return (
        f'<svg class="signature-art" xmlns="http://www.w3.org/2000/svg" viewBox="{numbers(view)}" '
        f'data-ink="{numbers(ink_box)}" role="img" aria-labelledby="sig-title" fill="none" '
        f'stroke="currentColor" stroke-width="{stroke:.4f}" stroke-linecap="round" stroke-linejoin="round">'
        f'<title id="sig-title">{SIGNATURE_TITLE}</title>'
        f'<path id="sig-o" d="{path_data(signature["_LETTER_O"])}"/>'
        f'<path id="sig-rest" d="{path_data(signature["_LEKSANDR_B"])}"/>'
        "</svg>"
    )


# ---------------------------------------------------------------- page checks on the built site

def readme_anchors() -> set[str]:
    fenced, anchors = False, set()
    for line in README.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            heading = line.lstrip("#").strip().lower()
            anchors.add(re.sub(r"[^\w\- ]", "", heading).replace(" ", "-"))
    return anchors


def repository_link_problem(url: str) -> str | None:
    match = REPOSITORY_LINK.match(url)
    if not match:
        return None if not url.startswith(REPOSITORY) else f"{url}: not a main-branch blob or tree link"
    kind, path, anchor = match.groups()
    if kind:
        target = REPO_ROOT / path
        if not (target.is_dir() if kind == "tree" else target.is_file()):
            return f"{url}: {path} does not exist in this checkout"
    elif anchor and anchor not in readme_anchors():
        return f"{url}: README.md has no heading for #{anchor}"
    return None


def link_problems(root: Path, page_path: Path, page: PageScan, ids_by_page: dict[Path, set[str]]) -> list[str]:
    problems = []
    for reference in [*page.links, *page.references]:
        if not reference or reference.startswith(("mailto:", "data:")):
            continue
        if EXTERNAL.match(reference):
            problem = repository_link_problem(reference)
            problems += [problem] if problem else []
            continue
        path_part, _, anchor = reference.partition("#")
        target = (page_path.parent / path_part).resolve() if path_part else page_path
        if not target.is_file() or root.resolve() not in target.parents:
            problems.append(f"{reference} does not resolve to a file in the site")
        elif anchor and anchor not in ids_by_page.get(target, set()):
            problems.append(f"{reference}: no element with id {anchor!r}")
    return problems


def image_problems(page: PageScan) -> list[str]:
    problems = []
    for index, (line, attributes, hidden) in enumerate(page.images):
        where = f"line {line} <img src={attributes.get('src', '?')!r}>"
        for needed in ("width", "height", "alt"):
            if needed not in attributes:
                problems.append(f"{where} has no {needed}")
        if attributes.get("alt") == "" and not hidden:
            problems.append(f"{where}: empty alt is allowed only inside aria-hidden=\"true\"")
        if index > 0 and attributes.get("loading") != "lazy":
            problems.append(f"{where}: every image after the first needs loading=\"lazy\"")
    return problems


def heading_problems(page: PageScan) -> list[str]:
    levels = [level for _, level in page.headings]
    problems = [] if levels.count(1) == 1 else [f"{levels.count(1)} h1 elements; a page has exactly one"]
    previous = 0
    for line, level in page.headings:
        if level > previous + 1:
            problems.append(f"line {line}: h{level} follows h{previous}")
        previous = level
    return problems


def duplicate_ids(page: PageScan) -> list[str]:
    seen, problems = set(), []
    for element_id in page.ids:
        if element_id in seen:
            problems.append(f"id {element_id!r} is used twice")
        seen.add(element_id)
    return problems


def check_built_pages(root: Path) -> list[str]:
    pages = {path.resolve(): scan(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.html"))}
    ids_by_page = {path: set(page.ids) for path, page in pages.items()}
    problems = []
    for path, page in pages.items():
        found = (link_problems(root, path, page, ids_by_page) + image_problems(page)
                 + heading_problems(page) + duplicate_ids(page))
        problems += [f"{path.name}: {problem}" for problem in found]
    return problems


# ---------------------------------------------------------------- WebP copies

def load_pillow():
    try:
        from PIL import Image
    except ImportError:
        return None
    return Image


def write_webp(image_module, reference: str, target: Path) -> None:
    """Resized copy of a PNG, cached in .build/ so a rebuild only encodes what changed."""
    source_reference, width = webp_source(reference)
    source = IMAGES / source_reference.removeprefix("images/")
    cached = WEBP_CACHE / reference.removeprefix("images/")
    if not cached.is_file() or cached.stat().st_mtime < source.stat().st_mtime:
        cached.parent.mkdir(parents=True, exist_ok=True)
        with image_module.open(source) as image:
            if image.width != width:
                image = image.resize((width, round(image.height * width / image.width)), image_module.LANCZOS)
            image.save(cached, "WEBP", quality=WEBP_QUALITY, method=6)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached, target)


# ---------------------------------------------------------------- the build

def self_check() -> None:
    """The patterns and the writer must do what they are for, or a green build means nothing."""
    sample = ('<img src="images/cad/a.png" alt=""><source srcset="images/cad/a-800.webp 800w, '
              'images/cad/a-1600.webp 1600w"><a href="https://x/images/b.png" data-gif="images/ui/c.gif">')
    assert picture_references(scan(sample)) == {"images/cad/a.png", "images/cad/a-800.webp",
                                                "images/cad/a-1600.webp", "images/ui/c.gif"}
    assert webp_source("images/pcb/render-top-1568.webp") == ("images/pcb/render-top.png", 1568)
    assert source_of(SIGNATURE_FILE) is None and webp_source("images/cad/a.png") is None
    lines = '<picture>\n  <source type="image/webp" srcset="x-800.webp 800w">\n  <img src="x.png">\n</picture>\n'
    assert WEBP_SOURCE_LINE.sub("", lines) == '<picture>\n  <img src="x.png">\n</picture>\n'
    hidden = scan('<div aria-hidden="true"><img alt=""></div><img alt="">')
    assert [inside for _, _, inside in hidden.images] == [True, False]
    assert heading_problems(scan("<h1>a</h1><h3>b</h3>")) == ["line 1: h3 follows h1"]
    assert path_data([(0, 0), (1, 2), (3, 4), (5.5, 6)]) == "M0 0 C1 2 3 4 5.5 6"
    assert REPOSITORY_LINK.match(REPOSITORY + "/tree/main/pcb/fab").groups() == ("tree", "pcb/fab", None)


def build(destination: Path) -> tuple[list[str], str]:
    """Builds into destination. Returns the problems found and a one-line summary."""
    self_check()
    pages = sorted(SITE.glob("*.html"))
    sources = {page: page.read_text(encoding="utf-8") for page in pages}
    references = set().union(*(picture_references(scan(html)) for html in sources.values()))
    problems = missing_pictures(references) + unused_renders(references)
    try:
        signature = read_signature(SIGNATURE_SOURCE)
    except (OSError, SyntaxError, ValueError) as error:
        problems.append(f"signature: {error}")
        signature = None
    placeholders = sum(html.count(SIGNATURE_PLACEHOLDER) for html in sources.values())
    if placeholders != 1:
        problems.append(f"{SIGNATURE_PLACEHOLDER} must appear exactly once in site/*.html, found {placeholders}")
    if signature and not any(signature["CAPTION"] in html for html in sources.values()):
        problems.append(f"no page shows the signature caption {signature['CAPTION']!r}")
    if problems:
        return problems, ""

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir()
    for path in SITE.rglob("*"):
        if path.is_file() and path.suffix in PUBLISHED_SUFFIXES:
            target = destination / path.relative_to(SITE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (destination / ".nojekyll").touch()

    svg = signature_svg(signature)
    (destination / SIGNATURE_FILE).parent.mkdir(parents=True, exist_ok=True)
    (destination / SIGNATURE_FILE).write_text(svg + "\n", encoding="utf-8")

    image_module = load_pillow()
    webp = sorted(reference for reference in references if webp_source(reference))
    for page, html in sources.items():
        html = html.replace(SIGNATURE_PLACEHOLDER, svg)
        if image_module is None:
            html = WEBP_SOURCE_LINE.sub("", html)
            if "image/webp" in html:
                problems.append(f"{page.name}: a WebP <source> is not on a line of its own")
        (destination / page.name).write_text(html, encoding="utf-8")
    for reference in sorted(references):
        target = destination / reference
        if webp_source(reference):
            if image_module is not None:
                write_webp(image_module, reference, target)
        elif source_of(reference):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(IMAGES / reference.removeprefix("images/"), target)
    if image_module is None:
        print("build_site: Pillow not installed, WebP copies skipped")

    problems += check_built_pages(destination)
    pictures = sum(1 for reference in references if source_of(reference) and not webp_source(reference))
    summary = (f"build_site: {len(pages)} pages, {pictures} pictures, "
               f"{len(webp) if image_module else 0} WebP copies, {len(SKIP)} skipped renders, "
               f"signature {stroke_length_mm(signature):.0f} mm of line")
    return problems, summary


def build_and_publish() -> bool:
    """Builds into the staging folder and replaces _site only when every check passes."""
    try:
        problems, summary = build(STAGING)
    except Exception:
        shutil.rmtree(STAGING, ignore_errors=True)
        raise
    if problems:
        for problem in problems:
            print(f"build_site: {problem}")
        shutil.rmtree(STAGING, ignore_errors=True)
        return False
    shutil.rmtree(OUTPUT, ignore_errors=True)
    STAGING.rename(OUTPUT)
    print(f"{summary} -> {OUTPUT.relative_to(REPO_ROOT)}")
    return True


# ---------------------------------------------------------------- the local loop

def source_state() -> dict[Path, float]:
    watched = [*SITE.rglob("*"), *IMAGES.rglob("*"), SIGNATURE_SOURCE]
    return {path: path.stat().st_mtime for path in watched if path.is_file()}


def watch_and_rebuild() -> None:
    state = source_state()
    while True:
        time.sleep(1)
        current = source_state()
        if current != state:
            state = current
            print("build_site: change seen, rebuilding")
            try:
                if not build_and_publish():
                    print("build_site: still serving the last good build")
            except Exception as error:  # a broken edit must not stop the server
                print(f"build_site: rebuild failed: {error!r}; still serving the last good build")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        if not str(args[1] if len(args) > 1 else "").startswith(("2", "3")):
            super().log_message(format, *args)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(port: int) -> int:
    sys.stdout.reconfigure(line_buffering=True)  # rebuild messages appear at once, even when piped
    if not build_and_publish() and not OUTPUT.is_dir():
        return 1
    threading.Thread(target=watch_and_rebuild, daemon=True).start()
    handler = partial(QuietHandler, directory=str(OUTPUT))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"build_site: serving http://127.0.0.1:{port}/ and rebuilding on change. Ctrl+C stops.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", type=int, metavar="PORT", help="serve _site on 127.0.0.1 and rebuild on change")
    arguments = parser.parse_args()
    if arguments.serve:
        return serve(arguments.serve)
    return 0 if build_and_publish() else 1


if __name__ == "__main__":
    sys.exit(main())
