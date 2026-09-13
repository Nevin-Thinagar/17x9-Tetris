"""Display that streams frames to the Green Building simulator over HTTP.

The simulator accepts one frame per POST to /api/i/<instance>/frame, as JSON
shaped 17 rows x 9 columns x [r, g, b] -- the same row-major layout as Frame,
so no transposing is needed.

Posting synchronously from the game loop would tie the frame rate to the round
trip: a 60 ms request would halve 30 FPS. Instead send() serialises the frame
on the caller's thread (cheap, and it has to happen before the caller mutates
the frame again) and hands the bytes to a background sender holding a single
slot. If the network cannot keep up, older frames are dropped rather than
queued, which is the right behaviour for a live display -- a stale frame is
worth less than the current one.

Uses only the standard library, so nothing extra needs installing.
"""

import http.client
import json
import threading
import urllib.parse

from utilities.display import Display, Frame

DEFAULT_API = "https://sundai.willsarg.com/api"


class WebDisplay(Display):
    """Streams frames to a simulator instance.

    Implements the same makeframe()/send() contract as DummyDisplay, so games
    do not change between the local window and the building.
    """

    def __init__(self, instance, base_url=DEFAULT_API, timeout=3.0):
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.netloc:
            raise ValueError(f"base_url must be absolute, got {base_url!r}")
        self._secure = parsed.scheme != "http"
        self._host = parsed.netloc
        self._path = f"{parsed.path.rstrip('/')}/i/{instance}/frame"
        self._timeout = timeout

        self._conn = None
        self._cond = threading.Condition()
        self._pending = None
        self._closed = False

        # Counters, so a caller can report what actually reached the display.
        self.sent = 0
        self.dropped = 0
        self.errors = 0
        self.last_error = None

        self._thread = threading.Thread(
            target=self._worker, name="webdisplay", daemon=True
        )
        self._thread.start()

    def makeframe(self):
        return Frame()

    def send(self, frame):
        """Queue a frame. Returns immediately; the POST happens off-thread."""
        body = json.dumps(
            [[[c.r, c.g, c.b] for c in row] for row in frame.asarray()]
        ).encode("ascii")
        with self._cond:
            if self._pending is not None:
                # The sender has not caught up; the newer frame wins.
                self.dropped += 1
            self._pending = body
            self._cond.notify()

    def close(self):
        """Stop the sender thread and drop the connection."""
        with self._cond:
            self._closed = True
            self._cond.notify()
        self._thread.join(timeout=2.0)
        self._disconnect()

    # -- internals ---------------------------------------------------------

    def _connect(self):
        cls = http.client.HTTPSConnection if self._secure else http.client.HTTPConnection
        return cls(self._host, timeout=self._timeout)

    def _disconnect(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None

    def _worker(self):
        while True:
            with self._cond:
                while self._pending is None and not self._closed:
                    self._cond.wait()
                if self._pending is None:
                    return
                body = self._pending
                self._pending = None
            self._post(body)

    def _post(self, body):
        """POST one frame, reconnecting once if the kept-alive socket died."""
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        for final in (False, True):
            try:
                if self._conn is None:
                    self._conn = self._connect()
                self._conn.request("POST", self._path, body, headers)
                response = self._conn.getresponse()
                # Drain the body so the connection can be reused.
                payload = response.read()
                if response.status >= 400:
                    self.errors += 1
                    self.last_error = f"HTTP {response.status}: {payload[:200]!r}"
                    self._disconnect()
                else:
                    self.sent += 1
                return
            except (OSError, http.client.HTTPException) as exc:
                self._disconnect()
                if final:
                    self.errors += 1
                    self.last_error = f"{type(exc).__name__}: {exc}"
