"""Stability tests for repeated stochastic simulations.

The simulation should be stochastic, but not chaotic. These tests run the same
scenario across multiple seeds and verify that the results stay within calibrated
variation bounds. They also verify that using the same seed twice gives exactly
the same result.

This is the intended randomness policy:

- Interactive app runs are unseeded and can differ each time.
- Test/scientific runs pass explicit seeds and are reproducible.
- Different seeds should produce similar-looking aggregate outcomes, not wildly
  different behavior.

Example output:

    Stability scenario: uniform_forest_no_wind
      burning_cells: {'mean': 997.83, 'std': 111.31, 'cv': 0.1115, 'range': 369}

Interpretation: the coefficient of variation (`cv = std / mean`) is about 11%.
The model remains stochastic, but aggregate spread is stable across seeds.
"""

from dataclasses import dataclass
from statistics import mean, stdev

import pytest

from simulation import BUILDINGS, FOREST, GREEN, load_grid_from_image, run_single_simulation


SEEDS = range(1, 13)
CONVERTED_MAP = "maps/map2_converted.png"


@dataclass(frozen=True)
class Scenario:
    """A repeated simulation setup with expected stability bounds."""

    name: str
    points: dict
    width: int
    height: int
    ignition_point: tuple[int, int]
    wind_direction: tuple[int, int]
    iterations: int
    max_burning_cv: float | None = None
    max_burning_std: float | None = None
    max_burning_range: int | None = None
    min_mean_wind_bias: float | None = None


def make_uniform_grid(width, height, terrain):
    """Build a synthetic map so only stochastic fire behavior can vary."""
    return {(x, y): (terrain, 0) for x in range(width) for y in range(height)}


def crop_grid(points, center, size):
    """Use a small real-map crop to keep stability tests fast and repeatable."""
    half = size // 2
    left = center[0] - half
    top = center[1] - half
    cropped = {}

    for x in range(left, left + size):
        for y in range(top, top + size):
            value = points.get((x, y))
            if value is not None:
                cropped[(x - left, y - top)] = value

    return cropped, size, size, (half, half)


def converted_map_crop(center, size=45):
    """Load the converted map and extract one representative test crop."""
    points, _width, _height = load_grid_from_image(CONVERTED_MAP)
    return crop_grid(points, center, size)


def build_scenarios():
    """Define the stability scenarios once so pytest can parametrize them."""
    forest_points = make_uniform_grid(45, 45, FOREST)
    green_points = make_uniform_grid(45, 45, GREEN)
    building_points = make_uniform_grid(45, 45, BUILDINGS)
    converted_forest_points, converted_width, converted_height, converted_ignition = (
        converted_map_crop((30, 63))
    )

    # Bounds are intentionally scenario-specific and calibrated to the
    # PROPAGATOR-scaled parameters. Buildings use absolute std/range bounds
    # because their lower spread rate makes relative variation noisy.
    return [
        Scenario(
            name="uniform_forest_no_wind",
            points=forest_points,
            width=45,
            height=45,
            ignition_point=(22, 22),
            wind_direction=(0, 0),
            iterations=40,
            max_burning_cv=0.13,
            max_burning_range=420,
        ),
        Scenario(
            name="uniform_green_no_wind",
            points=green_points,
            width=45,
            height=45,
            ignition_point=(22, 22),
            wind_direction=(0, 0),
            iterations=40,
            max_burning_cv=0.14,
            max_burning_range=340,
        ),
        Scenario(
            name="uniform_forest_east_wind",
            points=forest_points,
            width=45,
            height=45,
            ignition_point=(22, 22),
            wind_direction=(1, 0),
            iterations=40,
            max_burning_cv=0.20,
            max_burning_range=260,
            min_mean_wind_bias=6.5,
        ),
        Scenario(
            name="converted_map_forest_crop",
            points=converted_forest_points,
            width=converted_width,
            height=converted_height,
            ignition_point=converted_ignition,
            wind_direction=(0, 0),
            iterations=40,
            max_burning_cv=0.13,
            max_burning_range=420,
        ),
        Scenario(
            name="uniform_buildings_no_wind",
            points=building_points,
            width=45,
            height=45,
            ignition_point=(22, 22),
            wind_direction=(0, 0),
            iterations=70,
            max_burning_std=45.0,
            max_burning_range=140,
        ),
    ]


