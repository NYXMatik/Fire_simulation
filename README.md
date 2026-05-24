# Fire Simulation

[![Project Report](https://github.com/NYXMatik/Fire_simulation/actions/workflows/project-report.yml/badge.svg)](https://github.com/NYXMatik/Fire_simulation/actions/workflows/project-report.yml)

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

Each run of the project-report workflow executes the test suite and uploads the
`fire-simulation-project-report` artifact containing:

- `fire-simulation-project-report.pdf` - formal project report
- `fire-simulation-test-report.html` - custom report with summary chart and per-test output
- `pytest-report.html` - standard pytest-html report
- `pytest-report.json` - structured pytest data
- `pytest-junit.xml` - JUnit-compatible report
- `pytest-output.txt` - full console output

The workflow is available here:
[Project Report workflow](https://github.com/NYXMatik/Fire_simulation/actions/workflows/project-report.yml).

## Model Notes

Terrain ignition probabilities and spread speeds are scaled from Trucchia et al.
(2020), "PROPAGATOR: An Operational Cellular-Automata Based Wildfire Simulator".
The simulation is stochastic during interactive use, while tests use explicit
seeds for reproducible results.

## References

- Trucchia, A. et al. (2020). [PROPAGATOR: An Operational Cellular-Automata Based Wildfire Simulator](https://doi.org/10.3390/fire3030026).
- Alexandridis, A. et al. (2008). [A cellular automata model for forest fire spread prediction: The case of the wildfire that swept through Spetses Island in 1990](https://doi.org/10.1016/j.amc.2008.06.046).
