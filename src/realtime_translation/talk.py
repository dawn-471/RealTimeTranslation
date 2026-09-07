# -*- coding: utf-8 -*-
"""Realtime voice chat with Gemini Live (optional feature).

Architecture:
    mic (16k PCM LE) ──queue──> asyncio task ──send_realtime_input──> Gemini Live
                                                                      │
    speaker (24k PCM)  <──queue── asyncio task  <──receive──┘

P2T (push-to-talk) via a callback: the CLI hotkey listener sets
PushToTalk.active; only then is mic audio sent upstream.

Uses google.genai (live module). Model & endpoint come from CredentialsStore
— never hardcoded.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)


class PushToTalk:
    """Thread-safe P2T flag shared with the hotkey listener."""

    def __init__(self):
        self._active = threading.Event()
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self._active.is_set()

    def press(self) -> None:
        with self._lock:
            self._active.set()

    def release(self) -> None:
        with self._lock:
            self._active.clear()


class GeminiLiveSession:
    """Wraps one Live session; asyncio-native but startable from sync code."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        sample_rate_in: int = 16000,
        sample_rate_out: int = 24000,
        on_audio_out: Optional[Callable[[bytes], None]] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.sr_in = sample_rate_in
        self.sr_out = sample_rate_out
        self.on_audio_out = on_audio_out or (lambda b: None)
        self.on_transcript = on_transcript or (lambda t: None)
        self._session = None
        self._client = None

    async def connect(self) -> None:
        from google import genai
        client = genai.Client(api_key=self.api_key, http_options={"base_url": self.base_url})
        self._client = client
        live = client.live.connect(model=self.model)
        self._session = live

    async def send_audio(self, pcm_le: bytes) -> None:
        if self._session is None:
            return
        await self._session.send_realtime_input(audio=pcm_le)

    async def receive_loop(self, stop: asyncio.Event) -> None:
        """Read server audio until stop; dispatch to on_audio_out/on_transcript."""
        if self._session is None:
            return
        async for response in self._session.receive():
            if stop.is_set():
                break
            # response.model_dump() shape: {'serverContent': {'modelTurn': {'parts': [...]}}}
            try:
                r = response.model_dump()
            except Exception:
                continue
            server = r.get("serverContent") or {}
            turn = server.get("modelTurn") or {}
            for part in turn.get("parts") or []:
                inline = part.get("inlineData")
                if inline and inline.get("data"):
                    import base64
                    self.on_audio_out(base64.b64decode(inline["data"]))
                if part.get("text"):
                    self.on_transcript(part["text"])

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


class VoiceChat:
    """Sync facade: run the Live session in an asyncio loop (its own thread)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        on_audio_out: Optional[Callable[[bytes], None]] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        self.session = GeminiLiveSession(api_key, model, base_url,
                                         on_audio_out=on_audio_out,
                                         on_transcript=on_transcript)
        self.ptt = PushToTalk()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop = asyncio.Event()
        self._thread: Optional[threading.Thread] = None
        self._in_q: "queue.Queue[bytes]" = queue.Queue()
        self._ready = threading.Event()
        self._running = False
        self.on_error = on_error or (lambda e: log.warning("live error: %s", e))

    def start(self) -> None:
        """Start the asyncio thread; blocks until connected (or raises)."""
        if self._running:
            return
        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="gemini-live")
        self._thread.start()
        if not self._ready.wait(timeout=30.0):
            raise TimeoutError("Gemini Live connection timeout (check key/proxy)")

    def _run_loop(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        self._stop = asyncio.Event()
        try:
            await self.session.connect()
        except Exception as exc:
            self.on_error(exc)
            self._ready.set()
            return
        self._ready.set()
        sender = asyncio.create_task(self._send_loop())
        receiver = asyncio.create_task(self.session.receive_loop(self._stop))
        await self._stop.wait()
        await self.session.close()
        sender.cancel()
        receiver.cancel()

    async def _send_loop(self) -> None:
        while not self._stop.is_set():
            try:
                pcm = self._in_q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.02)
                continue
            if not self.ptt.active:
                continue
            try:
                await self.session.send_audio(pcm)
            except Exception as exc:
                self.on_error(exc)

    def push_audio(self, pcm_le: bytes) -> None:
        if self._running:
            self._in_q.put(pcm_le)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._loop and self._thread:
            try:
                self._loop.call_soon_threadsafe(self._stop.set)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5.0)
