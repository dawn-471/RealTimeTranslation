# -*- coding: utf-8 -*-
"""CLI entry point for MeetingTranscriber.

    python -m realtime_translation [options]
"""
from __future__ import annotations

import logging
import sys
import threading
import time

from .audio_capture import (
    LoopbackCapture,
    _pyaudio,
    list_input_devices,
    list_loopback_devices,
    validate_device_index,
)
from .asr_engine import StreamAsrEngine
from .config import Config, apply_cli, load_config, parse_args
from .pipeline import Pipeline
from .storage import TranscriptStorage
from .ui import SubtitlePanel

log = logging.getLogger(__name__)


def _print_devices() -> None:
    print("== 可用 loopback (系统输出/会议声音) 设备 ==")
    for idx, name in list_loopback_devices():
        print(f"  [{idx}] {name}")
    print("== 麦克风设备 ==")
    for idx, name in list_input_devices():
        print(f"  [{idx}] {name}")


def _pick_default_loopback() -> int:
    """Auto-select the loopback that mirrors the default output device.

    WASAPI loopback only delivers audio on the device that audio is actually
    played to. Match by the default output device's name.
    """
    pa = _pyaudio()
    try:
        default_out = pa.get_default_output_device_info()
        default_name = default_out.get("name", "")
        for idx, name in list_loopback_devices():
            if default_name and default_name[:20] in name:
                return idx
    except Exception as exc:
        log.warning("default output detection failed: %s", exc)
    finally:
        try:
            pa.terminate()
        except Exception:
            pass
    # fallback: first loopback device
    devices = list_loopback_devices()
    if not devices:
        raise RuntimeError(
            "未找到 WASAPI loopback 设备——请检查音频输出设备是否正常，"
            "或用 --list-devices 查看后 --device <index> 指定"
        )
    return devices[0][0]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config)
    cfg = apply_cli(cfg, args)

    if cfg.list_devices:
        _print_devices()
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # --- credentials (never hardcoded; first-run asks) ---
    from .credentials import CredentialsStore
    creds = CredentialsStore()

    if cfg.setup:
        from .setup import interactive_setup
        interactive_setup(creds, force=True)
        return 0

    # --- translator ---
    from .translator import create_translator
    try:
        translator = create_translator(cfg.translate, creds=creds)
    except Exception as exc:
        print(f"[warn] 翻译后端 {cfg.translate} 初始化失败: {exc} —— 降级为不翻译", file=sys.stderr)
        translator = create_translator("off", creds=creds)
        cfg.translate = "off"

    # --- capture ---
    if cfg.fake:
        from .fake_capture import FakeCapture
        capture = FakeCapture()
        print("[demo] fake 模式：使用合成音频流")
    else:
        device = cfg.device if cfg.device >= 0 else _pick_default_loopback()
        capture = LoopbackCapture(device)
        print(f"[info] 使用 loopback 设备 [{device}]")

    # --- engine & pipeline ---
    engine = StreamAsrEngine(model_dir=cfg.model_dir, num_threads=cfg.thread_nums)
    pipe = Pipeline(capture=capture, asr=engine, translator=translator)
    storage = TranscriptStorage(cfg.output_dir)
    pipe.subscribe(storage.append)

    if cfg.no_tui:
        panel = None
    else:
        panel = SubtitlePanel(backend_name=translator.name if translator else "off")
        pipe.subscribe(panel.on_entry)

    overlay = None
    if cfg.overlay:
        from .overlay import SubtitleOverlay
        overlay = SubtitleOverlay()
        pipe.subscribe(overlay.on_entry)
        overlay.start()
        print("[info] overlay 悬浮字幕已启动（T 切换译文 | 拖动可移动 | Q 退出）")

    # --- keyboard (pynput, non-admin) ---
    _toggle = panel.toggle_translation if panel else None
    _request_stop = panel.request_stop if panel else None
    overlay_ref = overlay

    if overlay_ref is not None:
        class _Both:
            def toggle(self):
                if panel:
                    panel.toggle_translation()
                overlay_ref.toggle_translation()

            def stop(self):
                if panel:
                    panel.request_stop()
                overlay_ref.request_stop()

        both = _Both()
        _toggle = both.toggle
        _request_stop = both.stop

    def on_key(key) -> None:
        try:
            ch = getattr(key, "char", None)
        except Exception:
            ch = None
        if ch == "t" and _toggle:
            _toggle()
        if ch == "q" and _request_stop:
            _request_stop()

    # --- Gemini Live voice chat (--talk): F2 push-to-talk ---
    voice = None
    if cfg.talk:
        if not creds.gemini_api_key:
            print("[warn] 未配置 Gemini API Key——`--setup` 配置后再启用语音对话", file=sys.stderr)
        else:
            from .talk import VoiceChat
            voice = VoiceChat(
                api_key=creds.gemini_api_key,
                model=creds.gemini_model,
                base_url=creds.gemini_base_url,
                on_transcript=lambda t: log.info("Live: %s", t),
                on_error=lambda e: log.warning("Live error: %s", e),
            )
            try:
                voice.start()
                print("[info] Gemini Live 已连接（按住 F2 说话，松开提交）")
            except Exception as exc:
                print(f"[warn] Gemini Live 连接失败: {exc} —— 语音对话不可用", file=sys.stderr)
                voice = None

    # mic feed for voice chat (uses input device[0] or --mic device)
    if voice is not None:
        def _voice_feed(chunk, frame):
            # 16-bit PCM LE from float32
            import numpy as np
            pcm = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
            voice.push_audio(pcm.tobytes())

        try:
            from .audio_capture import list_input_devices
            mics = list_input_devices()
            if mics:
                mic_cap = LoopbackCapture(mics[0][0])
                mic_cap.start(_voice_feed)
                print(f"[info] 语音对话麦克风: {mics[0][1]}")
            else:
                print("[warn] 未找到麦克风——语音对话无法使用", file=sys.stderr)
                voice = None
        except Exception as exc:
            print(f"[warn] 麦克风初始化失败: {exc}", file=sys.stderr)
            voice = None

    kb_thread = None
    try:
        from pynput import keyboard

        def _press(key) -> None:
            try:
                if key == keyboard.Key.f2:
                    if voice is not None:
                        voice.ptt.press()
            except Exception:
                pass

        def _release(key) -> None:
            try:
                if key == keyboard.Key.f2:
                    if voice is not None:
                        voice.ptt.release()
            except Exception:
                pass

        def _listen() -> None:
            with keyboard.Listener(on_press=on_key, on_release=_release) as listener:
                listener.join()

        kb_thread = threading.Thread(target=_listen, daemon=True)
        kb_thread.start()
    except Exception as exc:
        log.info("pynput 不可用(%s)——热键 T/Q 失效，Ctrl+C 退出", exc)

    print(f"[info] 转写保存 → {storage.path}")
    if panel:
        print("[info] 按 T 切换译文 | Q 退出")

    try:
        pipe.start()
        if panel:
            panel.run()
        else:
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[info] 停止并保存...")
        try:
            pipe.stop()
        except Exception as exc:
            log.warning("stop 失败: %s", exc)
        try:
            if voice is not None:
                voice.stop()
        except Exception as exc:
            log.warning("voice stop 失败: %s", exc)
        try:
            md_path = storage.save_markdown()
            print(f"[info] 已转写 {storage._count} 段 → {storage.path}")
            print(f"[info] Markdown → {md_path}")
        except Exception as exc:
            log.warning("保存失败: %s", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
