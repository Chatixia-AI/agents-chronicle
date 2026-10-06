"""The MIT core must work without ee/ (Chronicle Enterprise License): no module in src/chronicle may import it."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "chronicle"


def test_core_never_imports_ee():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders += [f"{path.relative_to(SRC)}: {n}" for n in names if n.split(".")[0] == "chronicle_ee"]
    assert not offenders, offenders
