# -*- coding: utf-8 -*-
"""Configuration: dataclass defaults, YAML load, argparse merge."""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import yaml

DEFAULT_MODEL_DIR = "models"
DEFAULT_OUTPUT_DIR = "data"


@dataclass
class Config:
    device: int = -1                       # -1 = auto (default loopback)
    mic: bool = False                      # capture own mic as second channel
    model_dir: str = DEFAULT_MODEL_DIR
    translate: str = "deepseek"            # on|off|deepseek|ollama
    output_dir: str = DEFAULT_OUTPUT_DIR
    overlay: bool = False                  # tkinter floating subtitle
    no_tui: bool = False                   # don't render rich panel
    fake: bool = False                     # run with fake capture (demo)
    list_devices: bool = False
    thread_nums: int = 4
    config_file: Optional[str] = None
    setup: bool = False                    # run interactive credential setup
    talk: bool = False                     # enable Gemini Live voice chat (P2T)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="realtime-translation",
        description="监听系统音频(腾讯会议等)，实时中英字幕 + 互译",
    )
    p.add_argument("--list-devices", action="store_true", help="列出音频设备并退出")
    p.add_argument("--device", type=int, default=-1, help="loopback 设备索引(-1=默认)")
    p.add_argument("--mic", action="store_true", help="同时捕获麦克风通道")
    p.add_argument("--model-dir", default=None, help="sherpa-onnx 模型目录")
    p.add_argument("--translate", choices=["on", "off", "deepseek", "ollama"], default=None,
                   help="翻译后端(默认深度推理走 deepseek)")
    p.add_argument("--output", default=None, help="转写保存目录")
    p.add_argument("--overlay", action="store_true", help="tkinter 悬浮字幕窗")
    p.add_argument("--no-tui", action="store_true", help="不显示终端字幕面板")
    p.add_argument("--fake", action="store_true", help="演示模式(合成音频流)")
    p.add_argument("--config", default=None, help="YAML 配置文件")
    p.add_argument("--setup", action="store_true", help="交互式配置凭据(URL/API key)")
    p.add_argument("--talk", action="store_true", help="启用 Gemini Live 实时语音对话(按住 F2 说话)")
    args = p.parse_args(argv)
    if args.device < -1:
        raise SystemExit("--device 必须 >= -1")
    return args


def load_config(path: Optional[str] = None) -> Config:
    cfg = Config()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for k, v in data.items():
            if hasattr(cfg, k) and v is not None:
                setattr(cfg, k, v)
    return cfg


def build_translator(backend: str):
    """Factory returning a Translator instance (or raising on unknown)."""
    from .translator import create_translator
    return create_translator(backend)


def apply_cli(cfg: Config, args: argparse.Namespace) -> Config:
    """Merge parsed CLI args over config (CLI wins)."""
    if args.device is not None and args.device != -1:
        cfg.device = args.device
    if args.model_dir:
        cfg.model_dir = args.model_dir
    if args.translate:
        cfg.translate = args.translate
    if args.output:
        cfg.output_dir = args.output
    cfg.mic = cfg.mic or args.mic
    cfg.overlay = cfg.overlay or args.overlay
    cfg.no_tui = cfg.no_tui or args.no_tui
    cfg.fake = cfg.fake or args.fake
    if args.list_devices:
        cfg.list_devices = True
    if args.setup:
        cfg.setup = True
    if args.talk:
        cfg.talk = True
    return cfg
