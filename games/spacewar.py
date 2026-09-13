"""Spacewar! (1962) on a 9x17 facade.

The original ran on a PDP-1 with a point-plotting CRT and roughly a thousand
addressable angles. This has 153 windows and eight. What survives that cut is
not the duel -- fine aiming is gone -- but the orbital dance, and that turns
out to be the part worth keeping.

Three decisions come out of measuring the geometry first:

* GM is tuned so orbits are stable between radius 2.5 and 4. Anything wider
  than radius 4 runs out of the nine-column field.
* Ships launch onto eccentric orbits down the seventeen-row axis, swinging
  from the top of the tower past the star and back. That path crosses about
  forty distinct windows, a quarter of the display, and is the most legible
  thing this game can draw.
* Every ship leaves a decaying trail. Without it a ship is a dot wandering
  semi-randomly and the gravity well is invisible; with it you can read the
  conic section directly off the building.

Torpedoes ignore gravity, as they did in the original.
"""

import math
from collections import deque

from games.base import (
    BLACK,
    CYAN,
    MiniGame,
    ORANGE,
    WHITE,
    YELLOW,
    clear,
    lerp,
    px,
    scale,
)
from utilities.display import Color

ROWS, COLS = 17, 9
STAR = (8.0, 4.0)

GM = 0.06               # Gravity, tuned for stable radius 2.5-4 orbits.
# Thrust has to beat gravity at the break-off radius or a ship can never climb
# out of perigee: at DANGER the well pulls GM/DANGER^2, about 0.006, and at two
# cells it is 0.015. Anything weaker than that and the star eats everyone.
THRUST = 0.020
MAX_SPEED = 0.45

TORP_SPEED = 0.38
TORP_LIFE = 42
TORP_COOLDOWN = 45
MAX_TORPS = 2
# Ships hold fire for the first few seconds of a round. Without it they launch
# already pointing at each other through the wrap and the round is over in a
# second and a half, before a single orbit has been drawn.
GRACE_FRAMES = 85
# And they only shoot inside this range, so kills come from closing in rather
# than from a lucky shot across the whole tower.
FIRE_RANGE = (1.6, 7.0)

ROTATE_PERIOD = 3       # Frames between heading changes.
TRAIL_LEN = 8

STAR_KILL = 1.1         # Closer than this to the star and you are gone.
HIT_RADIUS = 0.9
DANGER = 3.2            # Range at which the AI breaks off and climbs out.

EXPLODE_FRAMES = 26
ROUND_PAUSE = 20
WIN_SCORE = 3

# Heading 0 is north, increasing clockwise.
DIR8 = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
UNIT8 = tuple(
    (dr / math.hypot(dr, dc), dc / math.hypot(dr, dc)) for dr, dc in DIR8
)

# The "Expensive Planetarium" background, at the only density this grid allows.
BACKDROP = ((1, 1), (2, 7), (5, 0), (6, 8), (11, 1), (14, 7), (15, 3))
BACKDROP_COLOR = Color(28, 28, 44)

STAR_CORE = Color(255, 245, 200)


def wrapped_delta(a, b):
    """Shortest (drow, dcol) from a to b on a torus.

    Using the direct delta would make gravity snap to the opposite direction
    the instant a ship wraps an edge, which reads as a glitch. The wrapped
    delta flips only at the point of symmetry, where it is smooth.
    """
    dr = (b[0] - a[0] + ROWS / 2) % ROWS - ROWS / 2
    dc = (b[1] - a[1] + COLS / 2) % COLS - COLS / 2
    return dr, dc


def bearing(dr, dc):
    """Nearest of the eight headings pointing along (dr, dc)."""
    return int(round(math.atan2(dc, -dr) / (math.pi / 4))) % 8


class Torpedo:
    __slots__ = ("r", "c", "vr", "vc", "life", "owner")

    def __init__(self, r, c, vr, vc, owner):
        self.r, self.c = r, c
        self.vr, self.vc = vr, vc
        self.life = TORP_LIFE
        self.owner = owner


class Ship:
    def __init__(self, color, name):
        self.color = color
        self.name = name
        self.score = 0
        self.trail = deque(maxlen=TRAIL_LEN)

    def place(self, r, c, vr, vc, heading):
        self.r, self.c = r, c
        self.vr, self.vc = vr, vc
        self.heading = heading
        self.alive = True
        self.cooldown = 0
        self.rotate_tick = 0
        self.thrusting = False
        self.trail.clear()

    def pos(self):
        return (self.r, self.c)


