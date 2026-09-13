"""The Chrome offline dinosaur, fitted to a nine-column runway.

A side-scroller only nine cells wide gives very little runway, so the layout
uses the tower's height instead: the run strip sits in the bottom five rows
and everything above it becomes sky for the score, drifting clouds and the
day/night cycle. The runner is an AI with perfect information, so it clears
obstacles reliably and the segment plays as a long clean run rather than a
string of crashes.
"""

from games.base import (
    BLACK,
    DIM,
    GREEN,
    MiniGame,
    ORANGE,
    WHITE,
    YELLOW,
    clear,
    hline,
    number,
    px,
    rect,
    scale,
)
from utilities.display import Color

# The original is monochrome, but at one window per pixel a white dino and a
# white cactus are the same shape and the same colour. Obstacles get their own
# hues so the silhouette is never ambiguous.
CACTUS = GREEN
BIRD = ORANGE

DAY_INK = WHITE
# Night is a cool blue-white rather than a dimmed grey: dimming everything on
# a facade reads as a fault, not as nightfall.
NIGHT_INK = Color(150, 180, 255)

GROUND_ROW = 16
FEET_ROW = 15  # Row the dino's feet rest on when grounded.
DINO_COL = 1
DINO_WIDTH = 2

# Jump arc tuned for a ~5 row peak over ~22 frames, which is long enough to
# carry the runner over an obstacle at the speeds used below.
JUMP_VELOCITY = 0.91
GRAVITY = 0.0826
# Frames from launch to the top of the arc: 2 * v / g / 2. The runner aims to
# be at that peak exactly as the obstacle reaches it, which is what decides
# when to take off.
AIRTIME = 2 * JUMP_VELOCITY / GRAVITY
APEX_FRAMES = AIRTIME / 2

SPAWN_COL = 9.0
DESPAWN_COL = -3.0

RUN_FRAMES = 30 * 22  # Length of the segment before the closing game over.
CRASH_PAUSE = 30


class Obstacle:
    """A cactus or a pterodactyl scrolling right to left."""

    def __init__(self, kind, col, width, height, row):
        self.kind = kind  # "cactus" or "bird"
        self.col = col
        self.width = width
        self.height = height
        self.row = row  # Topmost row the obstacle occupies.

    @property
    def bottom(self):
        return self.row + self.height - 1

    def overlaps_cols(self, col, width):
        return self.col < col + width and col < self.col + self.width


