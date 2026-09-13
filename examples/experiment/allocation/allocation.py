"""Synthetic deterministic allocation batch used only as a product demonstration."""

from __future__ import annotations

import argparse
import csv
import json
from itertools import combinations
from pathlib import Path
import sys

import matplotlib.pyplot as plt


def value_of(items):
    return sum(item["value"] for item in items)


def greedy(items, capacity):
    chosen, used = [], 0
    for item in sorted(items, key=lambda item: item["value"] / item["cost"], reverse=True):
        if used + item["cost"] <= capacity:
            chosen.append(item)
            used += item["cost"]
    return value_of(chosen)


def exhaustive(items, capacity):
    return max((value_of(group) for count in range(len(items) + 1) for group in combinations(items, count) if sum(item["cost"] for item in group) <= capacity), default=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output = Path(args.output)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    rows, failed = [], False
    with (output / "observations.jsonl").open("w", encoding="utf-8") as stream:
        for instance in config["instances"]:
            if instance.get("deliberate_failure"):
                stream.write(json.dumps({"instance_id": instance["id"], "status": "failed", "reason": "synthetic deliberate failure"}) + "\n")
                failed = True
                continue
            baseline = greedy(instance["items"], instance["capacity"])
            alternative = exhaustive(instance["items"], instance["capacity"])
            record = {"instance_id": instance["id"], "status": "completed", "baseline_value": baseline, "alternative_value": alternative, "known_optimum": instance["known_optimum"]}
            stream.write(json.dumps(record) + "\n")
            rows.append(record)
    with (figures / "values.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["instance_id", "baseline_value", "alternative_value"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (figures / "plot.py").write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
    display = {"title": "Synthetic allocation values", "ylabel": "value", "colors": ["#4c78a8", "#f58518"]}
    (figures / "display.json").write_text(json.dumps(display, indent=2) + "\n", encoding="utf-8")
    labels = [row["instance_id"] for row in rows]
    x = list(range(len(rows)))
    figure, axis = plt.subplots(figsize=(5, 3.2), layout="constrained")
    axis.bar([value - 0.2 for value in x], [row["baseline_value"] for row in rows], width=0.4, label="density-greedy", color=display["colors"][0])
    axis.bar([value + 0.2 for value in x], [row["alternative_value"] for row in rows], width=0.4, label="exhaustive optimum", color=display["colors"][1])
    axis.set_xticks(x, labels)
    axis.set_ylabel(display["ylabel"])
    axis.set_title(display["title"])
    axis.legend()
    figure.savefig(figures / "value-comparison.png", dpi=160)
    plt.close(figure)
    (figures / "figures.json").write_text(json.dumps([{"name": "allocation-values", "image": "value-comparison.png", "data": "values.csv", "plot_code": "plot.py", "display_config": "display.json"}], indent=2) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