class Spacewar(MiniGame):
    """Two AI ships duelling in the star's gravity well."""

    name = "spacewar"
    max_frames = 30 * 40

    def reset(self):
        self.ships = [Ship(CYAN, "needle"), Ship(ORANGE, "wedge")]
        self.torps = []
        self.explosions = []
        self.state = "fly"
        self.timer = 0
        self._launch()

    def _launch(self):
        """Put both ships on opposing eccentric orbits down the tall axis.

        Launching at roughly 0.75 of circular speed from six rows out gives an
        orbit that swings in to about two cells from the star and back out to
        the top of the tower -- the slingshot the whole game is about.

        Launch angles stay near vertical because the field is only nine columns
        wide: a six-cell radius fits down the seventeen-row axis but not across.
        Everything is jittered per round, since perfectly mirrored starts make
        every round play out identically.
        """
        self.torps.clear()
        self.grace = GRACE_FRAMES
        base = self.rng.uniform(-0.35, 0.35)

        for i, ship in enumerate(self.ships):
            tilt = base + math.pi * i + self.rng.uniform(-0.25, 0.25)
            apo = self.rng.uniform(5.2, 6.8)
            r = STAR[0] - apo * math.cos(tilt)
            c = STAR[1] + apo * math.sin(tilt)
            ur, uc = (r - STAR[0]) / apo, (c - STAR[1]) / apo
            speed = self.rng.uniform(0.70, 0.82) * math.sqrt(GM / apo)
            # Perpendicular to the radius, same sense for both, so they orbit
            # in the same direction and end up chasing each other.
            vr, vc = uc * speed, -ur * speed
            ship.place(r % ROWS, c % COLS, vr, vc, bearing(vr, vc))
            ship.burn_phase = self.rng.randrange(9, 15)

    # -- physics -----------------------------------------------------------

    def _gravity(self, r, c):
        dr, dc = wrapped_delta((r, c), STAR)
        d = math.hypot(dr, dc)
        if d < 0.35:
            return 0.0, 0.0, d
        a = GM / (d * d)
        return a * dr / d, a * dc / d, d

    def _step_ship(self, ship):
        ar, ac, _ = self._gravity(ship.r, ship.c)
        ship.vr += ar
        ship.vc += ac

        if ship.thrusting:
            ur, uc = UNIT8[ship.heading]
            ship.vr += ur * THRUST
            ship.vc += uc * THRUST

        speed = math.hypot(ship.vr, ship.vc)
        if speed > MAX_SPEED:
            ship.vr *= MAX_SPEED / speed
            ship.vc *= MAX_SPEED / speed

        ship.r = (ship.r + ship.vr) % ROWS
        ship.c = (ship.c + ship.vc) % COLS
        ship.trail.append((round(ship.r) % ROWS, round(ship.c) % COLS))

    # -- ai ----------------------------------------------------------------

    def _pilot(self, ship, foe):
        """Fly the orbit, break off from the star, shoot when lined up."""
        ship.thrusting = False
        if ship.cooldown > 0:
            ship.cooldown -= 1

        sr, sc = wrapped_delta(ship.pos(), STAR)
        star_dist = math.hypot(sr, sc)

        if star_dist < DANGER:
            # Climb out: point straight away from the star and burn.
            want = bearing(-sr, -sc)
            ship.thrusting = True
        elif star_dist > 7.2:
            # Drifting out of the well: aim back across it to fall in again.
            want = bearing(sr, sc)
            ship.thrusting = self.frames % 3 == 0
        else:
            fr, fc = wrapped_delta(ship.pos(), foe.pos())
            want = bearing(fr, fc)
            # Burn occasionally to keep the orbit from settling into a circle.
            # Each ship has its own cadence so the two never move in lockstep.
            ship.thrusting = self.frames % ship.burn_phase == 0

        # Rotate at most one step at a time, the short way round.
        ship.rotate_tick += 1
        if ship.rotate_tick >= ROTATE_PERIOD and want != ship.heading:
            ship.rotate_tick = 0
            diff = (want - ship.heading) % 8
            ship.heading = (ship.heading + (1 if diff <= 4 else -1)) % 8

        # Fire when on target, clear of the star, and inside engagement range.
        if self.grace > 0 or ship.cooldown or star_dist <= DANGER:
            return
        if sum(1 for t in self.torps if t.owner is ship) >= MAX_TORPS:
            return
        fr, fc = wrapped_delta(ship.pos(), foe.pos())
        if not FIRE_RANGE[0] < math.hypot(fr, fc) < FIRE_RANGE[1]:
            return
        if bearing(fr, fc) == ship.heading:
            self._fire(ship)

    def _fire(self, ship):
        ur, uc = UNIT8[ship.heading]
        self.torps.append(
            Torpedo(
                ship.r + ur, ship.c + uc,
                ship.vr + ur * TORP_SPEED,
                ship.vc + uc * TORP_SPEED,
                ship,
            )
        )
        ship.cooldown = TORP_COOLDOWN

    # -- collisions --------------------------------------------------------

    def _kill(self, ship, scorer=None):
        ship.alive = False
        self.explosions.append([ship.r, ship.c, EXPLODE_FRAMES])
        if scorer is not None:
            scorer.score += 1
        self.state = "boom"
        self.timer = EXPLODE_FRAMES + ROUND_PAUSE

    def _collisions(self):
        for ship in self.ships:
            if not ship.alive:
                continue
            _, _, d = self._gravity(ship.r, ship.c)
            if d < STAR_KILL:
                foe = self.ships[1] if ship is self.ships[0] else self.ships[0]
                self._kill(ship, foe)
                return

        for torp in self.torps:
            for ship in self.ships:
                if not ship.alive or torp.owner is ship:
                    continue
                dr, dc = wrapped_delta((torp.r, torp.c), ship.pos())
                if math.hypot(dr, dc) < HIT_RADIUS:
                    self._kill(ship, torp.owner)
                    torp.life = 0
                    return

    # -- loop --------------------------------------------------------------

    def update(self):
        for blast in self.explosions:
            blast[2] -= 1
        self.explosions = [b for b in self.explosions if b[2] > 0]

        if self.state == "boom":
            self.timer -= 1
            if self.timer <= 0:
                if max(s.score for s in self.ships) >= WIN_SCORE:
                    self.state = "over"
                    self.timer = 45
                else:
                    self.state = "fly"
                    self._launch()
            return True

        if self.state == "over":
            self.timer -= 1
            return self.timer > 0

        if self.grace > 0:
            self.grace -= 1

        for ship in self.ships:
            if ship.alive:
                foe = self.ships[1] if ship is self.ships[0] else self.ships[0]
                self._pilot(ship, foe)
                self._step_ship(ship)

        for torp in self.torps:
            torp.r = (torp.r + torp.vr) % ROWS
            torp.c = (torp.c + torp.vc) % COLS
            torp.life -= 1
            _, _, d = self._gravity(torp.r, torp.c)
            if d < STAR_KILL:
                torp.life = 0
        self.torps = [t for t in self.torps if t.life > 0]

        self._collisions()
        return True

    # -- drawing -----------------------------------------------------------

    def render(self, frame):
        clear(frame)

        for r, c in BACKDROP:
            px(frame, r, c, BACKDROP_COLOR)

        # Trails, oldest and faintest first, so the orbit reads as a curve.
        for ship in self.ships:
            for age, (r, c) in enumerate(ship.trail):
                level = 0.16 + 0.44 * (age / max(1, len(ship.trail) - 1))
                px(frame, r, c, scale(ship.color, level))

        # The star. It needs a faint corona as well as a hot core: as a single
        # cream cell it reads no louder than the backdrop, and the whole game
        # is about where it is.
        pulse = 0.86 + 0.14 * math.sin(self.frames * 0.18)
        sr, sc = round(STAR[0]), round(STAR[1])
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            px(frame, sr + dr, sc + dc, scale(STAR_CORE, 0.13 * pulse))
        px(frame, sr, sc, scale(STAR_CORE, pulse))

        for torp in self.torps:
            px(frame, round(torp.r) % ROWS, round(torp.c) % COLS, WHITE)

        for ship in self.ships:
            if not ship.alive:
                continue
            row, col = round(ship.r) % ROWS, round(ship.c) % COLS
            dr, dc = DIR8[ship.heading]
            # Dim nose cell first, so the bright hull wins any overlap.
            px(frame, (row + dr) % ROWS, (col + dc) % COLS,
               scale(ship.color, 0.45 if not ship.thrusting else 0.85))
            px(frame, row, col, ship.color)

        for r, c, life in self.explosions:
            k = 1.0 - life / EXPLODE_FRAMES
            radius = int(k * 3)
            shade = lerp(WHITE, ORANGE, k)
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if abs(dr) + abs(dc) == radius:
                        px(frame, (round(r) + dr) % ROWS, (round(c) + dc) % COLS,
                           scale(shade, 1.0 - k))

        # Score pips in the corners: needle top-left, wedge bottom-right.
        for i in range(self.ships[0].score):
            px(frame, 0, i, scale(self.ships[0].color, 0.7))
        for i in range(self.ships[1].score):
            px(frame, 16, 8 - i, scale(self.ships[1].color, 0.7))
