"""Parameter sensitivity tests.

These tests change one model parameter at a time and check whether the simulation
responds in the expected direction. They are not meant to prove that one numeric
parameter value is "correct"; they prove that the model reacts consistently when
parameters are increased/decreased.

Covered relationships:

- Higher ignition probability should produce more active fire cells.
- Wind direction should move the fire center in the wind direction.
- A later burnout start should keep more cells actively burning and fewer cells
  already burned out.

Example output:

    Ignition probability sensitivity: forest
      {'probability': 0.08, 'mean_burning_cells': 429}
      {'probability': 0.26, 'mean_burning_cells': 1969.5}

Interpretation: raising forest ignition probability increases the average number
of burning cells, so the parameter has the intended monotonic effect.
"""

from statistics import mean

import pytest

from fire_simulation import simulation
from fire_simulation.simulation import (
    BUILDINGS,
    DEFAULT_IGNITION_PROBABILITIES,
    DEFAULT_SPREAD_SPEEDS,
    FOREST,
    GREEN,
    run_single_simulation,
)


SEEDS = range(1, 5)


def make_uniform_grid(width, height, terrain):
    """Create a controlled map so a single parameter is the main variable."""
    return {(x, y): (terrain, 0) for x in range(width) for y in range(height)}


def run_final_metrics(
    points,
    width,
    height,
    ignition_point,
    wind_direction,
    iterations,
    seed,
    ignition_probabilities=None,
    spread_speeds=None,
):
    """Run a simulation and return the final metrics row only."""
    return run_single_simulation(
        initial_points=points,
        grid_width=width,
        grid_height=height,
        ignition_point=ignition_point,
        wind_direction=wind_direction,
        iterations=iterations,
        seed=seed,
        ignition_probabilities=ignition_probabilities,
        spread_speeds=spread_speeds,
    )[-1]


