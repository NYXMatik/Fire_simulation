from __future__ import annotations

import argparse
import json
import re
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_URL = "https://github.com/NYXMatik/Fire_simulation"
TEST_WORKFLOW_URL = f"{REPOSITORY_URL}/actions/workflows/tests.yml"
REPORT_WORKFLOW_URL = f"{REPOSITORY_URL}/actions/workflows/project-report.yml"


def read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_summary(report: dict) -> tuple[int, Counter]:
    tests = report.get("tests") or []
    return len(tests), Counter(test.get("outcome", "unknown") for test in tests)


def outcome_sentence(total: int, counts: Counter) -> str:
    if total == 0:
        return "At report generation time, no pytest JSON data was available."

    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0) + counts.get("error", 0)
    skipped = counts.get("skipped", 0)
    return (
        f"The current automated run contains {total} collected test cases: "
        f"{passed} passed, {failed} failed or errored, and {skipped} skipped."
    )


def build_report(pytest_json: Path | None) -> str:
    report = read_json(pytest_json)
    total, counts = test_summary(report)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""# Simulation of Fire Spread in a Map-Based Environment

Mateusz Janowski

{created}

## 1. Introduction

## 2. Theoretical Background

## 3. Simulation

## 4. Evaluation of the Model

The model is evaluated with an automated pytest suite stored in the repository
under `tests/`. The suite is intentionally divided into three complementary
groups: behavioral tests, parameter sensitivity tests, and stability and
reproducibility tests. This structure makes the evaluation inspectable from
both a software-engineering perspective and a modelling perspective. The tests
do not only check whether the program runs; they verify whether important
properties of the fire-spread model remain consistent under controlled
conditions.

The full formal description of all test cases is available in
`tests/TESTING.txt`. That document describes the objective, input conditions,
execution procedure, measured evidence, and acceptance criteria for every test.
The GitHub repository also generates machine-readable and human-readable test
results through GitHub Actions. The main test workflow is stored in
`.github/workflows/tests.yml` and is available in GitHub Actions as
[`Tests`]({TEST_WORKFLOW_URL}). During each run, the workflow executes pytest,
creates structured and visual reports, and uploads them as the
`fire-simulation-test-report` artifact. The artifact contains:

- `fire-simulation-test-report.html`, a custom summary report with an outcome
  chart, per-test durations, and captured diagnostic output;
- `pytest-report.html`, the standard browsable pytest-html report;
- `pytest-report.json`, structured pytest data used by the custom report
  generator;
- `pytest-junit.xml`, a JUnit-compatible result file for external tools;
- `pytest-output.txt`, the complete console output, including printed model
  metrics from individual tests.

This project-report workflow is stored in `.github/workflows/project-report.yml`
and is available as [`Project Report`]({REPORT_WORKFLOW_URL}). It runs the same
test-reporting path before generating this formal report, so the project report
can be downloaded together with the current test evidence from the workflow
artifacts. {outcome_sentence(total, counts)}

### 4.1 Test Types

Behavioral tests verify qualitative rules of the simulation. They answer
questions such as whether terrain classes preserve the expected spread order,
whether water blocks fire propagation, whether wind produces a directional
bias, and whether controlled-burn cells behave as firebreaks after burnout.
These tests are located in `tests/test_behavioral.py`.

Parameter sensitivity tests change one model parameter at a time and verify
that the simulation response changes in the expected direction. They are not
intended to prove that a single numeric parameter value is universally correct.
Instead, they check whether ignition probabilities, spread-speed multipliers,
wind direction, and burnout timing are active and coherent within the
implemented model. These tests are located in `tests/test_parameters.py`.

Stability and reproducibility tests evaluate the stochastic part of the model.
The simulation is allowed to vary between different random seeds, but aggregate
outcomes must remain within calibrated bounds. The same seed must also produce
identical results. These tests are located in `tests/test_stability.py`.

### 4.2 Behavioral Test Examples

The converted-map terrain-order test checks whether the terrain coefficients
used by the model lead to the expected qualitative hierarchy on a real converted
map. Forest terrain should spread faster than green terrain, while building
terrain should remain much less fire-prone. The test runs three seeded
simulations for each selected terrain crop and compares average active fire
counts rather than exact cell counts:

```python
assert forest["mean_burning_cells"] > green["mean_burning_cells"] * 1.15
assert buildings["mean_burning_cells"] < green["mean_burning_cells"] * 0.1
```

This test is important because it connects the implementation to the modelling
assumption that terrain-dependent ignition probabilities and spread speeds are
meaningful on actual map data, not only on artificial grids.

