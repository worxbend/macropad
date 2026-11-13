#!/usr/bin/env python3
"""Builds the microsite in _site/ and checks it.

    build_site.py               build once; exit 1 when any check fails
    build_site.py --serve 8000  build, serve _site on 127.0.0.1:8000, rebuild when a source changes

What goes into _site/:
- the .html, .css, .js and .svg files of site/ (site/README.md and shots.sh stay behind);
- every picture a page names as images/<group>/<file>, copied from docs/images/<group>/<file>;
- images/signature.svg, drawn from the Bezier chains in cad/macropad_case/signature.py, and the
  same drawing inlined where index.html has the comment <!-- signature:svg -->;
- the silhouette of the parts in docs/images/cad/exploded.png, which the exploded scene uses so that
  moving slices of that render carry no background with them. The stylesheet names it as
  url(images/exploded-mask.png); the build puts the picture itself there as a data: URL, because
  browsers fetch mask pictures with CORS, which fails for file:// pages;
- resized WebP copies of the renders when Pillow is installed. Without Pillow the
  <source type="image/webp"> lines are dropped and the pages fall back to the PNGs.

The build fails when a page or a stylesheet names a picture that does not exist, when a picture in
docs/images/cad, pcb or ui is neither shown nor listed in SKIP, when a local link or #anchor does not
resolve, when an image lacks its size or alt text or its size differs from the picture's, when
headings skip a level, or when the signature cannot be drawn.
The site is built in a staging folder and moved into place only when every check passes.
"""
import argparse
import ast
import base64
import re
import zlib
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
# --serve builds in a folder of its own, so a `make site` run at the same time cannot collide with it.
SERVE_STAGING = REPO_ROOT / "_site.staging-serve"
WEBP_CACHE = REPO_ROOT / ".build" / "site-webp"
SIGNATURE_SOURCE = REPO_ROOT / "cad" / "macropad_case" / "signature.py"
README = REPO_ROOT / "README.md"

PUBLISHED_SUFFIXES = {".html", ".css", ".js", ".svg"}
# Pictures that may stay off the page, each with a one-line reason, keyed as "group/file.png".
# Every other raster picture in these folders (at any depth, any letter case) must be shown.
SKIP: dict[str, str] = {}
CHECKED_GROUPS = ("cad", "pcb", "ui")
RASTER_SUFFIXES = {".png", ".gif", ".jpg", ".jpeg", ".webp"}

SIGNATURE_FILE = "images/signature.svg"
MASK_FILE = "images/exploded-mask.png"
MASK_SOURCE = IMAGES / "cad" / "exploded.png"
MASK_CACHE = REPO_ROOT / ".build" / "site-mask" / "exploded-mask.png"
# A pixel counts as part when one colour channel differs from its row's background by this much;
# between the two numbers it is partly part, which keeps the edges soft.
MASK_RAMP = (3, 14)
GENERATED = {SIGNATURE_FILE, MASK_FILE}
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
# A picture counts as shown on a page only through these: an <img src>, a WebP srcset inside a
# <picture> whose <img> is the same picture, or data-gif, which the demo swaps into its <img>.
# A link to a picture or an og:image does not show it.
SHOWN_DATA_ATTRIBUTES = {"data-gif"}
REPOSITORY = "https://github.com/worxbend/macropad"
# The published address of the site. A link that starts with it (og:image) is checked as a local one.
SITE_URL = "https://worxbend.github.io/macropad/"
CSS_URL = re.compile(r"""url\(\s*["']?([^"')\s]+)""")
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
        self.shown: list[str] = []  # pictures the page actually displays (see SHOWN_DATA_ATTRIBUTES)
        self._webp_in_picture: list[str] = []  # WebP srcset entries of the open <picture>
        self.ids: list[str] = []
        self.images: list[tuple[int, dict[str, str], bool]] = []  # line, attributes, inside aria-hidden
        self.headings: list[tuple[int, int]] = []  # line, level
        self._hidden_stack: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        hidden = attributes.get("aria-hidden") == "true" or bool(self._hidden_stack and self._hidden_stack[-1][1])
        line = self.getpos()[0]
        for name, value in attributes.items():
            values = [local(v) for v in (srcset_urls(value) if name == "srcset" else [value])]
            if name in LINK_ATTRIBUTES:
                self.links += values
            if name in PICTURE_ATTRIBUTES or name.startswith("data-"):
                self.references += [v for v in values if v.startswith("images/")]
        if "id" in attributes:
            self.ids.append(attributes["id"])
        self._collect_shown(tag, attributes)
        if tag == "img":
            self.images.append((line, attributes, hidden))
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append((line, int(tag[1])))
        if tag not in VOID_ELEMENTS:
            self._hidden_stack.append((tag, hidden))

    def _collect_shown(self, tag: str, attributes: dict[str, str]) -> None:
        if tag == "picture":
            self._webp_in_picture = []
        elif tag == "source" and attributes.get("type") == "image/webp":
            self._webp_in_picture += [local(v) for v in srcset_urls(attributes.get("srcset", ""))]
        elif tag == "img":
            src = local(attributes.get("src", ""))
            if src.startswith("images/"):
                self.shown.append(src)
                self.shown += [w for w in self._webp_in_picture if (webp_source(w) or ("",))[0] == src]
            self._webp_in_picture = []
        self.shown += [local(v) for name, v in attributes.items()
                       if name in SHOWN_DATA_ATTRIBUTES and local(v).startswith("images/")]

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


