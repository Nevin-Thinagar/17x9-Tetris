"""Atari Pong, rotated for a 9x17 portrait display.

The original is a landscape game: paddles left and right, ball crossing a wide
field. On a nine-column tower that would leave a two-column rally, so the whole
board is turned 90 degrees. Paddles run horizontally across the top and bottom,
the ball travels the long axis of the building, and each side's score is shown
as a row of pips on the outermost row.
"""

from games.base import (
    BLACK,
    CYAN,
    DIM,
    MiniGame,
    ORANGE,
    WHITE,
    clear,
    hline,
    px,
    scale,
)

PADDLE_WIDTH = 3
# Paddles sit one row inside the score rows. Without that gap the pips on
# rows 0 and 16 touch the paddles and read as one ragged shape.
TOP_ROW = 2
BOTTOM_ROW = 14
NET_ROW = 8
WIN_SCORE = 4

# Frames to hold the field still after a point, so the miss is readable.
SCORE_PAUSE = 24
# Frames to hold the final score before handing the loop to the next game.
END_PAUSE = 50


class Paddle:
    """One AI-driven paddle.

    skill is the fraction of the gap to the predicted ball column that the
    paddle closes each frame; miss_chance is how often it deliberately aims
    at the wrong spot so that points actually get scored.
    """

    def __init__(self, row, color, skill, miss_chance, rng):
        self.row = row
        self.color = color
        self.skill = skill
        self.miss_chance = miss_chance
        self.rng = rng
        self.col = (9 - PADDLE_WIDTH) / 2
        self.target = self.col
        self.score = 0
        self.error = 0.0
        self.traverse = -1

    def center(self):
        return self.col + PADDLE_WIDTH / 2

    def covers(self, col):
        """True if the paddle spans the given column."""
        return self.col - 0.5 <= col <= self.col + PADDLE_WIDTH - 0.5

    def retarget(self, predicted_col, traverse):
        """Aim at a predicted column, sometimes badly on purpose.

        The aiming error is rolled once per traverse and then reused. The
        prediction is recomputed every time the ball bounces off a side wall,
        and re-rolling here would let a later bounce silently correct a miss
        the paddle had already committed to -- which is why rallies used to
        run forever.
        """
        if traverse != self.traverse:
            self.traverse = traverse
            if self.rng.random() < self.miss_chance:
                # Aim far enough off to miss, but stay on the board.
                self.error = self.rng.choice([-1, 1]) * self.rng.uniform(2.0, 3.5)
            else:
                self.error = self.rng.uniform(-0.4, 0.4)
        predicted_col += self.error
        self.target = max(0.0, min(9.0 - PADDLE_WIDTH, predicted_col - PADDLE_WIDTH / 2))

    def update(self):
        """Ease toward the current target."""
        self.col += (self.target - self.col) * self.skill
        self.col = max(0.0, min(9.0 - PADDLE_WIDTH, self.col))


