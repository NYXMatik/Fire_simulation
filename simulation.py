"""Core fire-spread model.

This file contains the simulation rules used by both the interactive app and the
pytest suites. The model is a cellular automaton:

- The map is represented as a dictionary keyed by grid coordinates `(x, y)`.
- Each cell stores `(color, duration)`, where `color` is the current terrain/fire
  state and `duration` is the number of simulation ticks spent in that state.
- The simulation is stochastic: ignition and burnout use random draws. Tests pass
  an explicit seed through `run_single_simulation`, so scientific/test runs are
  reproducible while the interactive app can still feel naturally variable.

Important behavior encoded here:

- Water is a complete local spread blocker. If an active fire cell touches water,
  it cannot ignite any new cells in that tick.
- Controlled burn does not spread by itself. It can be captured by regular fire
  before it finishes. Once finished, it becomes a burned firebreak and blocks fire.
- Forest is more flammable and also burns longer than green terrain/buildings.
- Wind biases spread probability using an exponential wind factor.
"""

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from PIL import Image


# Canonical colors used inside the simulation. Converted map images must contain
# only these terrain colors; dynamic states such as FIRE1/FIRE2 are drawn later.
FOREST = (51, 204, 51)
WATER = (153, 204, 255)
GREEN = (153, 255, 153)
GROUND = GREEN
BUILDINGS = (230, 230, 230)

WHITE = (255, 255, 255)

FIRE1 = (254, 48, 35)
FIRE2 = (72, 0, 4)
CONTROLLED_BURN = (255, 150, 70)
CONTROLLED_BURNED = (95, 95, 95)

# Terrain cells can be loaded from an image. Blocking cells stop direct ignition;
# path-blocking cells also stop wind-assisted jumps over a barrier.
TERRAIN_TYPES = {FOREST, WATER, GREEN, BUILDINGS}
BLOCKING_TYPES = {WATER, CONTROLLED_BURNED}
PATH_BLOCKING_TYPES = {WATER, CONTROLLED_BURN, CONTROLLED_BURNED}
SPREADING_FIRE_TYPES = {FIRE1}

# Terrain probability and speed values are scaled from Trucchia et al. (2020),
# "PROPAGATOR: An Operational Cellular-Automata Based Wildfire Simulator",
# Fire 3(3), 26. Table 1 gives nominal Fire Spread Probability values and
# nominal Fire Spread Velocity [m/min]. The paper models probability and Rate of
# Spread as separate quantities.
#
# Mapping used here:
#   FOREST    -> Fire-prone conifers, raw probability 0.35, velocity 200 m/min
#   GREEN     -> Grassland, raw probability 0.475, velocity 120 m/min
#   BUILDINGS -> WUI / low-flammable mixed fuel proxy. Pure PROPAGATOR urban is
#                non-vegetated and non-burnable, but this app's "buildings" map
#                class is used for wildland-urban-interface exposure. We use the
#                table value for not-fire-prone forest exposed to fire-prone
#                conifers, raw probability 0.275, velocity 60 m/min.
#   WATER     -> non-burnable blocker, probability 0.
#
# The app has abstract ticks and grid cells rather than real minutes and meters,
# so only one global probability scale is applied. GREEN/Grassland is the visual
# reference class and is scaled to a readable app baseline 0.09. Spread
# speed is normalized by GREEN's 120 m/min velocity.
PROPAGATOR_FOREST_PROBABILITY = 0.35
PROPAGATOR_GREEN_PROBABILITY = 0.475
PROPAGATOR_BUILDINGS_WUI_PROBABILITY = 0.275

PROPAGATOR_FOREST_VELOCITY_M_PER_MIN = 200
PROPAGATOR_GREEN_VELOCITY_M_PER_MIN = 120
PROPAGATOR_BUILDINGS_WUI_VELOCITY_M_PER_MIN = 60

APP_GREEN_BASELINE_PROBABILITY = 0.09
APP_PROBABILITY_SCALE = APP_GREEN_BASELINE_PROBABILITY / PROPAGATOR_GREEN_PROBABILITY