def mean_burning_cells_for_probability(terrain, probability, iterations):
    """Measure how one ignition probability value changes final active fire size."""
    width = 45
    height = 45
    ignition_point = (width // 2, height // 2)
    points = make_uniform_grid(width, height, terrain)
    probabilities = dict(DEFAULT_IGNITION_PROBABILITIES)
    probabilities[terrain] = probability

    # Multiple seeds smooth out random noise while keeping the test quick enough
    # to run often during development.
    samples = []
    for seed in SEEDS:
        final = run_final_metrics(
            points,
            width,
            height,
            ignition_point,
            wind_direction=(0, 0),
            iterations=iterations,
            seed=seed,
            ignition_probabilities=probabilities,
        )
        samples.append(final.burning_cells)

    return {
        "probability": probability,
        "samples": samples,
        "mean_burning_cells": mean(samples),
    }


def mean_burning_cells_for_speed(terrain, speed, iterations):
    """Measure how the explicit spread-speed multiplier changes final fire size."""
    width = 45
    height = 45
    ignition_point = (width // 2, height // 2)
    points = make_uniform_grid(width, height, terrain)
    spread_speeds = dict(DEFAULT_SPREAD_SPEEDS)
    spread_speeds[terrain] = speed

    samples = []
    for seed in SEEDS:
        final = run_final_metrics(
            points,
            width,
            height,
            ignition_point,
            wind_direction=(0, 0),
            iterations=iterations,
            seed=seed,
            spread_speeds=spread_speeds,
        )
        samples.append(final.burning_cells)

    return {
        "speed": speed,
        "samples": samples,
        "mean_burning_cells": mean(samples),
    }


def print_parameter_table(title, rows):
    """Print a compact table of parameter values and simulation responses."""
    print(f"\n{title}")
    for row in rows:
        print(f"  {row}")


@pytest.mark.parametrize(
    ("terrain_name", "terrain", "probabilities", "iterations"),
    [
        ("forest", FOREST, [0.08, 0.12, 0.18, 0.26], 35),
        ("green", GREEN, [0.02, 0.04, 0.055, 0.09], 35),
        ("buildings", BUILDINGS, [0.002, 0.008, 0.015, 0.03], 70),
    ],
)
def test_higher_ignition_probability_increases_spread(
    terrain_name,
    terrain,
    probabilities,
    iterations,
):
    """Increasing ignition probability should monotonically increase spread."""
    rows = [
        mean_burning_cells_for_probability(terrain, probability, iterations)
        for probability in probabilities
    ]
    means = [row["mean_burning_cells"] for row in rows]

    print_parameter_table(
        f"Ignition probability sensitivity: {terrain_name}",
        rows,
    )

    # Monotonicity matters more than exact numbers. If the values are monotonic,
    # the parameter is directionally meaningful for the model.
    assert means == sorted(means), (
        f"{terrain_name} spread should increase monotonically when ignition "
        f"probability increases. Means: {means}"
    )
    assert means[-1] > means[0] * 2, (
        f"{terrain_name} highest probability should produce a visibly larger "
        f"fire than the lowest probability. Means: {means}"
    )


@pytest.mark.parametrize(
    ("terrain_name", "terrain", "speeds", "iterations"),
    [
        ("forest", FOREST, [0.75, 1.0, 1.55, 2.1], 35),
        ("green", GREEN, [0.5, 0.8, 1.0, 1.35], 35),
        ("buildings", BUILDINGS, [0.25, 0.5, 0.67, 1.0], 70),
    ],
)
def test_higher_spread_speed_increases_spread(terrain_name, terrain, speeds, iterations):
    """Increasing explicit terrain speed should monotonically increase spread."""
    rows = [mean_burning_cells_for_speed(terrain, speed, iterations) for speed in speeds]
    means = [row["mean_burning_cells"] for row in rows]

    print_parameter_table(
        f"Spread speed sensitivity: {terrain_name}",
        rows,
    )

    assert means == sorted(means), (
        f"{terrain_name} spread should increase monotonically when spread speed "
        f"increases. Means: {means}"
    )
    assert means[-1] > means[0] * 1.5, (
        f"{terrain_name} highest speed should produce a visibly larger fire than "
        f"the lowest speed. Means: {means}"
    )


@pytest.mark.parametrize(
    ("wind_name", "wind_direction", "expected_axis", "expected_sign"),
    [
        ("west", (-1, 0), "x", -1),
        ("east", (1, 0), "x", 1),
        ("north", (0, -1), "y", -1),
        ("south", (0, 1), "y", 1),
    ],
)
def test_wind_direction_changes_fire_center(wind_name, wind_direction, expected_axis, expected_sign):
    """Changing wind direction should move the fire center in that direction."""
    width = 45
    height = 45
    ignition_point = (width // 2, height // 2)
    points = make_uniform_grid(width, height, FOREST)
    rows = []

    for seed in SEEDS:
        final = run_final_metrics(
            points,
            width,
            height,
            ignition_point,
            wind_direction=wind_direction,
            iterations=35,
            seed=seed,
        )
        dx = final.fire_center_x - ignition_point[0]
        dy = final.fire_center_y - ignition_point[1]
        rows.append(
            {
                "seed": seed,
                "dx": dx,
                "dy": dy,
                "wind_bias": final.wind_bias,
                "burning_cells": final.burning_cells,
            }
        )

    mean_dx = mean(row["dx"] for row in rows)
    mean_dy = mean(row["dy"] for row in rows)
    # The directional shift should dominate the cross-axis drift. Some cross-axis
    # movement is expected because the spread is stochastic.
    directional_shift = mean_dx if expected_axis == "x" else mean_dy
    cross_axis_shift = mean_dy if expected_axis == "x" else mean_dx

    print_parameter_table(
        f"Wind direction sensitivity: {wind_name}",
        rows,
    )
    print(f"  mean_dx: {mean_dx}")
    print(f"  mean_dy: {mean_dy}")

    assert directional_shift * expected_sign > 6, (
        f"{wind_name} wind should move the fire center along {expected_axis}. "
        f"directional_shift={directional_shift:.3f}"
    )
    assert abs(cross_axis_shift) < abs(directional_shift) * 0.2, (
        f"{wind_name} wind should mostly affect the {expected_axis} axis. "
        f"directional_shift={directional_shift:.3f}, "
        f"cross_axis_shift={cross_axis_shift:.3f}"
    )


def test_longer_fire_burnout_start_keeps_more_cells_burning(monkeypatch):
    """Longer fire lifetime should increase active fire and decrease burned-out cells."""
    width = 35
    height = 35
    ignition_point = (width // 2, height // 2)
    points = make_uniform_grid(width, height, GREEN)
    burnout_values = [30, 60, 90, 120]
    rows = []

    for burnout_start in burnout_values:
        # Monkeypatch changes the model constant only for this test. Pytest
        # restores the original value afterward, so other tests keep defaults.
        monkeypatch.setattr(simulation, "FIRE_BURNOUT_START", burnout_start)
        burning_samples = []
        burned_samples = []

        for seed in SEEDS:
            final = run_final_metrics(
                points,
                width,
                height,
                ignition_point,
                wind_direction=(0, 0),
                iterations=100,
                seed=seed,
            )
            burning_samples.append(final.burning_cells)
            burned_samples.append(final.burned_cells)

        rows.append(
            {
                "burnout_start": burnout_start,
                "burning_samples": burning_samples,
                "burned_samples": burned_samples,
                "mean_burning_cells": mean(burning_samples),
                "mean_burned_cells": mean(burned_samples),
            }
        )

    burning_means = [row["mean_burning_cells"] for row in rows]
    burned_means = [row["mean_burned_cells"] for row in rows]

    print_parameter_table(
        "Fire burnout timing sensitivity",
        rows,
    )

    assert burning_means == sorted(burning_means), (
        "Longer burnout start should keep more cells actively burning. "
        f"Means: {burning_means}"
    )
    assert burned_means == sorted(burned_means, reverse=True), (
        "Longer burnout start should leave fewer cells already burned out. "
        f"Means: {burned_means}"
    )
