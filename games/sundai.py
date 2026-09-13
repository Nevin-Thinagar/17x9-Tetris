"""The Sundai logo, as a closing segment for the arcade loop.

The artwork is not invented here. The simulator ships its own brand demos as
raw frame data, and decoding the fully-built frame of `sundai-reveal` gives the
logo exactly as Sundai authored it for this 9 x 17 grid: a sundae glass drawn
in a horizontal pink-to-yellow gradient, with the scoop and cherry above it in
off-white. Those seven gradient stops are reproduced verbatim below, because
they are not a linear RGB ramp -- interpolating between the endpoints gives
visibly different midtones.

The segment reveals the logo from the base upward, holds while the gradient
drifts across the glass, then fades out.
"""

from games.base import MiniGame, clear, px, scale
from utilities.display import Color

# Columns 1..7 of the brand gradient, straight from the demo frame.
GRADIENT = {
    1: Color(0xED, 0x75, 0xAF),
    2: Color(0xF0, 0x90, 0xA1),
    3: Color(0xF3, 0xA6, 0x92),
    4: Color(0xF6, 0xB9, 0x80),
    5: Color(0xF9, 0xC9, 0x6A),
    6: Color(0xFC, 0xD8, 0x4C),
    7: Color(0xFF, 0xE6, 0x00),
}
GRADIENT_COLS = 7

CREAM = Color(0xC8, 0xC8, 0xC8)

# The scoop and cherry, rows 0-5.
SCOOP = (
    "....#....",
    "...###...",
    "...#.#...",
    "..#...#..",
    ".....##..",
    ".#.....#.",
)

# The glass, rows 6-16.
GLASS = (
    ".#######.",
    ".#.....#.",
    "..#####..",
    "..#...#..",
    "...#.#...",
    "...###...",
    "....#....",
    ".........",
    "..#...#..",
    "..#####..",
    ".........",
)
GLASS_TOP = 6

REVEAL_FRAMES = 46
HOLD_FRAMES = 180
FADE_FRAMES = 46


class Sundai(MiniGame):
    """Logo outro: reveals from the base up, gradient drifts, fades out."""

    name = "sundai"
    max_frames = REVEAL_FRAMES + HOLD_FRAMES + FADE_FRAMES + 10

    def reset(self):
        self.cells = {}
        for r, line in enumerate(SCOOP):
            for c, ch in enumerate(line):
                if ch == "#":
                    self.cells[(r, c)] = "cream"
        for r, line in enumerate(GLASS):
            for c, ch in enumerate(line):
                if ch == "#":
                    self.cells[(GLASS_TOP + r, c)] = "glass"

        # Rows above this are still hidden. Starts past the bottom row so
        # nothing is drawn, and walks up to -1 once everything is out.
        self.reveal_row = 17
        self.shift = 0
        self.level = 1.0

    def update(self):
        t = self.frames

        if t < REVEAL_FRAMES:
            # Wipe upward from the base, so the glass fills before the scoop
            # lands on top of it.
            progress = t / REVEAL_FRAMES
            self.reveal_row = int(17 - progress * 18)
            self.level = 1.0
        elif t < REVEAL_FRAMES + HOLD_FRAMES:
            self.reveal_row = -1
            # Drift the gradient across the glass.
            self.shift = (t // 4) % GRADIENT_COLS
            self.level = 1.0
        else:
            self.reveal_row = -1
            k = (t - REVEAL_FRAMES - HOLD_FRAMES) / FADE_FRAMES
            self.level = max(0.0, 1.0 - k)

        return t < self.max_frames - 1

    def render(self, frame):
        clear(frame)
        if self.level <= 0.01:
            return

        for (row, col), kind in self.cells.items():
            if row < self.reveal_row:
                continue
            if kind == "cream":
                color = CREAM
            else:
                # Shift which gradient stop each column takes, wrapping within
                # the seven brand colours.
                index = ((col - 1 + self.shift) % GRADIENT_COLS) + 1
                color = GRADIENT[index]
            px(frame, row, col, color if self.level >= 1.0 else scale(color, self.level))
