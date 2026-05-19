"""Convert map source images into canonical simulation terrain colors.

The source map images contain many slightly different RGB values because of
anti-aliasing around roads, rivers, and terrain boundaries. The simulation cannot
work directly with those thousands of colors, so this converter maps every pixel
to the nearest known source color and then replaces it with one of the canonical
colors from `simulation.py`.

Example:

- A source pixel close to `(195, 241, 213)` becomes `FOREST`.
- A source pixel close to `(143, 218, 237)` becomes `WATER`.
- A source pixel close to `(245, 243, 244)` becomes `BUILDINGS`.

The output image is what the app and tests load.
"""

from PIL import Image
import numpy as np

from fire_simulation.simulation import BUILDINGS, FOREST, GREEN, WATER

# Representative source colors sampled from the original map style. These are
# not the final simulation colors; they are anchors for nearest-color matching.
COLORS = {
    "water": (143, 218, 237),
    "forest": (195, 241, 213),
    "green_terrain": (210, 248, 225),
    "buildings": (245, 243, 244),
}

# Mapping from source color names to the canonical terrain colors used by the
# simulation engine.
TERRAIN_BY_COLOR = {
    "water": WATER,
    "forest": FOREST,
    "green_terrain": GREEN,
    "buildings": BUILDINGS,
}


def convert_image(image_path):
    """Convert a source map image to a four-class simulation map.

    Implementation detail:
    `pixels[:, :, None, :] - source_colors` compares every pixel to every source
    palette color at once. Squared RGB distance is enough here because all classes
    are visually well separated. The nearest palette entry chooses the terrain.
    """
    img = Image.open(image_path).convert('RGB')
    pixels = np.array(img)

    source_colors = np.array(list(COLORS.values()), dtype=np.int16)
    terrain_colors = np.array(
        [TERRAIN_BY_COLOR[key] for key in COLORS],
        dtype=np.uint8,
    )

    distances = np.sum(
        (pixels.astype(np.int16)[:, :, None, :] - source_colors) ** 2,
        axis=3,
    )
    converted = terrain_colors[np.argmin(distances, axis=2)]

    return Image.fromarray(converted)


def main():
    """Manual converter entry point for regenerating the converted map asset."""
    converted_image = convert_image('maps/map2.JPG')
    converted_image.save(f"maps/map2_converted.png")


if __name__ == '__main__':
    main()
