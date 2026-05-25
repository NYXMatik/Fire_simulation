from __future__ import annotations

import argparse
import json
import re
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from reportlab.platypus import Image
from reportlab.lib.utils import ImageReader


REPOSITORY_URL = "https://github.com/NYXMatik/Fire_simulation"
REPORT_WORKFLOW_URL = f"{REPOSITORY_URL}/actions/workflows/project-report.yml"
REPORT_WORKFLOW_FILE_URL = f"{REPOSITORY_URL}/blob/main/.github/workflows/project-report.yml"
TEST_DOCUMENTATION_URL = f"{REPOSITORY_URL}/blob/main/tests/TESTING.txt"
BEHAVIORAL_TESTS_URL = f"{REPOSITORY_URL}/blob/main/tests/test_behavioral.py"
PARAMETER_TESTS_URL = f"{REPOSITORY_URL}/blob/main/tests/test_parameters.py"
STABILITY_TESTS_URL = f"{REPOSITORY_URL}/blob/main/tests/test_stability.py"
PROPAGATOR_URL = "https://doi.org/10.3390/fire3030026"
ALEXANDRIDIS_URL = "https://doi.org/10.1016/j.amc.2008.06.046"
BASE_DIR = Path(__file__).resolve().parent


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

Mateusz Janowski, Szymon Majdak

{created}

## 1. Introduction

### 1.1 Motivation

Forest fires are highly dynamic spatial phenomena: a small ignition point can
quickly become a complex moving front whose behaviour depends on fuel, terrain,
wind and local barriers. Modelling this process makes it possible to explore
such scenarios before they occur in reality. A well-designed simulation can help
reason about where a fire may accelerate, where it may slow down, and how
changes in the environment or intervention strategy may alter the final burned
area. In this sense, fire-spread modelling is valuable not only as a technical
exercise, but as a controlled way of studying risk, prevention and response in
landscapes where real experimentation would be impossible.

The motivation of this project is to create a fire-spread simulation that can
be applied to arbitrary real-world areas extracted from Google Earth. Instead of
being limited to a predefined synthetic map, the model is intended to transform
a selected map image into a computational environment in which fire propagation
can be studied across different spatial contexts, including forest areas, open
terrain, built-up zones and natural barriers.

The central idea is to make such experimentation accessible without introducing
unnecessary application complexity. The simulation should allow the user to
choose an area, convert visible land-cover classes into model states, place an
initial ignition point and observe how fire evolves under different wind,
barrier and intervention conditions. At the same time, the user interface and
the model logic are deliberately kept clear and accessible. This makes the
application easy to operate while still allowing advanced propagation mechanisms
to be examined: terrain-dependent ignition, wind-driven spread, water blocking
and burned-cell containment can all be studied within the same interface.

### 1.2 Scientific Questions

The project is guided by the following scientific questions:

- How can a real map image be converted into a practical cellular-automaton
  environment for simulating fire spread in realistic spatial settings?
- How do different terrain classes, such as forest, open green areas and
  buildings, influence the rate and spatial pattern of fire propagation?
- How do wind direction and water barriers affect the direction, intensity and
  possible containment of fire spread?
- How does the initial ignition location influence the final burned area and
  the overall geometry of the fire-spread pattern?

## 2. Theoretical Background

### 2.1 Cellular Automata

Cellular automata are discrete spatial models in which the environment is
divided into cells. Each cell has an actual current state, such as vegetation,
active fire, burned area or water. At the next step, the model does not choose
the new state independently; it computes it from the cell's current state and
from the current states of cells in its neighbourhood. In cellular automata, a
neighbourhood means the set of nearby cells that can influence a given cell.
In this project this idea is represented by the eight surrounding cells on the
grid, so fire can spread from a burning cell to adjacent and diagonal cells.

Transition rules define how a cell changes from one state to another between
two simulation steps. A rule can be deterministic, for example water remains
water, or probabilistic, for example a vegetation cell may become burning when
one of its neighbours is already burning and the spread probability is high
enough [1][2]. The important point is that each rule is applied locally: the
model checks a cell, checks its neighbourhood and then decides the cell's next
state from this local information.

This local-rule structure is powerful because complex global behaviour can
emerge from many simple updates. A wildfire front, its shape, its asymmetry and
its interaction with barriers do not need to be scripted as one large process;
they emerge from repeated neighbourhood interactions between individual cells.
This is the emergence property of cellular automata: simple transition rules,
applied many times across a grid, can produce behaviour that looks much more
complex than the individual rule itself. For that reason, cellular automata are
useful for difficult spatial simulations such as fire spread: the rules stay
understandable and computationally light, while the resulting pattern can still
represent a dynamic and irregular phenomenon [1][2]. In this project, the
converted map already has a grid-like structure, so forest, green terrain,
buildings, water, burning cells and burned cells can all be represented
directly as cell states.

### 2.2 Probabilities of Spread

