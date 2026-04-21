"""
Script to run the classifier over the unique tables that appear in the
sample.

For each table:
  - Extracts the full Django model code (from openedx_models.json).
  - Passes all model fields to the classifier to preserve the table's
    internal coherence.
  - Calls `classify_table()` with `OPENEDX_PROMPT` and
    `data_subjects=["USUARIO", "SYSTEM"]`.

Output: `openedx_predictions.json` — dict keyed by class_name with:
  {
    "table_semantic_summary": "...",
    "fields": [{"name": ..., "category": ..., "data_subject": ..., "reasoning": ...}],
    "cost_usd": ..,
    "source_file": "...",
    "django_app": "..."
  }

Resumable: if a table is already in predictions.json it is skipped. To
rerun from scratch, delete the file (or pass --clean).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from pathlib import Path

# Haiku 4.5 doesn't support the `effort` param. Scrub any harness vars that
# would cause the bundled CLI to forward it.
for _var in ("CLAUDE_CODE_EFFORT_LEVEL",):
    os.environ.pop(_var, None)


def _configure_temperature(temperature: float | None) -> None:
    """Inject temperature into the API request body via CLAUDE_CODE_EXTRA_BODY.

    The bundled Claude Code CLI does not expose --temperature. This env var
    lets us add arbitrary body params to the API call. Must be set BEFORE
    the SDK spawns the subprocess.
    """
    if temperature is None:
        os.environ.pop("CLAUDE_CODE_EXTRA_BODY", None)
        return
    os.environ["CLAUDE_CODE_EXTRA_BODY"] = json.dumps({"temperature": float(temperature)})

# Private Privai imports (see README "Qué NO hay" / "What is NOT here"):
# - `app.*` is the Lebrely classifier itself.
# - `openedx_prompt.OPENEDX_PROMPT` is the domain prompt, also a Privai product.
# Both are published via name only; their contents are not in this repo.
from app.agents.classification import ClassificationConfig, classify_table
from app.taxonomy.fides import DEFAULT_TAXONOMY, filter_deprecated
from openedx_prompt import OPENEDX_PROMPT

# Local sibling modules.
from ablation import CONDITIONS, apply_condition, output_filename


REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV = REPO_ROOT / "data" / "openedx_sample.csv"
MODELS_JSON = REPO_ROOT / "data" / "openedx_models.json"
PREDICTIONS_DIR = REPO_ROOT / "classification"
RUN_LOG = PREDICTIONS_DIR / "openedx_predictions_run.log"

OPENEDX_REPO = os.environ.get("OPENEDX_REPO", "./openedx-platform")
DATA_SUBJECTS = ["USUARIO", "SYSTEM"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(RUN_LOG), logging.StreamHandler()],
)
logger = logging.getLogger("openedx.agent")


def load_sampled_keys() -> list[tuple[str, str]]:
    """Return unique (django_app, table_name) pairs from the sample CSV,
    preserving first-seen order."""
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for row in csv.DictReader(SAMPLE_CSV.open()):
        key = (row["django_app"], row["table_name"])
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def load_models_by_class(sampled_keys: list[tuple[str, str]]) -> dict[str, dict]:
    """Load openedx_models.json, return dict keyed by class_name for the
    sampled tables. Errors loudly if a sampled table is not found."""
    all_models = json.loads(MODELS_JSON.read_text())
    by_class: dict[str, dict] = {}
    for app, class_name in sampled_keys:
        # models_out is keyed as "{scope}.{app}.{class_name}"
        matches = [
            m
            for k, m in all_models.items()
            if m["class_name"] == class_name and m["django_app"] == app
        ]
        if not matches:
            raise RuntimeError(
                f"Sampled table {app}.{class_name} not found in {MODELS_JSON}"
            )
        by_class[class_name] = matches[0]
    return by_class


def load_existing_predictions(predictions_path: Path) -> dict:
    if predictions_path.exists():
        return json.loads(predictions_path.read_text())
    return {}


def write_predictions(predictions: dict, predictions_path: Path) -> None:
    tmp = predictions_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(predictions, indent=2))
    tmp.replace(predictions_path)


async def classify_one(model_info: dict, taxonomy, condition: str) -> tuple[dict, float]:
    columns = [f["name"] for f in model_info["fields"]]
    transformed_code = apply_condition(model_info["code"], condition)
    config = ClassificationConfig(
        taxonomy=taxonomy,
        table_name=model_info["class_name"],
        code=transformed_code,
        domain_prompt=OPENEDX_PROMPT,
        data_subjects=DATA_SUBJECTS,
        project_path=OPENEDX_REPO,
        code_file_path=str(Path(OPENEDX_REPO) / model_info["source_file"]),
    )

    result, cost = await classify_table(config, columns)

    return (
        {
            "table_semantic_summary": result.table_semantic_summary,
            "fields": [
                {
                    "name": f.name,
                    "category": f.category,
                    "data_subject": f.data_subject,
                    "reasoning": f.reasoning,
                }
                for f in result.fields
            ],
        },
        cost,
    )


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--condition",
        default="c0",
        choices=CONDITIONS,
        help="Ablation condition. c0=original, c1=no PII annotations, etc.",
    )
    ap.add_argument(
        "--clean",
        action="store_true",
        help="Delete the condition's predictions file and start from scratch.",
    )
    ap.add_argument(
        "--only",
        default=None,
        help="Classify only one table (class_name). Useful for smoke tests.",
    )
    ap.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Temperature passed to the model via CLAUDE_CODE_EXTRA_BODY. "
             "Default = unset (SDK/API default ~1.0). Use 0 for "
             "reproducible runs (greedy decoding).",
    )
    args = ap.parse_args()

    _configure_temperature(args.temperature)

    predictions_path = PREDICTIONS_DIR / output_filename(args.condition, args.temperature)

    if args.clean and predictions_path.exists():
        predictions_path.unlink()
        logger.info(f"Deleted {predictions_path}")

    sampled_keys = load_sampled_keys()
    models_by_class = load_models_by_class(sampled_keys)
    predictions = load_existing_predictions(predictions_path)
    taxonomy = filter_deprecated(DEFAULT_TAXONOMY)

    to_process = [
        (app, cls) for app, cls in sampled_keys if cls not in predictions
    ]
    if args.only:
        to_process = [(app, cls) for app, cls in to_process if cls == args.only]
        if not to_process:
            logger.info(f"'{args.only}' is already in predictions or does not exist in sample")
            return

    logger.info(
        f"Condition: {args.condition}  temperature: {args.temperature}  "
        f"-> {predictions_path.name}"
    )
    logger.info(
        f"Sample: {len(sampled_keys)} unique tables. "
        f"Already classified: {len(predictions)}. "
        f"To process now: {len(to_process)}."
    )

    total_cost = sum(p.get("cost_usd", 0.0) for p in predictions.values())
    failed: list[str] = []

    for idx, (app, class_name) in enumerate(to_process, start=1):
        model_info = models_by_class[class_name]
        logger.info(f"[{idx}/{len(to_process)}] {app}.{class_name} "
                    f"({len(model_info['fields'])} fields)")
        try:
            prediction, cost = await classify_one(model_info, taxonomy, args.condition)
        except Exception as exc:
            logger.error(f"  ✗ FAIL {class_name}: {exc}")
            failed.append(class_name)
            continue

        predictions[class_name] = {
            **prediction,
            "cost_usd": cost,
            "django_app": app,
            "source_file": model_info["source_file"],
            "n_fields": len(model_info["fields"]),
            "condition": args.condition,
            "temperature": args.temperature,
        }
        total_cost += cost
        write_predictions(predictions, predictions_path)
        logger.info(f"  ✓ ${cost:.4f}  total=${total_cost:.4f}")

    logger.info("=" * 60)
    logger.info(
        f"Done. Classified {len(predictions)}/{len(sampled_keys)} sampled tables. "
        f"Failed: {len(failed)} {failed if failed else ''}. "
        f"Total cost: ${total_cost:.4f}."
    )


if __name__ == "__main__":
    asyncio.run(main())
