"""Every module-level name the sweep driver dereferences must be bound.

2026-09-12: ``collect_metrics`` called ``provenance.engine_label`` without importing
``provenance``; nothing failed until a 45-minute validation job crashed on its last line.
``unittest`` never executes that path, so this test walks the AST instead.
"""

import ast
import builtins
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestSweepDriverNamesResolve(unittest.TestCase):
    def test_every_attribute_base_is_a_module_global_or_local(self):
        src = (ROOT / "run_experiments.py").read_text()
        tree = ast.parse(src)
        bound = set(dir(builtins))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    bound.add((a.asname or a.name).split(".")[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(node.name)
                if not isinstance(node, ast.ClassDef):
                    for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                        bound.add(arg.arg)
                    if node.args.vararg:
                        bound.add(node.args.vararg.arg)
                    if node.args.kwarg:
                        bound.add(node.args.kwarg.arg)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                bound.add(node.id)
            elif isinstance(node, (ast.For, ast.comprehension)):
                for t in ast.walk(node.target):
                    if isinstance(t, ast.Name):
                        bound.add(t.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound.add(node.name)
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                for t in ast.walk(node.optional_vars):
                    if isinstance(t, ast.Name):
                        bound.add(t.id)
        unbound = sorted(
            {
                f"{n.value.id}.{n.attr} (line {n.lineno})"
                for n in ast.walk(tree)
                if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id not in bound
            }
        )
        self.assertEqual(unbound, [], f"unbound names dereferenced: {unbound}")


if __name__ == "__main__":
    unittest.main()
