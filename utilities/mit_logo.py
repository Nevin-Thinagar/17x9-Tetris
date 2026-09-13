"""The MIT logo for the display.

MIT_LOGO is the MIT wordmark as the Institute actually draws it: five vertical
bars and no diagonal strokes anywhere. The M is three bars whose middle one
stops short of the baseline, the I and the T each carry a gap below their top
element, and the T's arm extends rightward. It was derived by sampling the
official mark on brand.mit.edu down to the smallest size that keeps the bars
distinct.

SIZE. That smallest size is exactly nine columns: five one-column bars
separated by four one-column gaps. Sampling any smaller merges the bars into a
solid block -- at eight columns the whole mark comes out as "########" -- and
any larger needs eleven or more columns, which no longer fits the display. Six
rows follows from the wordmark's 1.89:1 proportions.

So the logo fits the display's width exactly, and needs only six of its
seventeen rows. One compromise falls out of that: at nine columns there is no
spare column between the I and the T's arm, so their top row touches. Keeping
them apart would need a tenth column.
"""

import time

from utilities.display import Color, Frame

#: The wordmark at minimum legible size: 6 rows x 9 columns.
#:   col 0, 2, 4  the M's three bars, the middle one short at the baseline
#:   col 6        the I, with its gap on row 1
#:   col 7        the T's arm
#:   col 8        the T's stem, with its gap on row 1
MIT_LOGO = [
    "#.#.#.###",
    "#.#.#....",
    "#.#.#.#.#",
    "#.#.#.#.#",
    "#.#.#.#.#",
    "#...#.#.#",
]

LOGO_ROWS = len(MIT_LOGO)
LOGO_COLS = len(MIT_LOGO[0])

#: Display.send() must not be called more than once every 0.033 seconds.
FPS = 30

DEFAULT_LIT = Color(255, 244, 214)
DEFAULT_OFF = Color(0, 0, 0)


def logo_top(frame):
    """Row at which the logo starts, centred vertically in the display."""
    return (frame.nrows() - LOGO_ROWS) // 2


def mit_logo_frame(lit_color=DEFAULT_LIT, off_color=DEFAULT_OFF):
    """Build a display-sized Frame with the MIT logo centred in it.

    The frame is a standard Frame() -- 17 rows by 9 columns -- so it can be
    sent to any Display unchanged.
    """
    frame = Frame()
    top = logo_top(frame)

    for r in range(frame.nrows()):
        for c in range(frame.ncols()):
            row = r - top
            lit = 0 <= row < LOGO_ROWS and MIT_LOGO[row][c] == "#"
            frame[r][c] = lit_color if lit else off_color

    return frame


def show_mit_logo(display, duration_seconds=3, lit_color=DEFAULT_LIT,
                  off_color=DEFAULT_OFF):
    """Hold the MIT logo on the display, then clear it.

    Sends a single frame and sleeps, rather than resending each tick: the image
    is static, and Display.send() must not be called more than once every
    0.033 seconds.
    """
    display.send(mit_logo_frame(lit_color, off_color))
    time.sleep(duration_seconds)
    display.send(Frame())
