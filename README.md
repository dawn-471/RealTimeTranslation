# RealTimeTranslation

实时监听系统音频（腾讯会议 PC 版、视频、直播等任意应用的扬声器输出），
像视频字幕一样**边听边出字**的转写 + 中英互译工具，可选集成 Gemini Live 实时语音对话。

- 转写：sherpa-onnx 流式识别（Paraformer 中英双语，纯 CPU，无 GPU 依赖）
- 翻译：DeepSeek API（默认）/ 本地 Ollama / 关闭，**运行时按 T 键开关译文**
- 界面：终端字幕面板（rich）/ 桌面悬浮字幕窗（tkinter，置顶半透明）
- 语音对话：`--talk` 集成 Gemini Live（按住 F2 说话，松开提交）
- 隐私与安全：**API Key/URL 零硬编码**——首次启动交互询问，保存于 `%APPDATA%\RealTimeTranslation\config.yaml`（Linux: `~/.config/RealTimeTranslation/`）；音频全程本地

## 安装

```bash
uv sync
uv run python scripts/download_models.py   # 下载 ASR 模型（或手动放置到 models/）
```

依赖：Windows 11、Python ≥ 3.12、uv。

## 首次配置（凭据）

```bash
uv run python -m realtime_translation --setup
```

交互式询问 DeepSeek 与 Gemini 的 API 地址与 Key（可回车跳过不用）。
已配置后重新运行可 `--setup`（force）重配。Key 永不写入代码/README。

## 运行

```bash
# 查看可用音频设备
uv run python -m realtime_translation --list-devices

# 默认运行（自动选取默认输出设备的 loopback）
uv run python -m realtime_translation

# 悬浮字幕窗 + 自己的麦克风
uv run python -m realtime_translation --overlay --mic

# 关闭翻译，仅转写
uv run python -m realtime_translation --translate off

# 启用 Gemini Live 实时语音对话（按住 F2 说话）
uv run python -m realtime_translation --talk
```

## 热键

| 键 | 功能 |
|---|---|
| `T` | 开关译文显示 |
| `F2` | 按住说话（仅 `--talk`） |
| `Q` / `Ctrl+C` | 退出（自动保存转写） |

## 翻译后端

| 值 | 说明 |
|---|---|
| `deepseek` | 默认。Key 来自 `--setup` 配置（或环境变量 `DEEPSEEK_API_KEY`），~1-2s/句 |
| `ollama` | 本地零外发。需 Ollama 本地模型（如 `mttranslate`） |
| `off` | 纯转写，不翻译 |

> 注：本地 Ollama 3B 模型单句翻译实测约 6s（辅助输出会干扰，需 128 token 截断），
> 因此默认推荐 DeepSeek。

## 中英识别与互译

- 识别：Paraformer 中英双语模型原生支持中英混合（如"这个 model 的 performance 很好"）
- 翻译方向：汉字占比 ≥ 15% 判为中文 → 译英；否则译英 → 译中
- 分段：WASAPI 静音检测（1.2s 静音切段，参数可配置）

## 项目结构

```
src/realtime_translation/
  audio_capture.py   # WASAPI loopback 采集
  asr_engine.py      # stream ASR 封装（partial/final 事件）
  lang_dir.py        # 中英方向检测
  translator.py      # DeepSeek / Ollama 后端
  pipeline.py        # 采集→识别→翻译 流水线
  ui.py              # rich 字幕面板
  overlay.py         # tkinter 悬浮字幕窗
  storage.py         # JSONL + Markdown 保存
  talk.py            # Gemini Live 语音对话（P2T）
  credentials.py     # 凭据存储（零硬编码）
  setup.py           # 首次启动交互配置
  __main__.py        # CLI
```

## 隐私说明

- 音频绝不外发（WASAPI loopback 本地采集，sherpa-onnx 本地推理）
- 默认 `deepseek` 后端会把转写文本发送至 DeepSeek 官方 API 进行翻译
- `--translate off` 或 `ollama` 后端时零外发
- API Key/URL 仅存于数据目录配置（`%APPDATA%\RealTimeTranslation\config.yaml`），
  不写入代码、不打印、不入 git

## 已知限制

- loopback 只捕获扬声器输出（会议中**对方**的声音）；自己说话需 `--mic`
- 中英混合句的翻译方向采用字符统计规则，边缘情况（专名夹杂）可能误判
- 本地 Ollama 翻译（3B 模型）单句约 6s，实时性不如 DeepSeek
- 本项目为 Windows 专用（WASAPI loopback）

## License

MIT
