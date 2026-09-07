# RealTimeTranslation

[English](README.en.md) | [中文](README.md)

Real-time transcription of system audio (Tencent Meeting, videos, live
streams — anything playing on the speakers) with **live CN/EN subtitles**,
bidirectional translation, and optional Gemini Live voice chat.

- ASR: sherpa-onnx streaming (Paraformer bilingual zh-en, CPU int8, no GPU needed)
- Translation: DeepSeek API (default) / local Ollama / off — **press `T` to toggle subtitles**
- UI: terminal subtitle panel (rich) / desktop floating overlay (tkinter, always-on-top)
- Voice chat: `--talk` integrates Gemini Live (hold `F2` to speak, release to submit)
- Privacy & security: **zero hardcoded API keys/URLs** — first-run interactive setup
  stores them in `%APPDATA%\RealTimeTranslation\config.yaml`
  (Linux: `~/.config/RealTimeTranslation/`); audio stays local

## Install

```bash
uv sync
uv run python scripts/download_models.py   # download ASR model (or place in models/)
```

Requires: Windows 11, Python ≥ 3.12, uv.

## First-run credential setup

```bash
uv run python -m realtime_translation --setup
```

Interactively asks for DeepSeek and Gemini API endpoints & keys (press Enter to
skip what you don't need). Re-run `--setup` (force) to reconfigure.
Keys are **never** written to the code, README, or git.

## Run

```bash
# List available audio devices
uv run python -m realtime_translation --list-devices

# Default run (auto-picks the loopback of your default output device)
uv run python -m realtime_translation

# Floating overlay + your own microphone
uv run python -m realtime_translation --overlay --mic

# No translation, transcription only
uv run python -m realtime_translation --translate off

# Gemini Live realtime voice chat (hold F2 to speak)
uv run python -m realtime_translation --talk
```

## Hotkeys

| Key | Function |
|---|---|
| `T` | Toggle translation |
| `F2` | Push-to-talk (with `--talk`) |
| `Q` / `Ctrl+C` | Quit (auto-saves transcript) |

## Translation backends

| Value | Description |
|---|---|
| `deepseek` | Default. Key from `--setup` config (or env `DEEPSEEK_API_KEY`), ~1-2s/sentence |
| `ollama` | Local, zero egress. Requires a local Ollama model (e.g. `mttranslate`) |
| `off` | Transcription only |

> Note: a local 3B Ollama model translates a sentence in ~6s and may emit
> auxiliary explanatory text (needs a 128-token cap), so DeepSeek is the
> recommended default.

## CN/EN detection & translation

- Recognition: Paraformer bilingual model natively handles mixed CN/EN
  (e.g. "这个 model 的 performance 很好")
- Direction: CJK ratio ≥ 15% → Chinese → translate to English; else → English → Chinese
- Segmentation: WASAPI silence detection (1.2s cutoff, tunable)

## Project layout

```
src/realtime_translation/
  audio_capture.py   # WASAPI loopback capture
  asr_engine.py      # streaming ASR wrapper (partial/final events)
  lang_dir.py        # CN/EN direction detection
  translator.py      # DeepSeek / Ollama backends
  pipeline.py        # capture -> ASR -> translate pipeline
  ui.py              # rich subtitle panel
  overlay.py         # tkinter floating subtitle window
  storage.py         # JSONL + Markdown persistence
  talk.py            # Gemini Live voice chat (P2T)
  credentials.py     # credential store (zero hardcoding)
  setup.py           # first-run interactive config
  __main__.py        # CLI
```

## Privacy

- Audio never leaves the machine (WASAPI loopback capture, local sherpa-onnx inference)
- The default `deepseek` backend sends **transcript text** to the DeepSeek API for translation
- `--translate off` or `ollama` backend = zero egress
- API keys/URLs live only in the data-dir config (`%APPDATA%\RealTimeTranslation\config.yaml`);
  never in code, never printed, never in git

## Known limitations

- Loopback captures speaker output only (the *other* party in a meeting);
  use `--mic` for your own voice
- Mixed-sentence translation direction uses a character-ratio heuristic;
  edge cases (names inside English) may misfire
- Local Ollama 3B translation is ~6s/sentence — not realtime-friendly
- Windows-only (WASAPI loopback)

## License

MIT
