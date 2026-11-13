"""KiCad s-expressions: text to nested lists and back. Pure Python.

An atom is a str. A quoted string keeps its quotes, so `"R"` and `R` stay different and the text
written back is the text that was read.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text: str) -> list:
    """The one top-level list in the text."""
    stack: list[list] = [[]]
    for token in _TOKEN.findall(text):
        if token == "(":
            stack.append([])
        elif token == ")":
            assert len(stack) > 1, "unbalanced ')'"
            closed = stack.pop()
            stack[-1].append(closed)
        else:
            stack[-1].append(token)
    assert len(stack) == 1, "unbalanced '('"
    assert len(stack[0]) == 1, "expected exactly one top-level list"
    return stack[0][0]


def dump(node) -> str:
    if isinstance(node, str):
        return node
    return "(" + " ".join(dump(child) for child in node) + ")"


def quoted(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def unquoted(atom: str) -> str:
    if atom.startswith('"'):
        return re.sub(r"\\(.)", r"\1", atom[1:-1])
    return atom


def children(node: list, head: str) -> list[list]:
    """The direct child lists that start with this word."""
    return [child for child in node[1:] if isinstance(child, list) and child and child[0] == head]


def child(node: list, head: str) -> list | None:
    found = children(node, head)
    return found[0] if found else None
