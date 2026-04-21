"""
Script to compare manual classification (golden) vs automatic
predictions for a scenario. Default: C0 T=0.

Scope: the 133 fields across the 25 sampled tables.

Metrics:
  - Global accuracy: exact match (subject + category), category-only,
    subject-only.
  - Accuracy by stratum (5 values).
  - By sensitivity level (canonical definition in
    `sensitivity_levels.py`): correct, false positives
    (over-classification), false negatives (under-classification) and
    same-sensitivity errors.
  - Per-category one-vs-rest: support, TP, cat_FP, cat_FN, precision,
    recall, F1. `cat_FP` / `cat_FN` are NOT the sensitivity FP/FN; they
    are per-category one-vs-rest counts used for precision/recall/F1.
  - Row-normalized confusion matrix on category.
  - Per-category error examples.

Output (under `reports/`):
  - validation_report.md
  - validation_confusion_matrix_<scenario>.png

Usage:
  python scripts/openedx/compare_and_evaluate.py
  python scripts/openedx/compare_and_evaluate.py --predictions openedx_predictions_c1_t0.json
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from sensitivity_levels import UNKNOWN, level_of

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
PRED_DIR = REPO_ROOT / "classification"
SAMPLE_CSV = REPO_ROOT / "data" / "openedx_sample.csv"
OUTPUT_DIR = REPO_ROOT / "reports"

MANUAL_JSON = PRED_DIR / "openedx_manual_classification.json"
DEFAULT_PREDICTIONS = PRED_DIR / "openedx_predictions_c0_t0.json"

STRATUM_ORDER = ["identity", "academic", "content", "verification", "operational"]
CONDITIONS_ORDERED = ["c0", "c1", "c2", "c3"]


def derive_condition(pred_path: Path) -> str:
    """Extract 'c0'/'c1'/'c2'/'c3' from a path like
    .../openedx_predictions_c1_t0.json."""
    stem = pred_path.stem  # openedx_predictions_c1_t0
    for part in stem.split("_"):
        if part in CONDITIONS_ORDERED:
            return part
    return stem


def derive_output_paths(pred_path: Path) -> tuple[Path, Path]:
    cond = derive_condition(pred_path)
    return (
        OUTPUT_DIR / f"validation_report_{cond}.md",
        OUTPUT_DIR / f"validation_confusion_matrix_{cond}.png",
    )


def build_table_to_stratum() -> dict[str, str]:
    """Map table_name -> stratum from the stratified sample CSV."""
    m: dict[str, str] = {}
    for row in csv.DictReader(SAMPLE_CSV.open()):
        m[row["table_name"]] = row["stratum"]
    return m


def load_manual_golden(table_to_stratum: dict[str, str]) -> list[dict]:
    """Read manual classification JSON and flatten into per-field rows."""
    raw = json.loads(MANUAL_JSON.read_text())
    out: list[dict] = []
    for table_name, info in raw.items():
        if table_name == "run_data":
            continue
        stratum = table_to_stratum.get(table_name, "unknown")
        for f in info["fields"]:
            out.append(
                {
                    "stratum": stratum,
                    "table_name": table_name,
                    "field_name": f["name"],
                    "category": f["category"],
                    "data_subject": f["data_subject"],
                }
            )
    return out


def load_predictions(path: Path) -> dict[tuple[str, str], dict]:
    """{(table_name, field_name): {category, data_subject, reasoning}}.

    Skips the `run_data` meta entry at the top of the JSON.
    """
    raw = json.loads(path.read_text())
    out: dict[tuple[str, str], dict] = {}
    for table_name, table_pred in raw.items():
        if table_name == "run_data":
            continue
        for f in table_pred["fields"]:
            out[(table_name, f["name"])] = f
    return out


def join(golden: list[dict], predictions: dict) -> tuple[list[dict], list[dict]]:
    matched: list[dict] = []
    missing: list[dict] = []
    for g in golden:
        key = (g["table_name"], g["field_name"])
        pred = predictions.get(key)
        if pred is None:
            missing.append(g)
            continue
        matched.append(
            {
                **g,
                "pred_category": pred["category"],
                "pred_data_subject": pred["data_subject"],
                "pred_reasoning": pred.get("reasoning", ""),
            }
        )
    return matched, missing


def compute_metrics(matched: list[dict]) -> dict:
    total = len(matched)
    if total == 0:
        return {"total": 0}

    cat_correct = sum(1 for r in matched if r["category"] == r["pred_category"])
    sub_correct = sum(1 for r in matched if r["data_subject"] == r["pred_data_subject"])
    both_correct = sum(
        1
        for r in matched
        if r["category"] == r["pred_category"]
        and r["data_subject"] == r["pred_data_subject"]
    )

    by_stratum: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "ok": 0})
    for r in matched:
        e = by_stratum[r["stratum"]]
        e["n"] += 1
        if r["category"] == r["pred_category"] and r["data_subject"] == r["pred_data_subject"]:
            e["ok"] += 1

    return {
        "total": total,
        "category_acc": cat_correct / total,
        "subject_acc": sub_correct / total,
        "exact_match_acc": both_correct / total,
        "by_stratum": {
            est: {"n": v["n"], "ok": v["ok"], "acc": v["ok"] / v["n"] if v["n"] else 0}
            for est, v in by_stratum.items()
        },
    }


def compute_curve_snapshot(table_to_stratum: dict[str, str]) -> dict[str, float]:
    """Compute accuracy for all conditions (c0, c1, c2, c3) if their files
    exist, to show the condition in context of the full degradation curve."""
    golden = load_manual_golden(table_to_stratum)
    out: dict[str, float] = {}
    for cond in CONDITIONS_ORDERED:
        path = PRED_DIR / f"openedx_predictions_{cond}_t0.json"
        if not path.exists():
            continue
        preds = load_predictions(path)
        matched_loc, _ = join(golden, preds)
        if not matched_loc:
            continue
        exact = sum(
            1 for r in matched_loc
            if r["category"] == r["pred_category"]
            and r["data_subject"] == r["pred_data_subject"]
        )
        out[cond] = exact / len(matched_loc)
    return out


def summarize_error_patterns(top_err: list, matched: list[dict]) -> str:
    """Short prose summary of dominant error modes."""
    if not top_err:
        return "No errors recorded."
    parts: list[str] = []
    total_errors = sum(n for _, n in top_err)
    top1 = top_err[0]
    parts.append(
        f"The most frequent error pattern is `{top1[0][0]}` - `{top1[0][1]}` "
        f"with {top1[1]} occurrences."
    )
    if len(top_err) >= 2:
        top2 = top_err[1]
        parts.append(
            f"Second pattern: `{top2[0][0]}` - `{top2[0][1]}` ({top2[1]} cases)."
        )
    # dominant direction
    to_op = sum(
        n for (real, pred), n in top_err if pred == "system.operations"
    )
    from_op = sum(
        n for (real, pred), n in top_err if real == "system.operations"
    )
    if to_op > from_op * 1.5 and to_op > 2:
        parts.append(
            f"Dominant tendency: the classifier **over-assigns `system.operations`** "
            f"(predicting it when it does not apply in {to_op} top errors)."
        )
    elif from_op > to_op * 1.5 and from_op > 2:
        parts.append(
            f"Dominant tendency: the classifier **misses `system.operations`** "
            f"when it does apply (missed in {from_op} top errors)."
        )
    return " ".join(parts)


def compute_per_category_metrics(matched: list[dict]) -> dict[str, dict]:
    """Per-category one-vs-rest TP / cat_FP / cat_FN, precision, recall, F1.

    Operates on the `category` axis only (ignoring data_subject).
    Reports every category that appears in golden OR predicted.

    `cat_fp` / `cat_fn` are per-category one-vs-rest counts — they are NOT
    the sensitivity false positives / negatives (see `sensitivity_levels`).
    """
    categories = {r["category"] for r in matched} | {r["pred_category"] for r in matched}

    out: dict[str, dict] = {}
    for c in categories:
        tp = cat_fp = cat_fn = 0
        for r in matched:
            g, p = r["category"], r["pred_category"]
            if g == c and p == c:
                tp += 1
            elif g != c and p == c:
                cat_fp += 1
            elif g == c and p != c:
                cat_fn += 1
        support = tp + cat_fn  # times category appears in golden
        precision = tp / (tp + cat_fp) if (tp + cat_fp) > 0 else None
        recall = tp / support if support > 0 else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall) > 0
            else None
        )
        out[c] = {
            "support": support,
            "tp": tp,
            "cat_fp": cat_fp,
            "cat_fn": cat_fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return out


def extract_per_category_error_examples(
    matched: list[dict], category: str, max_n: int = 5
) -> dict[str, list[dict]]:
    """For a category, return up to max_n examples of each type:

    - `predicted_as_cat`: field predicted as `category`, golden differs
      (contributes to the category's cat_FP).
    - `missed_cat`: golden = `category`, predicted as another
      (contributes to the category's cat_FN).

    NOTE: these are NOT sensitivity false positives/negatives.
    """
    predicted_as_cat: list[dict] = []
    missed_cat: list[dict] = []
    for r in matched:
        if r["pred_category"] == category and r["category"] != category:
            predicted_as_cat.append(
                {
                    "table": r["table_name"],
                    "field": r["field_name"],
                    "golden": r["category"],
                    "pred": r["pred_category"],
                    "pred_reasoning": r.get("pred_reasoning", ""),
                }
            )
        elif r["category"] == category and r["pred_category"] != category:
            missed_cat.append(
                {
                    "table": r["table_name"],
                    "field": r["field_name"],
                    "golden": r["category"],
                    "pred": r["pred_category"],
                    "pred_reasoning": r.get("pred_reasoning", ""),
                }
            )
    return {
        "predicted_as_cat": predicted_as_cat[:max_n],
        "missed_cat": missed_cat[:max_n],
    }


def compute_level_metrics(matched: list[dict]) -> dict:
    """Metrics by sensitivity level (definition in `sensitivity_levels.py`,
    sensitivity based on the nature of the data).

    Buckets (mutually exclusive, over matched rows):
      - correct:        category == pred_category.
      - false_positive: both levels known and level(pred) > level(golden).
      - false_negative: both levels known and level(pred) < level(golden).
      - same_level:     different categories, same known level.
      - no_level:       either side has UNKNOWN level.

    Also returns a breakdown by true level (0/1/2) with support, correct,
    false positives (over-classification from that level), false negatives
    (under-classification from that level), and same-level errors. Lists
    the categories that landed in `no_level` so the user can extend the
    mapping.
    """
    total = len(matched)
    buckets = {
        "correct": 0,
        "false_positive": 0,
        "false_negative": 0,
        "same_level": 0,
        "no_level": 0,
    }
    by_level: dict[int, dict[str, int]] = {
        L: {"support": 0, "correct": 0, "false_positive": 0, "false_negative": 0, "same_level": 0}
        for L in (0, 1, 2)
    }
    unmapped: set[str] = set()

    for r in matched:
        g_cat = r["category"]
        p_cat = r["pred_category"]
        g_lvl = level_of(g_cat)
        p_lvl = level_of(p_cat)

        if g_lvl == UNKNOWN or p_lvl == UNKNOWN:
            buckets["no_level"] += 1
            if g_lvl == UNKNOWN:
                unmapped.add(g_cat)
            if p_lvl == UNKNOWN:
                unmapped.add(p_cat)
            continue

        if g_lvl in by_level:
            by_level[g_lvl]["support"] += 1

        if g_cat == p_cat:
            buckets["correct"] += 1
            if g_lvl in by_level:
                by_level[g_lvl]["correct"] += 1
        elif p_lvl > g_lvl:
            buckets["false_positive"] += 1
            if g_lvl in by_level:
                by_level[g_lvl]["false_positive"] += 1
        elif p_lvl < g_lvl:
            buckets["false_negative"] += 1
            if g_lvl in by_level:
                by_level[g_lvl]["false_negative"] += 1
        else:
            buckets["same_level"] += 1
            if g_lvl in by_level:
                by_level[g_lvl]["same_level"] += 1

    return {
        "total": total,
        "buckets": buckets,
        "by_level": by_level,
        "unmapped_categories": sorted(unmapped),
    }


def confusion_matrix(matched: list[dict]) -> tuple[list[str], np.ndarray]:
    categories = sorted({r["category"] for r in matched} | {r["pred_category"] for r in matched})
    idx = {c: i for i, c in enumerate(categories)}
    n = len(categories)
    cm = np.zeros((n, n), dtype=int)
    for r in matched:
        cm[idx[r["category"]], idx[r["pred_category"]]] += 1
    return categories, cm


def plot_confusion_matrix(categories: list[str], cm: np.ndarray, out_path: Path, title_suffix: str) -> None:
    row_sums = cm.sum(axis=1, keepdims=True)
    cm_norm = np.where(row_sums > 0, cm / row_sums, 0.0)

    fig, ax = plt.subplots(figsize=(max(10, len(categories) * 0.55), max(7, len(categories) * 0.55)))
    im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(categories)))
    ax.set_yticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=70, ha="right", fontsize=8)
    ax.set_yticklabels(categories, fontsize=8)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual (golden)")
    ax.set_title(f"Row-normalized confusion matrix — {title_suffix}")

    for i in range(len(categories)):
        for j in range(len(categories)):
            v = cm_norm[i, j]
            if v >= 0.05:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        color="white" if v > 0.5 else "black", fontsize=7)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def top_errors(matched: list[dict], n: int = 10) -> list[tuple[tuple[str, str], int]]:
    errors: Counter = Counter()
    for r in matched:
        if r["category"] != r["pred_category"]:
            errors[(r["category"], r["pred_category"])] += 1
    return errors.most_common(n)


def _fmt_pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:.2%}"


def write_report(
    metrics: dict,
    per_cat: dict[str, dict],
    level_metrics: dict,
    top_err: list,
    matched: list[dict],
    missing: list[dict],
    pred_path: Path,
    out_md: Path,
    out_png: Path,
    curve_snapshot: dict[str, float],
) -> None:
    lines: list[str] = []
    this_cond = derive_condition(pred_path)
    lines.append(f"# Validation report — {this_cond.upper()} (T=0)")
    lines.append("")
    lines.append(f"- **Predictions**: `{pred_path.name}`")
    lines.append(f"- **Golden**: `{MANUAL_JSON.name}` (manual classification)")
    lines.append(f"- **Fields compared**: {metrics['total']}")
    if missing:
        lines.append(
            f"- ⚠ **{len(missing)} golden fields missing from predictions** "
            "(see end of report)"
        )
    lines.append("")

    # Curve snapshot (all conditions if available)
    if curve_snapshot:
        lines.append("## Degradation curve snapshot")
        lines.append("")
        lines.append(
            f"Global accuracy (exact match) of every condition run against "
            f"the same manual golden. **{this_cond.upper()}** highlighted."
        )
        lines.append("")
        lines.append("| Condition | Accuracy |")
        lines.append("|-----------|----------|")
        for cond in CONDITIONS_ORDERED:
            if cond not in curve_snapshot:
                continue
            marker = " ← this report" if cond == this_cond else ""
            lines.append(f"| **{cond.upper()}** | {curve_snapshot[cond]:.2%}{marker} |")
        lines.append("")
        lines.append("See `ablation_report.md` for the full curve with deltas and noise floor.")
        lines.append("")

    lines.append("## Global accuracy")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Exact match (subject + category) | **{metrics['exact_match_acc']:.2%}** |")
    lines.append(f"| Category only | {metrics['category_acc']:.2%} |")
    lines.append(f"| data_subject only | {metrics['subject_acc']:.2%} |")
    lines.append("")

    lines.append("## Accuracy by stratum (exact match)")
    lines.append("")
    lines.append("| Stratum | n | correct | accuracy |")
    lines.append("|---------|---|---------|----------|")
    for est in STRATUM_ORDER:
        s = metrics["by_stratum"].get(est, {"n": 0, "ok": 0, "acc": 0})
        lines.append(f"| {est} | {s['n']} | {s['ok']} | {s['acc']:.2%} |")
    lines.append("")

    lines.append("## Metrics by sensitivity level")
    lines.append("")
    lines.append(
        "Levels and error definitions: see docstring of "
        "`scripts/sensitivity_levels.py` (canonical source). "
        "Levels: 0 = enterprise, 1 = non-sensitive personal, "
        "2 = sensitive personal (Law 21.719)."
    )
    lines.append("")
    lm_total = level_metrics["total"]
    lm = level_metrics["buckets"]

    def _pct_of_total(v: int) -> str:
        return f"{v / lm_total:.2%}" if lm_total else "N/A"

    lines.append("| Metric | n | % |")
    lines.append("|--------|---|---|")
    lines.append(
        f"| Correct (exact category) | {lm['correct']} | {_pct_of_total(lm['correct'])} |"
    )
    lines.append(
        f"| False positives — over-classification (predicted level > manual level) "
        f"| {lm['false_positive']} | {_pct_of_total(lm['false_positive'])} |"
    )
    lines.append(
        f"| False negatives — under-classification (predicted level < manual level) "
        f"| {lm['false_negative']} | {_pct_of_total(lm['false_negative'])} |"
    )
    lines.append(
        f"| Same-sensitivity error (different categories, same level) "
        f"| {lm['same_level']} | {_pct_of_total(lm['same_level'])} |"
    )
    lines.append(
        f"| No assigned level (mapping needs extension) "
        f"| {lm['no_level']} | {_pct_of_total(lm['no_level'])} |"
    )
    lines.append("")

    lines.append("| True level | support | correct | FP (over) | FN (under) | same-level |")
    lines.append("|------------|---------|---------|-----------|------------|------------|")
    level_desc = {0: "0 (enterprise)", 1: "1 (non-sensitive personal)", 2: "2 (sensitive)"}
    for L in (0, 1, 2):
        b = level_metrics["by_level"][L]
        lines.append(
            f"| {level_desc[L]} | {b['support']} | {b['correct']} | "
            f"{b['false_positive']} | {b['false_negative']} | {b['same_level']} |"
        )
    lines.append("")

    if level_metrics["unmapped_categories"]:
        lines.append(
            "⚠ Categories without assigned level (extend "
            "`scripts/sensitivity_levels.py`):"
        )
        lines.append("")
        for cat in level_metrics["unmapped_categories"]:
            lines.append(f"- `{cat}`")
        lines.append("")

    lines.append("## Per-category metrics (one-vs-rest)")
    lines.append("")
    lines.append(
        "For each Fides category observed (in golden or predicted): "
        "support (n in golden), TP / cat_FP / cat_FN over the 133 fields, "
        "precision, recall, F1. Sorted by support desc."
    )
    lines.append("")
    lines.append(
        "> `cat_FP` / `cat_FN` are **per-category one-vs-rest counts** "
        "(`cat_FP` = fields predicted as this category with a different "
        "golden; `cat_FN` = fields whose golden = this category but were "
        "predicted as another). They feed per-category precision/recall/F1. "
        "**They are not the sensitivity false positives/negatives** from "
        "the previous section — see `scripts/sensitivity_levels.py`."
    )
    lines.append("")
    lines.append("| category | support | TP | cat_FP | cat_FN | precision | recall | F1 |")
    lines.append("|----------|---------|----|--------|--------|-----------|--------|-----|")
    sorted_cats = sorted(per_cat.items(), key=lambda kv: (-kv[1]["support"], kv[0]))
    for cat, m in sorted_cats:
        lines.append(
            f"| `{cat}` | {m['support']} | {m['tp']} | {m['cat_fp']} | {m['cat_fn']} | "
            f"{_fmt_pct(m['precision'])} | {_fmt_pct(m['recall'])} | {_fmt_pct(m['f1'])} |"
        )
    lines.append("")

    lines.append("## Confusion matrix")
    lines.append("")
    lines.append(f"See figure: `{out_png.name}` (row-normalized).")
    lines.append("")

    lines.append("## Main error patterns")
    lines.append("")
    lines.append(summarize_error_patterns(top_err, matched))
    lines.append("")

    lines.append("## Top 10 confusion pairs")
    lines.append("")
    if top_err:
        lines.append("| Actual (golden) | Predicted | n |")
        lines.append("|-----------------|-----------|---|")
        for (real, pred), n in top_err:
            lines.append(f"| `{real}` | `{pred}` | {n} |")
    else:
        lines.append("No errors recorded.")
    lines.append("")

    lines.append("## Error examples per category")
    lines.append("")
    lines.append(
        "For each category we show up to 5 fields **predicted as this "
        "category with a different golden** (contributing to `cat_FP`) and "
        "up to 5 fields **with golden = this category, predicted as another** "
        "(contributing to `cat_FN`). Do not confuse with the sensitivity "
        "false positives/negatives — see the corresponding section and "
        "`scripts/sensitivity_levels.py`."
    )
    lines.append("")
    for cat, _m in sorted_cats:
        examples = extract_per_category_error_examples(matched, cat, max_n=5)
        if not examples["predicted_as_cat"] and not examples["missed_cat"]:
            continue
        lines.append(f"### `{cat}`")
        lines.append("")
        if examples["predicted_as_cat"]:
            lines.append(
                f"**Predicted as this category, different golden "
                f"({len(examples['predicted_as_cat'])} shown):**"
            )
            lines.append("")
            lines.append("| table | field | golden | predicted |")
            lines.append("|-------|-------|--------|-----------|")
            for ex in examples["predicted_as_cat"]:
                lines.append(
                    f"| {ex['table']} | {ex['field']} | `{ex['golden']}` | `{ex['pred']}` |"
                )
            lines.append("")
        if examples["missed_cat"]:
            lines.append(
                f"**Golden = this category, predicted as another "
                f"({len(examples['missed_cat'])} shown):**"
            )
            lines.append("")
            lines.append("| table | field | golden | predicted |")
            lines.append("|-------|-------|--------|-----------|")
            for ex in examples["missed_cat"]:
                lines.append(
                    f"| {ex['table']} | {ex['field']} | `{ex['golden']}` | `{ex['pred']}` |"
                )
            lines.append("")

    lines.append("## Errors by stratum (summary)")
    lines.append("")
    by_stratum_errors: dict[str, list[dict]] = defaultdict(list)
    for r in matched:
        if r["category"] != r["pred_category"] or r["data_subject"] != r["pred_data_subject"]:
            by_stratum_errors[r["stratum"]].append(r)
    for est in STRATUM_ORDER:
        errs = by_stratum_errors.get(est, [])
        if not errs:
            continue
        lines.append(f"### {est} ({len(errs)} errors)")
        lines.append("")
        lines.append("| table | field | golden | predicted |")
        lines.append("|-------|-------|--------|-----------|")
        for r in errs[:20]:
            g = f"{r['data_subject']}/{r['category']}"
            p = f"{r['pred_data_subject']}/{r['pred_category']}"
            lines.append(f"| {r['table_name']} | {r['field_name']} | {g} | {p} |")
        if len(errs) > 20:
            lines.append(f"| ... | ... | ... | (+{len(errs) - 20} more) |")
        lines.append("")

    if missing:
        lines.append("## ⚠ Golden fields missing from predictions")
        lines.append("")
        for g in missing:
            lines.append(f"- `{g['table_name']}.{g['field_name']}` (stratum {g['stratum']})")
        lines.append("")

    out_md.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--predictions",
        type=Path,
        default=DEFAULT_PREDICTIONS,
        help=f"Predictions file (default: {DEFAULT_PREDICTIONS.name}).",
    )
    args = ap.parse_args()

    # Resolve predictions path. Accept absolute, relative-to-cwd, or
    # relative-to-PRED_DIR convenience.
    pred_path = args.predictions
    if not pred_path.is_absolute():
        candidates = [pred_path, PRED_DIR / pred_path.name, SCRIPT_DIR / pred_path]
        for c in candidates:
            if c.exists():
                pred_path = c
                break

    report_md, report_png = derive_output_paths(pred_path)

    print(f"Loading table-stratum from {SAMPLE_CSV.name}")
    table_to_stratum = build_table_to_stratum()
    print(f"Loading golden: {MANUAL_JSON.relative_to(Path.cwd())}")
    golden = load_manual_golden(table_to_stratum)
    print(f"  {len(golden)} labeled fields.")
    print(f"Loading predictions: {pred_path.relative_to(Path.cwd())}")
    predictions = load_predictions(pred_path)
    print(f"  {len(predictions)} predicted fields.")
    print(f"Computing curve snapshot across conditions...")
    curve_snapshot = compute_curve_snapshot(table_to_stratum)
    if curve_snapshot:
        print(f"  Conditions in snapshot: {list(curve_snapshot.keys())}")

    matched, missing = join(golden, predictions)
    print(f"Matched: {len(matched)}, missing in predictions: {len(missing)}")

    if not matched:
        print("✗ Nothing to compare.")
        return

    metrics = compute_metrics(matched)
    per_cat = compute_per_category_metrics(matched)
    level_metrics = compute_level_metrics(matched)

    print(f"\nGlobal accuracy:")
    print(f"  Exact match: {metrics['exact_match_acc']:.2%}")
    print(f"  Category:    {metrics['category_acc']:.2%}")
    print(f"  Subject:     {metrics['subject_acc']:.2%}")
    print()
    print("Per stratum (exact match):")
    for est in STRATUM_ORDER:
        s = metrics["by_stratum"].get(est, {"n": 0, "ok": 0, "acc": 0})
        print(f"  {est:15s}  {s['ok']:3d}/{s['n']:3d}  ({s['acc']:.2%})")

    print(f"\nPer-category (top 10 by support):")
    for cat, m in sorted(per_cat.items(), key=lambda kv: -kv[1]["support"])[:10]:
        print(
            f"  {cat:35s}  support={m['support']:3d}  "
            f"P={_fmt_pct(m['precision'])}  R={_fmt_pct(m['recall'])}  F1={_fmt_pct(m['f1'])}"
        )

    categories, cm = confusion_matrix(matched)
    title_suffix = f"{derive_condition(pred_path).upper()} (T=0) vs manual golden"
    plot_confusion_matrix(categories, cm, report_png, title_suffix)
    print(f"\n✓ Confusion matrix: {report_png.relative_to(Path.cwd())}")

    top_err = top_errors(matched, n=10)
    write_report(
        metrics, per_cat, level_metrics, top_err, matched, missing, pred_path,
        report_md, report_png, curve_snapshot,
    )
    print(f"✓ Report: {report_md.relative_to(Path.cwd())}")

    lm = level_metrics["buckets"]
    print(
        f"\nLevel metrics: correct={lm['correct']}  "
        f"FP(over)={lm['false_positive']}  FN(under)={lm['false_negative']}  "
        f"same-level={lm['same_level']}  no-level={lm['no_level']}"
    )
    if level_metrics["unmapped_categories"]:
        print(
            f"  ⚠ Unmapped categories: "
            f"{', '.join(level_metrics['unmapped_categories'])}"
        )


if __name__ == "__main__":
    main()
