from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SymbolHit:
    kind: str  # "function" | "class"
    name: str
    lineno: int
    end_lineno: Optional[int]


def extract_python_symbols(code: str) -> List[SymbolHit]:
    """
    Best-effort symbol extraction from a Python snippet.
    Works even if snippet is not a full file (may fail -> returns []).
    """
    try:
        tree = ast.parse(code)
    except Exception:
        return []

    hits: List[SymbolHit] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            hits.append(
                SymbolHit(
                    kind="function",
                    name=node.name,
                    lineno=getattr(node, "lineno", 0) or 0,
                    end_lineno=getattr(node, "end_lineno", None),
                )
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            hits.append(
                SymbolHit(
                    kind="function",
                    name=node.name,
                    lineno=getattr(node, "lineno", 0) or 0,
                    end_lineno=getattr(node, "end_lineno", None),
                )
            )
        elif isinstance(node, ast.ClassDef):
            hits.append(
                SymbolHit(
                    kind="class",
                    name=node.name,
                    lineno=getattr(node, "lineno", 0) or 0,
                    end_lineno=getattr(node, "end_lineno", None),
                )
            )
    return hits