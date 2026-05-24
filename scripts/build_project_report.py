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

The evaluation of the model was designed under an important methodological
constraint: no independent empirical fire-spread data set is available for the
analysed map, and therefore the simulation cannot be validated by direct
point-by-point comparison with an observed historical fire event. In such a
situation, the appropriate verification strategy is not to claim predictive
accuracy in an absolute sense, but to examine whether the implemented model is
internally coherent, reproducible under controlled assumptions, and consistent
with the theoretical mechanisms it is intended to represent. The test suite
therefore evaluates model behaviour through controlled scenarios, parameter
sensitivity analysis, and stochastic stability checks.

This distinction is essential. A cellular-automaton wildfire model is a
mechanistic approximation: its credibility depends on whether local transition
rules, terrain-dependent probabilities, wind effects, and intervention
mechanisms produce responses that are theoretically plausible. Since the project
does not include calibrated observational data, the tests are formulated as
structural and behavioural validation. They verify that the model reacts in the
correct direction when assumptions are changed, that important limiting cases
are handled correctly, and that random variation remains bounded rather than
dominating the simulated dynamics.

The automated test suite is stored in the repository under `tests/` and is
divided into three complementary groups: behavioral tests, parameter sensitivity
tests, and stability and reproducibility tests. The full formal description of
all test cases is available in `tests/TESTING.txt`. That document specifies the
objective, input conditions, execution procedure, measured evidence, and
acceptance criteria for every test. The GitHub repository also generates
machine-readable and human-readable test results through GitHub Actions. The
main test workflow is stored in `.github/workflows/tests.yml` and is available
in GitHub Actions as [`Tests`]({TEST_WORKFLOW_URL}). During each run, the
workflow executes pytest, creates structured and visual reports, and uploads
them as the `fire-simulation-test-report` artifact. The artifact contains:

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

Behavioral tests verify qualitative properties that should hold independently
of a particular calibration data set. They are used because the model contains
explicit rules whose validity can be assessed directly: water should block fire
propagation, completed controlled-burn areas should act as firebreaks, no-wind
spread should be geometrically symmetric under deterministic ignition, and
terrain classes should preserve the expected order of flammability. These tests
are located in `tests/test_behavioral.py`.

Parameter sensitivity tests evaluate whether the model responds coherently to
changes in its governing parameters. In the absence of empirical calibration,
it is especially important to confirm that parameters are not merely declared
in the code but actually control the resulting dynamics. For example, increasing
an ignition probability should increase the final number of active burning
cells, increasing a terrain spread-speed multiplier should make spread more
extensive, and changing the wind vector should move the fire centre in the
corresponding direction. These tests are located in `tests/test_parameters.py`.

Stability and reproducibility tests evaluate the stochastic character of the
simulation. Real fire spread is not deterministic: even under similar
environmental conditions, local fuel continuity, turbulence, moisture
heterogeneity, and small-scale ignition processes introduce variability. The
implemented simulation reflects this uncertainty through probabilistic
transition rules. Consequently, different random seeds are not expected to
produce identical final states. Instead, the evaluation admits a defined
threshold of similarity at the aggregate level, expressed through measures such
as the coefficient of variation, standard deviation, and range of active burning
cells. At the same time, when the same seed is supplied twice, the result must
be exactly reproducible. These tests are located in `tests/test_stability.py`.

### 4.2 Behavioral Test Examples

The converted-map terrain-order test verifies whether the terrain coefficients
used by the model preserve the expected qualitative hierarchy on a real
converted map. This is a behavioural validation test rather than a calibration
test: it does not assert that the simulated number of burning cells is equal to
an observed fire perimeter. Instead, it checks whether the model distinguishes
between fuel classes in a theoretically defensible way. Forest terrain is
expected to support faster spread than green terrain, whereas building terrain
is expected to remain substantially less fire-prone. The test runs three seeded
simulations for each selected terrain crop and compares average active fire
counts through ratio-based acceptance criteria:

