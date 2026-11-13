#!/usr/bin/env python3
"""Fails when a Markdown file points at a file or a heading that does not exist.

Checked in every Markdown file of the repository:
- link and image targets: [text](path), ![alt](path), <img src="path">, <a href="path">,
  resolved from the file's own directory;
- code spans that name a path from the repository root, like `pcb/gen/circuit.py`;
- `#section` anchors into a Markdown file: the heading must exist.

Not checked: web links, paths with wildcards or braces.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Build output and third-party trees: their Markdown is not ours.
SKIPPED_DIRECTORIES = {".git", ".venv", ".build", "target", "node_modules", "__pycache__"}
TOP_LEVEL = ("pcb", "cad", "firmware", "docs", "tools", ".github")

MARKDOWN_TARGET = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_TARGET = re.compile(r"<(?:img|a)\b[^>]*?\b(?:src|href)=\"([^\"]+)\"")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^(```|~~~)")
ROOT_PATH = re.compile(r"^(?:%s)/[\w./-]+$" % "|".join(re.escape(name) for name in TOP_LEVEL))


def prose_lines(text: str):
    """Lines outside fenced code blocks, with their 1-based numbers."""
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line.strip()):
            fenced = not fenced
        elif not fenced:
            yield number, line


def link_targets(line: str) -> list[str]:
    """Local targets as written, anchor included. A bare `#anchor` points into the same file."""
    without_code = CODE_SPAN.sub("", line)
    targets = MARKDOWN_TARGET.findall(without_code) + HTML_TARGET.findall(without_code)
    return [t for t in targets if not re.match(r"^[a-z][a-z0-9+.-]*:", t)]


def heading_anchors(markdown: Path) -> set[str]:
    """Anchors the way GitHub builds them: lower case, punctuation dropped, spaces to hyphens."""
    headings = (line.lstrip("#").strip() for _, line in prose_lines(markdown.read_text(encoding="utf-8"))
                if line.startswith("#"))
    return {re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-") for heading in headings}


def link_problem(markdown: Path, target: str) -> str | None:
    path_part, _, anchor = target.partition("#")
    path = markdown.parent / path_part if path_part else markdown
    if not path.exists():
        return f"{path_part} does not exist"
    if anchor and path.suffix == ".md" and anchor not in heading_anchors(path):
        return f"{target}: no heading for #{anchor}"
    return None


def root_paths(line: str) -> list[str]:
    """Code spans that name a repository path. `file.py:symbol` counts as `file.py`."""
    spans = (span.split(":")[0].strip() for span in CODE_SPAN.findall(line))
    return [span for span in spans if ROOT_PATH.match(span)]


def missing_in(markdown: Path) -> list[str]:
    problems = []
    for number, line in prose_lines(markdown.read_text(encoding="utf-8")):
        found = [link_problem(markdown, target) for target in link_targets(line)]
        found += [f"{p} does not exist" for p in root_paths(line) if not (REPO_ROOT / p).exists()]
        problems += [f"{markdown.relative_to(REPO_ROOT)}:{number}: {problem}" for problem in found if problem]
    return problems


def markdown_files() -> list[Path]:
    return sorted(
        path for path in REPO_ROOT.rglob("*.md")
        if not SKIPPED_DIRECTORIES.intersection(path.relative_to(REPO_ROOT).parts)
    )


def self_check() -> None:
    """The patterns must find what they are for, or a green run means nothing."""
    assert link_targets('![a](docs/x.png) and [b](y.md#top "t")') == ["docs/x.png", "y.md#top"]
    assert link_targets('<img src="a.png" alt="x" width="48%"> <a href="b.pdf">') == ["a.png", "b.pdf"]
    assert link_targets("[web](https://example.org) [here](#status) `[code](no.md)`") == ["#status"]
    this_file = Path(__file__)
    assert link_problem(this_file, "no-such-file.md") == "no-such-file.md does not exist"
    assert link_problem(this_file, this_file.name + "#anything") is None  # anchors only in Markdown
    assert root_paths("see `pcb/gen/layout.py:check_placement` and `make test`") == ["pcb/gen/layout.py"]
    assert root_paths("`cad/exports/print/base.*` `gen/circuit.py` `docs/`") == []
    assert [n for n, _ in prose_lines("a\n```\nb\n```\nc")] == [1, 5]


def main() -> int:
    self_check()
    files = markdown_files()
    problems = [problem for markdown in files for problem in missing_in(markdown)]
    for problem in problems:
        print(f"check_docs: {problem}")
    if problems:
        return 1
    checked = sum(
        len(link_targets(line)) + len(root_paths(line))
        for markdown in files for _, line in prose_lines(markdown.read_text(encoding="utf-8"))
    )
    print(f"check_docs: {checked} paths in {len(files)} Markdown files exist")
    return 0


if __name__ == "__main__":
    sys.exit(main())
