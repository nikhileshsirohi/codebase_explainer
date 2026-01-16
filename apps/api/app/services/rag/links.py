from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional

NOISE_CALLS = {
    "len", "print", "str", "int", "float", "dict", "list", "set", "tuple",
    "max", "min", "sum", "sorted", "range", "enumerate", "zip",
    "get", "items", "keys", "values",
}
NOISE_ATTRS = {"append", "extend", "split", "strip", "lower", "upper", "join"}

@dataclass
class LinkHint:
    kind: str  # "calls" | "imports"
    name: str
    extra: Optional[str] = None


def extract_python_links(code: str) -> List[LinkHint]:
    """
    Best-effort extraction of called function names + imported names.
    Works on partial snippets; returns [] if parse fails.
    """
    try:
        tree = ast.parse(code)
    except Exception:
        return []

    hints: List[LinkHint] = []

    # imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                hints.append(LinkHint(kind="imports", name=a.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                full = f"{mod}.{a.name}" if mod else a.name
                hints.append(LinkHint(kind="imports", name=full))

    # calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                name = fn.id
                if name not in NOISE_CALLS:
                    hints.append(LinkHint(kind="calls", name=name))
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
                if name not in NOISE_ATTRS:
                    hints.append(LinkHint(kind="calls", name=name))

    return hints