The controlled-burn barrier test verifies the intended defensive intervention.
A vertical line of completed controlled-burn cells is placed between an active
fire and the downwind side of the grid. Ignition probability is set to one, and
wind pushes the fire toward the barrier. Under these strict conditions, no
active fire may appear beyond the completed line:

```python
assert not leaked_fire_points
```

This is a strong behavioral check because the scenario is deliberately biased
toward failure: if the fire can cross the barrier under guaranteed ignition and
favorable wind, the controlled-burn mechanism is not working correctly.

### 4.3 Parameter Sensitivity Example

One parameter test verifies that higher ignition probability increases spread.
The test is parameterized for forest, green terrain, and buildings. For each
terrain type, it runs several deterministic seeds for multiple probability
values, computes mean active fire counts, and checks monotonic growth:

```python
assert means == sorted(means)
assert means[-1] > means[0] * 2
```

This confirms that ignition probability is not a passive configuration value.
When the probability is increased, the model produces a visibly larger fire,
while still allowing stochastic variation between seeded runs.

### 4.4 Stability and Reproducibility Example

The stability tests run representative scenarios across seeds 1 through 12.
For example, a uniform forest scenario without wind is evaluated using the
coefficient of variation and the range of active burning cells. The accepted
bounds are calibrated for the implemented model:

```python
assert burning_summary["cv"] <= scenario.max_burning_cv
assert burning_summary["range"] <= scenario.max_burning_range
```

The same module also checks deterministic reproducibility by running each
scenario twice with the same seed and comparing the final metrics exactly:

```python
assert first == second
```

Together, these checks support two requirements at the same time. First, the
model remains stochastic enough for interactive simulation. Second, scientific
or debugging runs can be reproduced exactly when an explicit seed is supplied.

### 4.5 Evaluation Summary

The current evaluation strategy covers local correctness, model behavior,
parameter response, stochastic stability, and reproducibility. Behavioral tests
protect the main simulation rules, parameter tests confirm that the model reacts
coherently to controlled changes, and stability tests prevent random variation
from becoming uncontrolled. GitHub Actions stores the resulting evidence as
downloadable artifacts, which makes the evaluation repeatable and auditable
directly from the repository.

