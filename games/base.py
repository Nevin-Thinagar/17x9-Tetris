"""Shared scaffolding for the 9x17 attract-mode games.

Everything here is built on the existing display primitives in
utilities/display.py so the games run unchanged on the pygame DummyDisplay,
on the Green Building simulator, or on the real facade.

The grid is 9 columns wide and 17 rows tall. That portrait shape drives
every design decision in this package: Pong turns sideways, the dino runs
along the bottom strip, Pac-Man gets a tall maze, and Mario's level leans
on vertical platforming instead of a long horizontal run.

Colours are never mutated in place. A Frame is a numpy array of *references*
to Color objects, and the constants below are shared, so mutating one would
recolour every cell pointing at it.
"""

import abc

from utilities.display import Color, Frame

# Display geometry. Kept here so games never hard-code the numbers.
ROWS = Frame.DISPLAY_ROWS
COLS = Frame.DISPLAY_COLS

# Shared palette. Deliberately bright and saturated: an unlit window reads as
# black on the facade, so contrast matters far more than subtlety.
BLACK = Color()
WHITE = Color(255, 255, 255)
GREY = Color(110, 110, 110)
DIM = Color(40, 40, 40)

RED = Color(255, 0, 0)
ORANGE = Color(255, 140, 0)
YELLOW = Color(255, 230, 0)
GREEN = Color(0, 230, 0)
CYAN = Color(0, 255, 255)
BLUE = Color(40, 80, 255)
PURPLE = Color(170, 0, 255)
PINK = Color(255, 120, 180)
BROWN = Color(150, 75, 0)


def clear(frame, color=BLACK):
    """Fill the whole frame with a single colour."""
    frame.asarray()[:] = color


def px(frame, row, col, color):
    """Set one cell, ignoring anything that falls outside the display."""
    if 0 <= row < frame.nrows() and 0 <= col < frame.ncols():
        frame[int(row), int(col)] = color


def rect(frame, row, col, height, width, color):
    """Fill an axis-aligned block, clipped to the display."""
    for r in range(int(row), int(row) + height):
        for c in range(int(col), int(col) + width):
            px(frame, r, c, color)


def hline(frame, row, col, length, color):
    """Draw a horizontal run of cells."""
    rect(frame, row, col, 1, length, color)


def vline(frame, row, col, length, color):
    """Draw a vertical run of cells."""
    rect(frame, row, col, length, 1, color)


# A 3x5 pixel font, wide enough to fit two digits across the 9-column display.
# Each glyph is five rows of three characters; '#' lights the cell.
_GLYPHS = {
    "0": ("###", "#.#", "#.#", "#.#", "###"),
    "1": ("..#", "..#", "..#", "..#", "..#"),
    "2": ("###", "..#", "###", "#..", "###"),
    "3": ("###", "..#", "###", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"),
    "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"),
    "7": ("###", "..#", "..#", "..#", "..#"),
    "8": ("###", "#.#", "###", "#.#", "###"),
    "9": ("###", "#.#", "###", "..#", "###"),
    " ": ("...", "...", "...", "...", "..."),
    "-": ("...", "...", "###", "...", "..."),
    "P": ("###", "#.#", "###", "#..", "#.."),
    "A": ("###", "#.#", "###", "#.#", "#.#"),
    "C": ("###", "#..", "#..", "#..", "###"),
    "M": ("#.#", "###", "###", "#.#", "#.#"),
    "N": ("#.#", "###", "###", "###", "#.#"),
    "O": ("###", "#.#", "#.#", "#.#", "###"),
    "G": ("###", "#..", "#.#", "#.#", "###"),
    "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "I": ("###", ".#.", ".#.", ".#.", "###"),
    "R": ("###", "#.#", "###", "##.", "#.#"),
    "S": ("###", "#..", "###", "..#", "###"),
    "T": ("###", ".#.", ".#.", ".#.", ".#."),
    "U": ("#.#", "#.#", "#.#", "#.#", "###"),
    "W": ("#.#", "#.#", "###", "###", "#.#"),
    "L": ("#..", "#..", "#..", "#..", "###"),
    "E": ("###", "#..", "###", "#..", "###"),
    "!": (".#.", ".#.", ".#.", "...", ".#."),
}

GLYPH_WIDTH = 3
GLYPH_HEIGHT = 5


def glyph(frame, char, row, col, color):
    """Draw a single 3x5 character with its top-left corner at (row, col)."""
    pattern = _GLYPHS.get(char.upper())
    if pattern is None:
        return
    for dr, line in enumerate(pattern):
        for dc, cell in enumerate(line):
            if cell == "#":
                px(frame, row + dr, col + dc, color)


def text(frame, string, row, col, color, spacing=1):
    """Draw a short string left-to-right. Only two glyphs fit across 9 columns."""
    for i, char in enumerate(string):
        glyph(frame, char, row, col + i * (GLYPH_WIDTH + spacing), color)


def text_width(string, spacing=1):
    """Pixel width of a string drawn by text()."""
    if not string:
        return 0
    return len(string) * GLYPH_WIDTH + (len(string) - 1) * spacing


def centered_text(frame, string, row, color, spacing=1):
    """Draw a string horizontally centred on the display."""
    col = (frame.ncols() - text_width(string, spacing)) // 2
    text(frame, string, row, col, color, spacing)


def number(frame, value, row, color, digits=2):
    """Draw a zero-padded number centred on the display."""
    string = str(int(value)).rjust(digits, "0")[-digits:]
    centered_text(frame, string, row, color)


def scale(color, factor):
    """Return a dimmed or brightened copy of a colour.

    Returns a new Color rather than mutating, since palette constants are
    shared across every cell that references them.
    """
    return Color(color.r * factor, color.g * factor, color.b * factor)


def lerp(a, b, t):
    """Blend two colours. t=0 gives a, t=1 gives b."""
    t = max(0.0, min(1.0, t))
    return Color(
        a.r + (b.r - a.r) * t,
        a.g + (b.g - a.g) * t,
        a.b + (b.b - a.b) * t,
    )


class MiniGame(abc.ABC):
    """A self-playing game segment.

    The runner drives every game the same way: reset() once, then step()
    and render() once per frame until step() returns False.
    """

    #: Shown in the console when the segment starts.
    name = "game"

    #: Hard cap on segment length in frames, so a stuck AI can never wedge
    #: the loop. Subclasses usually finish well before this.
    max_frames = 30 * 60

    def __init__(self, rng):
        self.rng = rng
        self.frames = 0

    @abc.abstractmethod
    def reset(self):
        """Set up a fresh round. Called once before the first step()."""

    @abc.abstractmethod
    def update(self):
        """Advance the simulation one frame.

        Return False to end the segment, True to keep playing.
        """

    @abc.abstractmethod
    def render(self, frame):
        """Draw the current state into frame."""

    def step(self):
        """Advance one frame, enforcing the max_frames safety cap."""
        self.frames += 1
        if self.frames >= self.max_frames:
            return False
        return self.update()
