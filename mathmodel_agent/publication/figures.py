"""Truthful, final-size figures redrawn from execution-owned data."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from mathmodel_agent.contracts import read_json, sha256_file

from .errors import PublicationError


MM_PER_INCH = 25.4
BLUE = "#0072B2"
VERMILION = "#D55E00"
GREEN = "#009E73"
GRAY = "#8A8F98"


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {"instance_id", "baseline_value", "alternative_value"}
    if not rows or any(set(row) != required for row in rows):
        raise PublicationError("figure CSV must contain exact allocation value columns")
    return [
        {
            "instance_id": row["instance_id"],
            "baseline_value": float(row["baseline_value"]),
            "alternative_value": float(row["alternative_value"]),
        }
        for row in rows
    ]


def _verify_rows(run_directory: Path, manifest: dict, rows: list[dict]) -> None:
    observation_path = run_directory / manifest["observations"]
    observations = [
        json.loads(line)
        for line in observation_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    completed = {
        item["instance_id"]: item
        for item in observations
        if item.get("status") == "completed"
    }
    for row in rows:
        source = completed.get(row["instance_id"])
        if source is None:
            raise PublicationError(f"figure row lacks a completed observation: {row['instance_id']}")
        for key in ("baseline_value", "alternative_value"):
            if float(source[key]) != row[key]:
                raise PublicationError(f"figure data differs from observation: {row['instance_id']} {key}")


def _save(figure, path: Path) -> None:
    figure.savefig(path, format="pdf", metadata={"Creator": "mathmodel-agent publication"})
    plt.close(figure)


def redraw_manifest_figures(
    run_directory: str | Path,
    output_directory: str | Path,
    *,
    style_path: str | Path,
) -> list[dict]:
    """Redraw the D4 allocation figure data without changing scientific results."""
    run_root = Path(run_directory)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    manifest = read_json(run_root / "run_manifest.json")
    figures = manifest.get("figures", [])
    if len(figures) != 1:
        raise PublicationError("the allocation demonstration expects exactly one source figure")
    source = figures[0]
    for key in ("data", "plot_code", "display_config", "image"):
        path = run_root / source[key]
        if not path.is_file():
            raise PublicationError(f"source figure asset is missing: {source[key]}")
    rows = _read_rows(run_root / source["data"])
    _verify_rows(run_root, manifest, rows)

    labels = [row["instance_id"] for row in rows]
    baseline = np.array([row["baseline_value"] for row in rows])
    alternative = np.array([row["alternative_value"] for row in rows])
    x = np.arange(len(rows))
    style = Path(style_path)
    if not style.is_file():
        raise PublicationError(f"Matplotlib style is missing: {style}")

    with mpl.rc_context(fname=style):
        comparison, axis = plt.subplots(
            figsize=(155 / MM_PER_INCH, 70 / MM_PER_INCH), layout="constrained"
        )
        axis.plot(x, baseline, color=BLUE, marker="o", linestyle="--", label="密度贪心")
        axis.plot(x, alternative, color=VERMILION, marker="s", linestyle="-", label="穷举最优")
        for index, (left, right) in enumerate(zip(baseline, alternative, strict=True)):
            axis.vlines(index, left, right, color=GRAY, linewidth=1.0, zorder=0)
            axis.annotate(f"差值 {right-left:g}", (index, max(left, right)), xytext=(0, 5),
                          textcoords="offset points", ha="center", fontsize=7)
        axis.set_xticks(x, labels)
        axis.set_ylabel("目标值（value）")
        axis.set_xlabel("完成的合成实例")
        axis.legend(ncols=2, loc="lower right")
        comparison_path = output / "allocation-comparison.pdf"
        _save(comparison, comparison_path)

        diagnostic = plt.figure(
            figsize=(155 / MM_PER_INCH, 112 / MM_PER_INCH), layout="constrained"
        )
        grid = diagnostic.add_gridspec(2, 2, height_ratios=(1.15, 1))
        values_axis = diagnostic.add_subplot(grid[0, :])
        width = 0.34
        values_axis.bar(x - width / 2, baseline, width, color=BLUE, hatch="//", label="密度贪心")
        values_axis.bar(x + width / 2, alternative, width, color=VERMILION, hatch="..", label="穷举最优")
        values_axis.set_xticks(x, labels)
        values_axis.set_ylabel("目标值（value）")
        values_axis.legend(ncols=2)
        values_axis.set_title("(a) 两种方法在完成实例上的原始观测")

        gap_axis = diagnostic.add_subplot(grid[1, 0])
        relative_gap = np.divide(alternative - baseline, alternative, out=np.zeros_like(alternative), where=alternative != 0) * 100
        gap_axis.bar(x, relative_gap, color=[VERMILION if value > 0 else GREEN for value in relative_gap])
        gap_axis.axhline(0, color="#333333", linewidth=0.7)
        gap_axis.set_xticks(x, labels, rotation=18, ha="right")
        gap_axis.set_ylabel("相对最优差距（%）")
        gap_axis.set_title("(b) 实例级相对差距（描述性）")

        status_axis = diagnostic.add_subplot(grid[1, 1])
        statuses = [item.get("status") for item in manifest.get("instances", [])]
        status_values = np.array([[1 if value == "completed" else 0 for value in statuses]])
        cmap = mpl.colors.ListedColormap([VERMILION, GREEN])
        status_axis.imshow(status_values, cmap=cmap, vmin=0, vmax=1, aspect="auto", rasterized=True)
        status_axis.set_xticks(np.arange(len(statuses)), [item["id"] for item in manifest["instances"]], rotation=25, ha="right")
        status_axis.set_yticks([0], ["运行状态"])
        for column, status in enumerate(statuses):
            status_axis.text(column, 0, "完成" if status == "completed" else "失败", ha="center", va="center", color="white", fontsize=7)
        status_axis.grid(False)
        status_axis.set_title("(c) 计划实例覆盖（2/1/3）")
        diagnostic_path = output / "allocation-diagnostics.pdf"
        _save(diagnostic, diagnostic_path)

    records = []
    for path, question in (
        (comparison_path, "两种方法在每个完成实例上的目标值及差距是多少？"),
        (diagnostic_path, "原始观测、描述性差距与部分运行覆盖如何共同解释？"),
    ):
        records.append(
            {
                "output": path.name,
                "sha256": sha256_file(path),
                "source_data": source["data"],
                "source_plot_code": source["plot_code"],
                "source_display_config": source["display_config"],
                "question": question,
                "redrawable": True,
            }
        )
    return records


def write_figure_index(records: list[dict], output_path: str | Path) -> None:
    lines = [
        "# Figure Index",
        "",
        "All figures below are redrawn from the selected execution run; display edits do not alter metrics.",
        "",
        "| Output | Question | Data | Script | Redrawable |",
        "|---|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            f"| `{record['output']}` | {record['question']} | `{record['source_data']}` | "
            f"`{record['source_plot_code']}` | yes |"
        )
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
