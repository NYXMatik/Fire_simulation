from __future__ import annotations

import argparse
import json
import re
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_URL = "https://github.com/NYXMatik/Fire_simulation"
REPORT_WORKFLOW_URL = f"{REPOSITORY_URL}/actions/workflows/project-report.yml"
REPORT_WORKFLOW_FILE_URL = f"{REPOSITORY_URL}/blob/main/.github/workflows/project-report.yml"
TEST_DOCUMENTATION_URL = f"{REPOSITORY_URL}/blob/main/tests/TESTING.txt"


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
        return (
            "No pytest JSON summary was available when this report was generated, "
            "so the current pass/fail counts could not be derived."
        )

    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0) + counts.get("error", 0)
    skipped = counts.get("skipped", 0)
    return (
        "According to `pytest-report.json`, which is generated during the same "
        f"workflow run, the current run collected {total} tests: {passed} passed, "
        f"{failed} failed or errored and {skipped} skipped."
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

### 4.1 Testing Strategy and Types of Testing

The evaluation of the fire-spread model is constrained by the absence of an
independent empirical data set for the analysed maps. Consequently, the model
cannot be validated through direct comparison between simulated and observed
fire perimeters at successive time steps. The evaluation therefore focuses on
structural verification: whether the implemented cellular-automaton model is
internally coherent, theoretically plausible and stable under controlled
experimental conditions.

The test suite applies three complementary forms of assessment. Behavioral
tests examine whether qualitative model rules hold in controlled scenarios.
Parameter sensitivity tests verify whether changes in declared model parameters
produce the expected direction of change in simulation outputs. Stability and
reproducibility tests evaluate whether stochastic variation remains bounded
across random seeds and whether identical seeded runs can be reproduced exactly.

### 4.2 Behavioral Tests

Behavioral tests are used to verify qualitative properties that should hold
independently of a particular empirical data set. They are especially important
in this project because the simulation contains explicit modelling assumptions:
wind should create directional bias, water and completed controlled-burn cells
should stop propagation, and terrain type should influence ignition likelihood
and spread speed. These tests are located in `tests/test_behavioral.py`.

The first representative behavioral test is `test_no_wind_spread_is_isotropic`.
Its purpose is to verify the geometric neutrality of the model when wind is
absent. A synthetic 41 by 41 grid is filled with one terrain class, the ignition
point is placed exactly at the centre, and the ignition probability is set to
1.0. By eliminating random non-ignition, the test isolates the geometry of the
neighbourhood update rule. If there is no wind and every eligible neighbour can
ignite, the active fire front should expand symmetrically along the horizontal
and vertical directions.

```python
assert left == right
assert up == down
assert left + right == up + down
```

The passing criteria are strict. The left and right radii of the burning region
must be equal, the upward and downward radii must be equal, and the total
horizontal diameter must match the total vertical diameter. A failure would
indicate that the model introduces directional bias even when no wind is
present, which would undermine later interpretation of wind-driven spread.

The second representative behavioral test is
`test_converted_map_literature_terrain_order_after_5s`. It evaluates whether
different ignition points on the converted map preserve the intended terrain
hierarchy. The test selects representative coordinates for forest, green
terrain, and buildings, extracts comparable local crops around these ignition
points, and runs seeded simulations for the same duration. The objective is not
to reproduce an observed fire perimeter, because no such reference data are
available. Instead, the test checks whether the implemented terrain parameters
produce a defensible ordering of spread intensity.

```python
assert forest["mean_burning_cells"] > green["mean_burning_cells"] * 1.15
assert buildings["mean_burning_cells"] < green["mean_burning_cells"] * 0.1
```

The passing criteria are ratio-based rather than exact-value-based. Forest must
produce a mean number of burning cells at least 15 percent greater than green
terrain, while buildings must remain below 10 percent of the green-terrain
spread. This form of criterion is appropriate because stochastic simulations
should not be judged by one exact cell count without observational calibration.
The test instead verifies that the terrain-dependent ignition probabilities and
spread speeds preserve the expected relative behaviour.

### 4.3 Parameter Sensitivity Tests

Parameter sensitivity tests verify that model parameters are operationally
meaningful. In a simulation without empirical calibration data, it is not enough
to define parameters in the code; it must also be shown that changing them
affects model dynamics in the expected direction. These tests are located in
`tests/test_parameters.py`.

The representative test is
`test_higher_ignition_probability_increases_spread`. The test is parameterized
for forest, green terrain, and buildings. For each terrain class, it constructs
a synthetic uniform grid, changes only the ignition probability for that
terrain, runs several seeded simulations for each probability value, and
computes the mean number of active burning cells at the end of the run. This
design isolates the ignition probability from other map effects, making it
possible to evaluate the response of the implemented model to a controlled
parameter change.

```python
assert means == sorted(means)
assert means[-1] > means[0] * 2
```

The passing criteria have two parts. First, the sequence of mean burning-cell
counts must be monotonically non-decreasing as ignition probability increases.
Second, the highest tested probability must produce more than twice as many
active burning cells as the lowest tested probability. The first condition
verifies directionality; the second verifies that the parameter has practical
effect at the scale of the simulation. This kind of sensitivity test is a
standard substitute for direct calibration when target empirical values are not
available.

### 4.4 Stability and Reproducibility Tests

Stability tests address the stochastic character of the simulation. Real fire
spread is not deterministic: even under similar environmental conditions, local
fuel continuity, moisture variability, turbulence, and small ignition events
can produce different trajectories. The implemented model reflects this by
using probabilistic transition rules. Therefore, different random seeds are not
expected to produce identical fire patterns. What should be required is
aggregate similarity within explicit thresholds.

The representative test is
`test_scenario_results_are_stable_across_seeds`. It runs the same scenario for
seeds 1 through 12 and summarizes the final burning-cell counts and wind-bias
values. For a uniform forest scenario without wind, the test evaluates the
coefficient of variation and range of active burning cells. These are aggregate
measures: they do not require identical maps for different seeds, but they do
detect excessive instability in the simulated spread.

```python
assert burning_summary["cv"] <= scenario.max_burning_cv
assert burning_summary["range"] <= scenario.max_burning_range
```

The passing criteria define an admissible threshold of stochastic variation. In
the forest no-wind scenario, the coefficient of variation must remain below the
scenario-specific bound and the range of burning-cell counts must not exceed the
accepted limit. This is not a claim that all stochastic runs are identical.
Rather, it means that the model remains statistically controlled across seeds.
The same module also contains reproducibility tests, where the same scenario is
run twice with the same seed and the final metrics must match exactly. Thus the
model is allowed to be stochastic across different seeds, but it must be
deterministic and reproducible when the seed is fixed.

### 4.5 Test Documentation and Generated Results

The examples above are only a selected part of the complete evaluation suite.
The documentation of all tests, including the tests discussed in this section
and all remaining behavioral, parameter sensitivity, stability, and
reproducibility tests, is stored in the
[`test documentation file`]({TEST_DOCUMENTATION_URL}). That document provides a
formal description of each test case: objective, input conditions, execution
procedure, measured evidence and acceptance criteria.

The test results can be inspected through the same GitHub Actions workflow that
generates this report. The workflow is stored in
[`project-report.yml`]({REPORT_WORKFLOW_FILE_URL}) and is available in GitHub
Actions as [`Project Report`]({REPORT_WORKFLOW_URL}). During each run, the workflow
executes pytest, generates structured reports, builds a custom HTML summary,
creates the formal PDF report, and uploads the `fire-simulation-project-report`
artifact. The files included in the artifact are listed in Table 1.

Table 1. Files generated by the Project Report workflow.

| File | Purpose |
| --- | --- |
| `fire-simulation-project-report.pdf` | Formal project report generated from the current repository state. |
| `fire-simulation-test-report.html` | Custom report with an outcome chart, per-test durations, and captured diagnostic output. |
| `pytest-report.html` | Standard browsable pytest-html report. |
| `pytest-report.json` | Structured pytest data used by the custom report generator. |
| `pytest-junit.xml` | JUnit-compatible report suitable for external tools. |
| `pytest-output.txt` | Complete console output, including printed model metrics from individual tests. |

The generated PDF and the complete test evidence are therefore preserved
together in one downloadable artifact.

{outcome_sentence(total, counts)}

## 5. Conclusions
"""


def plain_inline(text: str) -> str:
    text = text.replace("`", "")
    return text


def reportlab_inline(text: str) -> str:
    chunks: list[str] = []
    cursor = 0
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        chunks.append(
            text[cursor : match.start()]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        label = (
            match.group(1)
            .replace("`", "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        url = match.group(2).replace('"', "%22")
        chunks.append(f'<a href="{url}" color="blue">{label}</a>')
        cursor = match.end()
    chunks.append(
        text[cursor:]
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return "".join(chunks).replace("`", "")


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
    table_lines: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(("p", " ".join(paragraph)))
            paragraph.clear()

    def flush_table() -> None:
        if table_lines:
            blocks.append(("table", "\n".join(table_lines)))
            table_lines.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            flush_table()
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
            flush_table()
            flush_paragraph()
            continue

        if line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            table_lines.append(line)
            continue

        if line.startswith("# "):
            flush_table()
            flush_paragraph()
            blocks.append(("h1", plain_inline(line[2:].strip())))
        elif line.startswith("## "):
            flush_table()
            flush_paragraph()
            blocks.append(("h2", plain_inline(line[3:].strip())))
        elif line.startswith("### "):
            flush_table()
            flush_paragraph()
            blocks.append(("h3", plain_inline(line[4:].strip())))
        elif line.startswith("- "):
            flush_table()
            flush_paragraph()
            blocks.append(("bullet", plain_inline(line[2:].strip())))
        else:
            flush_table()
            paragraph.append(plain_inline(line.strip()))

    flush_table()
    flush_paragraph()
    if code_lines:
        blocks.append(("code", "\n".join(code_lines)))
    return blocks


def parse_markdown_table(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        cells = [plain_inline(cell.strip()) for cell in line.strip("|").split("|")]
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        rows.append(cells)
    return rows


def text_width(text: str, size: int) -> float:
    return len(text) * size * 0.46


def justified_word_spacing(line: str, target_width: float, size: int) -> float:
    spaces = line.count(" ")
    if spaces == 0:
        return 0.0
    extra = target_width - text_width(line, size)
    if extra <= 0:
        return 0.0
    return min(extra / spaces, 2.0)


def build_reportlab_pdf(markdown: str, output: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        PageBreak,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    author_style = ParagraphStyle(
        "ReportAuthor",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=13,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    date_style = ParagraphStyle(
        "ReportDate",
        parent=author_style,
        fontSize=12,
        spaceAfter=34,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        alignment=TA_LEFT,
        spaceBefore=14,
        spaceAfter=18,
    )
    subsection_style = ParagraphStyle(
        "Subsection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=12,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyJustified",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=11,
        leading=14,
        alignment=TA_JUSTIFY,
        firstLineIndent=0,
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle(
        "BulletJustified",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=0,
        bulletIndent=0,
        spaceAfter=5,
    )
    code_style = ParagraphStyle(
        "Code",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8.8,
        leading=11,
        textColor=colors.HexColor("#002b36"),
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        alignment=TA_LEFT,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=body_style,
        fontName="Times-Roman",
        fontSize=9.5,
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    table_caption_style = ParagraphStyle(
        "TableCaption",
        parent=body_style,
        fontName="Times-Roman",
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=0,
    )

    story = []
    blocks = markdown_blocks(markdown)
    page_width, _page_height = A4
    content_width = page_width - 2 * 28 * mm
    pending_table_caption = None

    for kind, text in blocks:
        escaped = reportlab_inline(text)
        if kind == "h1":
            story.append(Paragraph(escaped, title_style))
        elif text == "Mateusz Janowski":
            story.append(Paragraph(escaped, author_style))
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            story.append(Paragraph(escaped, date_style))
        elif kind == "h2":
            if text == "5. Conclusions":
                story.append(Spacer(1, 8))
                story.append(HRFlowable(width="48%", thickness=0.6, color=colors.black, spaceBefore=4, spaceAfter=18))
            story.append(Paragraph(escaped, section_style))
        elif kind == "h3":
            story.append(Paragraph(escaped, subsection_style))
        elif kind == "bullet":
            story.append(Paragraph(escaped, bullet_style, bulletText="-"))
        elif kind == "code":
            code = Preformatted(text, code_style)
            table = Table([[code]], colWidths=[content_width])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f1f3")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 8))
        elif kind == "table":
            parsed_rows = parse_markdown_table(text)
            table_data = []
            for row_index, row in enumerate(parsed_rows):
                style = table_header_style if row_index == 0 else table_cell_style
                table_data.append(
                    [
                        Paragraph(
                            reportlab_inline(cell),
                            style,
                        )
                        for cell in row
                    ]
                )
            table = Table(table_data, colWidths=[content_width * 0.42, content_width * 0.58], repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8a8a8a")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            table_block = []
            if pending_table_caption is not None:
                table_block.append(Paragraph(pending_table_caption, table_caption_style))
                table_block.append(Spacer(1, 6))
                pending_table_caption = None
            table_block.append(table)
            table_block.append(Spacer(1, 10))
            story.append(KeepTogether(table_block))
        else:
            if text.startswith("Table "):
                pending_table_caption = escaped
            else:
                story.append(Paragraph(escaped, body_style))

    def add_page_number(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Times-Roman", 10)
        canvas.drawCentredString(page_width / 2, 14 * mm, str(doc.page))
        canvas.restoreState()

    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=28 * mm,
        leftMargin=28 * mm,
        topMargin=35 * mm,
        bottomMargin=25 * mm,
    )
    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


def build_pdf(markdown: str, output: Path) -> None:
    try:
        build_reportlab_pdf(markdown, output)
        return
    except ImportError:
        pass

    width = 595
    height = 842
    margin = 82
    bottom = 82
    content_width = width - 2 * margin
    y = height - 122
    pages: list[list[str]] = [[]]

    def new_page() -> None:
        nonlocal y
        pages.append([])
        y = height - 92

    def add_text(x: float, y_pos: float, text: str, size: int, font: str, word_spacing: float = 0.0) -> None:
        spacing = f" {word_spacing:.3f} Tw" if word_spacing else ""
        pages[-1].append(
            f"BT /{font} {size} Tf{spacing} {x:.2f} {y_pos:.2f} Td ({pdf_escape(text)}) Tj ET"
        )

    def add_line(
        text: str,
        size: int = 11,
        font: str = "F1",
        leading: int = 14,
        word_spacing: float = 0.0,
    ) -> None:
        nonlocal y
        if y < bottom:
            new_page()
        add_text(margin, y, text, size, font, word_spacing)
        y -= leading

    def add_paragraph(text: str) -> None:
        wrapped = textwrap.wrap(text, width=86)
        for index, line in enumerate(wrapped):
            spacing = 0.0
            if index < len(wrapped) - 1 and len(line) > 68:
                spacing = justified_word_spacing(line, content_width, 11)
            add_line(line, size=11, leading=14, word_spacing=spacing)
        add_space(7)

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
                spacing = 0.0
                if index < len(wrapped) - 1 and len(line) > 68:
                    spacing = justified_word_spacing(prefix + line, content_width, 10)
                add_line(prefix + line, size=10, leading=13, word_spacing=spacing)
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
                add_paragraph(text)
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
