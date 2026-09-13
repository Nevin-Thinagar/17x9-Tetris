"""Electro's face, rendered on the facade.

Not a game -- an animation segment, built to the same MiniGame interface so it
drops into the arcade loop like everything else.

At nine windows across, a face only reads if it is built from silhouette and
two or three hot spots, not from features. So the head is a solid field of
electric blue against black, the eye sockets are cut out as dark holes, and the
eyes and mouth are the only white-hot cells. Everything else is motion: the
field flickers window by window, the whole face surges in brightness, and
bolts strike down across it.

The sequence runs reveal -> hold -> overload, so it has a shape rather than
looping forever on one pose.
"""

import math

from games.base import (
    BLACK,
    MiniGame,
    WHITE,
    clear,
    lerp,
    px,
    scale,
)
from utilities.display import Color

FACE_TOP = 3

# '#' face, ' ' dark socket inside the head, 'O' eye, 'M' mouth, '.' background.
FACE = (
    "..#####..",
    ".#######.",
    "#########",
    "#  ###  #",
    "#OO###OO#",
    "#########",
    "#########",
    ".#######.",
    ".##MMM##.",
    "..#####..",
    "...###...",
)

DEEP = Color(0, 30, 110)     # Unlit-but-present face cell.
LIVE = Color(0, 170, 255)    # Electric blue at normal charge.
HOT = Color(170, 245, 255)   # Near-white at full surge.

REVEAL_FRAMES = 55
HOLD_FRAMES = 300
OVERLOAD_FRAMES = 70

BOLT_INTERVAL = 38
BOLT_LIFE = 4


class Electro(MiniGame):
    """Electro's face surging on the building."""

    name = "electro"
    max_frames = REVEAL_FRAMES + HOLD_FRAMES + OVERLOAD_FRAMES + 30

    def reset(self):
        self.cells = {}
        for r, line in enumerate(FACE):
            for c, kind in enumerate(line):
                if kind != ".":
                    self.cells[(FACE_TOP + r, c)] = kind

        # Face cells light up in a scattered order during the reveal.
        self.order = [p for p, kind in self.cells.items() if kind == "#"]
        self.rng.shuffle(self.order)

        # Per-cell flicker phase, so the field shimmers instead of pulsing flat.
        self.phase = {p: self.rng.uniform(0, math.tau) for p in self.cells}

        self.bolts = []
        self.bolt_timer = BOLT_INTERVAL
        self.charge = 0.0
        self.flash = 0.0

    # -- helpers -----------------------------------------------------------

    def _spawn_bolt(self):
        """A jagged path down the whole tower, wandering one column at a time."""
        col = self.rng.randrange(0, 9)
        path = []
        for row in range(17):
            path.append((row, col))
            col = max(0, min(8, col + self.rng.choice([-1, 0, 1])))
        self.bolts.append([path, BOLT_LIFE])

    def _revealed(self):
        """How many face cells are lit during the reveal."""
        if self.frames >= REVEAL_FRAMES:
            return len(self.order)
        return int(len(self.order) * self.frames / REVEAL_FRAMES)

    # -- loop --------------------------------------------------------------

    def update(self):
        t = self.frames

        if t < REVEAL_FRAMES:
            self.charge = 0.35 + 0.25 * (t / REVEAL_FRAMES)
        elif t < REVEAL_FRAMES + HOLD_FRAMES:
            # Breathing surge with an irregular twitch on top.
            beat = (t - REVEAL_FRAMES) / 11.0
            self.charge = 0.72 + 0.16 * math.sin(beat) + 0.06 * math.sin(beat * 2.7)
            self.bolt_timer -= 1
            if self.bolt_timer <= 0:
                self._spawn_bolt()
                self.bolt_timer = BOLT_INTERVAL + self.rng.randint(-12, 14)
                self.flash = 0.55
        else:
            # Overload: charge runs away, then everything drops out.
            k = (t - REVEAL_FRAMES - HOLD_FRAMES) / OVERLOAD_FRAMES
            if k < 0.55:
                self.charge = 0.9 + 1.6 * k
                if self.rng.random() < 0.25:
                    self._spawn_bolt()
            else:
                self.charge = max(0.0, 2.3 * (1.0 - (k - 0.55) / 0.45))

        self.flash *= 0.82

        for bolt in self.bolts:
            bolt[1] -= 1
        self.bolts = [b for b in self.bolts if b[1] > 0]

        return t < self.max_frames - 1

    # -- drawing -----------------------------------------------------------

    def render(self, frame):
        clear(frame)

        limit = self._revealed()
        lit = set(self.order[:limit])
        charge = max(0.0, min(1.0, self.charge))

        for cell, kind in self.cells.items():
            row, col = cell
            if kind == " ":
                continue  # Eye socket: stays dark so the eyes read as deep-set.

            if kind == "#":
                if cell not in lit:
                    continue
                # Per-cell shimmer, so the field never looks like a flat fill.
                flicker = 0.72 + 0.28 * math.sin(self.frames * 0.35 + self.phase[cell])
                level = charge * flicker
                color = lerp(DEEP, LIVE, level)
                if level > 0.85:
                    color = lerp(color, HOT, (level - 0.85) / 0.15)
            else:
                # Eyes and mouth: the only white-hot cells, and the last to die.
                if limit < len(self.order) and kind == "M":
                    continue
                glow = min(1.0, charge * 1.25)
                color = lerp(LIVE, WHITE, glow)

            px(frame, row, col, color)

        for path, life in self.bolts:
            intensity = life / BOLT_LIFE
            for row, col in path:
                px(frame, row, col, lerp(LIVE, WHITE, intensity))

        # A dim wash over the whole facade when a bolt lands.
        if self.flash > 0.05:
            wash = scale(LIVE, self.flash * 0.35)
            for row in range(frame.nrows()):
                for col in range(frame.ncols()):
                    if str(frame[row][col]) == "#000000":
                        px(frame, row, col, wash)
