"""Colour ripples: expanding rings that grade into each other.

An ambient segment rather than a game. Rings spread outward from scattered
origins over a slowly drifting background gradient, and each ring carries its
own colour drawn from the palette currently in play.

The blending is the point. Every ring writes into a floating-point RGB
accumulator and the whole buffer is resolved once at the end of the frame, so
two rings crossing actually sum -- magenta over gold reads as a hot white seam
where they meet, not as whichever happened to be drawn last. Clamping per cell
after the fact is what produces the grading; painting rings one at a time would
just give flat overlapping arcs.

Rings are drawn as a Gaussian band around the current radius rather than as a
hard circle, which is what keeps them legible when a nine-column grid can only
sample the ring at a handful of points.
"""

import math

from games.base import MiniGame, clear, px
from utilities.display import Color

ROWS, COLS = 17, 9

# Each palette is a set of ring colours plus the two ends of its background
# gradient. Cycling these is what "different colours" means here: the whole
# screen changes key every few seconds, not just the next ring.
PALETTES = (
    {   # Sundai brand
        "rings": ((237, 117, 175), (246, 185, 128), (255, 230, 0)),
        "wash": ((60, 12, 40), (50, 40, 0)),
    },
    {   # Ocean
        "rings": ((0, 64, 255), (0, 229, 255), (0, 255, 160)),
        "wash": ((0, 14, 60), (0, 40, 45)),
    },
    {   # Sunset
        "rings": ((255, 0, 160), (255, 112, 0), (255, 208, 0)),
        "wash": ((55, 0, 40), (55, 28, 0)),
    },
    {   # Aurora
        "rings": ((0, 255, 128), (0, 208, 255), (160, 64, 255)),
        "wash": ((0, 50, 30), (26, 0, 55)),
    },
)

PALETTE_FRAMES = 150        # About five seconds in each key.
SPAWN_INTERVAL = 21
RING_SPEED = 0.16           # Cells per frame.
RING_WIDTH = 1.15           # Gaussian sigma, in cells.
RING_RANGE = 19.0           # Diagonal of the display; rings die past this.
RING_GAIN = 1.25

FADE_FRAMES = 30

# Highlight roll-off. Summed rings routinely push a channel past 255, and hard
# clipping drags every overloaded cell to flat white -- once all three channels
# clip, the hue is gone. Compressing everything above the knee instead keeps
# the ratio between channels, so a hot overlap stays recognisably pink or cyan.
KNEE = 150.0
HEADROOM = 105.0


def _rolloff(value):
    if value <= KNEE:
        return value
    return KNEE + HEADROOM * (1.0 - math.exp(-(value - KNEE) / HEADROOM))


class Ripple(MiniGame):
    """Expanding colour rings over a drifting background wash."""

    name = "ripple"
    max_frames = PALETTE_FRAMES * len(PALETTES) + FADE_FRAMES

    def reset(self):
        self.rings = []
        self.spawn_timer = 0
        self.ring_index = 0
        self._spawn()

    def _palette(self):
        index = min(
            len(PALETTES) - 1, self.frames // PALETTE_FRAMES
        )
        return PALETTES[index]

    def _spawn(self):
        """Start a ring at a random origin in the current palette's colours."""
        colors = self._palette()["rings"]
        color = colors[self.ring_index % len(colors)]
        self.ring_index += 1
        self.rings.append(
            {
                "row": self.rng.uniform(0, ROWS - 1),
                "col": self.rng.uniform(0, COLS - 1),
                "radius": 0.0,
                "color": color,
                # Slight speed variation so rings never march in lockstep.
                "speed": RING_SPEED * self.rng.uniform(0.82, 1.2),
            }
        )

    def update(self):
        for ring in self.rings:
            ring["radius"] += ring["speed"]
        self.rings = [r for r in self.rings if r["radius"] < RING_RANGE]

        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self._spawn()
            self.spawn_timer = SPAWN_INTERVAL + self.rng.randint(-6, 8)

        return self.frames < self.max_frames - 1

    def _envelope(self):
        """Overall level: fade in at the start, out at the end."""
        if self.frames < FADE_FRAMES:
            return self.frames / FADE_FRAMES
        remaining = self.max_frames - self.frames
        if remaining < FADE_FRAMES:
            return max(0.0, remaining / FADE_FRAMES)
        return 1.0

    def render(self, frame):
        clear(frame)
        level = self._envelope()
        if level <= 0.01:
            return

        palette = self._palette()
        wash_a, wash_b = palette["wash"]

        # Accumulate in floating point, resolve once at the end, so overlapping
        # rings sum into new colours instead of overwriting one another.
        buffer = [[[0.0, 0.0, 0.0] for _ in range(COLS)] for _ in range(ROWS)]

        # Background wash: a vertical gradient that slides down the tower.
        drift = (self.frames * 0.004) % 1.0
        for row in range(ROWS):
            t = (row / (ROWS - 1) + drift) % 1.0
            # Fold it so the gradient reverses instead of jumping at the wrap.
            t = t * 2 if t < 0.5 else (1.0 - t) * 2
            cell = buffer[row]
            for col in range(COLS):
                for i in range(3):
                    cell[col][i] += wash_a[i] + (wash_b[i] - wash_a[i]) * t

        for ring in self.rings:
            radius = ring["radius"]
            # Energy spreads as the ring grows, so it dims with radius.
            strength = RING_GAIN * max(0.0, 1.0 - radius / RING_RANGE)
            if strength <= 0.0:
                continue
            color = ring["color"]
            orow, ocol = ring["row"], ring["col"]
            for row in range(ROWS):
                dr = row - orow
                for col in range(COLS):
                    dc = col - ocol
                    offset = math.hypot(dr, dc) - radius
                    if abs(offset) > 3.0 * RING_WIDTH:
                        continue
                    amp = strength * math.exp(
                        -(offset * offset) / (2 * RING_WIDTH * RING_WIDTH)
                    )
                    target = buffer[row][col]
                    for i in range(3):
                        target[i] += color[i] * amp

        for row in range(ROWS):
            for col in range(COLS):
                r, g, b = buffer[row][col]
                px(
                    frame,
                    row,
                    col,
                    Color(
                        _rolloff(r) * level,
                        _rolloff(g) * level,
                        _rolloff(b) * level,
                    ),
                )
