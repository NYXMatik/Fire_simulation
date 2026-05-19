# Fire Simulation

[![Tests](https://github.com/NYXMatik/Fire_simulation/actions/workflows/tests.yml/badge.svg)](https://github.com/NYXMatik/Fire_simulation/actions/workflows/tests.yml)

Interactive cellular-automaton fire spread simulation.

## Interactive simulation

```bash
python app.py
```

Controls:

- left mouse button - add regular fire
- right mouse button - add a water barrier or a controlled burn line
- `C` - switch right mouse button between water and controlled burn
- `W/A/S/D` - set wind direction
- `X` - cancel wind
- `SPACE` - start/pause simulation
- `UP/DOWN` - change simulation speed
- `R` - reset the map

## Tests

Run behavioral, stability, and parameter tests:

```bash
python -m pytest
```

Run only one test group:

```bash
python -m pytest tests/test_behavioral.py
python -m pytest tests/test_stability.py
python -m pytest tests/test_parameters.py
```

The tests print detailed metrics while running.

## GitHub Actions test report

Tests are also run automatically in GitHub Actions on every push to `main`,
on pull requests targeting `main`, and manually from the Actions tab.

Each workflow run uploads an artifact named `fire-simulation-test-report` with:

- `pytest-report.html` - browsable HTML test report
- `pytest-junit.xml` - machine-readable JUnit report
- `pytest-output.txt` - full console output with printed metrics

To reference the report, open the latest run in the
[Tests workflow](https://github.com/NYXMatik/Fire_simulation/actions/workflows/tests.yml)
and download the artifact from the run summary.

The simulation is stochastic during normal interactive use. Test runs pass an explicit seed,
so the same scenario and seed remain reproducible while different seeds still exercise random
variation.

## Fire-spread parameter source and calibration

The model separates two terrain parameters:

- `ignition_probability`: how likely a target cell is to catch fire
- `spread_speed`: how quickly fire can propagate through that target terrain

They cooperate inside one visual tick as:

```text
P_effective = 1 - (1 - ignition_probability) ** spread_speed
```

This is equivalent to giving faster fuels more effective ignition opportunities
per tick while keeping flammability and speed visible as separate parameters.

The terrain probability and speed values are based on:

Trucchia et al. (2020). "`PROPAGATOR`: An Operational Cellular-Automata Based
Wildfire Simulator", Fire 3(3), 26.

The project uses PROPAGATOR Table 1:

```text
FOREST    -> Fire-prone conifers: raw probability 0.35, velocity 200 m/min
GREEN     -> Grassland:           raw probability 0.475, velocity 120 m/min
BUILDINGS -> WUI proxy:           raw probability 0.275, velocity 60 m/min
```

PROPAGATOR treats man-made buildings/infrastructure as non-vegetated and
non-burnable. This project uses the `BUILDINGS` color for a simplified
wildland-urban-interface class, so it is mapped to a low-flammable WUI proxy
rather than pure urban concrete.

Because this app has an abstract visual tick rather than real minutes and
meters, raw probabilities are scaled by one global factor. GREEN/Grassland is
the reference class and is scaled to `0.09`; speed is normalized by the GREEN
velocity of `120 m/min`:

```text
forest:    ignition_probability = 0.0663, spread_speed = 1.6667
green:     ignition_probability = 0.09,   spread_speed = 1.0
buildings: ignition_probability = 0.0521, spread_speed = 0.5
```

Wind uses the Alexandridis / Karakonstantis exponential factor:

```text
P_w = exp(V * (c1 + c2 * (cos(theta) - 1)))
```

where `theta` is the angle between wind direction and spread direction. The UI
stores only wind direction, so the app uses a single nominal wind speed of
`10 m/s` when wind is enabled.