The model uses terrain-dependent probabilities of spread because different land
cover types do not burn in the same way. The PROPAGATOR cellular-automata
wildfire simulator [1] uses land-cover classes with different spread
probabilities and velocities, and this project follows the same idea at an
application scale suitable for interactive map-based simulation. Forest is
therefore treated as more fire-prone than open green terrain, while building
areas are represented as much less flammable than vegetation.

In the source work, PROPAGATOR models fire spread as a stochastic contamination
process between a burning cell and the cells in its Moore neighbourhood, meaning
the eight surrounding cells on a square grid. During each update, an active
burning cell can attempt to ignite neighbouring cells, but the chance of a
successful ignition is not constant. The nominal probability depends on both
the vegetation type of the burning cell and the vegetation type of the
neighbouring target cell. For this reason, the source does not provide one
single flammability number per terrain class; it provides a matrix of possible
burning-cell and neighbour-cell combinations. Reading the table therefore
requires choosing the row of the currently burning source cell and the column
of the neighbouring candidate cell. The resulting value is the base probability
used before other model influences, such as wind, are applied.

The same source also assigns a nominal fire-spread velocity to each vegetation
class. This velocity describes how quickly fire is expected to propagate through
that land-cover type under nominal conditions, and it supports the interpretation
of the probability matrix: highly fire-prone classes tend to receive stronger
spread behaviour than less fire-prone forest classes. The probability matrix
and the corresponding nominal velocities are presented together in Table 1
because the source uses them as linked parts of the same fire-propagation
parameterisation.

In the implementation, the raw literature-inspired values from Table 1 are
scaled to the visual time step of the application. In the project, forest is
mapped to the fire-prone-conifers row, green terrain is mapped to grassland,
and buildings are treated as a low-spread built-up proxy rather than as fully
non-burnable terrain. This keeps the simulation readable for a user while
preserving the expected ordering of spread intensity from the literature [1].

Table 1: Probabilities of fire spread and nominal fire spread velocity. Source: [1].

| Burning Cell / Neighbor Cells | Broadleaves | Shrubs | Grassland | Fire-Prone Conifers | Agro-Forestry Areas | Not Fire-Prone Forest |
| --- | --- | --- | --- | --- | --- | --- |
| Broadleaves | 0.3 | 0.375 | 0.25 | 0.275 | 0.25 | 0.25 |
| Shrubs | 0.375 | 0.375 | 0.35 | 0.4 | 0.3 | 0.375 |
| Grassland | 0.45 | 0.475 | 0.475 | 0.475 | 0.375 | 0.475 |
| Fire-Prone Conifers | 0.225 | 0.325 | 0.25 | 0.35 | 0.2 | 0.35 |
| Agro-Forestry Areas | 0.25 | 0.25 | 0.3 | 0.475 | 0.35 | 0.25 |
| Not Fire-Prone Forest | 0.075 | 0.1 | 0.075 | 0.275 | 0.075 | 0.075 |
| Nominal Fire Spread Velocity [m/min] | 100 | 140 | 120 | 200 | 120 | 60 |

The base ignition probability used by the application before the wind modifier
is applied is given in Equation (1).

Equation: IGNITION_PROBABILITY

This equation uses c as the terrain class of the neighbouring candidate cell.
P_ignite(c) is the probability that this cell ignites during one simulation
update, p_raw(c) is the raw probability selected from the literature-inspired
values in Table 1, and s is the application scaling factor. The scaling factor
is chosen from the green-terrain reference case, so s = 0.09 / 0.475 = 0.1895.
This means that grassland keeps a readable application probability of about
0.09, while the other terrain classes are scaled by the same factor. Water and
burned cells are assigned 0 because they do not provide available fuel for
further propagation.

The resulting project parameters calculated from Equation (1) are summarized
in Table 2.

Table 2: Scaled ignition probabilities and relative spread speeds used in the project.

| Terrain in project | Raw probability | Application P_ignite | Relative speed |
| --- | --- | --- | --- |
| Forest | 0.35 | 0.35 · 0.1895 = 0.0663 | 200 / 120 = 1.67 |
| Green terrain | 0.475 | 0.475 · 0.1895 = 0.09 | 120 / 120 = 1.00 |
| Buildings | 0.275 | 0.275 · 0.1895 = 0.0521 | 60 / 120 = 0.50 |
| Water / burned | 0 | 0 | - |

Forest can therefore spread more effectively than grassland even though its
single-step ignition probability is lower. The ignition probability controls
whether an individual neighbouring cell catches fire during one update, while
the relative speed controls how quickly burning cells advance through that
terrain once propagation is underway. Since forest has 1.67 times the grassland
reference speed, it can produce a stronger overall spread intensity because its
faster propagation compensates for its lower probability in Equation (1).

### 2.3 Wind Influence

Wind is included because it changes not only how much fire spreads, but also
where it spreads. Alexandridis et al. [2] model wind as a directional modifier:
spread is strengthened when the candidate spread direction is aligned with the
wind and weakened when it is opposed to the wind. The project uses this same
principle so that wind creates a visible spatial bias rather than simply
increasing all ignition probabilities equally.