def local(url: str) -> str:
    """A link to the published site, as the path it has inside the site."""
    return url.removeprefix(SITE_URL) if url.startswith(SITE_URL) else url


def css_references(css: str) -> list[str]:
    return [local(url) for url in CSS_URL.findall(css) if not url.startswith(("data:", "#"))]


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
    if reference in GENERATED:
        return None
    resized = webp_source(reference)
    return resized[0] if resized else reference


def header_size(header: bytes) -> tuple[int, int] | None:
    """Width and height from the first 24 bytes of a PNG (IHDR) or a GIF; None for anything else."""
    if header.startswith(b"\x89PNG") and len(header) >= 24:
        return struct.unpack(">II", header[16:24])
    if header.startswith(b"GIF") and len(header) >= 10:
        return struct.unpack("<HH", header[6:10])
    return None


def picture_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        size = header_size(file.read(24))
    if size is None:
        raise ValueError(f"{path}: not a PNG or GIF")
    return size


def picture_width(path: Path) -> int:
    return picture_size(path)[0]


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
    return {path.relative_to(IMAGES).as_posix()
            for group in CHECKED_GROUPS for path in (IMAGES / group).rglob("*")
            if path.is_file() and path.suffix.lower() in RASTER_SUFFIXES}


def unused_renders(references: set[str], displayed: set[str]) -> list[str]:
    """references: every picture a page names. displayed: the ones a page shows (PageScan.shown)."""
    shown = {source.removeprefix("images/") for source in map(source_of, displayed) if source}
    renders = all_renders()
    problems = [f"docs/images/{name} is not shown on any page (a link does not count); show it or add it to SKIP with a reason"
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


def size_problem(root: Path, attributes: dict[str, str]) -> str | None:
    """The width and height attributes must be the picture's own, or the page reserves the wrong box."""
    src = local(attributes.get("src", ""))
    path = root / src
    if not src.startswith("images/") or not path.is_file():
        return None
    size = picture_size(path)
    stated = (attributes.get("width"), attributes.get("height"))
    if stated != (str(size[0]), str(size[1])):
        return f"width/height {stated[0]} x {stated[1]}, but {src} is {size[0]} x {size[1]}"
    return None


def image_problems(page: PageScan, root: Path | None = None) -> list[str]:
    problems = []
    for index, (line, attributes, hidden) in enumerate(page.images):
        where = f"line {line} <img src={attributes.get('src', '?')!r}>"
        for needed in ("width", "height", "alt"):
            if needed not in attributes:
                problems.append(f"{where} has no {needed}")
        mismatch = size_problem(root, attributes) if root else None
        if mismatch:
            problems.append(f"{where}: {mismatch}")
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
        found = (link_problems(root, path, page, ids_by_page) + image_problems(page, root)
                 + heading_problems(page) + duplicate_ids(page))
        problems += [f"{path.name}: {problem}" for problem in found]
    for path in sorted(root.glob("*.css")):
        sheet = PageScan()
        sheet.links = css_references(path.read_text(encoding="utf-8"))
        problems += [f"{path.name}: {problem}" for problem in link_problems(root, path.resolve(), sheet, ids_by_page)]
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


# ---------------------------------------------------------------- the exploded-view mask

def png_rows(path: Path) -> tuple[int, int, list[bytes]]:
    """RGB rows of an 8-bit, non-interlaced RGB or RGBA PNG, decoded with zlib alone."""
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"{path}: not a PNG")
    position, chunks, header = 8, [], None
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            chunks.append(body)
        position += 12 + length
    width, height, depth, colour, _, _, interlace = header
    if depth != 8 or colour not in (2, 6) or interlace:
        raise ValueError(f"{path}: only 8-bit RGB or RGBA without interlacing is supported")
    step = 3 if colour == 2 else 4
    raw, stride = zlib.decompress(b"".join(chunks)), width * step
    rows, previous = [], bytearray(stride)
    for y in range(height):
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            left = line[x - step] if x >= step else 0
            up, corner = previous[x], previous[x - step] if x >= step else 0
            if kind == 1:
                line[x] = (line[x] + left) & 255
            elif kind == 2:
                line[x] = (line[x] + up) & 255
            elif kind == 3:
                line[x] = (line[x] + ((left + up) >> 1)) & 255
            elif kind == 4:
                guess = left + up - corner
                near = min((abs(guess - left), 0, left), (abs(guess - up), 1, up), (abs(guess - corner), 2, corner))
                line[x] = (line[x] + near[2]) & 255
        rows.append(bytes(line[i] for i in range(stride) if i % step < 3) if step == 4 else bytes(line))
        previous = line
    return width, height, rows


