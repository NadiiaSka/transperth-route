"""Compare k6 result JSON files in perf/results/.

    python perf/compare.py                # table of all runs + delta vs previous
    python perf/compare.py --baseline 0   # pin run N as the baseline for deltas

Each k6 run writes a timestamped summary JSON; this builds the trend report.
"""
import argparse
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

# (label, metric, stat) — the numbers worth comparing run over run.
COLUMNS = [
    ("steps_no_ai p95", "directions_steps_no_ai_ms", "p(95)"),
    ("steps_no_ai avg", "directions_steps_no_ai_ms", "avg"),
    ("maneuvers p95", "directions_maneuvers_ms", "p(95)"),
    ("maneuvers avg", "directions_maneuvers_ms", "avg"),
    ("err %", "http_req_failed", "rate"),
]


def load_runs():
    runs = []
    for path in sorted(RESULTS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        row = {"file": path.name}
        for label, metric, stat in COLUMNS:
            m = data.get("metrics", {}).get(metric)
            row[label] = m["values"].get(stat) if m else None
        runs.append(row)
    return runs


def fmt(value, scale=1.0, pct=False):
    if value is None:
        return "-"
    v = value * 100 if pct else value
    return f"{v:.1f}"


def delta(current, previous):
    if current is None or previous is None or previous == 0:
        return ""
    change = (current - previous) / previous * 100
    sign = "+" if change > 0 else ""
    marker = " !" if abs(change) >= 50 else ""  # flag big regressions
    return f" ({sign}{change:.0f}%{marker})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=int, default=0, help="index of baseline run (default: first)")
    args = ap.parse_args()

    runs = load_runs()
    if not runs:
        print(f"no results in {RESULTS} — run k6 first")
        return
    base = runs[min(args.baseline, len(runs) - 1)]

    print(f"baseline: {base['file']}\n")
    header = f"{'run':<28}" + "".join(f"{label:>22}" for label, _, _ in COLUMNS)
    print(header)
    print("-" * len(header))
    for i, run in enumerate(runs):
        prev = runs[i - 1] if i else None
        cells = []
        for label, _, _ in COLUMNS:
            pct = label == "err %"
            text = fmt(run[label], pct=pct)
            if prev and not pct:
                text += delta(run[label], prev[label])
            cells.append(f"{text:>22}")
        print(f"{run['file'][:28]:<28}" + "".join(cells))


if __name__ == "__main__":
    main()