The wind multiplier used in the project is given in Equation (2).

Equation: WIND_MULTIPLIER

This equation defines P_w as the wind multiplier, V as wind speed, theta as the
angle between the wind direction and the candidate spread direction, and c1 and
c2 as empirical constants from Alexandridis et al. [2]. The project uses
c1 = 0.045 and c2 = 0.131, matching the values used in that model. Because the
application interface lets the user choose wind direction but does not ask for
measured wind speed, V is fixed to 10 when wind is enabled. This value is
treated as a nominal active wind speed that makes the directional effect visible
without adding another uncertain user-controlled parameter.

The dependence on theta controls whether wind helps or suppresses spread. When
the spread direction follows the wind, theta = 0 degrees and cos(theta) = 1, so
the directional term c2(cos(theta) - 1) becomes zero and the multiplier grows
with exp(V c1). When spread is perpendicular to the wind, cos(theta) = 0, so the
directional part becomes -c2 and the multiplier is much smaller. When spread is
opposed to the wind, cos(theta) = -1, which makes the directional penalty even
stronger. When wind is disabled, the multiplier is set to 1 so that Equation (1)
remains unchanged.

The terrain probability, wind multiplier and terrain spread speed are then
combined into the final probability used for one simulation update in
Equation (3).

Equation: EFFECTIVE_PROBABILITY

This equation defines P_effective(c) as the probability actually tested during
the cell update. P_ignite(c) comes from Equation (1), P_w comes from Equation (2),
and r(c) is the relative spread speed from Table 2. The value r(c) is fixed by
terrain type rather than by the user because it represents the nominal fuel
spread behaviour inherited from the literature-based velocity ordering in
Table 1. The product P_ignite(c) · P_w is clamped to the valid probability range
before the speed exponent is applied, keeping the stochastic update stable even
under favourable wind alignment.

## 3. Simulation

Application start screen.

![Application start screen](images/application_start.png)

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
wind should create directional bias, water and burned cells
should stop propagation, and terrain type should influence ignition likelihood
and spread speed. These tests are located in
[`test_behavioral.py`]({BEHAVIORAL_TESTS_URL}).

The first representative behavioral test is *test_no_wind_spread_is_isotropic*.
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

Another behavioral example, *test_converted_map_literature_terrain_order_after_5s*,
evaluates whether different ignition points on the converted map preserve the
intended terrain hierarchy. The test selects representative coordinates for
forest, green terrain, and buildings, extracts comparable local crops around
these ignition points, and runs seeded simulations for the same duration. The
objective is not to reproduce an observed fire perimeter, because no such
reference data are available. Instead, the test checks whether the implemented
terrain parameters produce a defensible ordering of spread intensity.

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
[`test_parameters.py`]({PARAMETER_TESTS_URL}).

The representative test, *test_higher_ignition_probability_increases_spread*,
is parameterized for forest, green terrain, and buildings. For each terrain
class, it constructs a synthetic uniform grid, changes only the ignition
probability for that terrain, runs several seeded simulations for each
probability value, and computes the mean number of active burning cells at the
end of the run. This design isolates the ignition probability from other map
effects, making it possible to evaluate the response of the implemented model
to a controlled parameter change.

```python
assert means == sorted(means)
assert means[-1] > means[0] * min_growth_factor
```

The passing criteria have two parts. First, the sequence of mean burning-cell
counts must be monotonically non-decreasing as ignition probability increases.
Second, the highest tested probability must produce a sufficient increase over
the lowest tested probability, expressed through the configured
min_growth_factor threshold. This keeps the report focused on the test logic
rather than on one particular run's numeric output.

The same test group also checks spread-speed and wind parameters. Increasing
the spread-speed multiplier must increase the measured spread, wind-direction
tests must move the fire centre along the selected wind axis, and burnout timing
tests must show that delaying burnout leaves fire active for longer. The exact
measured values for the current run are available in `pytest-output.txt` and
`pytest-report.html`, which are generated in the workflow artifact.

### 4.4 Stability and Reproducibility Tests

Stability tests address the stochastic character of the simulation. Real fire
spread is not deterministic: even under similar environmental conditions, local
fuel continuity, moisture variability, turbulence, and small ignition events
can produce different trajectories. The implemented model reflects this by
using probabilistic transition rules. Therefore, different random seeds are not
expected to produce identical fire patterns. What should be required is
aggregate similarity within explicit thresholds. These tests are located in
[`test_stability.py`]({STABILITY_TESTS_URL}).

The representative test, *test_scenario_results_are_stable_across_seeds*, runs
the same scenario for seeds 1 through 12 and summarizes the final burning-cell
counts and wind-bias values. For a uniform forest scenario without wind, the
test evaluates the coefficient of variation and range of active burning cells.
These are aggregate measures: they do not require identical maps for different
seeds, but they do detect excessive instability in the simulated spread.

