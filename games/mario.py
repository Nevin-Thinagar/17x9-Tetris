"""A Mario-style auto-running platformer for the 9x17 tower.

Nine columns is not enough runway to read a side-scroller the way the original
does, so the level is built to use height instead. The ground is not flat: it
steps up into plateaus one to three rows high, drops into pits, and carries
pipes, so Mario spends the run at varying altitude rather than tracking along
the bottom two rows. Brick runs and coins fill the air above him.

Mario is carried forward by the scroll and only controls his jump, which is
what makes an autonomous run legible: every decision is visible as an arc. The
AI is purely reactive -- it reads the ground and the obstacles just ahead of
him -- so the level generator guarantees a flat approach before every feature.
"""

from games.base import (
    BLACK,
    BLUE,
    BROWN,
    GREEN,
    MiniGame,
    ORANGE,
    RED,
    WHITE,
    YELLOW,
    clear,
    px,
    scale,
)

LEVEL_LENGTH = 170
GROUND_TOP = 15         # Surface row of the default, unraised ground.
FEET_ROW = GROUND_TOP - 1
MARIO_COL = 2           # Mario's fixed column on screen.
SCROLL_SPEED = 0.28     # Level columns per frame.

JUMP_VELOCITY = -0.91   # Negative is up: rows are numbered downward.
GRAVITY = 0.0826
STOMP_BOUNCE = -0.55
# Peak of the arc, in rows. Caps how high a step Mario can take.
JUMP_HEIGHT = (JUMP_VELOCITY ** 2) / (2 * GRAVITY)

SOLID = "GBP?"
DEATH_PAUSE = 24
END_PAUSE = 45

BRICK = BROWN
GRASS = scale(GREEN, 0.8)
DIRT = scale(BROWN, 0.55)
PIPE = GREEN
CAP = RED
OVERALLS = BLUE
CLOUD = scale(WHITE, 0.18)


class Goomba:
    def __init__(self, col, row):
        self.col = float(col)
        self.row = row
        self.alive = True
        self.squash = 0


