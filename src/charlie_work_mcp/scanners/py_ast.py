from __future__ import annotations

import ast

from ..models import HIGH, SourceFile, ToilItem, ToilKind, make_id

_SKIP_DECORATORS = {
    "pytest.mark.skip",
    "pytest.mark.skipif",
    "pytest.mark.xfail",
    "unittest.skip",
    "unittest.skipIf",
    "unittest.skipUnless",
    "skip",
    "skipif",
}
_FLAKY_DECORATORS = {"pytest.mark.flaky", "flaky"}
_SKIP_CALLS = {"pytest.skip", "pytest.xfail", "skipTest"}
_DEBUG_CALLS = {
    "breakpoint",
    "pdb.set_trace",
    "ipdb.set_trace",
    "pytest.set_trace",
    "IPython.embed",
    "ipdb.post_mortem",
}
_FLAG_READS = {
    "is_enabled",
    "isEnabled",
    "feature_enabled",
    "get_flag",
    "flag",
    "variation",
    "is_on",
}
_FLAG_DEF_CALLS = {"register_flag", "define_flag", "add_flag", "set_flag"}


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    return _dotted(target)


def _string_arg(node: ast.Call) -> str | None:
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.items: list[ToilItem] = []
        self.flag_reads: dict[str, tuple[str, int, str]] = {}
        self.flag_defs: set[str] = set()

    def _add(self, kind: ToilKind, line: int, title: str, evidence: str, severity: int) -> None:
        self.items.append(
            ToilItem(
                id=make_id(kind, self.path, line, evidence),
                kind=kind,
                path=self.path,
                line=line,
                title=title,
                evidence=evidence[:200],
                severity=severity,
                effort=2,
                confidence=HIGH,
            )
        )

    def _check_decorators(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            name = _decorator_name(decorator)
            if name in _SKIP_DECORATORS:
                self._add(
                    ToilKind.skipped_test,
                    decorator.lineno,
                    "Skipped test quietly rotting in the suite",
                    f"@{name}",
                    3,
                )
            elif name in _FLAKY_DECORATORS:
                self._add(
                    ToilKind.flaky_test,
                    decorator.lineno,
                    "Flaky test papered over with retries",
                    f"@{name}",
                    4,
                )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _dotted(node.func)
        short = name.rsplit(".", 1)[-1]
        if name in _DEBUG_CALLS or (short == "set_trace"):
            self._add(
                ToilKind.debug_leftover,
                node.lineno,
                f"{name}() left in the code",
                f"{name}()",
                2,
            )
        elif name in _SKIP_CALLS or short == "skipTest":
            self._add(
                ToilKind.skipped_test,
                node.lineno,
                "Runtime skip left in a test",
                f"{name}()",
                3,
            )
        elif short in _FLAG_READS:
            literal = _string_arg(node)
            if literal:
                self.flag_reads.setdefault(literal, (self.path, node.lineno, name))
        elif short in _FLAG_DEF_CALLS:
            literal = _string_arg(node)
            if literal:
                self.flag_defs.add(literal)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=False):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, bool)
            ):
                self.flag_defs.add(key.value)
        self.generic_visit(node)


def _visit(file: SourceFile) -> _Visitor | None:
    try:
        tree = ast.parse(file.text, filename=file.path)
    except (SyntaxError, ValueError):
        return None
    visitor = _Visitor(file.path)
    visitor.visit(tree)
    return visitor


def scan_python(file: SourceFile) -> list[ToilItem]:
    visitor = _visit(file)
    return visitor.items if visitor else []


def collect_flags(
    file: SourceFile,
) -> tuple[dict[str, tuple[str, int, str]], set[str]]:
    visitor = _visit(file)
    if not visitor:
        return {}, set()
    return visitor.flag_reads, visitor.flag_defs
