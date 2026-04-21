"""
Script to stratify and sample tables from Open edX.

What it does:
- Assigns each inventory model to a stratum via APP_TO_STRATUM.
- Fixes quotas of 5 tables, each with at least 4 fields, per stratum.
- Stratified random sampling with `random.sample(seed=42)`.

Output: `openedx_sample.csv` with `stratum | django_app | table_name |
field_name | django_type | sql_type_inferred | source_file`.
"""

from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

INPUT_CSV = Path(__file__).parent / "openedx_inventory.csv"
INPUT_JSON = Path(__file__).parent / "openedx_models.json"
OUTPUT_CSV = Path(__file__).parent / "openedx_sample.csv"

SEED = 42
TABLES_PER_STRATUM = 5
FIELDS_PER_TABLE = 4

# App -> stratum. Apps not listed fall into "operational".
APP_TO_STRATUM: dict[str, str] = {
    # Identity/profile
    "student": "identity",
    "user_api": "identity",
    "third_party_auth": "identity",
    "external_user_ids": "identity",
    "user_tours": "identity",
    # Academic/performance
    "courseware": "academic",
    "certificates": "academic",
    "credit": "academic",
    "grades": "academic",
    "program_enrollments": "academic",
    "course_modes": "academic",
    "entitlements": "academic",
    "course_goals": "academic",
    # Content/communication
    "bulk_email": "content",
    "django_comment_common": "content",
    "discussions": "content",
    "notifications": "content",
    "bookmarks": "content",
    "teams": "content",
    "survey": "content",
    # Verification
    "verify_student": "verification",
    "agreements": "verification",
}

STRATUM_ORDER = ["identity", "academic", "content", "verification", "operational"]


def load_inventory() -> list[dict]:
    import json

    rows = list(csv.DictReader(INPUT_CSV.open()))
    models_json = json.loads(INPUT_JSON.read_text())
    by_key: dict[tuple[str, str], dict] = {}
    for key, info in models_json.items():
        by_key[(info["django_app"], info["class_name"])] = info
    for r in rows:
        info = by_key.get((r["django_app"], r["model_class"]))
        r["fields_detail"] = info["fields"] if info else []
    return rows


def assign_strata(rows: list[dict]) -> None:
    for r in rows:
        r["stratum"] = APP_TO_STRATUM.get(r["django_app"], "operational")


def sample_stratum(
    stratum_rows: list[dict], rng: random.Random, stratum_name: str
) -> list[dict]:
    eligible = [r for r in stratum_rows if len(r["fields_detail"]) >= FIELDS_PER_TABLE]
    if len(eligible) < TABLES_PER_STRATUM:
        raise RuntimeError(
            f"Stratum '{stratum_name}' has only {len(eligible)} tables with >= "
            f"{FIELDS_PER_TABLE} fields. {TABLES_PER_STRATUM} are required."
        )

    picked_tables = rng.sample(eligible, TABLES_PER_STRATUM)

    sampled: list[dict] = []
    for table in picked_tables:
        picked_fields = rng.sample(table["fields_detail"], FIELDS_PER_TABLE)
        for fld in picked_fields:
            sampled.append(
                {
                    "stratum": stratum_name,
                    "django_app": table["django_app"],
                    "table_name": table["table_name"],
                    "field_name": fld["name"],
                    "django_type": fld["django_type"],
                    "sql_type_inferred": fld["sql_type_inferred"],
                    "source_file": table["source_file"],
                }
            )
    return sampled


def main() -> None:
    rows = load_inventory()
    assign_strata(rows)

    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_stratum[r["stratum"]].append(r)

    print(f"Models per stratum:")
    for est in STRATUM_ORDER:
        n = len(by_stratum[est])
        eligible = sum(1 for r in by_stratum[est] if len(r["fields_detail"]) >= FIELDS_PER_TABLE)
        print(f"  {est:15s}  total={n:4d}  eligible(>= {FIELDS_PER_TABLE} fields)={eligible}")

    rng = random.Random(SEED)
    all_sampled: list[dict] = []
    for est in STRATUM_ORDER:
        sampled = sample_stratum(by_stratum[est], rng, est)
        all_sampled.extend(sampled)

    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "stratum",
                "django_app",
                "table_name",
                "field_name",
                "django_type",
                "sql_type_inferred",
                "source_file",
            ],
        )
        writer.writeheader()
        writer.writerows(all_sampled)

    print(f"\nWrote {len(all_sampled)} sampled fields to {OUTPUT_CSV.relative_to(Path.cwd())}")
    print(f"(seed={SEED}, {TABLES_PER_STRATUM} tables x {FIELDS_PER_TABLE} fields per stratum)")

    print(f"\nSampled tables per stratum:")
    for est in STRATUM_ORDER:
        stratum_rows = [r for r in all_sampled if r["stratum"] == est]
        tables = sorted({r["table_name"] for r in stratum_rows})
        print(f"  {est:15s}  {tables}")


if __name__ == "__main__":
    main()
