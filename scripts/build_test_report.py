from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path


OUTCOME_LABELS = {
    "passed": "Passed",
    "failed": "Failed",
    "error": "Error",
    "skipped": "Skipped",
    "xfailed": "Expected failure",
    "xpassed": "Unexpected pass",
}

OUTCOME_COLORS = {
    "passed": "#1a936f",
    "failed": "#d64045",
    "error": "#9d2a2a",
    "skipped": "#f2b84b",
    "xfailed": "#6b7280",
    "xpassed": "#7c3aed",
}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def node_parts(nodeid: str) -> tuple[str, str]:
    if "::" not in nodeid:
        return nodeid, nodeid
    file_name, test_name = nodeid.split("::", 1)
    return file_name, test_name


def phase_output(test: dict) -> str:
    chunks: list[str] = []
    for phase_name in ("setup", "call", "teardown"):
        phase = test.get(phase_name) or {}
        stdout = phase.get("stdout") or ""
        stderr = phase.get("stderr") or ""
        crash = phase.get("crash") or {}
        traceback = phase.get("traceback") or []
        if stdout:
            chunks.append(f"[{phase_name} stdout]\n{stdout.rstrip()}")
        if stderr:
            chunks.append(f"[{phase_name} stderr]\n{stderr.rstrip()}")
        if crash:
            message = crash.get("message") or crash.get("reprcrash") or crash
            chunks.append(f"[{phase_name} crash]\n{message}")
        if traceback:
            chunks.append(f"[{phase_name} traceback]\n" + "\n".join(map(str, traceback)))
    return "\n\n".join(chunks).strip()


def duration(test: dict) -> float:
    if isinstance(test.get("duration"), (int, float)):
        return float(test["duration"])
    total = 0.0
    for phase_name in ("setup", "call", "teardown"):
        phase = test.get(phase_name) or {}
        if isinstance(phase.get("duration"), (int, float)):
            total += float(phase["duration"])
    return total


def pct(value: int, total: int) -> str:
    if not total:
        return "0.0%"
    return f"{(value / total) * 100:.1f}%"


def donut_gradient(counts: Counter, total: int) -> str:
    if total == 0:
        return "#e5e7eb 0 360deg"
    angle = 0.0
    stops: list[str] = []
    for outcome in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
        count = counts.get(outcome, 0)
        if count == 0:
            continue
        next_angle = angle + (count / total) * 360
        color = OUTCOME_COLORS.get(outcome, "#64748b")
        stops.append(f"{color} {angle:.2f}deg {next_angle:.2f}deg")
        angle = next_angle
    return ", ".join(stops) or "#e5e7eb 0 360deg"


