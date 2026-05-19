"""Interactive Pygame user interface for the fire simulation.

This file is intentionally thin: the simulation rules live in `simulation.py`.
The app is responsible for loading the converted map, drawing the current grid,
handling mouse/keyboard input, and presenting enough live status information for
an end user to understand what is happening.

User model:

- Left mouse button always starts regular fire.
- Right mouse button performs one of two actions: add water or add a controlled
  burn line. Press `C` to switch between those two actions.
- `SPACE` starts/pauses the simulation. `W/A/S/D` set wind, and `X` clears it.

The app does not seed random numbers. That is deliberate: interactive runs should
feel like natural stochastic simulations. Test code calls seeded helper functions
from `simulation.py` when exact reproducibility is needed.
"""

import pygame
from PIL import Image

from simulation import (
    BUILDINGS,
    CONTROLLED_BURN,
    CONTROLLED_BURNED,
    FIRE1,
    FIRE2,
    FOREST,
    GREEN,
    WATER,
    add_controlled_burn_patch,
    add_water_patch,
    ignite,
    load_grid_from_image,
    update_grid,
)

pygame.init()

# Visual/layout constants. The map is drawn on the left; the right panel explains
# controls and shows live simulation state.
WHITE = (255, 255, 255)
PANEL_WIDTH = 300
TILE_SIZE = 3
FPS = 60

# These globals are recalculated after the converted map image is loaded. They
# start with safe defaults so Pygame can create an initial window immediately.
WIDTH, HEIGHT = 1500, 750
GRID_WIDTH = WIDTH // TILE_SIZE
GRID_HEIGHT = HEIGHT // TILE_SIZE

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.SysFont("Lato", 16)
title_font = pygame.font.SysFont("Lato", 20, bold=True)

TERRAIN_LABELS = {
    FOREST: "Forest",
    GREEN: "Green terrain",
    BUILDINGS: "Buildings",
    WATER: "Water barrier",
    FIRE1: "Active fire",
    FIRE2: "Burned",
    CONTROLLED_BURN: "Controlled burn",
    CONTROLLED_BURNED: "Burned firebreak",
}


def draw_text(text, x, y, color=WHITE, selected_font=None):
    """Draw text and return the next vertical position for stacked panel rows."""
    text_surface = (selected_font or font).render(text, True, color)
    screen.blit(text_surface, (x, y))
    return y + text_surface.get_height() + 6


def draw_color_row(label, color, x, y):
    """Draw a legend swatch followed by its human-readable label."""
    pygame.draw.rect(screen, color, (x, y + 3, 14, 14))
    pygame.draw.rect(screen, (85, 85, 85), (x, y + 3, 14, 14), 1)
    return draw_text(label, x + 22, y)


def count_cells(points):
    """Count currently visible cell states for the status panel."""
    counts = {label: 0 for label in TERRAIN_LABELS.values()}
    for color, _duration in points.values():
        label = TERRAIN_LABELS.get(color)
        if label:
            counts[label] += 1
    return counts


def right_mouse_action_name(right_button_action):
    """Translate the internal right-button mode into final-user wording."""
    return "Controlled burn line" if right_button_action == "controlled" else "Water barrier"


def draw_grid(points, wind_direction, right_button_action, playing, current_fps):
    """Draw the map grid and the explanatory side panel.

    The grid itself is redrawn every frame from the current simulation state.
    The panel avoids technical implementation terms and instead tells users what
    each input does and what the active simulation settings are.
    """
    for point, (color, _duration) in points.items():
        col, row = point
        pygame.draw.rect(
            screen,
            color,
            (col * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE),
        )

    panel_x = GRID_WIDTH * TILE_SIZE
    pygame.draw.rect(screen, (30, 30, 30), (panel_x, 0, PANEL_WIDTH, HEIGHT))

    wind_text = "None"
    if wind_direction == (0, 1):
        wind_text = "South"
    elif wind_direction == (0, -1):
        wind_text = "North"
    elif wind_direction == (1, 0):
        wind_text = "East"
    elif wind_direction == (-1, 0):
        wind_text = "West"

    right_action_text = right_mouse_action_name(right_button_action)
    counts = count_cells(points)

    x = panel_x + 14
    y = 12
    y = draw_text("Fire Simulation", x, y, selected_font=title_font)
    y = draw_text(f"Status: {'Running' if playing else 'Paused'}", x, y)
    y = draw_text(f"FPS: {current_fps}", x, y)
    y = draw_text(f"Wind: {wind_text}", x, y)
    y = draw_text(f"Right mouse adds: {right_action_text}", x, y)

    y += 8
    y = draw_text("Mouse", x, y, selected_font=title_font)
    y = draw_text("Left: ignite fire", x, y)
    y = draw_text("Right: add water or burn line", x, y)

    y += 8
    y = draw_text("Keyboard", x, y, selected_font=title_font)
    y = draw_text("Space: run / pause", x, y)
    y = draw_text("C: switch right mouse action", x, y)
    y = draw_text("R: reset map", x, y)
    y = draw_text("W/A/S/D: set wind", x, y)
    y = draw_text("X: clear wind", x, y)
    y = draw_text("Up/Down: simulation speed", x, y)
    y = draw_text("Esc: quit", x, y)

    y += 8
    y = draw_text("Legend", x, y, selected_font=title_font)
    for color, label in TERRAIN_LABELS.items():
        y = draw_color_row(label, color, x, y)

    y += 8
    y = draw_text("Cell counts", x, y, selected_font=title_font)
    for label in ["Active fire", "Burned", "Controlled burn", "Burned firebreak", "Water barrier"]:
        y = draw_text(f"{label}: {counts[label]}", x, y)