SCENARIOS = build_scenarios()


def run_scenario(scenario, seed):
    """Run one scenario once and return only the metrics relevant for stability."""
    final = run_single_simulation(
        initial_points=scenario.points,
        grid_width=scenario.width,
        grid_height=scenario.height,
        ignition_point=scenario.ignition_point,
        wind_direction=scenario.wind_direction,
        iterations=scenario.iterations,
        seed=seed,
    )[-1]

    return {
        "burning_cells": final.burning_cells,
        "burned_cells": final.burned_cells,
        "affected_cells": final.burning_cells + final.burned_cells,
        "wind_bias": final.wind_bias,
    }


def summarize(samples, key):
    """Summarize repeated runs with the same scenario and different seeds."""
    values = [sample[key] for sample in samples]
    avg = mean(values)
    std = stdev(values) if len(values) > 1 else 0.0
    cv = std / avg if avg else 0.0

    return {
        "values": values,
        "mean": avg,
        "std": std,
        "cv": cv,
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
    }


def print_scenario_details(scenario, burning_summary, bias_summary):
    """Print the exact stability evidence for the current scenario."""
    print(f"\nStability scenario: {scenario.name}")
    print(f"  seeds: {list(SEEDS)}")
    print(f"  wind_direction: {scenario.wind_direction}")
    print(f"  iterations: {scenario.iterations}")
    print(f"  burning_cells: {burning_summary}")
    print(f"  wind_bias: {bias_summary}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario.name for scenario in SCENARIOS])
def test_scenario_results_are_stable_across_seeds(scenario):
    """Different seeds may vary, but the spread should stay within calibrated bounds."""
    samples = [run_scenario(scenario, seed) for seed in SEEDS]
    burning_summary = summarize(samples, "burning_cells")
    bias_summary = summarize(samples, "wind_bias")

    print_scenario_details(scenario, burning_summary, bias_summary)

    # CV is useful when counts are large. For low-count building scenarios,
    # absolute std/range checks are more meaningful than percentage variation.
    if scenario.max_burning_cv is not None:
        assert burning_summary["cv"] <= scenario.max_burning_cv, (
            f"{scenario.name} burning cell CV is too high: "
            f"{burning_summary['cv']:.3f} > {scenario.max_burning_cv:.3f}"
        )

    if scenario.max_burning_std is not None:
        assert burning_summary["std"] <= scenario.max_burning_std, (
            f"{scenario.name} burning cell std is too high: "
            f"{burning_summary['std']:.3f} > {scenario.max_burning_std:.3f}"
        )

    if scenario.max_burning_range is not None:
        assert burning_summary["range"] <= scenario.max_burning_range, (
            f"{scenario.name} burning cell range is too high: "
            f"{burning_summary['range']} > {scenario.max_burning_range}"
        )

    if scenario.min_mean_wind_bias is not None:
        assert bias_summary["mean"] >= scenario.min_mean_wind_bias, (
            f"{scenario.name} mean wind bias is too low: "
            f"{bias_summary['mean']:.3f} < {scenario.min_mean_wind_bias:.3f}"
        )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario.name for scenario in SCENARIOS])
def test_same_seed_gives_identical_result(scenario):
    """The model is stochastic, but seeded runs must be reproducible for science/tests."""
    first = run_scenario(scenario, seed=7)
    second = run_scenario(scenario, seed=7)

    print(f"\nDeterminism scenario: {scenario.name}")
    print(f"  first: {first}")
    print(f"  second: {second}")

    # This protects reproducible research/debugging: when a scenario fails, the
    # exact same seed should reproduce the same final metrics.
    assert first == second
