"""Behavioral tests for core fire-spread rules.

These tests answer qualitative questions about the model:

- Does the literature-derived terrain ordering hold on the converted map?
- Does fire spread symmetrically without wind?
- Does water fully block a nearby fire source?
- Do controlled-burn cells behave like unfinished/finished firebreaks?

The printed output is part of the explanation, not part of the assertion itself.
Example output:

    Converted map spread after 5s
      forest: {'samples': [2421, 2461, 2475], 'mean_burning_cells': 2452.33}
      green: {'samples': [540, 444, 395], 'mean_burning_cells': 459.67}

Interpretation: after the same simulated time and comparable map crops, the
literature-derived coefficients should keep coniferous forest more fire-prone
than natural grassland, while urban/developed cells remain much less fire-prone.
"""

from statistics import mean

from simulation import (
    BUILDINGS,
    CONTROLLED_BURN,
    CONTROLLED_BURNED,
    DEFAULT_IGNITION_PROBABILITIES,
    FIRE1,
    FIRE2,
    FOREST,
    GREEN,
    WATER,
    load_grid_from_image,
    reflect_coordinate,
    run_single_simulation,
    update_grid,
)


CONVERTED_MAP = "maps/map2_converted.png"
FIVE_SECONDS_AT_APP_SPEED = 50

# Human-readable labels used in printed diagnostics.
TERRAIN_NAMES = {
    FOREST: "forest",
    GREEN: "green",
    BUILDINGS: "buildings",
    WATER: "water",
}


def print_details(title, **values):
    """Print structured diagnostics that are visible when pytest runs with -s."""
    print(f"\n{title}")
    for key, value in values.items():
        print(f"  {key}: {value}")


def make_uniform_grid(width, height, terrain):
    """Build a synthetic map containing exactly one terrain type."""
    return {(x, y): (terrain, 0) for x in range(width) for y in range(height)}


def crop_grid(points, center, size):
    """Crop a real converted map around a known ignition point for fast tests."""
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


def converted_map_burning_cells_after_5s(terrain):
    """Run the same real-map crop for several seeds and return the mean spread."""
    points, _grid_width, _grid_height = load_grid_from_image(CONVERTED_MAP)
    ignition_points = {
        FOREST: (30, 63),
        GREEN: (30, 30),
        BUILDINGS: (123, 184),
    }
    ignition_point = ignition_points[terrain]

    assert points[ignition_point][0] == terrain

    cropped_points, width, height, cropped_ignition = crop_grid(
        points,
        ignition_point,
        size=60,
    )

    # Use several deterministic seeds so the test sees typical stochastic
    # behavior without becoming dependent on one lucky/unlucky random draw.
    samples = []
    for seed in [1, 2, 3]:
        history = run_single_simulation(
            initial_points=cropped_points,
            grid_width=width,
            grid_height=height,
            ignition_point=cropped_ignition,
            wind_direction=(0, 0),
            iterations=FIVE_SECONDS_AT_APP_SPEED,
            seed=seed,
        )
        samples.append(history[-1].burning_cells)

    return {
        "terrain": TERRAIN_NAMES[terrain],
        "ignition_point": ignition_point,
        "samples": samples,
        "mean_burning_cells": mean(samples),
    }


def test_boundary_reflection():
    """Grid reflection should keep wind-shifted neighbor lookups inside bounds."""
    assert reflect_coordinate(-1, 10) == 1
    assert reflect_coordinate(10, 10) == 8
    assert reflect_coordinate(9, 10) == 9


def test_converted_map_literature_terrain_order_after_5s():
    """The converted map should follow the documented terrain coefficient order."""
    forest = converted_map_burning_cells_after_5s(FOREST)
    green = converted_map_burning_cells_after_5s(GREEN)
    buildings = converted_map_burning_cells_after_5s(BUILDINGS)

    print_details(
        "Converted map spread after 5s",
        forest=forest,
        green=green,
        buildings=buildings,
    )

    # The thresholds compare ratios rather than exact values. The current
    # Parameters are derived from PROPAGATOR Table 1 and then globally scaled
    # for this app's abstract tick. Forest has higher normalized spread speed
    # than green terrain, while buildings are modeled as low-flammable WUI fuel.
    assert forest["mean_burning_cells"] > green["mean_burning_cells"] * 1.15, (
        "Forest should spread faster than green terrain under the "
        "PROPAGATOR-derived coefficients. "
        f"forest={forest['mean_burning_cells']:.2f}, "
        f"green={green['mean_burning_cells']:.2f}"
    )
    assert buildings["mean_burning_cells"] < green["mean_burning_cells"] * 0.1, (
        "Urban/developed terrain should remain much less fire-prone than "
        "natural grassland. "
        f"green={green['mean_burning_cells']:.2f}, "
        f"buildings={buildings['mean_burning_cells']:.2f}"
    )