```python
assert forest["mean_burning_cells"] > green["mean_burning_cells"] * 1.15
assert buildings["mean_burning_cells"] < green["mean_burning_cells"] * 0.1
```

The ratio-based formulation is deliberate. Exact cell counts would be an
inappropriate criterion without observational reference data and would make the
test sensitive to incidental stochastic variation. A relative comparison,
however, directly evaluates whether the implemented terrain probabilities and
spread speeds preserve the intended ordering of fire susceptibility.

The controlled-burn barrier test verifies the intended defensive intervention.
A vertical line of completed controlled-burn cells is placed between an active
fire source and the downwind side of the grid. Ignition probability is set to
one, and wind pushes the fire toward the barrier. This creates a deliberately
severe stress scenario: if any spread across the completed burnout line is
observed, the firebreak mechanism is not functioning as specified. Under these
conditions, no active fire may appear beyond the completed line:

```python
assert not leaked_fire_points
```

This test is necessary because controlled burnout is not only a visual feature
of the application. It is a modelling assumption about intervention: once the
line has completed its burnout state, it must remove available fuel and prevent
subsequent propagation through that cell sequence.

### 4.3 Parameter Sensitivity Example

One parameter test verifies that higher ignition probability increases spread.
This is an important sensitivity check because, in a model without external
calibration data, the internal role of each parameter must be demonstrated
explicitly. The test is parameterized for forest, green terrain, and buildings.
For each terrain type, it runs several deterministic seeds for multiple
probability values, computes mean active fire counts, and checks monotonic
growth:

```python
assert means == sorted(means)
assert means[-1] > means[0] * 2
```

The test therefore verifies both directionality and practical magnitude. The
monotonicity assertion checks that increasing the probability does not reduce
spread, while the ratio condition requires the change to be large enough to be
meaningful at the simulation scale. This is a common substitute for direct
calibration when empirical target values are unavailable: the model is assessed
by whether its response surface is qualitatively consistent with the governing
assumptions.

### 4.4 Stability and Reproducibility Example

The stability tests run representative scenarios across seeds 1 through 12.
They acknowledge that a probabilistic fire model should not produce identical
outputs for different seeds. Fire spread is inherently sensitive to local
conditions and small ignition events; therefore, enforcing determinism across
different seeds would be conceptually wrong. The purpose of stability testing is
instead to determine whether the aggregate behaviour remains controlled. For
example, a uniform forest scenario without wind is evaluated using the
coefficient of variation and the range of active burning cells. The accepted
bounds are model-specific thresholds selected to identify excessive instability:

```python
assert burning_summary["cv"] <= scenario.max_burning_cv
assert burning_summary["range"] <= scenario.max_burning_range
```

The same module also checks deterministic reproducibility by running each
scenario twice with the same seed and comparing the final metrics exactly:

```python
assert first == second
```

Together, these checks separate stochastic variability from computational
non-reproducibility. Different seeds may lead to different trajectories, but
those trajectories must remain statistically comparable within the accepted
thresholds. The same seed, however, must reproduce the same final metrics. This
combination is essential for a simulation that is both realistic in its
uncertainty and usable for scientific inspection, debugging, and continuous
integration.

### 4.5 Evaluation Summary

The current evaluation strategy does not claim empirical prediction accuracy;
such a claim would require independent observations of fire spread under known
meteorological and fuel conditions. Instead, the evaluation establishes that the
implemented model is internally consistent, sensitive to its declared
parameters, stable under repeated stochastic runs, and exactly reproducible when
the random seed is fixed. This is the appropriate level of validation for the
available evidence. GitHub Actions stores the resulting evidence as
downloadable artifacts, which makes the evaluation repeatable and auditable
directly from the repository.

## 5. Conclusions
"""


def plain_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
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

    story = []
    blocks = markdown_blocks(markdown)
    page_width, _page_height = A4
    content_width = page_width - 2 * 28 * mm

    for kind, text in blocks:
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
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