class Pong(MiniGame):
    """First to five, played by two slightly fallible AI paddles."""

    name = "pong"
    max_frames = 30 * 75

    def reset(self):
        self.top = Paddle(TOP_ROW, CYAN, skill=0.30, miss_chance=0.30, rng=self.rng)
        self.bottom = Paddle(BOTTOM_ROW, ORANGE, skill=0.30, miss_chance=0.30, rng=self.rng)
        self.state = "rally"
        self.timer = 0
        self.flash = 0
        self.traverse = 0
        self._serve(self.rng.choice([-1, 1]))

    def _serve(self, direction):
        """Put the ball back in play travelling toward direction (-1 up, +1 down)."""
        self.ball_r = NET_ROW
        self.ball_c = self.rng.uniform(2.0, 6.0)
        self.speed = 0.30
        self.traverse += 1
        self.vr = self.speed * direction
        self.vc = self.speed * self.rng.uniform(-0.7, 0.7)
        self._predict()

    def _predict(self):
        """Tell whichever paddle the ball is heading for where to wait.

        Walks the ball forward analytically, folding it off the side walls,
        so the paddles play like they can read the trajectory.
        """
        if self.vr == 0:
            return
        target_row = self.top.row if self.vr < 0 else self.bottom.row
        steps = (target_row - self.ball_r) / self.vr
        if steps < 0:
            return
        landing = self.ball_c + self.vc * steps

        # Reflect the landing column back into 0..8 as many times as needed.
        span = 8.0
        landing = abs(landing)
        landing %= 2 * span
        if landing > span:
            landing = 2 * span - landing

        paddle = self.top if self.vr < 0 else self.bottom
        paddle.retarget(landing, self.traverse)

    def _bounce_off(self, paddle):
        """Reflect the ball off a paddle, angling it by where it struck."""
        offset = (self.ball_c - paddle.center()) / (PADDLE_WIDTH / 2)
        self.speed = min(0.44, self.speed * 1.06)
        self.traverse += 1
        self.vr = -self.vr
        self.vr = self.speed if self.vr > 0 else -self.speed
        self.vc = self.speed * offset * 0.9
        self.ball_r = paddle.row + (1 if self.vr > 0 else -1)
        self.flash = 3
        self._predict()

    def _point_to(self, winner, loser):
        winner.score += 1
        self.state = "scored"
        self.timer = SCORE_PAUSE
        self._serve_direction = 1 if loser is self.bottom else -1

    def update(self):
        if self.flash > 0:
            self.flash -= 1

        if self.state == "scored":
            self.timer -= 1
            if self.timer <= 0:
                if self.top.score >= WIN_SCORE or self.bottom.score >= WIN_SCORE:
                    self.state = "over"
                    self.timer = END_PAUSE
                else:
                    self.state = "rally"
                    self._serve(self._serve_direction)
            return True

        if self.state == "over":
            self.timer -= 1
            return self.timer > 0

        self.top.update()
        self.bottom.update()

        self.ball_r += self.vr
        self.ball_c += self.vc

        # Side walls.
        if self.ball_c < 0:
            self.ball_c = -self.ball_c
            self.vc = -self.vc
            self._predict()
        elif self.ball_c > 8:
            self.ball_c = 16 - self.ball_c
            self.vc = -self.vc
            self._predict()

        # Paddles.
        if self.vr < 0 and self.ball_r <= self.top.row:
            if self.top.covers(self.ball_c):
                self._bounce_off(self.top)
            elif self.ball_r < 0:
                self._point_to(self.bottom, self.top)
        elif self.vr > 0 and self.ball_r >= self.bottom.row:
            if self.bottom.covers(self.ball_c):
                self._bounce_off(self.bottom)
            elif self.ball_r > 16:
                self._point_to(self.top, self.bottom)

        return True

    def _draw_score(self, frame, row, score, color):
        """Score pips, centred on the outermost row of that side.

        Dimmed relative to the paddle so the two never read as one shape.
        """
        pip = scale(color, 0.45)
        start = (frame.ncols() - (score * 2 - 1)) // 2 if score else 0
        for i in range(score):
            px(frame, row, start + i * 2, pip)

    def render(self, frame):
        clear(frame)

        # Dashed centre net.
        for col in range(0, frame.ncols(), 2):
            px(frame, NET_ROW, col, DIM)

        for paddle in (self.top, self.bottom):
            hline(frame, paddle.row, round(paddle.col), PADDLE_WIDTH, paddle.color)

        self._draw_score(frame, 0, self.top.score, self.top.color)
        self._draw_score(frame, 16, self.bottom.score, self.bottom.color)

        if self.state == "rally":
            px(frame, round(self.ball_r), round(self.ball_c), WHITE if not self.flash else CYAN)
        elif self.state == "scored":
            # Flash the scoring side's paddle row while the field is frozen.
            if (self.timer // 4) % 2 == 0:
                winner = self.top if self._serve_direction == -1 else self.bottom
                hline(frame, winner.row, round(winner.col), PADDLE_WIDTH, WHITE)
        else:
            winner = self.top if self.top.score > self.bottom.score else self.bottom
            if (self.timer // 5) % 2 == 0:
                hline(frame, winner.row, 0, frame.ncols(), winner.color)
