"""
Script to build an inventory of Open edX models.

Walks the openedx-platform repo, detects Django classes (classes with at
least one field of the form `xxx = (models.)?XxxField(...)`) and
produces:

- openedx_inventory.csv: one row per model (table_name, django_app,
  model_class, n_fields, source_file, source_lines).
- openedx_models.json: full class code + metadata, keyed by
  "{app}.{class_name}". This is the input to the classifier.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

from tree_sitter import Language, Node, Parser
from tree_sitter_python import language as python_language


OPENEDX_ROOT = Path(os.environ.get("OPENEDX_REPO", "./openedx-platform"))
OUTPUT_DIR = Path(__file__).parent


FIELD_TYPE_SQL: dict[str, str] = {
    "AutoField": "int",
    "BigAutoField": "bigint",
    "BigIntegerField": "bigint",
    "BinaryField": "binary",
    "BooleanField": "bool",
    "CharField": "varchar",
    "CountryField": "varchar",  # django-countries
    "CourseKeyField": "varchar",  # opaque_keys
    "DateField": "date",
    "DateTimeField": "timestamp",
    "DecimalField": "decimal",
    "DurationField": "duration",
    "EmailField": "varchar",
    "FileField": "file",
    "FilePathField": "varchar",
    "FloatField": "float",
    "ForeignKey": "fk",
    "GenericIPAddressField": "varchar",
    "IPAddressField": "varchar",
    "ImageField": "file",
    "IntegerField": "int",
    "JSONField": "json",
    "LearningContextKeyField": "varchar",  # opaque_keys
    "ManyToManyField": "m2m",
    "NullBooleanField": "bool",
    "OneToOneField": "fk",
    "PositiveBigIntegerField": "bigint",
    "PositiveIntegerField": "int",
    "PositiveSmallIntegerField": "smallint",
    "SlugField": "varchar",
    "SmallAutoField": "smallint",
    "SmallIntegerField": "smallint",
    "StatusField": "varchar",  # django-model-utils
    "TextField": "text",
    "TimeField": "time",
    "URLField": "varchar",
    "UUIDField": "uuid",
    "UsageKeyField": "varchar",  # opaque_keys
}

EXCLUDE_PATH_SEGMENTS = {
    "tests",
    "test",
    "testing",
    "__pycache__",
    "node_modules",
    "migrations",
    "features",
    "docs",
    "scripts",
}


def find_model_files(root: Path) -> list[Path]:
    """Find candidate Django model source files (models.py and models/*.py under djangoapps)."""
    results: list[Path] = []
    for path in root.rglob("*.py"):
        parts_lower = {p.lower() for p in path.parts}
        if parts_lower & EXCLUDE_PATH_SEGMENTS:
            continue
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
        if "djangoapps" not in path.parts:
            continue
        if path.name == "models.py":
            results.append(path)
        elif path.parent.name == "models" and path.name != "__init__.py":
            results.append(path)
    return sorted(results)


def derive_django_app(path: Path, root: Path) -> str:
    """`common/djangoapps/student/models/user.py` -> `student`."""
    rel = path.relative_to(root)
    parts = rel.parts
    for i, p in enumerate(parts):
        if p == "djangoapps" and i + 1 < len(parts):
            return parts[i + 1]
    return "unknown"


def derive_django_app_scope(path: Path, root: Path) -> str:
    """Top-level scope: `common`, `lms`, `cms`, `openedx`."""
    rel = path.relative_to(root)
    return rel.parts[0] if rel.parts else "unknown"


def _node_text(node: Node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _extract_call_callee(call_node: Node, source_bytes: bytes) -> str | None:
    """For a `call` node, return the textual callee (e.g. `models.CharField` or `CourseKeyField`)."""
    for child in call_node.children:
        if child.type in ("identifier", "attribute"):
            return _node_text(child, source_bytes)
    return None


def _is_field_callee(callee: str) -> bool:
    simple = callee.split(".")[-1]
    return simple.endswith("Field") or simple in {"ForeignKey", "OneToOneField", "ManyToManyField"}


def extract_fields_from_body(body_node: Node, source_bytes: bytes) -> list[dict]:
    """Walk the direct children of a class body and pull out Django field assignments."""
    fields: list[dict] = []
    seen_names: set[str] = set()
    for child in body_node.children:
        if child.type != "expression_statement":
            continue
        for sub in child.children:
            if sub.type != "assignment":
                continue
            left_name: str | None = None
            right_call: Node | None = None
            for c in sub.children:
                if c.type == "identifier" and left_name is None:
                    left_name = _node_text(c, source_bytes)
                elif c.type == "call" and right_call is None:
                    right_call = c
            if not (left_name and right_call):
                continue
            callee = _extract_call_callee(right_call, source_bytes)
            if not callee or not _is_field_callee(callee):
                continue
            if left_name in seen_names:
                continue
            seen_names.add(left_name)
            simple = callee.split(".")[-1]
            fields.append(
                {
                    "name": left_name,
                    "django_type": simple,
                    "sql_type_inferred": FIELD_TYPE_SQL.get(simple, "other"),
                }
            )
    return fields


def extract_classes(file_path: Path, parser: Parser) -> list[dict]:
    source_bytes = file_path.read_bytes()
    try:
        tree = parser.parse(source_bytes)
    except Exception as exc:  # pragma: no cover
        print(f"Failed to parse {file_path}: {exc}", file=sys.stderr)
        return []

    results: list[dict] = []

    def walk(node: Node) -> None:
        if node.type == "class_definition":
            class_name: str | None = None
            body_node: Node | None = None
            for child in node.children:
                if child.type == "identifier" and class_name is None:
                    class_name = _node_text(child, source_bytes)
                elif child.type == "block":
                    body_node = child
            if class_name and body_node is not None:
                fields = extract_fields_from_body(body_node, source_bytes)
                if fields:
                    results.append(
                        {
                            "class_name": class_name,
                            "fields": fields,
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "code": _node_text(node, source_bytes),
                        }
                    )
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return results


def main() -> None:
    parser = Parser(Language(python_language()))

    model_files = find_model_files(OPENEDX_ROOT)
    print(f"Scanning {len(model_files)} candidate model files under {OPENEDX_ROOT}")

    inventory_rows: list[dict] = []
    models_out: dict[str, dict] = {}

    for f in model_files:
        app = derive_django_app(f, OPENEDX_ROOT)
        scope = derive_django_app_scope(f, OPENEDX_ROOT)
        rel_source = str(f.relative_to(OPENEDX_ROOT))
        for cls in extract_classes(f, parser):
            key = f"{scope}.{app}.{cls['class_name']}"
            if key in models_out:
                # Same class seen twice (re-export across files). Keep first.
                continue
            inventory_rows.append(
                {
                    "table_name": cls["class_name"],
                    "django_app": app,
                    "scope": scope,
                    "model_class": cls["class_name"],
                    "n_fields": len(cls["fields"]),
                    "source_file": rel_source,
                    "source_lines": f"{cls['start_line']}-{cls['end_line']}",
                }
            )
            models_out[key] = {
                "class_name": cls["class_name"],
                "django_app": app,
                "scope": scope,
                "source_file": rel_source,
                "start_line": cls["start_line"],
                "end_line": cls["end_line"],
                "fields": cls["fields"],
                "code": cls["code"],
            }

    csv_path = OUTPUT_DIR / "openedx_inventory.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "table_name",
                "django_app",
                "scope",
                "model_class",
                "n_fields",
                "source_file",
                "source_lines",
            ],
        )
        writer.writeheader()
        writer.writerows(inventory_rows)

    json_path = OUTPUT_DIR / "openedx_models.json"
    with json_path.open("w") as f:
        json.dump(models_out, f, indent=2)

    apps_count: dict[str, int] = {}
    for row in inventory_rows:
        apps_count[row["django_app"]] = apps_count.get(row["django_app"], 0) + 1
    top_apps = sorted(apps_count.items(), key=lambda x: x[1], reverse=True)

    print(f"\nWrote {len(inventory_rows)} models to {csv_path.relative_to(Path.cwd())}")
    print(f"Wrote model code to {json_path.relative_to(Path.cwd())}")
    print(f"\nTop 15 apps by model count:")
    for app, count in top_apps[:15]:
        print(f"  {count:4d}  {app}")
    print(f"\nTotal django apps with models: {len(apps_count)}")


if __name__ == "__main__":
    main()