def test_no_wind_spread_is_isotropic():
    """Without wind and with probability 1.0, spread should be symmetric."""
    width = 41
    height = 41
    ignition_point = (width // 2, height // 2)
    points = make_uniform_grid(width, height, GREEN)
    points[ignition_point] = (FIRE1, 0)

    # Probability 1.0 removes random missing cells from this test. That isolates
    # geometry: with no wind and guaranteed ignition, the shape should expand
    # evenly in every direction.
    probabilities = dict(DEFAULT_IGNITION_PROBABILITIES)
    probabilities[GREEN] = 1.0

    for _iteration in range(6):
        points = update_grid(points, (0, 0), width, height, probabilities)

    burning_points = [point for point, (color, _duration) in points.items() if color == FIRE1]
    xs = [point[0] for point in burning_points]
    ys = [point[1] for point in burning_points]
    left = ignition_point[0] - min(xs)
    right = max(xs) - ignition_point[0]
    up = ignition_point[1] - min(ys)
    down = max(ys) - ignition_point[1]

    print_details(
        "No-wind isotropic spread",
        burning_cells=len(burning_points),
        left_radius=left,
        right_radius=right,
        up_radius=up,
        down_radius=down,
    )

    assert left == right, f"Horizontal spread is not symmetric: left={left}, right={right}"
    assert up == down, f"Vertical spread is not symmetric: up={up}, down={down}"
    assert left + right == up + down, (
        "No-wind spread should have the same width and height. "
        f"width={left + right}, height={up + down}"
    )


def test_water_touching_fire_stops_source_spread():
    """A burning cell touching water should not ignite any new neighbors."""
    width = 7
    height = 7
    points = make_uniform_grid(width, height, GREEN)
    points[(3, 3)] = (FIRE1, 0)
    points[(3, 4)] = (WATER, 0)

    # Probability 1.0 makes this a strict blocker test. If any neighbor ignites,
    # it means water-contact blocking failed rather than random chance intervened.
    probabilities = dict(DEFAULT_IGNITION_PROBABILITIES)
    probabilities[GREEN] = 1.0

    updated = update_grid(points, (0, 0), width, height, probabilities)
    new_fire_points = [
        point
        for point, (color, _duration) in updated.items()
        if point != (3, 3) and color == FIRE1
    ]

    print_details(
        "Water contact blocks source spread",
        fire_point=(3, 3),
        water_point=(3, 4),
        new_fire_points=new_fire_points,
    )

    assert not new_fire_points, f"Fire next to water should not spread, got {new_fire_points}"


def test_east_wind_creates_positive_bias():
    """East wind should move the active fire center to the east of the ignition point."""
    width = 60
    height = 60
    ignition_point = (width // 2, height // 2)
    initial_points = make_uniform_grid(width, height, FOREST)

    history = run_single_simulation(
        initial_points=initial_points,
        grid_width=width,
        grid_height=height,
        ignition_point=ignition_point,
        wind_direction=(1, 0),
        iterations=60,
        seed=11,
    )

    final = history[-1]
    print_details(
        "East wind bias",
        fire_center_x=final.fire_center_x,
        fire_center_y=final.fire_center_y,
        wind_bias=final.wind_bias,
        burning_cells=final.burning_cells,
    )

    assert final.wind_bias > 5, f"Expected east wind bias > 5, got {final.wind_bias:.2f}"


def test_controlled_burn_does_not_spread_by_itself():
    """Controlled burn is a passive firebreak process and must not create FIRE1."""
    width = 7
    height = 7
    points = make_uniform_grid(width, height, GREEN)
    points[(3, 3)] = (CONTROLLED_BURN, 0)

    probabilities = dict(DEFAULT_IGNITION_PROBABILITIES)
    probabilities[GREEN] = 1.0

    updated = update_grid(points, (0, 0), width, height, probabilities)
    fire_cells = [
        point for point, (color, _duration) in updated.items() if color == FIRE1
    ]

    print_details(
        "Controlled burn does not spread by itself",
        initial_controlled_burn=(3, 3),
        fire_cells=fire_cells,
    )

    assert not fire_cells, f"Controlled burn should not create FIRE1 cells, got {fire_cells}"


def test_controlled_burn_can_be_captured_before_burnout():
    """Active controlled burn should be flammable until it finishes and becomes burned."""
    width = 7
    height = 7
    points = make_uniform_grid(width, height, GREEN)
    points[(2, 3)] = (FIRE1, 0)
    points[(3, 3)] = (CONTROLLED_BURN, 0)

    updated = update_grid(points, (0, 0), width, height)

    print_details(
        "Controlled burn captured before burnout",
        source_fire=(2, 3),
        controlled_burn=(3, 3),
        resulting_color=updated[(3, 3)][0],
    )

    assert updated[(3, 3)][0] == FIRE1, "Active controlled burn should be capturable by fire"


def test_burned_controlled_line_blocks_fire():
    """Finished controlled burn should behave as a blocking firebreak."""
    width = 20
    height = 15
    points = make_uniform_grid(width, height, GREEN)
    for y in range(height):
        points[(8, y)] = (CONTROLLED_BURNED, 0)
    points[(7, 7)] = (FIRE1, 0)

    probabilities = dict(DEFAULT_IGNITION_PROBABILITIES)
    probabilities[GREEN] = 1.0

    for _iteration in range(8):
        points = update_grid(points, (1, 0), width, height, probabilities)

    leaked_fire_points = [
        (x, y)
        for x in range(9, width)
        for y in range(height)
        if points[(x, y)][0] in {FIRE1, FIRE2}
    ]

    print_details(
        "Burned controlled line blocks fire",
        barrier_x=8,
        leaked_fire_points=leaked_fire_points,
    )

    assert not leaked_fire_points, (
        "Burned controlled line should block fire. "
        f"Leaked points: {leaked_fire_points[:10]}"
    )