class Mario(MiniGame):
    """Auto-runner that jumps gaps, climbs plateaus and stomps goombas."""

    name = "mario"
    max_frames = 30 * 40

    def reset(self):
        self._build_level()
        self.scroll = 0.0
        self.y = float(FEET_ROW)
        self.vy = 0.0
        self.coins = 0
        self.deaths = 0
        self.state = "run"
        self.timer = 0

    # -- level -------------------------------------------------------------

    def _build_level(self):
        """Generate a level as a tile grid plus a list of goombas.

        Built in two passes: the first picks features and records the ground
        surface height per column, the second paints tiles. Every feature is
        followed by several flat columns so the reactive AI always has a clean
        run-up, pits are capped at three columns, and plateaus are capped at a
        rise the jump arc can actually clear.
        """
        self.grid = [[" "] * LEVEL_LENGTH for _ in range(17)]
        # Surface row for each column; None marks a pit.
        surface = [GROUND_TOP] * LEVEL_LENGTH
        pipes = []
        platforms = []
        goomba_cols = []

        max_rise = int(JUMP_HEIGHT) - 2  # Leave headroom over the step.

        c = 12
        while c < LEVEL_LENGTH - 16:
            roll = self.rng.random()
            if roll < 0.20:
                width = self.rng.randint(2, 3)
                for i in range(width):
                    surface[c + i] = None
                c += width + self.rng.randint(5, 8)
            elif roll < 0.44:
                # A plateau: the ground steps up for a stretch, then back down.
                rise = self.rng.randint(1, max_rise)
                width = self.rng.randint(4, 9)
                for i in range(width):
                    if c + i < LEVEL_LENGTH:
                        surface[c + i] = GROUND_TOP - rise
                c += width + self.rng.randint(4, 7)
            elif roll < 0.60:
                # A staircase. A single plateau can only rise as far as one
                # jump clears, which leaves the top half of the tower empty;
                # stacking short steps walks the ground up six rows or more
                # while keeping every individual step jumpable.
                c = self._carve_staircase(surface, c)
            elif roll < 0.72:
                pipes.append((c, self.rng.randint(2, 3)))
                c += 1 + self.rng.randint(5, 8)
            elif roll < 0.82:
                goomba_cols.append(c)
                c += self.rng.randint(6, 9)
            else:
                # Row 8-10 puts the bricks within a jump of the ground, so the
                # coins above them are actually collectable from flat running
                # as well as from a plateau.
                platforms.append((c, self.rng.randint(3, 4), self.rng.choice([8, 9, 10])))
                c += self.rng.randint(6, 10)

        # Paint the ground from each column's surface down to the bottom.
        for col in range(LEVEL_LENGTH):
            top = surface[col]
            if top is None:
                continue
            for row in range(top, 17):
                self.grid[row][col] = "G"

        for col, height in pipes:
            base = surface[col] if surface[col] is not None else GROUND_TOP
            for row in range(base - height, base):
                self.grid[row][col] = "P"

        for col, width, row in platforms:
            for i in range(width):
                if col + i >= LEVEL_LENGTH:
                    break
                self.grid[row][col + i] = "?" if i % 2 == 0 else "B"
                if self.rng.random() < 0.6:
                    self.grid[row - 1][col + i] = "C"

        self.surface = surface
        self.goombas = [
            Goomba(col, (surface[col] or GROUND_TOP) - 1) for col in goomba_cols
        ]

    def _carve_staircase(self, surface, start):
        """Step the ground up, run along the top, then step back down.

        Returns the column to carry on generating from. Each tread rises two
        rows, well inside a single jump, so the reactive AI climbs it without
        needing to know the staircase is there.
        """
        steps = self.rng.randint(2, 3)
        tread = self.rng.randint(2, 3)
        rise = 2
        height = 0
        col = start

        def run(length, level):
            nonlocal col
            for _ in range(length):
                if col < LEVEL_LENGTH:
                    surface[col] = GROUND_TOP - level
                col += 1

        for _ in range(steps):
            height += rise
            run(tread, height)
        run(self.rng.randint(2, 4), height)
        for _ in range(steps):
            height -= rise
            run(tread, height)

        return col + self.rng.randint(4, 7)

    def _tile(self, col, row):
        if 0 <= row < 17 and 0 <= col < LEVEL_LENGTH:
            return self.grid[row][col]
        return " "

    def _solid(self, col, row):
        return self._tile(col, row) in SOLID

    def _ground_row(self, col):
        """Topmost solid row in a column, or None if it is a pit."""
        if 0 <= col < LEVEL_LENGTH:
            return self.surface[col]
        return GROUND_TOP

    @property
    def col(self):
        """Mario's column in level coordinates."""
        return self.scroll + MARIO_COL

    @property
    def grounded(self):
        return self.vy == 0 and self._solid(int(self.col), int(self.y) + 1)

    # -- ai ----------------------------------------------------------------

    def _think(self):
        """Jump if a pit, a step up, an obstacle or a goomba is coming up."""
        if not self.grounded:
            return

        here = int(self.col)
        feet = int(self.y)

        for ahead in (1, 2, 3):
            col = here + ahead
            # A pit: nothing solid anywhere below Mario in that column.
            if not any(self._solid(col, r) for r in range(feet + 1, 17)):
                self.vy = JUMP_VELOCITY
                return

        for ahead in (1, 2):
            col = here + ahead
            # A wall at body height: a pipe, a brick, or the face of a plateau.
            if self._solid(col, feet) or self._solid(col, feet - 1):
                self.vy = JUMP_VELOCITY
                return

        for goomba in self.goombas:
            if not goomba.alive:
                continue
            gap = goomba.col - self.col
            if 1.0 < gap < 3.2:
                self.vy = JUMP_VELOCITY
                return

        # Nothing to avoid, so go for a coin. The arc peaks after
        # JUMP_VELOCITY / GRAVITY frames, which at the scroll speed is about
        # three columns, so that is where a coin has to be to take off now.
        reach = here + 3
        for row in range(feet - int(JUMP_HEIGHT), feet):
            if self._tile(reach, row) == "C":
                self.vy = JUMP_VELOCITY
                return

    # -- physics -----------------------------------------------------------

    def _move_vertical(self):
        self.vy += GRAVITY
        new_y = self.y + self.vy
        col = int(self.col)

        if self.vy > 0:
            # Falling: land on the first solid row crossed this frame.
            for row in range(int(self.y) + 1, int(new_y) + 2):
                if self._solid(col, row):
                    self.y = row - 1
                    self.vy = 0.0
                    return
            self.y = new_y
        else:
            # Rising: stop if Mario's head hits something.
            head = int(new_y) - 1
            if self._solid(col, head):
                self.y = head + 2
                self.vy = 0.0
            else:
                self.y = new_y

    def _collect_coins(self):
        col = int(self.col)
        for row in (int(self.y), int(self.y) - 1):
            if self._tile(col, row) == "C":
                self.grid[row][col] = " "
                self.coins += 1

    def _handle_goombas(self):
        for goomba in self.goombas:
            if not goomba.alive:
                if goomba.squash > 0:
                    goomba.squash -= 1
                continue

            goomba.col -= 0.045
            ground = self._ground_row(int(goomba.col))
            if ground is None:
                # Walked off the edge into a pit, as goombas do.
                goomba.alive = False
                goomba.squash = 0
                continue
            goomba.row = ground - 1

            if abs(goomba.col - self.col) > 0.85:
                continue

            if self.vy > 0 and self.y <= goomba.row - 0.2:
                goomba.alive = False
                goomba.squash = 10
                self.vy = STOMP_BOUNCE
                self.coins += 1
            elif abs(self.y - goomba.row) < 0.9:
                self._die()
                return

    def _die(self):
        self.state = "dying"
        self.timer = DEATH_PAUSE
        self.deaths += 1

    def _respawn(self):
        """Skip past whatever killed him and drop back onto solid ground."""
        self.scroll += 4
        col = int(self.col)
        for step in range(0, 30):
            probe = col + step
            if self._ground_row(probe) is not None:
                self.scroll = probe - MARIO_COL
                self.y = float(self._ground_row(probe) - 1)
                break
        else:
            self.y = float(FEET_ROW)
        self.vy = 0.0
        self.state = "run"

    # -- loop --------------------------------------------------------------

    def update(self):
        if self.state == "dying":
            self.timer -= 1
            if self.timer <= 0:
                self._respawn()
            return True

        if self.state == "over":
            self.timer -= 1
            return self.timer > 0

        if self.scroll >= LEVEL_LENGTH - 12:
            self.state = "over"
            self.timer = END_PAUSE
            return True

        self.scroll += SCROLL_SPEED
        self._think()
        self._move_vertical()
        self._collect_coins()
        self._handle_goombas()

        # Fell down a pit.
        if self.y > 17:
            self._die()

        return True

    # -- drawing -----------------------------------------------------------

    def _draw_coins(self, frame):
        """Coin tally as pips along the top row.

        A 3x5 numeric readout would eat five of the seventeen rows, which on
        this display is a third of the level.
        """
        shown = min(self.coins, frame.ncols())
        color = YELLOW if self.coins <= frame.ncols() else ORANGE
        for i in range(shown):
            px(frame, 0, i, color)

    def render(self, frame):
        clear(frame)

        self._draw_coins(frame)

        base = int(self.scroll)
        for screen_col in range(frame.ncols()):
            level_col = base + screen_col
            for row in range(17):
                tile = self._tile(level_col, row)
                if tile == "G":
                    # Grass on the topmost ground tile of the column, dirt below.
                    top = self._tile(level_col, row - 1) != "G"
                    px(frame, row, screen_col, GRASS if top else DIRT)
                elif tile == "B":
                    px(frame, row, screen_col, BRICK)
                elif tile == "?":
                    pulse = (self.frames // 6) % 2 == 0
                    px(frame, row, screen_col, YELLOW if pulse else scale(YELLOW, 0.6))
                elif tile == "P":
                    px(frame, row, screen_col, PIPE)
                elif tile == "C":
                    if (self.frames // 4) % 2 == 0:
                        px(frame, row, screen_col, scale(YELLOW, 0.9))

        # A drifting cloud, purely so the sky is not dead.
        cloud_col = int(8 - (self.scroll * 0.25) % 11)
        px(frame, 3, cloud_col, CLOUD)
        px(frame, 3, cloud_col + 1, CLOUD)

        for goomba in self.goombas:
            screen_col = goomba.col - base
            if not -1 <= screen_col < frame.ncols():
                continue
            if goomba.alive:
                px(frame, goomba.row, round(screen_col), ORANGE)
            elif goomba.squash > 0:
                px(frame, goomba.row, round(screen_col), scale(ORANGE, 0.35))

        if self.state == "dying" and (self.timer // 3) % 2 == 0:
            return

        feet = int(round(self.y))
        px(frame, feet, MARIO_COL, OVERALLS)
        px(frame, feet - 1, MARIO_COL, CAP)
