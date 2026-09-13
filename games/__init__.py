"""Autonomous mini-games for the 9x17 Green Building display.

Each module exposes a MiniGame subclass that plays itself, so the whole
package can be run as an attract-mode loop by arcade.py.
"""

from games.base import MiniGame
from games.pong import Pong
from games.dino import Dino
from games.pacman import PacMan
from games.mario import Mario
from games.spacewar import Spacewar
from games.ripple import Ripple
from games.sundai import Sundai
from games.mit import MIT
from games.electro import Electro

#: The attract-mode rotation, in order. Ripple winds down out of the games,
#: then the Sundai logo and the MIT wordmark close every pass.
GAMES = [Pong, Dino, PacMan, Mario, Spacewar, Ripple, Sundai, MIT]

#: Built but not in rotation. Still selectable with `arcade.py --game <name>`.
EXTRAS = [Electro]

#: Everything runnable by name.
ALL = GAMES + EXTRAS

__all__ = [
    "MiniGame",
    "Pong",
    "Dino",
    "PacMan",
    "Mario",
    "Spacewar",
    "Ripple",
    "Sundai",
    "MIT",
    "Electro",
    "GAMES",
    "EXTRAS",
    "ALL",
]
