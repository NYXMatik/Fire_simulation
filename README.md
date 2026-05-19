# Fire Simulation

[![Tests](https://github.com/NYXMatik/Fire_simulation/actions/workflows/tests.yml/badge.svg)](https://github.com/NYXMatik/Fire_simulation/actions/workflows/tests.yml)

Interactive cellular-automaton simulation of fire spread on a converted map.
The model supports terrain-dependent spread, wind bias, water barriers, and
controlled-burn firebreaks.

## Repository Structure

```text
fire_simulation/   Application package and simulation engine
maps/              Source and converted map images
tests/             Automated tests and formal test documentation
scripts/           Helper scripts used by CI reporting
.github/workflows/ GitHub Actions workflow definitions
```

## Run the Application

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the interactive simulation:

```bash
python -m fire_simulation.app
```

Controls:

- left mouse button - add regular fire
- right mouse button - add a water barrier or controlled-burn line
- `C` - switch the right mouse action
- `W/A/S/D` - set wind direction
- `X` - cancel wind
- `SPACE` - start or pause simulation
- `UP/DOWN` - change simulation speed
- `R` - reset the map

## Tests

Run the full test suite:

```bash
python -m pytest
```

Run a selected test group:

```bash
python -m pytest tests/test_behavioral.py
python -m pytest tests/test_parameters.py
python -m pytest tests/test_stability.py
```

Detailed formal documentation for every test case is available in
[tests/TESTING.txt](tests/TESTING.txt).

## Continuous Integration

GitHub Actions runs the test suite on every push to `main`, on pull requests,
and manually from the Actions tab.

Each run uploads the `fire-simulation-test-report` artifact containing:

- `fire-simulation-test-report.html` - custom report with summary chart and per-test output
- `pytest-report.html` - standard pytest-html report
- `pytest-report.json` - structured pytest data
- `pytest-junit.xml` - JUnit-compatible report
- `pytest-output.txt` - full console output

The workflow is available here:
[Tests workflow](https://github.com/NYXMatik/Fire_simulation/actions/workflows/tests.yml).

## Model Notes

Terrain ignition probabilities and spread speeds are scaled from Trucchia et al.
(2020), "PROPAGATOR: An Operational Cellular-Automata Based Wildfire Simulator".
The simulation is stochastic during interactive use, while tests use explicit
seeds for reproducible results.
