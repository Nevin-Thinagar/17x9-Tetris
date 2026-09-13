"""Attract-mode loop for the 9x17 display.

Cycles Pong, the dinosaur runner, Pac-Man and Mario, each playing itself, with
a short wipe between segments. Nothing here reads input: this is built to run
unattended on the Green Building facade or its simulator.

    python arcade.py                  # loop all four on the pygame window
    python arcade.py --game pacman    # one game, on repeat
    python arcade.py --once           # one pass through the loop, then exit
    python arcade.py --display web --instance <slug>

The frame rate is capped at 30 fps by sleeping, not by spinning: the display
contract in the README is that send() must not be called more than once every
0.033 seconds.
"""

import argparse
import random
import sys
import time

import pygame

from games import ALL, GAMES
from games.base import lerp
from utilities.display import Frame

FPS = 30
FRAME_SECONDS = 1.0 / FPS
WIPE_FRAMES = 10


class FrameClock:
    """Paces the loop at a fixed frame rate without burning a core.

    Tracks the ideal next-frame deadline rather than sleeping a fixed amount,
    so a slow frame does not push every later frame back.
    """

    def __init__(self, fps=FPS):
        self.period = 1.0 / fps
        self.next_frame = time.perf_counter()

    def tick(self):
        self.next_frame += self.period
        delay = self.next_frame - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            # Fell behind; give up on catching up rather than sprinting.
            self.next_frame = time.perf_counter()


def copy_frame(src):
    """Snapshot a frame so it survives the next render pass."""
    out = Frame(rows=src.nrows(), cols=src.ncols())
    out.asarray()[:] = src.asarray()
    return out


def should_quit():
    """Drain the pygame event queue, reporting a window close or Esc.

    The web display never opens a pygame window, and polling events with the
    video system uninitialised raises, so there is nothing to drain there.
    """
    if not pygame.display.get_init():
        return False
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return True
    return False


def wipe(display, old, new, clock):
    """Dissolve from one frame to another, top rows first."""
    blend = Frame(rows=old.nrows(), cols=old.ncols())
    for step in range(1, WIPE_FRAMES + 1):
        cut = old.nrows() * step / WIPE_FRAMES
        for r in range(old.nrows()):
            # Rows above the moving edge are fully swapped; the edge row
            # itself is a partial blend, which softens the sweep.
            t = max(0.0, min(1.0, cut - r))
            for c in range(old.ncols()):
                blend[r, c] = lerp(old[r][c], new[r][c], t)
        display.send(blend)
        clock.tick()
        if should_quit():
            return True
    return False


def build_display(kind, scale, instance, url):
    """Create the output device.

    Both back ends implement the same makeframe()/send() contract, so the
    games are identical between the local pygame window and the building.
    """
    if kind == "dummy":
        from utilities.dummy import DummyDisplay

        return DummyDisplay(scalar=scale)

    if not instance:
        sys.exit("--display web needs --instance <slug> (create one on the simulator)")

    from utilities.web import WebDisplay

    return WebDisplay(instance, url)


def select_games(name):
    """The rotation, or a single segment by name.

    Named lookup covers ALL, not just the rotation, so segments that are built
    but held out of the loop stay runnable on their own.
    """
    if not name:
        return list(GAMES)
    matches = [g for g in ALL if g.name == name]
    if not matches:
        sys.exit(f"unknown game {name!r}; choose from: {', '.join(g.name for g in ALL)}")
    return matches


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", help="run only this game, on repeat")
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    parser.add_argument("--seed", type=int, help="fix the RNG for a repeatable run")
    parser.add_argument("--display", choices=["dummy", "web"], default="dummy")
    parser.add_argument("--scale", type=int, default=40, help="pygame window cell size")
    parser.add_argument("--instance", help="simulator instance slug")
    parser.add_argument(
        "--url",
        default="https://sundai.willsarg.com/api",
        help="simulator API base url",
    )
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    display = build_display(args.display, args.scale, args.instance, args.url)
    clock = FrameClock()
    games = select_games(args.game)

    frame = display.makeframe()
    previous = None
    quitting = False

    try:
        while not quitting:
            for game_cls in games:
                game = game_cls(rng)
                game.reset()
                game.render(frame)

                if previous is not None:
                    if wipe(display, previous, copy_frame(frame), clock):
                        quitting = True
                        break

                print(f"[arcade] {game.name}")
                while True:
                    alive = game.step()
                    game.render(frame)
                    display.send(frame)
                    clock.tick()
                    if should_quit():
                        quitting = True
                        break
                    if not alive:
                        break

                if quitting:
                    break
                previous = copy_frame(frame)

            if args.once:
                break
    except KeyboardInterrupt:
        pass
    finally:
        display.send(Frame())  # Leave the display dark.
        if hasattr(display, "close"):
            if display.errors:
                print(f"[arcade] {display.errors} send errors, "
                      f"last: {display.last_error}")
            print(f"[arcade] {display.sent} frames delivered, "
                  f"{display.dropped} dropped")
            display.close()
        pygame.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