```python
assert burning_summary["cv"] <= max_cv
assert burning_summary["range"] <= max_range
```

The stability checks use explicit scenario thresholds and report aggregate
values for each scenario. The coefficient of variation must stay below max_cv,
the range must stay below max_range, and wind-driven scenarios must preserve the
minimum required wind-bias direction. This means the model is allowed to be
stochastic across different seeds, but its variation must remain bounded and
interpretable. The same module also contains reproducibility tests, where the
same scenario is run twice with a fixed seed and the final metrics must match
exactly. The detailed per-seed values and aggregate summaries for the current
run are available in `pytest-output.txt` and `pytest-report.html`, which are
included in the generated artifact.

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
artifact. The files included in the artifact are presented in Table 3.

Table 3: Files generated by the Project Report workflow.

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

### 5.1 General Conclusions

The project demonstrates that a real map image can be transformed into a
capable, user-friendly fire-spread simulation environment. The main strength of
the application is that it keeps interaction simple without making the model
hard to understand, while retaining modelling depth. A user can load a
converted map, choose an ignition point, change wind, place water barriers or
burned-cell barriers and immediately observe how these decisions affect the
evolving fire front.

This combination gives the project both practical and analytical value. The
interface is easy to understand, but the behaviour behind it reflects several
important mechanisms of fire propagation: terrain-dependent ignition,
wind-driven spread, active blocking by water, containment by burned cells and
sensitivity to the initial fire location. The result is a model that
is approachable for experimentation while still rich enough to study meaningful
spatial fire dynamics.

### 5.2 Answers to the Scientific Questions

The model and the accompanying analysis answer the map-conversion question by
showing that a selected Google Earth area can become the spatial basis of a
working simulation. The conversion step translates visible land-cover classes
into terrain states, and the simulation then treats those states as active
elements of the cellular automaton. This makes it possible to study fire spread
on recognizable, real-world-like areas rather than only on abstract grids.

The influence of terrain is made observable through different ignition
probabilities and spread speeds assigned to forest, open green areas and
buildings. When fire starts in or reaches these terrain classes, the model does
not propagate uniformly. Forest regions support faster spread, green terrain
produces a different response and building areas remain substantially less
flammable. The tests based on different ignition points show this mechanism
directly: changing the terrain context of the starting point changes the
measured spread and the final spatial pattern.

The model also answers the question about wind and barriers through concrete
interactive mechanisms. Wind can be added to the simulation and it changes the
direction of propagation by biasing the active fire front toward the selected
wind vector. Water can be added artificially during the simulation; once placed,
it completely blocks the possibility of fire spreading through the water cells.
Burned cells provide the same kind of barrier after fuel has already been
consumed: they do not ignite again and they stop further propagation through
that location. These features allow the user to compare free propagation,
wind-driven propagation and interrupted propagation within the same environment.

The ignition-location question is answered by making the starting point an
interactive part of the experiment. Placing the initial fire in a forest patch,
near open ground, close to buildings or next to a barrier exposes the fire front
to a different local neighbourhood from the first simulation step. As a result,
the final burned area and the geometry of the fire front can change
substantially. The model therefore makes ignition location visible as a real
driver of the scenario and a central factor in spatial fire behaviour.

### 5.3 Future Directions

Future development should focus on extending the model while preserving the
clarity and usability that make it effective. One natural extension would be to
improve map conversion by using more advanced image classification methods, so
that terrain classes can be detected more reliably from different Google Earth
exports. Another direction would be to introduce additional environmental
variables, such as slope, vegetation moisture or wind strength, which would make
the simulation more sensitive to real landscape conditions.

The model could also be extended with richer evaluation data. If historical fire
perimeters or controlled reference scenarios became available, the current
structural tests could be complemented with empirical validation. This would
make it possible to compare simulated spread patterns with observed outcomes,
calibrate parameters more precisely and assess predictive accuracy. The current
implementation provides a strong foundation for that development: it is
user-friendly, inspectable and already equipped with automated tests and
reproducible reporting through GitHub Actions.

## References

[1] Trucchia, A. et al. (2020). [PROPAGATOR: An Operational Cellular-Automata
Based Wildfire Simulator]({PROPAGATOR_URL}). Fire, 3(3), 26.