def silhouette(width: int, height: int, rows: list[bytes]) -> tuple[int, int, bytes]:
    """Alpha at half size: opaque where any pixel of a 2 x 2 block differs from its row's
    background (the render's first column, which is always empty studio)."""
    low, high = MASK_RAMP
    out_w, out_h = width // 2, height // 2
    alpha = bytearray(out_w * out_h)
    for y in range(out_h):
        for row in (rows[2 * y], rows[2 * y + 1]):
            background = row[0:3]
            for x in range(out_w):
                for i in (6 * x, 6 * x + 3):
                    diff = max(abs(row[i] - background[0]), abs(row[i + 1] - background[1]), abs(row[i + 2] - background[2]))
                    level = 255 if diff >= high else 0 if diff <= low else (diff - low) * 255 // (high - low)
                    if level > alpha[y * out_w + x]:
                        alpha[y * out_w + x] = level
    return out_w, out_h, bytes(alpha)


def png_alpha(width: int, height: int, alpha: bytes) -> bytes:
    """A grey-plus-alpha PNG: black everywhere, opaque where the mask is."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    lines = b"".join(b"\x00" + bytes(v for a in alpha[y * width:(y + 1) * width] for v in (0, a)) for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 4, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(lines, 9)) + chunk(b"IEND", b""))


def mask_png(image_module) -> bytes:
    """The exploded-view silhouette, cached in .build/ until exploded.png changes. Pillow decodes
    faster when it is there; the result is the same either way."""
    if not MASK_CACHE.is_file() or MASK_CACHE.stat().st_mtime < MASK_SOURCE.stat().st_mtime:
        if image_module is not None:
            with image_module.open(MASK_SOURCE) as image:
                rgb = image.convert("RGB")
                width, height = rgb.size
                flat = rgb.tobytes()
                rows = [flat[y * width * 3:(y + 1) * width * 3] for y in range(height)]
        else:
            width, height, rows = png_rows(MASK_SOURCE)
        MASK_CACHE.parent.mkdir(parents=True, exist_ok=True)
        MASK_CACHE.write_bytes(png_alpha(*silhouette(width, height, rows)))
    return MASK_CACHE.read_bytes()


def inline_mask(destination: Path, image_module) -> list[str]:
    """Puts the silhouette into every stylesheet that names it."""
    token = f"url({MASK_FILE})"
    sheets = [path for path in sorted(destination.glob("*.css")) if token in path.read_text(encoding="utf-8")]
    if not sheets:
        return [f"no stylesheet uses {token}; the exploded scene needs it"]
    data = "url(data:image/png;base64," + base64.b64encode(mask_png(image_module)).decode("ascii") + ")"
    for path in sheets:
        path.write_text(path.read_text(encoding="utf-8").replace(token, data), encoding="utf-8")
    return []


# ---------------------------------------------------------------- the build

def self_check() -> list[str]:
    """The patterns and the writer must do what they are for, or a green build means nothing.
    Plain comparisons rather than assert, so `python -O` cannot switch them off."""
    sample = ('<img src="images/cad/a.png" alt=""><source srcset="images/cad/a-800.webp 800w, '
              'images/cad/a-1600.webp 1600w"><a href="https://x/images/b.png" data-gif="images/ui/c.gif">'
              f'<meta content="{SITE_URL}images/cad/d.png">')
    lines = '<picture>\n  <source type="image/webp" srcset="x-800.webp 800w">\n  <img src="x.png">\n</picture>\n'
    hidden = scan('<div aria-hidden="true"><img alt=""></div><img alt="">')
    checks = [
        (picture_references(scan(sample)),
         {"images/cad/a.png", "images/cad/a-800.webp", "images/cad/a-1600.webp", "images/ui/c.gif", "images/cad/d.png"}),
        (webp_source("images/pcb/render-top-1568.webp"), ("images/pcb/render-top.png", 1568)),
        ((source_of(SIGNATURE_FILE), webp_source("images/cad/a.png")), (None, None)),
        (WEBP_SOURCE_LINE.sub("", lines), '<picture>\n  <img src="x.png">\n</picture>\n'),
        ([inside for _, _, inside in hidden.images], [True, False]),
        (heading_problems(scan("<h1>a</h1><h3>b</h3>")), ["line 1: h3 follows h1"]),
        (path_data([(0, 0), (1, 2), (3, 4), (5.5, 6)]), "M0 0 C1 2 3 4 5.5 6"),
        (REPOSITORY_LINK.match(REPOSITORY + "/tree/main/pcb/fab").groups(), ("tree", "pcb/fab", None)),
        (css_references('a{background:url("images/ui/x.png")} b{mask:url(#m)} c{background:url(data:x)}'),
         ["images/ui/x.png"]),
        (silhouette(4, 2, [bytes([9, 9, 9] * 3 + [90, 9, 9]), bytes([9, 9, 9] * 3 + [9, 9, 10])]),
         (2, 1, bytes([0, 255]))),
        (source_of(MASK_FILE), None),
        (sorted(scan('<a href="images/cad/x.png">x</a><meta content="images/cad/y.png">'
                     '<picture><source type="image/webp" srcset="images/cad/a-800.webp 800w, images/cad/b-800.webp 800w">'
                     '<img src="images/cad/a.png" alt=""></picture><figure data-gif="images/ui/c.gif"></figure>').shown),
         ["images/cad/a-800.webp", "images/cad/a.png", "images/ui/c.gif"]),
        (header_size(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 3, 2)), (3, 2)),
        (header_size(b"GIF89a" + struct.pack("<HH", 5, 4)), (5, 4)),
    ]
    return [f"self-check {index}: got {got!r}, expected {expected!r}"
            for index, (got, expected) in enumerate(checks) if got != expected]


def source_problems(sources: dict[Path, str], references: set[str], displayed: set[str]) -> tuple[list[str], dict | None]:
    """Checks on site/ and docs/images before anything is written. Returns the signature literals too."""
    problems = missing_pictures(references) + unused_renders(references, displayed)
    try:
        signature = read_signature(SIGNATURE_SOURCE)
    except (OSError, SyntaxError, TypeError, ValueError) as error:
        problems.append(f"signature: {error}")
        signature = None
    placeholders = sum(html.count(SIGNATURE_PLACEHOLDER) for html in sources.values())
    if placeholders != 1:
        problems.append(f"{SIGNATURE_PLACEHOLDER} must appear exactly once in site/*.html, found {placeholders}")
    if signature and not any(signature["CAPTION"] in html for html in sources.values()):
        problems.append(f"no page shows the signature caption {signature['CAPTION']!r}")
    return problems, signature


def copy_site_files(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir()
    for path in SITE.rglob("*"):
        if path.is_file() and path.suffix in PUBLISHED_SUFFIXES:
            target = destination / path.relative_to(SITE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (destination / ".nojekyll").touch()


def write_pages(destination: Path, sources: dict[Path, str], svg: str, with_webp: bool) -> list[str]:
    """The pages with the signature inlined, and without WebP sources when there are no WebP copies."""
    problems = []
    for page, html in sources.items():
        html = html.replace(SIGNATURE_PLACEHOLDER, svg)
        if not with_webp:
            html = WEBP_SOURCE_LINE.sub("", html)
            if "image/webp" in html:
                problems.append(f"{page.name}: a WebP <source> is not on a line of its own")
        (destination / page.name).write_text(html, encoding="utf-8")
    return problems


def copy_pictures(destination: Path, references: set[str], image_module) -> None:
    for reference in sorted(references):
        target = destination / reference
        if webp_source(reference):
            if image_module is not None:
                write_webp(image_module, reference, target)
        elif source_of(reference):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(IMAGES / reference.removeprefix("images/"), target)


def build(destination: Path) -> tuple[list[str], str]:
    """Builds into destination. Returns the problems found and a one-line summary."""
    broken = self_check()
    if broken:
        return broken, ""
    sources = {page: page.read_text(encoding="utf-8") for page in sorted(SITE.glob("*.html"))}
    scans = [scan(html) for html in sources.values()]
    references = set().union(*(picture_references(page) for page in scans))
    displayed = set().union(*(set(page.shown) for page in scans))
    for sheet in sorted(SITE.glob("*.css")):
        backgrounds = {url for url in css_references(sheet.read_text(encoding="utf-8")) if url.startswith("images/")}
        references |= backgrounds
        displayed |= backgrounds
    problems, signature = source_problems(sources, references, displayed)
    if problems:
        return problems, ""

    copy_site_files(destination)
    svg = signature_svg(signature)
    (destination / SIGNATURE_FILE).parent.mkdir(parents=True, exist_ok=True)
    (destination / SIGNATURE_FILE).write_text(svg + "\n", encoding="utf-8")
    image_module = load_pillow()
    if image_module is None:
        print("build_site: Pillow not installed, WebP copies skipped")
    problems += inline_mask(destination, image_module)
    problems += write_pages(destination, sources, svg, with_webp=image_module is not None)
    copy_pictures(destination, references, image_module)
    problems += check_built_pages(destination)

    pictures = sum(1 for reference in references if source_of(reference) and not webp_source(reference))
    webp = sum(1 for reference in references if webp_source(reference)) if image_module else 0
    summary = (f"build_site: {len(sources)} pages, {pictures} pictures, {webp} WebP copies, "
               f"{len(SKIP)} skipped renders, signature {stroke_length_mm(signature):.0f} mm of line")
    return problems, summary


def build_and_publish(staging: Path = STAGING) -> bool:
    """Builds into the staging folder and replaces _site only when every check passes. The old
    _site is renamed out of the way before the new one moves in, so a server never sees it missing
    for longer than one rename."""
    try:
        problems, summary = build(staging)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if problems:
        for problem in problems:
            print(f"build_site: {problem}")
        shutil.rmtree(staging, ignore_errors=True)
        return False
    retired = staging.with_name(staging.name + ".old")
    shutil.rmtree(retired, ignore_errors=True)
    if OUTPUT.exists():
        OUTPUT.rename(retired)
    staging.rename(OUTPUT)
    shutil.rmtree(retired, ignore_errors=True)
    print(f"{summary} -> {OUTPUT.relative_to(REPO_ROOT)}")
    return True


# ---------------------------------------------------------------- the local loop

def source_state() -> dict[Path, float]:
    """Everything a build reads. A change to this script itself needs a restart of the server."""
    watched = [*SITE.rglob("*"), *IMAGES.rglob("*"), SIGNATURE_SOURCE, README]
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
                if not build_and_publish(SERVE_STAGING):
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
    if not build_and_publish(SERVE_STAGING) and not OUTPUT.is_dir():
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