def build_html(report: dict) -> str:
    tests = report.get("tests") or []
    counts = Counter(test.get("outcome", "unknown") for test in tests)
    total = len(tests)
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0) + counts.get("error", 0)
    skipped = counts.get("skipped", 0)
    total_duration = sum(duration(test) for test in tests)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for test in tests:
        file_name, _ = node_parts(test.get("nodeid", "unknown"))
        grouped[file_name].append(test)

    legend_items = []
    for outcome in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
        count = counts.get(outcome, 0)
        if count:
            label = OUTCOME_LABELS.get(outcome, outcome.title())
            color = OUTCOME_COLORS.get(outcome, "#64748b")
            legend_items.append(
                f'<span class="legend-item"><span class="dot" style="background:{color}"></span>'
                f"{escape(label)}: {count} ({pct(count, total)})</span>"
            )

    sections = []
    for file_name in sorted(grouped):
        file_tests = grouped[file_name]
        rows = []
        for test in file_tests:
            outcome = test.get("outcome", "unknown")
            _, test_name = node_parts(test.get("nodeid", "unknown"))
            output = phase_output(test)
            output_block = (
                f"<pre>{escape(output)}</pre>" if output else '<p class="empty">No captured output.</p>'
            )
            rows.append(
                f"""
                <details class="test-card">
                  <summary>
                    <span class="status status-{escape(outcome)}">{escape(outcome.upper())}</span>
                    <span class="test-name">{escape(test_name)}</span>
                    <span class="duration">{duration(test):.2f}s</span>
                  </summary>
                  <div class="test-body">
                    <p><strong>Node id:</strong> <code>{escape(test.get("nodeid", ""))}</code></p>
                    {output_block}
                  </div>
                </details>
                """
            )
        sections.append(
            f"""
            <section>
              <h2>{escape(file_name)}</h2>
              {''.join(rows)}
            </section>
            """
        )

    status_text = "PASSED" if failed == 0 else "FAILED"
    status_class = "ok" if failed == 0 else "bad"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fire Simulation Test Report</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: #f6f7f9;
      color: #172033;
    }}
    body {{
      margin: 0;
      background: #f6f7f9;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 32px auto;
    }}
    header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 24px;
      align-items: center;
      border-bottom: 1px solid #d9dee7;
      padding-bottom: 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.12;
    }}
    h2 {{
      margin: 28px 0 12px;
      font-size: 20px;
    }}
    .meta {{
      margin: 0;
      color: #596579;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 8px 12px;
      font-weight: 700;
      color: white;
      background: #1a936f;
    }}
    .badge.bad {{
      background: #d64045;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 24px 0;
    }}
    .metric {{
      background: white;
      border: 1px solid #e2e6ee;
      border-radius: 8px;
      padding: 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 28px;
      margin-bottom: 4px;
    }}
    .metric span {{
      color: #596579;
    }}
    .chart-row {{
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 24px;
      align-items: center;
      background: white;
      border: 1px solid #e2e6ee;
      border-radius: 8px;
      padding: 20px;
    }}
    .donut {{
      width: 190px;
      height: 190px;
      border-radius: 50%;
      background: conic-gradient({donut_gradient(counts, total)});
      position: relative;
    }}
    .donut::after {{
      content: "{passed}/{total}";
      position: absolute;
      inset: 34px;
      border-radius: 50%;
      background: white;
      display: grid;
      place-items: center;
      font-size: 28px;
      font-weight: 800;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #334155;
    }}
    .dot {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }}
    .test-card {{
      background: white;
      border: 1px solid #e2e6ee;
      border-radius: 8px;
      margin: 8px 0;
      overflow: hidden;
    }}
    summary {{
      cursor: pointer;
      display: grid;
      grid-template-columns: 92px 1fr 76px;
      gap: 12px;
      align-items: center;
      padding: 12px 14px;
    }}
    .status {{
      border-radius: 999px;
      color: white;
      font-size: 12px;
      font-weight: 800;
      padding: 5px 8px;
      text-align: center;
    }}
    .status-passed {{ background: #1a936f; }}
    .status-failed, .status-error {{ background: #d64045; }}
    .status-skipped {{ background: #f2b84b; color: #35220a; }}
    .status-xfailed {{ background: #6b7280; }}
    .status-xpassed {{ background: #7c3aed; }}
    .test-name {{
      font-family: Consolas, Menlo, monospace;
      overflow-wrap: anywhere;
    }}
    .duration {{
      color: #596579;
      text-align: right;
    }}
    .test-body {{
      border-top: 1px solid #edf0f5;
      padding: 14px;
    }}
    code {{
      background: #f1f4f8;
      border-radius: 5px;
      padding: 2px 5px;
    }}
    pre {{
      margin: 12px 0 0;
      padding: 14px;
      overflow-x: auto;
      border-radius: 8px;
      background: #111827;
      color: #d1d5db;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    .empty {{
      color: #64748b;
      margin-bottom: 0;
    }}
    @media (max-width: 760px) {{
      header, .chart-row, .summary {{
        grid-template-columns: 1fr;
      }}
      summary {{
        grid-template-columns: 1fr;
      }}
      .duration {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Fire Simulation Test Report</h1>
        <p class="meta">Generated {escape(created)} from pytest JSON results.</p>
      </div>
      <span class="badge {status_class}">{status_text}</span>
    </header>

    <div class="summary">
      <div class="metric"><strong>{total}</strong><span>Total tests</span></div>
      <div class="metric"><strong>{passed}</strong><span>Passed</span></div>
      <div class="metric"><strong>{failed}</strong><span>Failed/errors</span></div>
      <div class="metric"><strong>{total_duration:.1f}s</strong><span>Total test time</span></div>
    </div>

    <div class="chart-row">
      <div class="donut" aria-label="Test outcome donut chart"></div>
      <div>
        <h2>Outcome Summary</h2>
        <div class="legend">{''.join(legend_items)}</div>
      </div>
    </div>

    {''.join(sections)}
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an HTML test report from pytest-json-report output.")
    parser.add_argument("--json", required=True, type=Path, help="Path to pytest JSON report.")
    parser.add_argument("--output", required=True, type=Path, help="Path to generated HTML report.")
    args = parser.parse_args()

    report = read_json(args.json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