def get_grid_pos():
    """Convert the current mouse position to a valid simulation grid coordinate."""
    x, y = pygame.mouse.get_pos()
    col = x // TILE_SIZE
    row = y // TILE_SIZE

    if 0 <= col < GRID_WIDTH and 0 <= row < GRID_HEIGHT:
        return col, row
    return None


def main():
    """Run the interactive event loop."""
    global FPS, GRID_WIDTH, GRID_HEIGHT, HEIGHT, WIDTH, screen

    # The app operates on the converted map, not the original screenshot-like map.
    # The converter reduces source colors to the canonical terrain colors expected
    # by `simulation.load_grid_from_image`.
    image_path = "maps/map1_converted.png"
    image = Image.open(image_path).convert("RGB")

    # Resize the window to the exact map grid plus the explanatory side panel.
    GRID_WIDTH = image.width // TILE_SIZE
    GRID_HEIGHT = image.height // TILE_SIZE
    WIDTH = GRID_WIDTH * TILE_SIZE + PANEL_WIDTH
    HEIGHT = GRID_HEIGHT * TILE_SIZE
    screen = pygame.display.set_mode((WIDTH, HEIGHT))

    background_image = pygame.image.fromstring(
        image.tobytes(),
        image.size,
        image.mode,
    )
    background_image = pygame.transform.scale(
        background_image,
        (GRID_WIDTH * TILE_SIZE, GRID_HEIGHT * TILE_SIZE),
    )
    screen.blit(background_image, (0, 0))

    wind_direction = (0, 0)
    running = True
    playing = False
    paused_fps = 10
    right_button_action = "water"

    points, grid_width, grid_height = load_grid_from_image(image_path, TILE_SIZE)

    while running:
        clock.tick(FPS)

        # When paused, the user can still paint fire/water/firebreaks. When
        # running, the automaton advances once per frame.
        if playing:
            points = update_grid(points, wind_direction, grid_width, grid_height)

        pygame.display.set_caption(
            "Fire Simulation - "
            f"{'Running' if playing else 'Paused'} - "
            f"Right mouse: {right_mouse_action_name(right_button_action)}"
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            left_pressed = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            left_drag = event.type == pygame.MOUSEMOTION and pygame.mouse.get_pressed()[0]
            right_pressed = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            right_drag = event.type == pygame.MOUSEMOTION and pygame.mouse.get_pressed()[2]
            mouse_grid_pos = get_grid_pos()

            # Left mouse is intentionally fixed to ignition so users always have
            # one stable, memorable way to start a fire.
            if mouse_grid_pos and (left_pressed or left_drag):
                ignite(points, mouse_grid_pos)

            # Right mouse is the only switched action. `C` toggles between water
            # and controlled burn, and the side panel always shows the active one.
            if mouse_grid_pos and (right_pressed or right_drag):
                if right_button_action == "controlled":
                    add_controlled_burn_patch(
                        points,
                        mouse_grid_pos,
                        grid_width=grid_width,
                        grid_height=grid_height,
                    )
                else:
                    add_water_patch(
                        points,
                        mouse_grid_pos,
                        grid_width=grid_width,
                        grid_height=grid_height,
                    )

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if playing:
                        playing = False
                        paused_fps = FPS
                        FPS = 60
                    else:
                        playing = True
                        FPS = paused_fps
                elif event.key == pygame.K_UP:
                    FPS = min(FPS + 1, 60)
                elif event.key == pygame.K_DOWN:
                    FPS = max(FPS - 1, 1)
                elif event.key == pygame.K_r:
                    points, grid_width, grid_height = load_grid_from_image(image_path, TILE_SIZE)
                elif event.key == pygame.K_c:
                    right_button_action = "controlled" if right_button_action == "water" else "water"
                elif event.key == pygame.K_w:
                    wind_direction = (0, -1)
                elif event.key == pygame.K_a:
                    wind_direction = (-1, 0)
                elif event.key == pygame.K_s:
                    wind_direction = (0, 1)
                elif event.key == pygame.K_d:
                    wind_direction = (1, 0)
                elif event.key == pygame.K_x:
                    wind_direction = (0, 0)

        draw_grid(points, wind_direction, right_button_action, playing, FPS)

        fps = font.render(f"{FPS} FPS", True, WHITE)
        screen.blit(fps, (3, 3))
        pygame.display.update()

    pygame.quit()


if __name__ == "__main__":
    main()
