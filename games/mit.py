"""The MIT logo as a loop segment, cycling its official colourways.

The wordmark fits the display's nine columns exactly at its minimum legible
size, so it is shown whole and still rather than panned. What moves instead is
the colour: the segment steps through the logo's approved variants from the
brand guide, crossfading between them, and ends on the reversed treatment with
the mark knocked out of a full red facade.

The bitmap and its sizing rationale live in utilities/mit_logo.py, shared with
the startup logo in tetris.py.

Unofficial: this is a personal educational project and is not affiliated with
or endorsed by MIT.
"""

from games.base import BLACK, MiniGame, WHITE, clear, lerp, px, scale
from utilities.display import Color
from utilities.mit_logo import LOGO_COLS, MIT_LOGO, logo_top

# MIT's palette, pushed brighter than the print values: straight cardinal is
# dim against a night facade, and the simulator's bloom does the rest.
CARDINAL = Color(205, 40, 65)     # MIT red, #A31F34
BRIGHT_RED = Color(255, 45, 60)   # MIT bright red
SILVER = Color(175, 177, 178)     # MIT silver grey, #8A8B8C

#: (mark colour, background colour) for each slide.
SLIDES = (
    (CARDINAL, BLACK),
    (SILVER, BLACK),
    (BRIGHT_RED, BLACK),
    # Reversed: the whole facade lit, the wordmark knocked out of it.
    (WHITE, CARDINAL),
)

HOLD_FRAMES = 46
CROSSFADE_FRAMES = 16
SLIDE_PERIOD = HOLD_FRAMES + CROSSFADE_FRAMES
OUTRO_FRAMES = 26


class MIT(MiniGame):
    """Steps the MIT logo through its brand colourways."""

    name = "mit"
    max_frames = SLIDE_PERIOD * len(SLIDES) + OUTRO_FRAMES

    def reset(self):
        self.cells = [
            (r, c)
            for r, line in enumerate(MIT_LOGO)
            for c in range(LOGO_COLS)
            if line[c] == "#"
        ]

    def update(self):
        return self.frames < self.max_frames - 1

    def _slide_colors(self):
        """Mark and background colour for this frame, crossfaded between slides."""
        index = min(len(SLIDES) - 1, self.frames // SLIDE_PERIOD)
        within = self.frames - index * SLIDE_PERIOD
        mark, background = SLIDES[index]

        if within >= HOLD_FRAMES and index + 1 < len(SLIDES):
            t = (within - HOLD_FRAMES) / CROSSFADE_FRAMES
            next_mark, next_background = SLIDES[index + 1]
            mark = lerp(mark, next_mark, t)
            background = lerp(background, next_background, t)

        return mark, background

    def _outro_level(self):
        """Fade everything out over the final frames."""
        start = SLIDE_PERIOD * len(SLIDES)
        if self.frames < start:
            return 1.0
        return max(0.0, 1.0 - (self.frames - start) / OUTRO_FRAMES)

    def render(self, frame):
        clear(frame)
        level = self._outro_level()
        if level <= 0.01:
            return

        mark, background = self._slide_colors()
        if level < 1.0:
            mark = scale(mark, level)
            background = scale(background, level)

        # Background first: on the reversed slide this lights the whole facade.
        for row in range(frame.nrows()):
            for col in range(frame.ncols()):
                px(frame, row, col, background)

        top = logo_top(frame)
        for row, col in self.cells:
            px(frame, top + row, col, mark)