def scaled_probability(raw_probability: float) -> float:
    """Scale a literature probability to this app's abstract visual tick."""
    return raw_probability * APP_PROBABILITY_SCALE


def normalized_speed(raw_velocity_m_per_min: float) -> float:
    """Normalize PROPAGATOR velocity using GREEN/Grassland as the reference."""
    return raw_velocity_m_per_min / PROPAGATOR_GREEN_VELOCITY_M_PER_MIN


DEFAULT_IGNITION_PROBABILITIES = {
    FOREST: scaled_probability(PROPAGATOR_FOREST_PROBABILITY),
    GREEN: scaled_probability(PROPAGATOR_GREEN_PROBABILITY),
    BUILDINGS: scaled_probability(PROPAGATOR_BUILDINGS_WUI_PROBABILITY),
    CONTROLLED_BURN: 1.0,
}

DEFAULT_SPREAD_SPEEDS = {
    FOREST: normalized_speed(PROPAGATOR_FOREST_VELOCITY_M_PER_MIN),
    GREEN: normalized_speed(PROPAGATOR_GREEN_VELOCITY_M_PER_MIN),
    BUILDINGS: normalized_speed(PROPAGATOR_BUILDINGS_WUI_VELOCITY_M_PER_MIN),
    CONTROLLED_BURN: 1.0,
}

# Wind factor from Alexandridis et al. / Karakonstantis & Xylomenos:
#   P_w = exp(V * (c1 + c2 * (cos(theta) - 1)))
# where theta is the angle between wind direction and spread direction. The UI
# stores only direction, so this app uses one nominal wind speed when wind is on.
DEFAULT_WIND_SPEED = 10.0
WIND_C1 = 0.045
WIND_C2 = 0.131

# Fire starts trying to burn out only after this many ticks. Forest fires start
# with a negative duration, which effectively makes them burn longer.
FIRE_BURNOUT_START = 90
FOREST_FIRE_DURATION_BONUS = 55
CONTROLLED_BURN_DURATION = 80

Point = Tuple[int, int]
Color = Tuple[int, int, int]
Grid = Dict[Point, Tuple[Color, int]]


@dataclass(frozen=True)
class SimulationMetrics:
    """Summary values recorded for behavioral, stability, and parameter tests."""

    iteration: int
    burning_cells: int
    burned_cells: int
    controlled_burn_cells: int
    controlled_burned_cells: int
    forest_burning_or_burned_pct: float
    green_burning_or_burned_pct: float
    buildings_burning_or_burned_pct: float
    water_burning_or_burned_pct: float
    fire_center_x: Optional[float]
    fire_center_y: Optional[float]
    wind_bias: float


def load_grid_from_image(image_path: str, tile_size: int = 3) -> Tuple[Grid, int, int]:
    """Load a converted map image into the grid dictionary used by the model.

    `tile_size` maps image pixels to simulation cells. For example, tile size 3
    means cell `(10, 5)` reads pixel `(30, 15)`. Pixels that are not one of the
    canonical terrain colors are ignored, which protects the model from accidental
    non-terrain colors in source images.
    """
    image = Image.open(image_path).convert("RGB")
    grid_width = image.width // tile_size
    grid_height = image.height // tile_size
    points: Grid = {}

    for col in range(grid_width):
        for row in range(grid_height):
            x, y = col * tile_size, row * tile_size
            color = image.getpixel((x, y))
            if color in TERRAIN_TYPES:
                points[(col, row)] = (color, 0)

    return points, grid_width, grid_height


def clone_grid(points: Grid) -> Grid:
    """Copy a grid before a seeded simulation run mutates it."""
    return {point: (color, duration) for point, (color, duration) in points.items()}


def reflect_coordinate(value: int, limit: int) -> int:
    """Reflect coordinates at map borders instead of losing neighbor lookups."""
    if value < 0:
        return -value
    if value >= limit:
        return 2 * limit - value - 2
    return value


