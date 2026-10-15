"""Run async code from Streamlit (D-17, architecture §10).

Streamlit reruns its script synchronously. Calling asyncio.run() on each rerun
creates and closes a new event loop every time, which breaks async clients
(httpx, ChatOpenAI) created on an earlier loop. Instead, one background thread
runs a single long-lived loop for the whole app process; `run` submits a
coroutine to it and waits for the result.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class AsyncRunner:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, name="finnie-async", daemon=True)
        self._thread.start()

    def run(self, coro: Coroutine[Any, Any, T], timeout: float | None = 120) -> T:
        """Run `coro` on the background loop and return its result (or raise its error)."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)
