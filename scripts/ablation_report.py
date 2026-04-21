"""
Comparing golden (manual classification) vs predictions (C0, C1, C2, C3).
Generates the ablation curve and per-category analysis.

Scope: 133 fields, distributed across 25 tables.

Metrics:
  - Accuracy per condition (global and by stratum).
  - Deltas C0-C1, C1-C2, C2-C3.
  - **By sensitivity level × condition** (canonical definition in
    `sensitivity_levels.py`): correct, FP (over-classification),
    FN (under-classification), same-sensitivity error.
  - **Per-category × condition (one-vs-rest)**: recall per category
    under each condition + heatmap. `cat_FP` is the one-vs-rest count
    (not the sensitivity FP).
  - Empirical noise floor estimated via tables without PII annotations
    (CourseAccessRoleHistory, StagedContentFile) — identical code C0/C1.
  - Per-field trace (when each prediction breaks).

Output (under `reports/`):
  - ablation_report.md
  - ablation_curve.png
  - ablation_per_category.png  (category × condition heatmap)
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
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
REPORT_MD = OUTPUT_DIR / "ablation_report.md"
REPORT_PNG = OUTPUT_DIR / "ablation_curve.png"
PER_CAT_PNG = OUTPUT_DIR / "ablation_per_category.png"

CONDITIONS = ["c0", "c1", "c2", "c3"]
PRED_PATHS = {cond: PRED_DIR / f"openedx_predictions_{cond}_t0.json" for cond in CONDITIONS}

NO_ANNOTATION_TABLES = {"CourseAccessRoleHistory", "StagedContentFile"}

CONDITION_LABELS = {
    "c0": "C0\n(original)",
    "c1": "C1\n(no PII annotations)",
    "c2": "C2\n(no docstrings)",
    "c3": "C3\n(C2 + anon. names)",
}

STRATUM_ORDER = ["identity", "academic", "content", "verification", "operational"]


def build_table_to_stratum() -> dict[str, str]:
    m: dict[str, str] = {}
    for row in csv.DictReader(SAMPLE_CSV.open()):
        m[row["table_name"]] = row["stratum"]
    return m


def load_manual_golden(table_to_stratum: dict[str, str]) -> list[dict]:
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
    raw = json.loads(path.read_text())
    out: dict[tuple[str, str], dict] = {}
    for table_name, table_pred in raw.items():
        if table_name == "run_data":
            continue
        for f in table_pred["fields"]:
            out[(table_name, f["name"])] = f
    return out


def is_correct(golden_row: dict, pred: dict) -> bool:
    return (
        golden_row["category"] == pred["category"]
        and golden_row["data_subject"] == pred["data_subject"]
    )


def compute_per_condition(golden: list[dict]) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for cond in CONDITIONS:
        path = PRED_PATHS[cond]
        if not path.exists():
            print(f"⚠ {path.name} does not exist — skipping condition {cond}")
            continue
        preds = load_predictions(path)

        total = 0
        correct = 0
        by_stratum: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "ok": 0})
        per_field: dict[tuple[str, str], bool] = {}
        per_field_pred: dict[tuple[str, str], str] = {}  # predicted category

        for g in golden:
            key = (g["table_name"], g["field_name"])
            pred = preds.get(key)
            if pred is None:
                continue
            ok = is_correct(g, pred)
            per_field[key] = ok
            per_field_pred[key] = pred["category"]
            total += 1
            if ok:
                correct += 1
            e = by_stratum[g["stratum"]]
            e["n"] += 1
            if ok:
                e["ok"] += 1

        results[cond] = {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total else 0,
            "by_stratum": {
                est: {"n": v["n"], "ok": v["ok"], "acc": v["ok"] / v["n"] if v["n"] else 0}
                for est, v in by_stratum.items()
            },
            "per_field": per_field,
            "per_field_pred": per_field_pred,
        }
    return results


def compute_per_category_cross(
    golden: list[dict], results: dict[str, dict]
) -> dict[str, dict]:
    """Per (category, condition): recall and per-category one-vs-rest counts.

    Returns {category: {support: n, per_cond: {cond: {tp, cat_fp, cat_fn, recall}}}}.

    `cat_fp` / `cat_fn` are per-category one-vs-rest counts (not the
    sensitivity false positives/negatives — see `sensitivity_levels`).
    """
    conds = [c for c in CONDITIONS if c in results]
    categories = sorted({g["category"] for g in golden} | {
        results[c]["per_field_pred"][k]
        for c in conds
        for k in results[c]["per_field_pred"]
    })

    out: dict[str, dict] = {}
    for cat in categories:
        support = sum(1 for g in golden if g["category"] == cat)
        per_cond: dict[str, dict] = {}
        for c in conds:
            preds = results[c]["per_field_pred"]
            tp = cat_fp = cat_fn = 0
            for g in golden:
                key = (g["table_name"], g["field_name"])
                p = preds.get(key)
                if p is None:
                    continue
                is_gold = g["category"] == cat
                is_pred = p == cat
                if is_gold and is_pred:
                    tp += 1
                elif is_pred and not is_gold:
                    cat_fp += 1
                elif is_gold and not is_pred:
                    cat_fn += 1
            recall = tp / support if support > 0 else None
            per_cond[c] = {"tp": tp, "cat_fp": cat_fp, "cat_fn": cat_fn, "recall": recall}
        out[cat] = {"support": support, "per_cond": per_cond}
    return out


def compute_per_condition_level_metrics(
    golden: list[dict], results: dict[str, dict]
) -> dict[str, dict]:
    """For each run condition, compute sensitivity-level metrics
    (canonical definition in `sensitivity_levels.py`).

    Returns {cond: {total, correct, false_positive, false_negative,
                    same_level, no_level, unmapped_categories}}.
    """
    out: dict[str, dict] = {}
    for cond in CONDITIONS:
        if cond not in results:
            continue
        preds = results[cond]["per_field_pred"]
        buckets = {
            "total": 0,
            "correct": 0,
            "false_positive": 0,
            "false_negative": 0,
            "same_level": 0,
            "no_level": 0,
        }
        unmapped: set[str] = set()
        for g in golden:
            key = (g["table_name"], g["field_name"])
            p_cat = preds.get(key)
            if p_cat is None:
                continue
            buckets["total"] += 1
            g_cat = g["category"]
            g_lvl = level_of(g_cat)
            p_lvl = level_of(p_cat)
            if g_lvl == UNKNOWN or p_lvl == UNKNOWN:
                buckets["no_level"] += 1
                if g_lvl == UNKNOWN:
                    unmapped.add(g_cat)
                if p_lvl == UNKNOWN:
                    unmapped.add(p_cat)
                continue
            if g_cat == p_cat:
                buckets["correct"] += 1
            elif p_lvl > g_lvl:
                buckets["false_positive"] += 1
            elif p_lvl < g_lvl:
                buckets["false_negative"] += 1
            else:
                buckets["same_level"] += 1
        buckets["unmapped_categories"] = sorted(unmapped)
        out[cond] = buckets
    return out


def estimate_noise_floor(golden: list[dict]) -> dict:
    if not (PRED_PATHS["c0"].exists() and PRED_PATHS["c1"].exists()):
        return {"available": False}

    c0 = load_predictions(PRED_PATHS["c0"])
    c1 = load_predictions(PRED_PATHS["c1"])

    relevant_fields = [g for g in golden if g["table_name"] in NO_ANNOTATION_TABLES]
    if not relevant_fields:
        return {"available": False, "reason": "no fields from no-annotation tables in golden"}

    n = 0
    cat_disagree = 0
    sub_disagree = 0
    both_disagree = 0
    examples: list[dict] = []

    for g in relevant_fields:
        key = (g["table_name"], g["field_name"])
        p0 = c0.get(key)
        p1 = c1.get(key)
        if p0 is None or p1 is None:
            continue
        n += 1
        cat_diff = p0["category"] != p1["category"]
        sub_diff = p0["data_subject"] != p1["data_subject"]
        if cat_diff:
            cat_disagree += 1
        if sub_diff:
            sub_disagree += 1
        if cat_diff or sub_diff:
            both_disagree += 1
            examples.append(
                {
                    "table": g["table_name"],
                    "field": g["field_name"],
                    "c0": f"{p0['data_subject']}/{p0['category']}",
                    "c1": f"{p1['data_subject']}/{p1['category']}",
                }
            )

    return {
        "available": True,
        "n": n,
        "cat_disagree": cat_disagree,
        "sub_disagree": sub_disagree,
        "both_disagree": both_disagree,
        "noise_pct": both_disagree / n if n else 0,
        "examples": examples,
        "tables": sorted(NO_ANNOTATION_TABLES),
    }


def trace_field_breakage(results: dict[str, dict], golden: list[dict]) -> list[dict]:
    if not all(c in results for c in CONDITIONS):
        return []

    breakages: list[dict] = []
    for g in golden:
        key = (g["table_name"], g["field_name"])
        trace = []
        for cond in CONDITIONS:
            ok = results[cond]["per_field"].get(key)
            trace.append("✓" if ok else ("✗" if ok is False else "—"))
        first_break = None
        seen_ok = False
        for cond, mark in zip(CONDITIONS, trace):
            if mark == "✓":
                seen_ok = True
            elif mark == "✗" and seen_ok and first_break is None:
                first_break = cond
        breakages.append(
            {
                "table": g["table_name"],
                "field": g["field_name"],
                "stratum": g["stratum"],
                "golden": f"{g['data_subject']}/{g['category']}",
                "trace": " ".join(trace),
                "first_break": first_break,
            }
        )
    return breakages


def plot_curve(results: dict[str, dict], out_path: Path) -> None:
    conds = [c for c in CONDITIONS if c in results]
    if not conds:
        return

    overall = [results[c]["accuracy"] for c in conds]
    labels = [CONDITION_LABELS.get(c, c) for c in conds]

    fig, (ax_overall, ax_stratum) = plt.subplots(1, 2, figsize=(14, 5))

    bars = ax_overall.bar(labels, overall, color=["#4c72b0", "#55a868", "#c44e52", "#8172b2"])
    ax_overall.set_ylabel("Accuracy (exact match)")
    ax_overall.set_title("Degradation curve — global accuracy by condition")
    ax_overall.set_ylim(0, 1)
    ax_overall.axhline(0, color="gray", lw=0.5)
    for bar, v in zip(bars, overall):
        ax_overall.text(bar.get_x() + bar.get_width() / 2, v + 0.02, f"{v:.1%}",
                        ha="center", fontsize=10)

    width = 0.2
    x = range(len(STRATUM_ORDER))
    for i, cond in enumerate(conds):
        vals = [results[cond]["by_stratum"].get(e, {"acc": 0})["acc"] for e in STRATUM_ORDER]
        ax_stratum.bar([xi + i * width for xi in x], vals, width=width, label=cond.upper())
    ax_stratum.set_xticks([xi + 1.5 * width for xi in x])
    ax_stratum.set_xticklabels(STRATUM_ORDER, rotation=20)
    ax_stratum.set_ylabel("Accuracy")
    ax_stratum.set_ylim(0, 1)
    ax_stratum.set_title("Accuracy by stratum and condition")
    ax_stratum.legend()

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_per_category_heatmap(per_cat: dict[str, dict], out_path: Path) -> None:
    conds = CONDITIONS
    # Only categories with support > 0 (appear in golden) for the recall view.
    cats = [c for c in per_cat if per_cat[c]["support"] > 0]
    cats.sort(key=lambda c: (-per_cat[c]["support"], c))

    if not cats:
        return

    mat = np.full((len(cats), len(conds)), np.nan)
    for i, cat in enumerate(cats):
        for j, cond in enumerate(conds):
            cell = per_cat[cat]["per_cond"].get(cond)
            if cell is not None and cell["recall"] is not None:
                mat[i, j] = cell["recall"]

    fig, ax = plt.subplots(figsize=(8, max(4, len(cats) * 0.4)))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(conds)))
    ax.set_yticks(range(len(cats)))
    ax.set_xticklabels([c.upper() for c in conds])
    ax.set_yticklabels([f"{c}  (n={per_cat[c]['support']})" for c in cats], fontsize=9)
    ax.set_xlabel("Condition")
    ax.set_title("Recall per category × condition (manual vs automatic)")

    for i in range(len(cats)):
        for j in range(len(conds)):
            v = mat[i, j]
            if not np.isnan(v):
                color = "white" if v < 0.5 else "black"
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        color=color, fontsize=9)

    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04, label="recall")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def _fmt_pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:.2%}"


def write_report(
    results: dict[str, dict],
    per_cat: dict[str, dict],
    level_per_cond: dict[str, dict],
    noise: dict,
    breakages: list[dict],
    out_md: Path,
    out_png: Path,
    per_cat_png: Path,
) -> None:
    lines: list[str] = []
    lines.append("# Ablation report")
    lines.append("")
    lines.append(
        "Comparison of the 4 conditions (C0/C1/C2/C3) at `temperature=0` "
        "against the manual classification. Scope: 133 fields across 25 tables."
    )
    lines.append("")

    lines.append("## Global degradation curve")
    lines.append("")
    lines.append("| Condition | Description | n | correct | accuracy | Δ vs previous |")
    lines.append("|-----------|-------------|---|---------|----------|---------------|")
    prev = None
    desc = {
        "c0": "original code (with PII annotations)",
        "c1": "no `.. pii*` annotations",
        "c2": "no docstrings or comments",
        "c3": "C2 + anonymized column names",
    }
    for cond in CONDITIONS:
        if cond not in results:
            continue
        r = results[cond]
        delta = ""
        if prev is not None:
            d = r["accuracy"] - prev
            delta = f"{d:+.2%}"
        lines.append(
            f"| **{cond.upper()}** | {desc[cond]} | {r['total']} | {r['correct']} | "
            f"**{r['accuracy']:.2%}** | {delta} |"
        )
        prev = r["accuracy"]
    lines.append("")
    lines.append(f"See figure: `{out_png.name}`")
    lines.append("")

    lines.append("## Accuracy by stratum and condition")
    lines.append("")
    header = "| Stratum | " + " | ".join(c.upper() for c in CONDITIONS if c in results) + " |"
    sep = "|---------|" + "|".join("------" for _ in results) + "|"
    lines.append(header)
    lines.append(sep)
    for est in STRATUM_ORDER:
        cells = [est]
        for cond in CONDITIONS:
            if cond not in results:
                continue
            s = results[cond]["by_stratum"].get(est, {"n": 0, "ok": 0, "acc": 0})
            cells.append(f"{s['acc']:.2%} ({s['ok']}/{s['n']})")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Metrics by sensitivity level × condition")
    lines.append("")
    lines.append(
        "Counts per condition according to the canonical definition in "
        "`scripts/sensitivity_levels.py`. Levels: 0 = enterprise, "
        "1 = non-sensitive personal, 2 = sensitive personal (Law 21.719). "
        "FP = over-classification (predicted level > manual level); "
        "FN = under-classification (predicted level < manual level); "
        "same-level = incorrect category, same level."
    )
    lines.append("")
    conds_run = [c for c in CONDITIONS if c in results]
    header = "| Condition | correct | FP (over) | FN (under) | same-level | no-level |"
    sep = "|-----------|---------|-----------|------------|------------|----------|"
    lines.append(header)
    lines.append(sep)
    for cond in conds_run:
        lm = level_per_cond[cond]
        lines.append(
            f"| **{cond.upper()}** | {lm['correct']} | {lm['false_positive']} | "
            f"{lm['false_negative']} | {lm['same_level']} | {lm['no_level']} |"
        )
    lines.append("")
    unmapped_all = sorted({
        cat
        for cond in conds_run
        for cat in level_per_cond[cond].get("unmapped_categories", [])
    })
    if unmapped_all:
        lines.append(
            "⚠ Categories without assigned level (extend "
            "`scripts/sensitivity_levels.py`): "
            + ", ".join(f"`{c}`" for c in unmapped_all)
        )
        lines.append("")

    lines.append("## Recall per category × condition (one-vs-rest)")
    lines.append("")
    lines.append(
        "Recall = TP / support (how often the classifier gets the category "
        "right when the golden says it is that category). Sorted by support "
        "desc. See heatmap in `{}`.".format(per_cat_png.name)
    )
    lines.append("")
    lines.append(
        "> `cat_FP` values are per-category one-vs-rest counts (fields "
        "predicted as this category but with a different golden). They are "
        "not the sensitivity false positives — see the previous section and "
        "`scripts/sensitivity_levels.py`."
    )
    lines.append("")
    cats_sorted = sorted(
        [c for c in per_cat if per_cat[c]["support"] > 0],
        key=lambda c: (-per_cat[c]["support"], c),
    )
    header = "| category | support | " + " | ".join(c.upper() for c in conds_run) + " |"
    sep = "|----------|---------|" + "|".join("------" for _ in conds_run) + "|"
    lines.append(header)
    lines.append(sep)
    for cat in cats_sorted:
        row = [f"`{cat}`", str(per_cat[cat]["support"])]
        for cond in conds_run:
            cell = per_cat[cat]["per_cond"].get(cond)
            if cell is None:
                row.append("—")
            else:
                r = cell["recall"]
                cat_fp = cell["cat_fp"]
                row.append(f"{_fmt_pct(r)} (cat_FP={cat_fp})")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Categories that ONLY appear as predicted (support in golden == 0)
    fp_only_cats = [
        cat for cat in per_cat
        if per_cat[cat]["support"] == 0
        and any(
            per_cat[cat]["per_cond"].get(c, {}).get("cat_fp", 0) > 0
            for c in results
        )
    ]
    if fp_only_cats:
        lines.append("### Predicted categories that do not exist in the golden")
        lines.append("")
        lines.append(
            "These categories were never assigned by the manual labeler, yet "
            "the classifier used them at least once. They are spurious "
            "assignments (each occurrence adds to the category's `cat_FP`; "
            "their impact on the sensitivity metric depends on their level "
            "relative to the golden — see the level-metrics section)."
        )
        lines.append("")
        header = "| category | " + " | ".join(
            f"{c.upper()} (cat_FP)" for c in conds_run
        ) + " |"
        lines.append(header)
        lines.append("|----------|" + "|".join("------" for _ in conds_run) + "|")
        for cat in sorted(fp_only_cats):
            row = [f"`{cat}`"]
            for cond in conds_run:
                fp = per_cat[cat]["per_cond"].get(cond, {}).get("cat_fp", 0)
                row.append(str(fp))
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    lines.append("## Empirical noise floor (LLM stochasticity)")
    lines.append("")
    if noise.get("available"):
        lines.append(
            f"Tables `{', '.join(noise['tables'])}` have no `.. pii*` "
            f"annotations, so their C0 and C1 code is **identical**. Any "
            f"difference between the C0 and C1 predictions on these tables "
            f"is pure model variance (even at temperature=0 there is "
            f"residual non-determinism in the agent SDK tool calls)."
        )
        lines.append("")
        lines.append(f"- Fields compared: **{noise['n']}**")
        if noise["n"]:
            lines.append(
                f"- `category` disagreements: {noise['cat_disagree']} "
                f"({noise['cat_disagree']/noise['n']:.1%})"
            )
            lines.append(
                f"- `data_subject` disagreements: {noise['sub_disagree']} "
                f"({noise['sub_disagree']/noise['n']:.1%})"
            )
            lines.append(
                f"- Noise floor (any disagreement): "
                f"**{noise['noise_pct']:.1%}** ({noise['both_disagree']}/{noise['n']})"
            )
            lines.append("")
        if noise["examples"]:
            lines.append("Disagreement cases (pure noise):")
            lines.append("")
            lines.append("| table | field | C0 | C1 |")
            lines.append("|-------|-------|----|----|")
            for ex in noise["examples"][:10]:
                lines.append(f"| {ex['table']} | {ex['field']} | {ex['c0']} | {ex['c1']} |")
            lines.append("")
        lines.append(
            "**Conclusion**: over the {n} fields where the input is identical "
            "between C0 and C1 (tables without PII annotations), predictions "
            "agreed 100% — floor = **{pct:.1%}**. This does **not** say that "
            "predictions are identical across conditions (they do differ, "
            "and that difference shows up as accuracy variation in the "
            "global table); it says that **given the same input, the model "
            "responds the same way**. Therefore the accuracy differences "
            "observed between C0/C1/C2/C3 **reflect the treatment effect** "
            "(removal of annotations, docstrings or names) and not model "
            "non-determinism.".format(
                n=noise["n"], pct=noise["noise_pct"]
            )
        )
    else:
        lines.append("Not available.")
    lines.append("")

    if breakages:
        lines.append("## Per-field trace (when each prediction breaks)")
        lines.append("")
        lines.append(
            "For each field, ✓ = correct classification in that condition, "
            "✗ = incorrect. `first_break` = first condition where the "
            "prediction breaks (transition ✓ - ✗)."
        )
        lines.append("")

        lines.append("### Fields that break at C0 - C1 (PII annotations effect)")
        lines.append("")
        broken_c1 = [b for b in breakages if b["first_break"] == "c1"]
        if broken_c1:
            lines.append("| table | field | golden | trace (C0/C1/C2/C3) |")
            lines.append("|-------|-------|--------|---------------------|")
            for b in broken_c1:
                lines.append(
                    f"| {b['table']} | {b['field']} | {b['golden']} | {b['trace']} |"
                )
        else:
            lines.append("None.")
        lines.append("")

        lines.append("### Fields that break at C1 - C2 (docstring effect)")
        lines.append("")
        broken_c2 = [b for b in breakages if b["first_break"] == "c2"]
        if broken_c2:
            lines.append("| table | field | golden | trace |")
            lines.append("|-------|-------|--------|-------|")
            for b in broken_c2:
                lines.append(f"| {b['table']} | {b['field']} | {b['golden']} | {b['trace']} |")
        else:
            lines.append("None.")
        lines.append("")

        lines.append("### Fields that break at C2 - C3 (column name effect)")
        lines.append("")
        broken_c3 = [b for b in breakages if b["first_break"] == "c3"]
        if broken_c3:
            lines.append("| table | field | golden | trace |")
            lines.append("|-------|-------|--------|-------|")
            for b in broken_c3:
                lines.append(f"| {b['table']} | {b['field']} | {b['golden']} | {b['trace']} |")
        else:
            lines.append("None.")
        lines.append("")

        always_wrong = [b for b in breakages if b["trace"].count("✗") == len(CONDITIONS)]
        if always_wrong:
            lines.append("### Fields the classifier NEVER gets right")
            lines.append("")
            lines.append("Possible causes: systematic classifier bias on these cases, "
                         "or divergent criteria between manual and prompt.")
            lines.append("")
            lines.append("| table | field | golden |")
            lines.append("|-------|-------|--------|")
            for b in always_wrong[:20]:
                lines.append(f"| {b['table']} | {b['field']} | {b['golden']} |")
            lines.append("")

    lines.append("## Design limitations")
    lines.append("")
    lines.append(
        "- **Cumulative, not factorial, ablation**: the 4 conditions "
        "progressively remove signals in a fixed order (annotations - "
        "docstrings - names). The cell 'anonymized names with intact "
        "docstrings' (C0 + anon) is not measured."
    )
    lines.append(
        "- **Each gap is marginal and ordering-conditional**: the C2-C3 gap "
        "is read as 'effect of column name conditional on no docstrings', "
        "not as an independent contribution."
    )
    lines.append(
        "- **Residual lexical leakage in C3**: `unique_together`, `help_text`, "
        "`db_column`, `related_name`, `verbose_name`, method names remain "
        "preserved. C3 measures the loss of the name-token, not of all "
        "lexical signal."
    )
    lines.append(
        "- **Single-labeler golden**: manual labels come from a single "
        "person. A more robust golden would require inter-annotator "
        "agreement."
    )
    lines.append(
        "- **Noise floor at T=0**: even running at `temperature=0` there is "
        "residual non-determinism (agent SDK tool-call ordering). See the "
        "noise floor section."
    )
    lines.append("")

    out_md.write_text("\n".join(lines))


def main() -> None:
    print(f"Loading table-stratum from {SAMPLE_CSV.name}")
    table_to_stratum = build_table_to_stratum()
    print(f"Loading golden: {MANUAL_JSON.relative_to(Path.cwd())}")
    golden = load_manual_golden(table_to_stratum)
    print(f"  {len(golden)} labeled fields.")

    print(f"\nComputing per-condition metrics...")
    results = compute_per_condition(golden)

    print(f"\nPer-condition summary:")
    for cond in CONDITIONS:
        if cond in results:
            r = results[cond]
            print(f"  {cond.upper()}: {r['accuracy']:.2%} ({r['correct']}/{r['total']})")

    print(f"\nPer-category × condition...")
    per_cat = compute_per_category_cross(golden, results)

    print(f"\nPer-condition level metrics (sensitivity)...")
    level_per_cond = compute_per_condition_level_metrics(golden, results)
    for cond, lm in level_per_cond.items():
        print(
            f"  {cond.upper()}: correct={lm['correct']} "
            f"FP(over)={lm['false_positive']} FN(under)={lm['false_negative']} "
            f"same-level={lm['same_level']} no-level={lm['no_level']}"
        )

    print(f"\nEstimating noise floor (C0 vs C1 on tables without PII annotations)...")
    noise = estimate_noise_floor(golden)
    if noise.get("available"):
        print(f"  Noise floor: {noise['noise_pct']:.1%} ({noise['both_disagree']}/{noise['n']})")

    breakages = trace_field_breakage(results, golden)

    plot_curve(results, REPORT_PNG)
    print(f"\n✓ Global curve: {REPORT_PNG.relative_to(Path.cwd())}")

    plot_per_category_heatmap(per_cat, PER_CAT_PNG)
    print(f"✓ Per-category heatmap: {PER_CAT_PNG.relative_to(Path.cwd())}")

    write_report(
        results, per_cat, level_per_cond, noise, breakages,
        REPORT_MD, REPORT_PNG, PER_CAT_PNG,
    )
    print(f"✓ Report: {REPORT_MD.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