[2] Alexandridis, A. et al. (2008). [A cellular automata model for forest fire
spread prediction: The case of the wildfire that swept through Spetses Island
in 1990]({ALEXANDRIDIS_URL}). Applied Mathematics and Computation, 204(1),
191-201.
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
    escaped = "".join(chunks).replace("`", "")
    escaped = re.sub(r"(?<!\w)\[1\](?!\w)", f'<a href="{PROPAGATOR_URL}" color="blue">[1]</a>', escaped)
    escaped = re.sub(r"(?<!\w)\[2\](?!\w)", f'<a href="{ALEXANDRIDIS_URL}" color="blue">[2]</a>', escaped)
    escaped = re.sub(r"\*([^*\n]+)\*", r"<i>\1</i>", escaped)
    math_tokens = {
        "s = 0.09 / 0.475 = 0.1895": '<i>s = 0.09 / 0.475 = 0.1895</i>',
        "c1 = 0.045 and c2 = 0.131": '<i>c</i><sub>1</sub><i> = 0.045 and c</i><sub>2</sub><i> = 0.131</i>',
        "theta = 0 degrees": '<i>θ = 0 degrees</i>',
        "cos(theta) = 1": '<i>cos(θ) = 1</i>',
        "cos(theta) = 0": '<i>cos(θ) = 0</i>',
        "cos(theta) = -1": '<i>cos(θ) = -1</i>',
        "c2(cos(theta) - 1)": '<i>c</i><sub>2</sub><i>(cos(θ) - 1)</i>',
        "exp(V c1)": '<i>exp(V c</i><sub>1</sub><i>)</i>',
        "P_effective(c)": '<i>P</i><sub><i>effective</i></sub>(<i>c</i>)',
        "P_effective": '<i>P</i><sub><i>effective</i></sub>',
        "P_ignite(c)": '<i>P</i><sub><i>ignite</i></sub>(<i>c</i>)',
        "P_ignite": '<i>P</i><sub><i>ignite</i></sub>',
        "P_w": '<i>P</i><sub><i>w</i></sub>',
        "p_raw(c)": '<i>p</i><sub><i>raw</i></sub>(<i>c</i>)',
        "p_raw": '<i>p</i><sub><i>raw</i></sub>',
        "V is": '<i>V</i> is',
        "V as": '<i>V</i> as',
        "V is fixed": '<i>V</i> is fixed',
        "theta": '<i>θ</i>',
        "c1": '<i>c</i><sub>1</sub>',
        "c2": '<i>c</i><sub>2</sub>',
        "r(c)": '<i>r</i>(<i>c</i>)',
    }
    for token in sorted(math_tokens, key=len, reverse=True):
        escaped = escaped.replace(token, math_tokens[token])
    return escaped


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
    bullet: list[str] = []
    table_lines: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(("p", " ".join(paragraph)))
            paragraph.clear()

    def flush_bullet() -> None:
        if bullet:
            blocks.append(("bullet", plain_inline(" ".join(bullet))))
            bullet.clear()

    def flush_table() -> None:
        if table_lines:
            blocks.append(("table", "\n".join(table_lines)))
            table_lines.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            flush_table()
            flush_bullet()
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
            flush_bullet()
            flush_paragraph()
            continue

        image_match = re.match(r'!\[(.*?)\]\((.*?)\)', line)
        if image_match:
            flush_table()
            flush_bullet()
            flush_paragraph()
            alt_text = image_match.group(1).strip()
            image_path = image_match.group(2).strip()
            blocks.append(("image", f"{alt_text}|{image_path}"))
            continue

        if line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            flush_bullet()
            table_lines.append(line)
            continue

        if line.startswith("# "):
            flush_table()
            flush_bullet()
            flush_paragraph()
            blocks.append(("h1", plain_inline(line[2:].strip())))
        elif line.startswith("## "):
            flush_table()
            flush_bullet()
            flush_paragraph()
            blocks.append(("h2", plain_inline(line[3:].strip())))
        elif line.startswith("### "):
            flush_table()
            flush_bullet()
            flush_paragraph()
            blocks.append(("h3", plain_inline(line[4:].strip())))
        elif line.startswith("Equation:"):
            flush_table()
            flush_bullet()
            flush_paragraph()
            blocks.append(("equation", plain_inline(line[len("Equation:") :].strip())))
        elif line.startswith("- "):
            flush_table()
            flush_bullet()
            flush_paragraph()
            bullet.append(line[2:].strip())
        elif bullet and line.startswith("  "):
            bullet.append(line.strip())
        else:
            flush_table()
            flush_bullet()
            paragraph.append(plain_inline(line.strip()))

    flush_table()
    flush_bullet()
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
        Flowable,
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
        leading=15,
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
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.6,
        leading=11,
        leftIndent=0,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0,
        textColor=colors.HexColor("#16323f"),
    )
    equation_style = ParagraphStyle(
        "Equation",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=9.0,
        leading=12,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=10,
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
    wide_table_header_style = ParagraphStyle(
        "WideTableHeader",
        parent=table_header_style,
        fontSize=7.1,
        leading=8.6,
    )
    source_table_top_style = ParagraphStyle(
        "SourceTableTop",
        parent=table_header_style,
        fontSize=9.2,
        leading=11,
        alignment=TA_CENTER,
    )
    source_table_header_style = ParagraphStyle(
        "SourceTableHeader",
        parent=table_header_style,
        fontSize=7.0,
        leading=8.7,
        alignment=TA_CENTER,
        splitLongWords=0,
    )
    source_table_side_style = ParagraphStyle(
        "SourceTableSide",
        parent=table_header_style,
        fontSize=8.4,
        leading=10,
        alignment=TA_CENTER,
    )
    source_table_label_style = ParagraphStyle(
        "SourceTableLabel",
        parent=table_cell_style,
        fontSize=8.2,
        leading=10,
        alignment=TA_CENTER,
    )
    source_table_value_style = ParagraphStyle(
        "SourceTableValue",
        parent=table_cell_style,
        fontSize=8.2,
        leading=10,
        alignment=TA_CENTER,
    )
    wide_table_cell_style = ParagraphStyle(
        "WideTableCell",
        parent=table_cell_style,
        fontSize=7.1,
        leading=8.6,
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

    class SourceMatrixTable(Flowable):
        def __init__(
            self,
            headers: list[str],
            probability_rows: list[list[str]],
            velocity_row: list[str],
            width: float,
        ) -> None:
            super().__init__()
            self.headers = headers
            self.probability_rows = probability_rows
            self.velocity_row = velocity_row
            self.width = width
            self.height = width * 0.435

        def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
            return self.width, self.height

        def _center_lines(
            self,
            text: str,
            x: float,
            y: float,
            font: str,
            size: float,
            leading: float,
        ) -> None:
            lines = text.split("<br/>")
            start = y + leading * (len(lines) - 1) / 2 - size * 0.34
            self.canv.setFont(font, size)
            for index, line in enumerate(lines):
                self.canv.drawCentredString(x, start - index * leading, line)

        def draw(self) -> None:
            canvas = self.canv
            width = self.width
            height = self.height
            left = 0
            right = width
            split_x = width * 0.27
            side_center_x = width * 0.083
            row_label_x = width * 0.205
            value_width = (right - split_x) / 6
            value_centers = [split_x + value_width * (index + 0.5) for index in range(6)]

            y_top = height
            y_burning_bottom = height * (1 - 68 / 605)
            y_header_bottom = height * (1 - 172 / 605)
            y_velocity_top = height * (1 - 511 / 605)
            y_bottom = 0

            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(0.9)
            canvas.line(left, y_top, right, y_top)
            canvas.setLineWidth(0.75)
            canvas.line(split_x, y_burning_bottom, right, y_burning_bottom)
            canvas.line(left, y_header_bottom, right, y_header_bottom)
            canvas.line(left, y_velocity_top, right, y_velocity_top)
            canvas.setLineWidth(0.9)
            canvas.line(left, y_bottom, right, y_bottom)

            self._center_lines(
                "Burning Cell",
                split_x + (right - split_x) / 2,
                (y_top + y_burning_bottom) / 2,
                "Helvetica-Bold",
                8.7,
                10,
            )
            for header, x in zip(self.headers, value_centers):
                self._center_lines(
                    header,
                    x,
                    (y_burning_bottom + y_header_bottom) / 2,
                    "Helvetica-Bold",
                    7.2,
                    8.8,
                )

            row_area = y_header_bottom - y_velocity_top
            row_step = row_area / 6
            self._center_lines(
                "Neighbor<br/>Cells",
                side_center_x,
                (y_header_bottom + y_velocity_top) / 2,
                "Helvetica-Bold",
                8.0,
                9.2,
            )
            for index, row in enumerate(self.probability_rows):
                y = y_header_bottom - row_step * (index + 0.5)
                self._center_lines(row[0], row_label_x, y, "Helvetica", 7.7, 9.3)
                for value, x in zip(row[1:], value_centers):
                    self._center_lines(value, x, y, "Helvetica", 7.7, 9.3)

            self._center_lines(
                "Nominal Fire<br/>Spread Velocity [m/min]",
                width * 0.16,
                (y_velocity_top + y_bottom) / 2,
                "Helvetica-Bold",
                8.4,
                10.2,
            )
            for value, x in zip(self.velocity_row[1:], value_centers):
                self._center_lines(value, x, (y_velocity_top + y_bottom) / 2, "Helvetica", 7.9, 9.5)

    class IgnitionEquation(Flowable):
        def __init__(self, width: float) -> None:
            super().__init__()
            self.width = width
            self.height = 54

        def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
            return self.width, self.height

        def _draw_parts(self, x: float, y: float, parts: list[tuple[str, str, float, float]]) -> float:
            cursor = x
            for text, font, size, y_offset in parts:
                self.canv.setFont(font, size)
                self.canv.drawString(cursor, y + y_offset, text)
                cursor += self.canv.stringWidth(text, font, size)
            return cursor

        def _draw_p_ignite(self, x: float, y: float, size: float = 13) -> float:
            return self._draw_parts(
                x,
                y,
                [
                    ("P", "Times-Italic", size, 0),
                    ("ignite", "Times-Italic", size * 0.62, -3.8),
                    ("(c)", "Times-Italic", size, 0),
                ],
            )

        def _draw_p_raw(self, x: float, y: float, size: float = 12) -> float:
            return self._draw_parts(
                x,
                y,
                [
                    ("p", "Times-Italic", size, 0),
                    ("raw", "Times-Italic", size * 0.62, -3.4),
                    ("(c)", "Times-Italic", size, 0),
                ],
            )

        def draw(self) -> None:
            canvas = self.canv
            start_x = self.width * 0.18
            base_y = 27

            cursor = self._draw_p_ignite(start_x, base_y, 13)
            cursor = self._draw_parts(cursor + 11, base_y, [("=", "Times-Roman", 13, 0)])

            brace_x = cursor + 12
            canvas.saveState()
            canvas.translate(brace_x, base_y - 10)
            canvas.scale(0.68, 1)
            canvas.setFont("Times-Roman", 39)
            canvas.drawString(0, 0, "{")
            canvas.restoreState()

            case_x = cursor + 47
            top_y = base_y + 10
            bottom_y = base_y - 14
            self._draw_parts(
                case_x,
                top_y,
                [
                    ("0,", "Times-Roman", 12, 0),
                    (" if ", "Times-Roman", 12, 0),
                    ("c", "Times-Italic", 12, 0),
                    (" is water or burned", "Times-Roman", 12, 0),
                ],
            )
            p_cursor = self._draw_p_raw(case_x, bottom_y, 12)
            self._draw_parts(
                p_cursor,
                bottom_y,
                [
                    (" · ", "Times-Roman", 12, 0),
                    ("s", "Times-Italic", 12, 0),
                    (", otherwise", "Times-Roman", 12, 0),
                ],
            )
            canvas.setFont("Times-Roman", 12)
            canvas.drawRightString(self.width - 4, base_y - 2, "(1)")

    class WindMultiplierEquation(Flowable):
        def __init__(self, width: float) -> None:
            super().__init__()
            self.width = width
            self.height = 42

        def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
            return self.width, self.height

        def _draw_parts(self, x: float, y: float, parts: list[tuple[str, str, float, float]]) -> float:
            cursor = x
            for text, font, size, y_offset in parts:
                self.canv.setFont(font, size)
                self.canv.drawString(cursor, y + y_offset, text)
                cursor += self.canv.stringWidth(text, font, size)
            return cursor

        def _draw_p_w(self, x: float, y: float, size: float = 13) -> float:
            return self._draw_parts(
                x,
                y,
                [
                    ("P", "Times-Italic", size, 0),
                    ("w", "Times-Italic", size * 0.62, -3.8),
                ],
            )

        def draw(self) -> None:
            start_x = self.width * 0.25
            base_y = 20
            cursor = self._draw_p_w(start_x, base_y, 13)
            self._draw_parts(
                cursor + 11,
                base_y,
                [
                    ("= exp", "Times-Italic", 13, 0),
                    ("[", "Times-Italic", 16, -1),
                    ("V", "Times-Italic", 13, 0),
                    ("(", "Times-Italic", 13, 0),
                    ("c", "Times-Italic", 13, 0),
                    ("1", "Times-Italic", 8, -3.8),
                    (" + ", "Times-Italic", 13, 0),
                    ("c", "Times-Italic", 13, 0),
                    ("2", "Times-Italic", 8, -3.8),
                    ("(cos ", "Times-Italic", 13, 0),
                    ("θ", "Times-Italic", 13, 0),
                    (" - 1))", "Times-Italic", 13, 0),
                    ("]", "Times-Italic", 16, -1),
                ],
            )
            self.canv.setFont("Times-Roman", 12)
            self.canv.drawRightString(self.width - 4, base_y - 2, "(2)")

    class EffectiveProbabilityEquation(Flowable):
        def __init__(self, width: float) -> None:
            super().__init__()
            self.width = width
            self.height = 42

        def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
            return self.width, self.height

        def _draw_parts(self, x: float, y: float, parts: list[tuple[str, str, float, float]]) -> float:
            cursor = x
            for text, font, size, y_offset in parts:
                self.canv.setFont(font, size)
                self.canv.drawString(cursor, y + y_offset, text)
                cursor += self.canv.stringWidth(text, font, size)
            return cursor

        def _draw_probability(self, x: float, y: float, label: str, size: float = 13) -> float:
            return self._draw_parts(
                x,
                y,
                [
                    ("P", "Times-Italic", size, 0),
                    (label, "Times-Italic", size * 0.62, -3.8),
                    ("(c)", "Times-Italic", size, 0),
                ],
            )

        def _draw_p_w(self, x: float, y: float, size: float = 13) -> float:
            return self._draw_parts(
                x,
                y,
                [
                    ("P", "Times-Italic", size, 0),
                    ("w", "Times-Italic", size * 0.62, -3.8),
                ],
            )

        def draw(self) -> None:
            start_x = self.width * 0.19
            base_y = 20
            cursor = self._draw_probability(start_x, base_y, "effective", 13)
            cursor = self._draw_parts(cursor + 11, base_y, [("= 1 - (1 - ", "Times-Roman", 13, 0)])
            cursor = self._draw_probability(cursor, base_y, "ignite", 13)
            cursor = self._draw_parts(cursor + 4, base_y, [(" · ", "Times-Roman", 13, 0)])
            cursor = self._draw_p_w(cursor, base_y, 13)
            cursor = self._draw_parts(cursor, base_y, [(")", "Times-Roman", 13, 0)])
            self._draw_parts(
                cursor + 1,
                base_y,
                [
                    ("r", "Times-Italic", 8.5, 7.0),
                    ("(c)", "Times-Italic", 8.5, 7.0),
                ],
            )
            self.canv.setFont("Times-Roman", 12)
            self.canv.drawRightString(self.width - 4, base_y - 2, "(3)")

    story = []
    blocks = markdown_blocks(markdown)
    page_width, _page_height = A4
    content_width = page_width - 2 * 28 * mm
    pending_table_caption = None
    seen_section = False
    figure_counter = 0

    for kind, text in blocks:
        escaped = reportlab_inline(text)
        if kind == "h1":
            story.append(Paragraph(escaped, title_style))
        elif text == "Mateusz Janowski, Szymon Majdak":
            story.append(Paragraph(escaped, author_style))
        elif kind == "p":
            if re.match(r'!\[(.*?)\]\((.*?)\)', text.strip()):
                continue
            story.append(Paragraph(reportlab_inline(text), body_style))
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            story.append(Paragraph(escaped, date_style))
        elif kind == "h2":
            if seen_section:
                story.append(Spacer(1, 8))
                story.append(
                    HRFlowable(
                        width="48%",
                        thickness=0.6,
                        color=colors.black,
                        spaceBefore=4,
                        spaceAfter=18,
                        hAlign="CENTER",
                    )
                )
            story.append(Paragraph(escaped, section_style))
            seen_section = True
        elif kind == "h3":
            story.append(Paragraph(escaped, subsection_style))
        elif kind == "bullet":
            story.append(Paragraph(escaped, bullet_style, bulletText="-"))
        elif kind == "equation":
            if text == "IGNITION_PROBABILITY":
                story.append(IgnitionEquation(content_width))
            elif text == "WIND_MULTIPLIER":
                story.append(WindMultiplierEquation(content_width))
            elif text == "EFFECTIVE_PROBABILITY":
                story.append(EffectiveProbabilityEquation(content_width))
            else:
                story.append(Paragraph(escaped, equation_style))
        elif kind == "code":
            code = Preformatted(text, code_style)
            table = Table([[code]], colWidths=[content_width])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f3f5")),
                        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d4da")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 8))
        elif kind == "table":
            parsed_rows = parse_markdown_table(text)
            if pending_table_caption and pending_table_caption.startswith("Table 1:"):
                headers = [
                    header.replace("Fire-Prone Conifers", "Fire-Prone<br/>Conifers")
                    .replace("Agro-Forestry Areas", "Agro-<br/>Forestry<br/>Areas")
                    .replace("Not Fire-Prone Forest", "Not<br/>Fire-Prone<br/>Forest")
                    for header in parsed_rows[0][1:]
                ]
                probability_rows = [
                    [
                        row[0].replace("Fire-Prone Conifers", "Fire-prone conifers")
                        .replace("Agro-Forestry Areas", "Agro-forestry areas")
                        .replace("Not Fire-Prone Forest", "Not fire-prone forest")
                    ]
                    + row[1:]
                    for row in parsed_rows[1:-1]
                ]
                velocity_row = parsed_rows[-1]
                table_block = [
                    Paragraph(pending_table_caption, table_caption_style),
                    Spacer(1, 6),
                    SourceMatrixTable(headers, probability_rows, velocity_row, content_width),
                    Spacer(1, 10),
                ]
                pending_table_caption = None
                story.append(KeepTogether(table_block))
                continue

            column_count = max(len(row) for row in parsed_rows)
            is_wide_table = column_count > 2
            if is_wide_table:
                first_column_width = content_width * 0.24
                other_column_width = (content_width - first_column_width) / (column_count - 1)
                column_widths = [first_column_width] + [other_column_width] * (column_count - 1)
            else:
                column_widths = [content_width * 0.42, content_width * 0.58]
            table_data = []
            for row_index, row in enumerate(parsed_rows):
                if is_wide_table:
                    style = wide_table_header_style if row_index == 0 else wide_table_cell_style
                else:
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
            table = Table(table_data, colWidths=column_widths, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8a8a8a")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3 if is_wide_table else 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3 if is_wide_table else 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4 if is_wide_table else 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if is_wide_table else 5),
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

        elif kind == "image":
            figure_counter += 1
            caption, img_path = text.split("|", 1)
            resolved_img_path = (BASE_DIR / img_path).resolve()

            img = Image(str(resolved_img_path))
            available_width = A4[0] - (28 * mm) - (28 * mm)
            img._restrictSize(available_width, 260)
            story.append(img)

            full_caption = f"Figure {figure_counter}. {caption}" if caption else f"Figure {figure_counter}."
            story.append(Paragraph(full_caption, table_caption_style))
            story.append(Spacer(1, 10))

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
