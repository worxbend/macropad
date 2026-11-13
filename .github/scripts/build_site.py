#!/usr/bin/env python3
"""Assembles the microsite in _site/: the pages in site/ plus the pictures they name from docs/images/.

The pages name pictures as `images/<group>/<file>`, the same path as under docs/images/. Only the
pictures a page names are copied, and the build fails when one of them does not exist, so the site
never ships a broken image and always shows the renders of the commit it was built from.
"""
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE = REPO_ROOT / "site"
IMAGES = REPO_ROOT / "docs" / "images"
OUTPUT = REPO_ROOT / "_site"
IMAGE_REFERENCE = re.compile(r"""(?:src|href|content)=["'](images/[^"'#?]+)["']""")


def referenced_images(page: Path) -> list[str]:
    return IMAGE_REFERENCE.findall(page.read_text(encoding="utf-8"))


def self_check() -> None:
    sample = '<img src="images/cad/hero.png"> <a href="images/pcb/schematic.pdf"> <a href="https://x/images/a.png">'
    assert IMAGE_REFERENCE.findall(sample) == ["images/cad/hero.png", "images/pcb/schematic.pdf"]


def main() -> int:
    self_check()
    pages = sorted(SITE.glob("*.html"))
    wanted = sorted({reference for page in pages for reference in referenced_images(page)})
    missing = [reference for reference in wanted if not (IMAGES / reference.removeprefix("images/")).is_file()]
    for reference in missing:
        print(f"build_site: {reference} does not exist under docs/images")
    if missing:
        return 1
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(SITE, OUTPUT)
    for reference in wanted:
        target = OUTPUT / reference
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(IMAGES / reference.removeprefix("images/"), target)
    (OUTPUT / ".nojekyll").touch()
    print(f"build_site: {len(pages)} pages, {len(wanted)} pictures -> {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
