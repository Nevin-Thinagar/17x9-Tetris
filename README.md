# 17 x 9 Tetris
Tetris! But on a 17 x 9 grid, what an odd choice...

This game was put together in a relatively short amount of time to hit a deadline for this project. It works decently and is still fun to play, but I think there is still room for improvement both aesthetically and in terms of gameplay. Anything in the `tetris.py` and `input_manager.py` file can be changed without impacting the overall functionality of the system. Things in the other utilities can be changed as well, but this will require restructuring other parts of the system and is not the prefered method of improving the game. However, if there is a significant improvement by restructuring those systems, go for it and make a pull request!

I'm hoping that by making this public, people can play around with it, see how the system works, and overall improve the whole system! Maybe you'll even be inspired to make your own game for this kind of display! (Please feel free to do this as well! You can just reuse the display and dummy classes)

## Arcade loop

`arcade.py` runs an attract-mode loop on the same 17 x 9 display: Atari Pong,
the Chrome dinosaur, Pac-Man, a Mario-style platformer and Spacewar!, then a
colour-ripple wind-down, closing each pass with the Sundai logo and the MIT
wordmark. Nothing reads input — each segment drives itself, so the loop can run
unattended on the facade or the simulator.

```
python arcade.py                   # loop all four in the pygame window
python arcade.py --game pacman     # one game, on repeat
python arcade.py --once            # a single pass, then exit
python arcade.py --seed 42         # repeatable run
```

Each segment lives in `games/` and subclasses `MiniGame` (`reset`, `update`,
`render`), built on the existing `Frame` / `Color` primitives, so adding
another is a single file plus an entry in `games/__init__.py`. The portrait
grid drives the designs: Pong is rotated 90 degrees so the paddles run across
the top and bottom, the dinosaur uses the bottom strip with the sky above it
for the score, Pac-Man gets a purpose-drawn 9 x 17 maze, and Mario's ground
climbs in jumpable steps instead of staying flat.

`spacewar` reproduces the 1962 PDP-1 original's orbital duel, not its aiming.
The gravity constant is tuned so orbits stay bounded between radius 2.5 and 4 —
wider than 4 runs out of the nine-column field — and ships launch onto
eccentric orbits down the tall axis, which trace about forty distinct windows.
Ships carry a decaying trail, without which the gravity well is invisible and a
ship is just a dot wandering. One window has no orientation, so heading is
shown as a dimmer nose cell, giving eight headings against the original's
thousand. Torpedoes ignore gravity, as they did in 1962.

`ripple` is ambient: expanding colour rings over a drifting background wash,
cycling through four palettes. Rings accumulate into a floating-point RGB
buffer that is resolved once per frame, so crossing rings sum into new colours
rather than overpainting each other. Summed rings routinely exceed 255, and
hard clipping turns every overloaded cell flat white — once all three channels
clip the hue is gone — so channels above a knee are rolled off instead, which
keeps a hot overlap recognisably pink or cyan. It is the most expensive segment
at 0.7 ms/frame, still around 2% of the frame budget.

`sundai` and `mit` are the outro rather than games. The Sundai logo wipes in
from the base, the brand gradient drifts across the glass, then it fades; the
artwork and its seven gradient stops are taken from the simulator's own
`sundai-reveal` demo frames, so it matches the brand exactly rather than
approximating it. The MIT logo follows, shown whole and still. Its five bars
need one-column gaps to stay distinct, which comes to exactly nine columns —
sampled any smaller the bars merge into a solid block, any larger and it no
longer fits — so the mark lands on the display's width exactly and needs only
six of its seventeen rows. The bitmap was sampled from the official logo on
brand.mit.edu and is shared with `utilities/mit_logo.py`, which offers the same
logo as a startup screen for `tetris.py` via `show_mit_logo(display)`.

`games/electro.py` is built but held out of the rotation — `GAMES` is the loop,
`EXTRAS` is everything else, and `--game <name>` can still run either.

Unlike `tetris.py`, the loop paces itself by sleeping to a frame deadline
rather than busy-waiting, so it holds 30 FPS (measured mean 33.3 ms/frame)
without pinning a core.

Dependencies: `pip install pygame numpy`.

### Running it on the Green Building simulator

The simulator at <https://sundai.willsarg.com/> renders the same 9 x 17 window
grid. Create an instance there (needs the event password), then:

```
python arcade.py --display web --instance <slug>
```

`utilities/web.py` implements `Display` against the simulator's HTTP API —
one frame per POST to `/api/i/<slug>/frame`, as JSON shaped 17 rows x 9 x
`[r, g, b]`. It is standard library only, so `gbsim` is not required. The
simulator's frame buffer is indexed `(row * 9 + col) * 3`, the same row-major
order as `Frame`, so frames map across with no transpose.

Frames are posted from a background thread holding a single slot: `send()`
serialises and returns immediately, and if the network falls behind, the older
frame is dropped rather than queued, since a stale frame is worth less than the
current one. The game loop keeps simulating at a true 30 FPS either way, so
gameplay timing is unaffected by the link.

Expect some drops over the public internet. Measured warm round trip to the
simulator was mean 39 ms (p50 28 ms, p95 109 ms) against a 33 ms frame budget,
which delivered 520 of 705 frames on a dino run — smooth to watch, but not
every frame arrives. `arcade.py` prints the delivered/dropped counts on exit.

## Things that need to be fixed
- Game loop is not performant
- Better line clear and game over animations
- Auto-repeat inputs are cancelled when a different key is pressed
- More to be added as I think of them...

## Things that need to be added
- Lock delay
- Color change on level up
- Second window with next pieces, hold piece, score, level, and timer
- More accurate scoring
- High score tracking (partially implemented, needs visual on second window)
- Pausing the game
- Change handling and keybinds while in-game
- Scroll score after game over
- More to be added as I think of them...

## Other notes
- If you forked this repo before the most recent commit to fix the bug with the `_playing` variable not being initialized, you will have to pull again
- The `Display.send()` function should be called *at most* at 30 FPS (i.e. Once every 0.033 seconds). The send command might get smarter at some point to handle faster send commands, but currently it is up to the game to limit the frame rate

Feel free to add any other features that you think would be useful even if they're not listed here! Just make a PR :)

Disclaimer: *This is a personal educational project and is not affiliated with, sponsored by, or endorsed by The Tetris Company*
