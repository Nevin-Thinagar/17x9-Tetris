"""Pac-Man on a 9x17 maze.

The arcade board is 28x31, so this is a redrawn maze rather than a crop:
nine columns wide, seventeen tall, mirrored left-to-right and top-to-bottom,
with two vertical highways at columns 1 and 7 tying the halves together.
Seventy pellets and four power pellets fill it.

Both sides are real search. Pac-Man runs a breadth-first search to the nearest
pellet across cells the ghosts are not about to occupy, and switches to hunting
once a power pellet flips them; the ghosts run their own search back toward him,
one chasing his cell and one aiming ahead of him.
"""

from collections import deque

from games.base import (
    BLACK,
    BLUE,
    CYAN,
    MiniGame,
    PINK,
    RED,
    WHITE,
    YELLOW,
    clear,
    px,
    scale,
)
from utilities.display import Color

MAZE = (
    "#########",
    "#o.....o#",
    "#.##.##.#",
    "#.......#",
    "#.#.#.#.#",
    "#...#...#",
    "##.###.##",
    "#.......#",
    "#.#####.#",
    "#.......#",
    "##.###.##",
    "#...#...#",
    "#.#.#.#.#",
    "#.......#",
    "#.##.##.#",
    "#o.....o#",
    "#########",
)

PAC_START = (13, 4)
# Ghosts pick two of these each round, so no two runs open the same way.
GHOST_SPAWNS = [(3, 1), (3, 3), (3, 5), (3, 7), (7, 3), (7, 5), (9, 3), (9, 5)]

PAC_PERIOD = 4          # Frames between Pac-Man's moves.
GHOST_PERIOD = 5        # Ghosts are a touch slower than Pac-Man.
# Odds a ghost ignores its search and wanders. Without this the whole board
# is deterministic and every run plays out identically.
GHOST_NOISE = 0.15
FRIGHT_PERIOD = 9       # And much slower once frightened.
FRIGHT_FRAMES = 30 * 6
DEATH_PAUSE = 40
END_PAUSE = 50
LIVES = 3

DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))

# Walls are kept deliberately dark. Frightened ghosts are blue in the arcade
# game, and against a brighter blue maze they vanish into the walls entirely.
WALL = Color(18, 26, 80)
PELLET = scale(WHITE, 0.30)
FRIGHTENED = Color(140, 170, 255)


class Ghost:
    def __init__(self, home, color, ambush):
        self.home = home
        self.color = color
        self.ambush = ambush  # Aim ahead of Pac-Man instead of at him.
        self.reset()

    def reset(self):
        self.pos = self.home
        self.dir = (0, 0)
        self.frightened = False
        self.eaten = False
        self.respawn = 0