def get_neighbors(
    point: Point,
    points: Grid,
    wind_direction: Point,
    grid_width: int,
    grid_height: int,
) -> Iterable[Tuple[Point, Optional[Tuple[Color, int]]]]:
    """Return 8-neighborhood cells.

    Wind is applied later as a probability factor. Boundary reflection keeps
    coordinates valid.
    """
    x, y = point
    neighbors = []

    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue

            nx = reflect_coordinate(x + dx, grid_width)
            ny = reflect_coordinate(y + dy, grid_height)
            neighbor_pos = (nx, ny)
            neighbors.append((neighbor_pos, points.get(neighbor_pos)))

    return neighbors


def path_is_blocked(start: Point, end: Point, points: Grid) -> bool:
    """Check whether a wind-assisted jump crosses water or a firebreak.

    Adjacent cells do not need path checking. For longer wind-shifted moves, the
    cells between `start` and `end` are scanned. Water, active controlled burn,
    and finished controlled burn all block that path.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    steps = max(abs(dx), abs(dy))

    if steps <= 1:
        return False

    step_x = 0 if dx == 0 else dx // abs(dx)
    step_y = 0 if dy == 0 else dy // abs(dy)

    current = start
    for _step in range(1, steps):
        current = (current[0] + step_x, current[1] + step_y)
        color = points.get(current, (None, 0))[0]
        if color in PATH_BLOCKING_TYPES:
            return True

    return False


def touches_water(point: Point, points: Grid) -> bool:
    """Return True if a cell touches water in the 8-neighborhood.

    This is intentionally stronger than just blocking water cells themselves. It
    prevents fire from leaking through tiny conversion gaps along rivers/streams:
    a burning source adjacent to water cannot spread at all during that tick.
    """
    x, y = point
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            if points.get((x + dx, y + dy), (None, 0))[0] == WATER:
                return True
    return False


def update_grid(
    points: Grid,
    wind_direction: Point,
    grid_width: int,
    grid_height: int,
    ignition_probabilities: Optional[Dict[Color, float]] = None,
    spread_speeds: Optional[Dict[Color, float]] = None,
    wind_speed: float = DEFAULT_WIND_SPEED,
) -> Grid:
    """Advance the simulation by one tick.

    The update is two-phase:
    1. Age all current states and turn old fire/controlled burn into burned states.
    2. Spread active fire into eligible neighbors based on terrain probability
       and terrain speed.

    Two-phase updates avoid order-dependent artifacts where a cell updated early
    in the loop could immediately influence another cell in the same tick.
    """
    probabilities = ignition_probabilities or DEFAULT_IGNITION_PROBABILITIES
    speeds = spread_speeds or DEFAULT_SPREAD_SPEEDS
    new_points: Grid = {}

    for point, (color, duration) in points.items():
        duration += 1
        if color == FIRE1 and duration >= FIRE_BURNOUT_START:
            # Burnout probability increases with age, so fires do not disappear
            # at exactly the same duration. This keeps runs stochastic but bounded.
            if (
                (duration < 75 and random.random() < 0.01)
                or (duration < 100 and random.random() < 0.05)
                or (duration < 125 and random.random() < 0.15)
                or (random.random() < 0.3)
            ):
                new_points[point] = (FIRE2, 0)
            else:
                new_points[point] = (color, duration)
        else:
            if color == CONTROLLED_BURN and duration >= CONTROLLED_BURN_DURATION:
                # A completed controlled burn becomes a permanent blocking line.
                new_points[point] = (CONTROLLED_BURNED, 0)
            else:
                new_points[point] = (color, duration)

    new_points_updated = new_points.copy()
    for point, (color, _duration) in points.items():
        if color in SPREADING_FIRE_TYPES:
            # Strong water rule: a source touching water cannot ignite anything.
            if touches_water(point, points):
                continue

            neighbors = get_neighbors(point, points, wind_direction, grid_width, grid_height)
            for neighbor_pos, neighbor_value in neighbors:
                if neighbor_pos not in new_points:
                    continue

                neighbor_state = new_points[neighbor_pos][0]
                if neighbor_state in BLOCKING_TYPES or neighbor_state == FIRE2:
                    continue
                if path_is_blocked(point, neighbor_pos, new_points):
                    continue

                ignition_probability = effective_ignition_probability(
                    neighbor_state,
                    probabilities,
                    speeds,
                    point,
                    neighbor_pos,
                    wind_direction,
                    wind_speed,
                )
                if ignition_probability is not None and random.random() < ignition_probability:
                    new_points_updated[neighbor_pos] = (
                        FIRE1,
                        initial_fire_duration(neighbor_state),
                    )

    return new_points_updated


def effective_ignition_probability(
    terrain_color: Color,
    ignition_probabilities: Dict[Color, float],
    spread_speeds: Dict[Color, float],
    source: Point,
    target: Point,
    wind_direction: Point,
    wind_speed: float = DEFAULT_WIND_SPEED,
) -> Optional[float]:
    """Combine target flammability, target spread speed, and wind for one tick."""
    ignition_probability = ignition_probabilities.get(terrain_color)
    if ignition_probability is None:
        return None

    spread_speed = spread_speeds.get(terrain_color, 1.0)
    wind_adjusted_probability = ignition_probability * wind_probability_factor(
        source,
        target,
        wind_direction,
        wind_speed,
    )
    wind_adjusted_probability = max(0.0, min(1.0, wind_adjusted_probability))
    return max(0.0, min(1.0, 1 - (1 - wind_adjusted_probability) ** spread_speed))


def wind_probability_factor(
    source: Point,
    target: Point,
    wind_direction: Point,
    wind_speed: float = DEFAULT_WIND_SPEED,
) -> float:
    """Return the Alexandridis-style wind multiplier for one spread direction."""
    if wind_direction == (0, 0) or wind_speed <= 0:
        return 1.0

    spread_x = target[0] - source[0]
    spread_y = target[1] - source[1]
    spread_length = math.hypot(spread_x, spread_y)
    wind_length = math.hypot(wind_direction[0], wind_direction[1])
    if spread_length == 0 or wind_length == 0:
        return 1.0

    cos_theta = (
        (spread_x * wind_direction[0] + spread_y * wind_direction[1])
        / (spread_length * wind_length)
    )
    return math.exp(wind_speed * (WIND_C1 + WIND_C2 * (cos_theta - 1)))


def run_single_simulation(
    initial_points: Grid,
    grid_width: int,
    grid_height: int,
    ignition_point: Point,
    wind_direction: Point,
    iterations: int,
    seed: int,
    ignition_probabilities: Optional[Dict[Color, float]] = None,
    spread_speeds: Optional[Dict[Color, float]] = None,
    wind_speed: float = DEFAULT_WIND_SPEED,
) -> list[SimulationMetrics]:
    """Run a seeded headless simulation and return metrics for every tick.

    This helper is used by tests. Passing the seed here makes repeatable test
    evidence possible while leaving the interactive app free to use live random
    draws from the global random module.
    """
    random.seed(seed)
    points = clone_grid(initial_points)
    ignite(points, ignition_point)

    history = [
        calculate_metrics(initial_points, points, 0, ignition_point, wind_direction)
    ]

    for iteration in range(1, iterations + 1):
        points = update_grid(
            points,
            wind_direction,
            grid_width,
            grid_height,
            ignition_probabilities=ignition_probabilities,
            spread_speeds=spread_speeds,
            wind_speed=wind_speed,
        )
        history.append(
            calculate_metrics(initial_points, points, iteration, ignition_point, wind_direction)
        )

    return history


def ignite(points: Grid, point: Point) -> None:
    """Turn a terrain cell into active fire, preserving terrain-specific duration."""
    terrain_color = points.get(point, (None, 0))[0]
    points[point] = (FIRE1, initial_fire_duration(terrain_color))


def initial_fire_duration(terrain_color: Optional[Color]) -> int:
    """Return the starting fire duration for a terrain type.

    Forest starts below zero, so it has to age for extra ticks before reaching
    `FIRE_BURNOUT_START`. This is the model's "forest burns longer" behavior.
    """
    if terrain_color == FOREST:
        return -FOREST_FIRE_DURATION_BONUS
    return 0


def add_water_patch(
    points: Grid,
    center: Point,
    radius_min: int = -3,
    radius_max: int = 4,
    grid_width: Optional[int] = None,
    grid_height: Optional[int] = None,
) -> None:
    """Paint a square water barrier around a grid cell."""
    col, row = center
    for dx in range(radius_min, radius_max + 1):
        for dy in range(radius_min, radius_max + 1):
            point = (col + dx, row + dy)
            if point_is_in_bounds(point, grid_width, grid_height):
                points[point] = (WATER, 0)


def add_controlled_burn_patch(
    points: Grid,
    center: Point,
    radius_min: int = -1,
    radius_max: int = 1,
    grid_width: Optional[int] = None,
    grid_height: Optional[int] = None,
) -> None:
    """Paint a small square controlled-burn patch around a grid cell."""
    col, row = center
    for dx in range(radius_min, radius_max + 1):
        for dy in range(radius_min, radius_max + 1):
            point = (col + dx, row + dy)
            if point_is_in_bounds(point, grid_width, grid_height):
                points[point] = (CONTROLLED_BURN, 0)


def point_is_in_bounds(
    point: Point,
    grid_width: Optional[int],
    grid_height: Optional[int],
) -> bool:
    """Keep brush operations inside the actual loaded map dimensions."""
    if grid_width is not None and not 0 <= point[0] < grid_width:
        return False
    if grid_height is not None and not 0 <= point[1] < grid_height:
        return False
    return True


def calculate_metrics(
    initial_points: Grid,
    current_points: Grid,
    iteration: int,
    ignition_point: Point,
    wind_direction: Point,
) -> SimulationMetrics:
    """Compute aggregate values used for diagnostics and tests.

    Percent metrics compare affected cells against the original terrain map, not
    the current dynamic colors. This lets tests ask questions such as "what share
    of original forest has burned or is burning?"
    """
    burning_points = [point for point, (color, _duration) in current_points.items() if color == FIRE1]
    burned_points = [point for point, (color, _duration) in current_points.items() if color == FIRE2]
    controlled_burn_points = [
        point for point, (color, _duration) in current_points.items() if color == CONTROLLED_BURN
    ]
    controlled_burned_points = [
        point for point, (color, _duration) in current_points.items() if color == CONTROLLED_BURNED
    ]
    affected_points = set(burning_points) | set(burned_points)

    def terrain_pct(terrain_color: Color) -> float:
        total = sum(1 for color, _duration in initial_points.values() if color == terrain_color)
        if total == 0:
            return 0.0
        affected = sum(1 for point in affected_points if initial_points.get(point, (None, 0))[0] == terrain_color)
        return affected / total * 100.0

    if burning_points:
        center_x = sum(point[0] for point in burning_points) / len(burning_points)
        center_y = sum(point[1] for point in burning_points) / len(burning_points)
    else:
        center_x = None
        center_y = None

    if center_x is None or center_y is None:
        wind_bias = 0.0
    else:
        wind_bias = (center_x - ignition_point[0]) * wind_direction[0]
        wind_bias += (center_y - ignition_point[1]) * wind_direction[1]

    return SimulationMetrics(
        iteration=iteration,
        burning_cells=len(burning_points),
        burned_cells=len(burned_points),
        controlled_burn_cells=len(controlled_burn_points),
        controlled_burned_cells=len(controlled_burned_points),
        forest_burning_or_burned_pct=terrain_pct(FOREST),
        green_burning_or_burned_pct=terrain_pct(GREEN),
        buildings_burning_or_burned_pct=terrain_pct(BUILDINGS),
        water_burning_or_burned_pct=terrain_pct(WATER),
        fire_center_x=center_x,
        fire_center_y=center_y,
        wind_bias=wind_bias,
    )
