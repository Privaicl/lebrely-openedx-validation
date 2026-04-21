"""Code transformations for the ablation.

Each condition defines a transformation applied to the body of the
Django model before it is passed to the classifier:

- C0: identity (original code, with `.. pii*` annotations).
- C1: strips the lines `.. pii:`, `.. no_pii:`, `.. pii_types:`,
  `.. pii_retirement:` from docstrings. Preserves the rest.
- C2: strips the entire docstring and `#` comments.
- C3: renames columns to `col_1, col_2, ...` preserving types and FKs.
"""

from __future__ import annotations

import re

from tree_sitter import Language, Node, Parser
from tree_sitter_python import language as python_language

from app.parsers.python_parser import PythonParser

CONDITIONS = ("c0", "c1", "c2", "c3")

PII_ANNOTATION_RE = re.compile(
    r"^\s*\.\.\s*(pii|no_pii|pii_types|pii_retirement)\b.*$",
    re.MULTILINE,
)

_parser: PythonParser | None = None


def _get_parser() -> PythonParser:
    global _parser
    if _parser is None:
        _parser = PythonParser()
    return _parser


def apply_c0(code: str) -> str:
    return code


def apply_c1(code: str) -> str:
    """Strip `.. pii*` annotation lines from docstrings."""
    return PII_ANNOTATION_RE.sub("", code)


def apply_c2(code: str) -> str:
    """Strip docstrings and comments via tree-sitter.

    Removes the first string-literal statement in each class/function body
    (the docstring) and all `#` comments. Preserves code, field names,
    types, FKs, help_text values, choices, etc.
    """
    return _get_parser().strip_comments_and_docstrings(code)


def _is_field_call(call_node: Node, source_bytes: bytes) -> bool:
    for c in call_node.children:
        if c.type in ("identifier", "attribute"):
            callee = source_bytes[c.start_byte : c.end_byte].decode(
                "utf-8", errors="replace"
            )
            simple = callee.split(".")[-1]
            return simple.endswith("Field") or simple in {
                "ForeignKey",
                "OneToOneField",
                "ManyToManyField",
            }
    return False


def _anonymize_field_names(code: str) -> str:
    """Rename LHS of Django field assignments to col_1, col_2, ... and
    keep references `self.<field>` in sync within the same class.

    Preserves: class name, field types, FK targets, help_text/choices
    strings, Meta attributes, method names, and top-level constants."""
    ts_lang = Language(python_language())
    parser = Parser(ts_lang)
    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)

    def node_text(n: Node) -> str:
        return source_bytes[n.start_byte : n.end_byte].decode("utf-8", errors="replace")

    class_node: Node | None = None
    for child in tree.root_node.children:
        if child.type == "class_definition":
            class_node = child
            break
    if class_node is None:
        return code

    body_node: Node | None = None
    for child in class_node.children:
        if child.type == "block":
            body_node = child
            break
    if body_node is None:
        return code

    name_map: dict[str, str] = {}
    lhs_ranges: list[tuple[int, int]] = []
    counter = 0

    for stmt in body_node.children:
        if stmt.type != "expression_statement":
            continue
        for sub in stmt.children:
            if sub.type != "assignment":
                continue
            left_node: Node | None = None
            right_call: Node | None = None
            for c in sub.children:
                if c.type == "identifier" and left_node is None:
                    left_node = c
                elif c.type == "call" and right_call is None:
                    right_call = c
            if left_node is None or right_call is None:
                continue
            if not _is_field_call(right_call, source_bytes):
                continue
            original_name = node_text(left_node)
            if original_name in name_map:
                continue
            counter += 1
            new_name = f"col_{counter}"
            name_map[original_name] = new_name
            lhs_ranges.append((left_node.start_byte, left_node.end_byte))

    if not name_map:
        return code

    self_ranges: list[tuple[int, int]] = []

    def walk_for_self_refs(node: Node) -> None:
        if node.type == "attribute":
            obj_node = node.child_by_field_name("object")
            attr_node = node.child_by_field_name("attribute")
            if (
                obj_node is not None
                and attr_node is not None
                and obj_node.type == "identifier"
                and attr_node.type == "identifier"
                and node_text(obj_node) == "self"
            ):
                attr_name = node_text(attr_node)
                if attr_name in name_map:
                    self_ranges.append((attr_node.start_byte, attr_node.end_byte))
        for c in node.children:
            walk_for_self_refs(c)

    walk_for_self_refs(class_node)

    replacements: list[tuple[int, int, str]] = []
    for start, end in lhs_ranges:
        original_name = source_bytes[start:end].decode("utf-8")
        replacements.append((start, end, name_map[original_name]))
    for start, end in self_ranges:
        original_name = source_bytes[start:end].decode("utf-8")
        replacements.append((start, end, name_map[original_name]))

    replacements.sort(key=lambda r: r[0], reverse=True)
    out = source_bytes
    for start, end, new_name in replacements:
        out = out[:start] + new_name.encode("utf-8") + out[end:]
    return out.decode("utf-8", errors="replace")


def apply_c3(code: str) -> str:
    """C3 = C2 + anonymize LHS field names to col_1, col_2, ... and all
    `self.<field>` references. Applied cumulatively from C2."""
    return _anonymize_field_names(apply_c2(code))


def apply_condition(code: str, condition: str) -> str:
    if condition == "c0":
        return apply_c0(code)
    if condition == "c1":
        return apply_c1(code)
    if condition == "c2":
        return apply_c2(code)
    if condition == "c3":
        return apply_c3(code)
    raise ValueError(f"Condition '{condition}' not implemented yet")


def output_filename(condition: str, temperature: float | None = None) -> str:
    """File name for the predictions of a condition/temperature combo.

    Defaults (temperature unset = API default ≈ 1.0):
      c0 -> openedx_predictions.json   (legacy name from the first baseline)
      cN -> openedx_predictions_cN.json

    Temperature = 0 (greedy, reproducible):
      c0 -> openedx_predictions_c0_t0.json
      cN -> openedx_predictions_cN_t0.json
    """
    if temperature == 0:
        return f"openedx_predictions_{condition}_t0.json"
    if condition == "c0":
        return "openedx_predictions.json"
    return f"openedx_predictions_{condition}.json"
