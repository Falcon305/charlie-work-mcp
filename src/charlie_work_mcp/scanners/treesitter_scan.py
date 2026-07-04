from __future__ import annotations

from functools import lru_cache

from ..models import HIGH, SourceFile, ToilItem, ToilKind, make_id

_EXT_LANG = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
}

_TEST_OBJECTS = {"it", "describe", "test", "context", "suite"}
_SKIP_IDENTS = {"xit", "xdescribe", "xtest", "xcontext"}
_FOCUS_IDENTS = {"fit", "fdescribe", "ftest", "iit", "ddescribe"}
_GO_SKIP_METHODS = {"skip", "skipf", "skipnow"}

_MEMBER_QUERY = """
(call_expression
  function: (member_expression
    object: (identifier) @obj
    property: (property_identifier) @prop)) @call
"""
_IDENT_QUERY = "(call_expression function: (identifier) @fn) @call"
_DEBUGGER_QUERY = "(debugger_statement) @dbg"
_GO_QUERY = """
(call_expression
  function: (selector_expression field: (field_identifier) @field)) @call
"""


@lru_cache(maxsize=8)
def _parser(language: str):
    try:
        from tree_sitter import Parser
        from tree_sitter_language_pack import get_language
    except ImportError:
        return None
    try:
        return Parser(get_language(language))
    except Exception:
        return None


@lru_cache(maxsize=32)
def _query(language: str, source: str):
    try:
        from tree_sitter import Query
        from tree_sitter_language_pack import get_language
    except ImportError:
        return None
    try:
        return Query(get_language(language), source)
    except Exception:
        return None


def _matches(language: str, source: str, root):
    query = _query(language, source)
    if not query:
        return []
    try:
        from tree_sitter import QueryCursor
    except ImportError:
        return []
    return QueryCursor(query).matches(root)


def _one(capture: dict, name: str):
    nodes = capture.get(name)
    return nodes[0] if nodes else None


def _text(node) -> str:
    return node.text.decode("utf-8", "ignore")


def _emit(path: str, kind: ToilKind, node, title: str, evidence: str, severity: int) -> ToilItem:
    line = node.start_point[0] + 1
    return ToilItem(
        id=make_id(kind, path, line, evidence),
        kind=kind,
        path=path,
        line=line,
        line_end=node.end_point[0] + 1,
        col=node.start_point[1] + 1,
        title=title,
        evidence=evidence[:200],
        severity=severity,
        effort=2,
        confidence=HIGH,
    )


def _scan_js(path: str, language: str, root) -> list[ToilItem]:
    items: list[ToilItem] = []
    for _, cap in _matches(language, _MEMBER_QUERY, root):
        obj, prop, call = _one(cap, "obj"), _one(cap, "prop"), _one(cap, "call")
        if not (obj and prop and call):
            continue
        obj_name, prop_name = _text(obj), _text(prop)
        if obj_name == "console" and prop_name == "log":
            items.append(
                _emit(path, ToilKind.debug_leftover, call, "console.log left in the code", "console.log(", 2)
            )
        elif obj_name in _TEST_OBJECTS and prop_name == "skip":
            items.append(
                _emit(
                    path,
                    ToilKind.skipped_test,
                    call,
                    "Skipped test quietly rotting in the suite",
                    f"{obj_name}.skip",
                    3,
                )
            )
        elif obj_name in _TEST_OBJECTS and prop_name == "only":
            items.append(
                _emit(
                    path,
                    ToilKind.focused_test,
                    call,
                    "Focused test left in — the rest of the suite isn't running",
                    f"{obj_name}.only",
                    4,
                )
            )
    for _, cap in _matches(language, _IDENT_QUERY, root):
        fn, call = _one(cap, "fn"), _one(cap, "call")
        if not (fn and call):
            continue
        name = _text(fn)
        if name in _SKIP_IDENTS:
            items.append(
                _emit(path, ToilKind.skipped_test, call, "Skipped test quietly rotting in the suite", name, 3)
            )
        elif name in _FOCUS_IDENTS:
            items.append(
                _emit(
                    path,
                    ToilKind.focused_test,
                    call,
                    "Focused test left in — the rest of the suite isn't running",
                    name,
                    4,
                )
            )
    for _, cap in _matches(language, _DEBUGGER_QUERY, root):
        node = _one(cap, "dbg")
        if node:
            items.append(
                _emit(path, ToilKind.debug_leftover, node, "debugger statement left in the code", "debugger", 2)
            )
    return items


def _scan_go(path: str, root) -> list[ToilItem]:
    items: list[ToilItem] = []
    for _, cap in _matches("go", _GO_QUERY, root):
        field, call = _one(cap, "field"), _one(cap, "call")
        if field and call and _text(field).lower() in _GO_SKIP_METHODS:
            items.append(
                _emit(path, ToilKind.skipped_test, call, "Skipped test left in the suite", _text(field), 3)
            )
    return items


def language_for(path: str) -> str | None:
    lowered = path.lower()
    for ext, language in _EXT_LANG.items():
        if lowered.endswith(ext):
            return language
    return None


def scan_file(file: SourceFile) -> list[ToilItem]:
    language = language_for(file.path)
    if not language:
        return []
    parser = _parser(language)
    if not parser:
        return []
    try:
        tree = parser.parse(file.text.encode("utf-8", "ignore"))
    except Exception:
        return []
    if language == "go":
        return _scan_go(file.path, tree.root_node)
    return _scan_js(file.path, language, tree.root_node)
