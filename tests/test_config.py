# -*- coding: utf-8 -*-
"""Tests for config parsing (YAML + CLI merge)."""
import pytest

from realtime_translation.config import Config, load_config, parse_args


def test_defaults():
    cfg = Config()
    assert cfg.translate == "deepseek"
    assert cfg.model_dir == "models"
    assert cfg.output_dir == "data"
    assert cfg.device == -1  # auto
    assert cfg.mic is False
    assert cfg.overlay is False
    assert cfg.no_tui is False
    assert cfg.list_devices is False
    assert cfg.fake is False


def test_parse_args_basic(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["mt", "--device", "25", "--translate", "off", "--mic"],
    )
    args = parse_args()
    assert args.device == 25
    assert args.translate == "off"
    assert args.mic is True


def test_parse_args_list_devices():
    # --list-devices should work without other args
    import sys
    old = sys.argv
    sys.argv = ["mt", "--list-devices"]
    try:
        args = parse_args()
        assert args.list_devices is True
    finally:
        sys.argv = old


def test_load_config_yaml_overrides_defaults(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "model_dir: /abs/models\n"
        "translate: ollama\n"
        "output_dir: /tmp/out\n",
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_file))
    assert cfg.model_dir == "/abs/models"
    assert cfg.translate == "ollama"
    assert cfg.output_dir == "/tmp/out"


def test_load_config_missing_file_uses_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "nope.yaml"))
    assert cfg.translate == "deepseek"
    assert cfg.model_dir == "models"


def test_factory_builds_backend():
    from realtime_translation.config import build_translator
    t = build_translator("off")
    assert t.name == "off"