class Dino(MiniGame):
    """Endless runner that plays itself until the segment time is up."""

    name = "dino"
    max_frames = RUN_FRAMES + CRASH_PAUSE + 60

    def reset(self):
        self.obstacles = []
        self.clouds = [
            [self.rng.uniform(0, 9), self.rng.randint(7, 10)] for _ in range(3)
        ]
        self.score = 0
        self.crashes = 0
        self.night = False
        self.state = "running"
        self.timer = 0
        self._start_run()

    def _start_run(self):
        """Reset the runner itself without clearing the score or time."""
        self.obstacles.clear()
        self.height = 0.0  # Rows above the ground.
        self.vy = 0.0
        self.ducking = False
        self.speed = 0.22
        self.spawn_gap = 0.0
        self.leg = 0

    @property
    def grounded(self):
        return self.height <= 0.0

    def _dino_rows(self):
        """(top_row, height) the dino currently occupies."""
        feet = FEET_ROW - self.height
        if self.ducking and self.grounded:
            return feet, 1
        return feet - 1, 2

    def _spawn(self):
        """Add an obstacle, alternating cacti with the occasional bird."""
        if self.rng.random() < 0.25 and self.score > 8:
            # Pterodactyl at duck height: the runner has to go low, not high.
            self.obstacles.append(Obstacle("bird", SPAWN_COL, 2, 1, FEET_ROW - 1))
        else:
            tall = self.rng.random() < 0.4
            width = self.rng.choice([1, 1, 2])
            height = 2 if tall else 1
            self.obstacles.append(
                Obstacle("cactus", SPAWN_COL, width, height, FEET_ROW - height + 1)
            )
        # Leave enough clear road for the next jump to land before the
        # following obstacle arrives: a full arc covers speed * AIRTIME columns.
        self.spawn_gap = self.rng.uniform(3.0, 6.0) + self.speed * AIRTIME

    def _think(self):
        """Decide whether to jump or duck this frame.

        The launch point is not a fixed lead distance. The obstacle closes at
        `speed` columns per frame and the arc takes APEX_FRAMES to reach its
        peak, so the runner takes off once the obstacle is APEX_FRAMES' worth
        of travel away. That puts the obstacle underneath it at the top of the
        arc rather than under its feet on the way back down.
        """
        self.ducking = False
        if not self.obstacles:
            return

        nearest = min(
            (o for o in self.obstacles if o.col + o.width > DINO_COL),
            key=lambda o: o.col,
            default=None,
        )
        if nearest is None:
            return

        distance = nearest.col - DINO_COL

        if nearest.kind == "bird":
            # Birds fly at standing head height: go low and hold until it passes.
            if -2.0 < distance < 3.0 and self.grounded:
                self.ducking = True
        elif self.grounded and 0 < distance <= self.speed * APEX_FRAMES + 0.6:
            self.vy = JUMP_VELOCITY

    def _collided(self):
        top, height = self._dino_rows()
        bottom = top + height - 1
        for o in self.obstacles:
            if not o.overlaps_cols(DINO_COL, DINO_WIDTH):
                continue
            if o.row <= bottom and top <= o.bottom:
                return True
        return False

    def update(self):
        if self.state == "crashed":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "running"
                self._start_run()
            return True

        if self.state == "over":
            self.timer -= 1
            return self.timer > 0

        if self.frames >= RUN_FRAMES:
            self.state = "over"
            self.timer = 45
            return True

        self._think()

        # Vertical motion.
        if not self.grounded or self.vy > 0:
            self.height += self.vy
            self.vy -= GRAVITY
            if self.height <= 0:
                self.height = 0.0
                self.vy = 0.0

        # Scroll the world.
        self.speed = min(0.40, self.speed + 0.00022)
        for o in self.obstacles:
            o.col -= self.speed
        self.obstacles = [o for o in self.obstacles if o.col > DESPAWN_COL]

        self.spawn_gap -= self.speed
        if self.spawn_gap <= 0:
            self._spawn()

        for cloud in self.clouds:
            cloud[0] -= self.speed * 0.22
            if cloud[0] < -2:
                cloud[0] = 9.0 + self.rng.uniform(0, 3)
                cloud[1] = self.rng.randint(7, 10)

        self.leg = (self.leg + 1) % 8
        # Paced so a full run lands in the eighties: the readout is two digits
        # wide, and rolling past 99 would just look like a fault.
        self.score += self.speed * 0.42
        self.night = int(self.score) // 25 % 2 == 1

        if self._collided():
            self.state = "crashed"
            self.timer = CRASH_PAUSE
            self.crashes += 1

        return True

    def render(self, frame):
        clear(frame)

        ink = NIGHT_INK if self.night else DAY_INK
        faint = scale(ink, 0.22)

        # Sky: score, then clouds, then a moon once night falls.
        number(frame, self.score, 1, scale(ink, 0.8), digits=2)

        for col, row in self.clouds:
            px(frame, row, round(col), faint)
            px(frame, row, round(col) + 1, faint)

        if self.night:
            px(frame, 7, 7, scale(YELLOW, 0.5))

        # Ground.
        hline(frame, GROUND_ROW, 0, frame.ncols(), scale(ink, 0.35))

        # Obstacles.
        for o in self.obstacles:
            color = CACTUS if o.kind == "cactus" else BIRD
            rect(frame, o.row, round(o.col), o.height, o.width, color)

        # The runner. Flashes while crashed.
        if self.state == "crashed" and (self.timer // 4) % 2 == 0:
            return

        top, height = self._dino_rows()
        body = ink if self.state != "crashed" else scale(ink, 0.5)

        if height == 1:
            # Ducking: a flat two-cell crouch.
            rect(frame, top, DINO_COL, 1, DINO_WIDTH, body)
        else:
            # Standing: an L, head over the trailing body, so the silhouette
            # reads as an animal facing right rather than as a 2x2 block.
            px(frame, top, DINO_COL + 1, body)
            px(frame, top + 1, DINO_COL, body)
            px(frame, top + 1, DINO_COL + 1, body)
            # Alternating foot while grounded, for a sense of stride.
            if self.grounded and self.state == "running":
                px(frame, top, DINO_COL, scale(body, 0.35 if self.leg < 4 else 0.15))