## 5. Conclusions
"""


def plain_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = text.replace("`", "")
    return text


def pdf_escape(text: str) -> str:
    return (
        text.encode("latin-1", errors="replace")
        .decode("latin-1")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def markdown_blocks(markdown: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    paragraph: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(("p", " ".join(paragraph)))
            paragraph.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                blocks.append(("code", "\n".join(code_lines)))
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line:
            flush_paragraph()
            continue

        if line.startswith("# "):
            flush_paragraph()
            blocks.append(("h1", plain_inline(line[2:].strip())))
        elif line.startswith("## "):
            flush_paragraph()
            blocks.append(("h2", plain_inline(line[3:].strip())))
        elif line.startswith("### "):
            flush_paragraph()
            blocks.append(("h3", plain_inline(line[4:].strip())))
        elif line.startswith("- "):
            flush_paragraph()
            blocks.append(("bullet", plain_inline(line[2:].strip())))
        else:
            paragraph.append(plain_inline(line.strip()))

    flush_paragraph()
    if code_lines:
        blocks.append(("code", "\n".join(code_lines)))
    return blocks


def text_width(text: str, size: int) -> float:
    return len(text) * size * 0.46


def build_pdf(markdown: str, output: Path) -> None:
    width = 595
    height = 842
    margin = 82
    bottom = 82
    y = height - 122
    pages: list[list[str]] = [[]]

    def new_page() -> None:
        nonlocal y
        pages.append([])
        y = height - 92

    def add_text(x: float, y_pos: float, text: str, size: int, font: str) -> None:
        pages[-1].append(f"BT /{font} {size} Tf {x:.2f} {y_pos:.2f} Td ({pdf_escape(text)}) Tj ET")

    def add_line(text: str, size: int = 11, font: str = "F1", leading: int = 14) -> None:
        nonlocal y
        if y < bottom:
            new_page()
        add_text(margin, y, text, size, font)
        y -= leading

    def add_centered(text: str, size: int, font: str, leading: int) -> None:
        nonlocal y
        x = (width - text_width(text, size)) / 2
        add_text(max(margin, x), y, text, size, font)
        y -= leading

    def add_rule() -> None:
        nonlocal y
        if y < bottom + 20:
            new_page()
        x1 = margin + 110
        x2 = width - margin - 110
        pages[-1].append(f"{x1:.2f} {y:.2f} m {x2:.2f} {y:.2f} l S")
        y -= 28

    def add_code_background(line_count: int) -> None:
        block_height = line_count * 12 + 12
        x = margin - 4
        rect_y = y - block_height + 16
        rect_width = width - 2 * margin + 8
        pages[-1].append(f"0.94 0.95 0.96 rg {x:.2f} {rect_y:.2f} {rect_width:.2f} {block_height:.2f} re f 0 g")

    def add_space(points: int) -> None:
        nonlocal y
        y -= points
        if y < bottom:
            new_page()

    title_done = False
    pending_rule = False
    for kind, text in markdown_blocks(markdown):
        if kind == "h1":
            for title_line in textwrap.wrap(text, width=48):
                add_centered(title_line, size=19, font="F4", leading=24)
            add_space(12)
            title_done = True
        elif kind == "h2":
            if pending_rule:
                add_rule()
                pending_rule = False
            add_space(10)
            add_line(text, size=14, font="F4", leading=20)
            add_space(16)
        elif kind == "h3":
            add_space(6)
            add_line(text, size=11, font="F4", leading=16)
            add_space(5)
        elif kind == "bullet":
            wrapped = textwrap.wrap(text, width=82)
            for index, line in enumerate(wrapped):
                prefix = "- " if index == 0 else "  "
                add_line(prefix + line, size=10, leading=13)
            add_space(3)
        elif kind == "code":
            wrapped_lines: list[str] = []
            for code_line in text.splitlines():
                wrapped_lines.extend(textwrap.wrap(code_line, width=78, replace_whitespace=False) or [""])
            if y - (len(wrapped_lines) * 12 + 16) < bottom:
                new_page()
            add_code_background(len(wrapped_lines))
            for wrapped in wrapped_lines:
                add_line(wrapped, size=9, font="F3", leading=12)
            add_space(5)
        else:
            if title_done and text in {"Mateusz Janowski"}:
                add_centered(text, size=13, font="F1", leading=24)
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                add_centered(text, size=12, font="F1", leading=52)
            else:
                for line in textwrap.wrap(text, width=86):
                    add_line(line, size=11, leading=14)
                add_space(7)
                if text.startswith("Together, these checks"):
                    pending_rule = True

    objects: list[bytes] = []
    catalog_id = 1
    pages_id = 2
    font_times_id = 3
    font_times_bold_id = 4
    font_courier_id = 5
    font_helvetica_bold_id = 6
    first_page_id = 7
    page_ids: list[int] = []
    content_ids: list[int] = []

    next_id = first_page_id
    for _page in pages:
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        next_id += 2

    objects.append(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1"))
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    for index, (page_id, content_id, lines) in enumerate(zip(page_ids, content_ids, pages), start=1):
        page_number_x = width / 2 - 3
        lines.append(f"BT /F1 10 Tf {page_number_x:.2f} 44 Td ({index}) Tj ET")
        page_obj = (
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {width} {height}] "
            f"/Resources << /Font << /F1 {font_times_id} 0 R /F2 {font_times_bold_id} 0 R "
            f"/F3 {font_courier_id} 0 R /F4 {font_helvetica_bold_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        stream = "\n".join(lines).encode("latin-1", errors="replace")
        content_obj = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        objects.append(page_obj.encode("latin-1"))
        objects.append(content_obj)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as file:
        file.write(b"%PDF-1.4\n")
        offsets = [0]
        for object_number, obj in enumerate(objects, start=1):
            offsets.append(file.tell())
            file.write(f"{object_number} 0 obj\n".encode("ascii"))
            file.write(obj)
            file.write(b"\nendobj\n")
        xref = file.tell()
        file.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        file.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            file.write(f"{offset:010d} 00000 n \n".encode("ascii"))
        file.write(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n"
            ).encode("ascii")
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the formal Fire Simulation project report.")
    parser.add_argument("--pytest-json", type=Path, help="Optional pytest JSON report used for current summary.")
    parser.add_argument("--output", type=Path, help="Optional path to the generated Markdown report.")
    parser.add_argument("--pdf-output", type=Path, help="Optional path to the generated PDF report.")
    args = parser.parse_args()

    if args.output is None and args.pdf_output is None:
        parser.error("at least one of --output or --pdf-output is required")

    report = build_report(args.pytest_json)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    if args.pdf_output is not None:
        build_pdf(report, args.pdf_output)


if __name__ == "__main__":
    main()