class PacMan(MiniGame):
    """A full board, played out by search on both sides."""

    name = "pacman"
    max_frames = 30 * 90

    def reset(self):
        self.open = {
            (r, c)
            for r, line in enumerate(MAZE)
            for c, cell in enumerate(line)
            if cell != "#"
        }
        self.pellets = {p for p in self.open if MAZE[p[0]][p[1]] in ".o"}
        self.power = {p for p in self.open if MAZE[p[0]][p[1]] == "o"}
        homes = self.rng.sample(GHOST_SPAWNS, 2)
        self.ghosts = [
            Ghost(homes[0], RED, ambush=False),
            Ghost(homes[1], PINK, ambush=True),
        ]
        self.lives = LIVES
        self.score = 0
        self.state = "play"
        self.timer = 0
        self.fright = 0
        # Vary the pace and how wide a berth Pac-Man gives the ghosts, so some
        # rounds are comfortable clears and some are genuinely close.
        self.ghost_period = self.rng.choice([4, 5, 5])
        self.caution = self.rng.choice([1, 2, 2])
        self._place()

    def _place(self):
        """Put everyone back on their starting cell."""
        self.pac = PAC_START
        self.pac_dir = (0, -1)
        self.pac_tick = 0
        self.ghost_tick = 0
        for ghost in self.ghosts:
            ghost.reset()

    # -- search helpers ----------------------------------------------------

    def _neighbours(self, cell):
        r, c = cell
        for dr, dc in DIRECTIONS:
            nxt = (r + dr, c + dc)
            if nxt in self.open:
                yield nxt

    def _bfs(self, start, blocked=frozenset()):
        """Distances and parents from start, optionally routing around cells."""
        dist = {start: 0}
        prev = {}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            for nxt in self._neighbours(cell):
                if nxt in dist or (nxt in blocked and nxt != start):
                    continue
                dist[nxt] = dist[cell] + 1
                prev[nxt] = cell
                queue.append(nxt)
        return dist, prev

    def _first_step(self, start, goal, prev):
        """Walk the BFS parent chain back to the move that starts the path."""
        if goal == start or goal not in prev:
            return None
        cell = goal
        while prev[cell] != start:
            cell = prev[cell]
        return cell

    def _danger(self, radius=2):
        """Cells at or near an active ghost, which Pac-Man will route around."""
        blocked = set()
        for ghost in self.ghosts:
            if ghost.frightened or ghost.eaten:
                continue
            dist, _ = self._bfs(ghost.pos)
            blocked |= {cell for cell, d in dist.items() if d <= radius}
        return blocked

    # -- actors ------------------------------------------------------------

    def _move_pac(self):
        """Head for the nearest pellet, or the nearest edible ghost."""
        prey = [g for g in self.ghosts if g.frightened and not g.eaten]
        if prey:
            dist, prev = self._bfs(self.pac)
            reachable = [g for g in prey if g.pos in dist]
            if reachable:
                target = min(reachable, key=lambda g: dist[g.pos]).pos
                step = self._first_step(self.pac, target, prev)
                if step:
                    self._step_pac(step)
                    return

        # Prefer a route that keeps clear of the ghosts; relax it if the safe
        # region has no pellets left to reach.
        for radius in range(self.caution, -1, -1):
            blocked = self._danger(radius) if radius else frozenset()
            dist, prev = self._bfs(self.pac, blocked)
            targets = [p for p in self.pellets if p in dist and p != self.pac]
            if targets:
                target = min(targets, key=lambda p: dist[p])
                step = self._first_step(self.pac, target, prev)
                if step:
                    self._step_pac(step)
                    return

        # Cornered: take any neighbour that is not a ghost.
        options = [n for n in self._neighbours(self.pac)
                   if all(n != g.pos for g in self.ghosts)]
        if options:
            self._step_pac(self.rng.choice(options))

    def _step_pac(self, cell):
        self.pac_dir = (cell[0] - self.pac[0], cell[1] - self.pac[1])
        self.pac = cell
        if cell in self.pellets:
            self.pellets.discard(cell)
            self.score += 1
            if cell in self.power:
                self.power.discard(cell)
                self.fright = FRIGHT_FRAMES
                for ghost in self.ghosts:
                    if not ghost.eaten:
                        ghost.frightened = True

    def _ghost_target(self, ghost):
        if ghost.eaten:
            return ghost.home
        if not ghost.ambush:
            return self.pac
        # Aim three cells ahead of Pac-Man, falling back toward him if that
        # lands in a wall.
        for lead in (3, 2, 1, 0):
            cell = (self.pac[0] + self.pac_dir[0] * lead,
                    self.pac[1] + self.pac_dir[1] * lead)
            if cell in self.open:
                return cell
        return self.pac

    def _move_ghost(self, ghost):
        if ghost.eaten and ghost.pos == ghost.home:
            ghost.respawn -= 1
            if ghost.respawn <= 0:
                ghost.eaten = False
                ghost.frightened = False
            return

        if ghost.frightened and not ghost.eaten:
            # Flee: pick the neighbour that maximises distance from Pac-Man.
            dist, _ = self._bfs(self.pac)
            options = list(self._neighbours(ghost.pos))
            if options:
                ghost.pos = max(options, key=lambda n: dist.get(n, 0))
            return

        options = list(self._neighbours(ghost.pos))
        if options and self.rng.random() < GHOST_NOISE:
            # Wander instead of chasing, preferring not to double back.
            forward = [n for n in options
                       if (n[0] - ghost.pos[0], n[1] - ghost.pos[1]) != (-ghost.dir[0], -ghost.dir[1])]
            step = self.rng.choice(forward or options)
            ghost.dir = (step[0] - ghost.pos[0], step[1] - ghost.pos[1])
            ghost.pos = step
            return

        target = self._ghost_target(ghost)
        dist, prev = self._bfs(ghost.pos)
        if target in dist:
            step = self._first_step(ghost.pos, target, prev)
            if step:
                ghost.dir = (step[0] - ghost.pos[0], step[1] - ghost.pos[1])
                ghost.pos = step

    def _collide(self):
        """Resolve Pac-Man sharing a cell with a ghost."""
        for ghost in self.ghosts:
            if ghost.eaten or ghost.pos != self.pac:
                continue
            if ghost.frightened:
                ghost.eaten = True
                ghost.frightened = False
                ghost.respawn = 30
                self.score += 5
            else:
                self.lives -= 1
                self.state = "dying"
                self.timer = DEATH_PAUSE
                return

    # -- loop --------------------------------------------------------------

    def update(self):
        if self.state == "dying":
            self.timer -= 1
            if self.timer <= 0:
                if self.lives <= 0:
                    self.state = "over"
                    self.timer = END_PAUSE
                else:
                    self.state = "play"
                    self._place()
            return True

        if self.state in ("over", "won"):
            self.timer -= 1
            return self.timer > 0

        if self.fright > 0:
            self.fright -= 1
            if self.fright == 0:
                for ghost in self.ghosts:
                    ghost.frightened = False

        self.pac_tick += 1
        if self.pac_tick >= PAC_PERIOD:
            self.pac_tick = 0
            self._move_pac()
            self._collide()
            if self.state != "play":
                return True
            if not self.pellets:
                self.state = "won"
                self.timer = END_PAUSE
                return True

        self.ghost_tick += 1
        period = FRIGHT_PERIOD if self.fright > 0 else self.ghost_period
        if self.ghost_tick >= period:
            self.ghost_tick = 0
            for ghost in self.ghosts:
                self._move_ghost(ghost)
            self._collide()

        return True

    def render(self, frame):
        clear(frame)

        for r, line in enumerate(MAZE):
            for c, cell in enumerate(line):
                if cell == "#":
                    px(frame, r, c, WALL)

        for cell in self.pellets:
            px(frame, cell[0], cell[1], PELLET)

        # Power pellets pulse so they read differently from ordinary food.
        if (self.frames // 8) % 2 == 0:
            for cell in self.power:
                px(frame, cell[0], cell[1], WHITE)

        if self.state == "won":
            # Flash the walls on a completed board.
            if (self.timer // 5) % 2 == 0:
                for r, line in enumerate(MAZE):
                    for c, cell in enumerate(line):
                        if cell == "#":
                            px(frame, r, c, WHITE)
            return

        for ghost in self.ghosts:
            if ghost.eaten:
                px(frame, ghost.pos[0], ghost.pos[1], scale(CYAN, 0.35))
            elif ghost.frightened:
                # Blink white as the power pellet runs out.
                blink = self.fright < 60 and (self.fright // 5) % 2 == 0
                px(frame, ghost.pos[0], ghost.pos[1], WHITE if blink else FRIGHTENED)
            else:
                px(frame, ghost.pos[0], ghost.pos[1], ghost.color)

        if self.state == "dying":
            if (self.timer // 3) % 2 == 0:
                px(frame, self.pac[0], self.pac[1], scale(YELLOW, 0.4))
        elif self.state == "over":
            pass
        else:
            px(frame, self.pac[0], self.pac[1], YELLOW)
