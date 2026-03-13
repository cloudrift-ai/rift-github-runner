from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rift_github_runner.repo_config import ConfigError, resolve_job_config


def _mock_github(file_content: str | None) -> MagicMock:
    gh = MagicMock()
    gh.fetch_file.return_value = file_content
    return gh


def test_no_config_file_returns_none():
    gh = _mock_github(None)
    result = resolve_job_config(gh, "o", "r", "sha", "test-job")
    assert result is None


def test_defaults_section():
    yaml_content = """
defaults:
  instance_type: gpu.a100-80
  image_url: https://example.com/a100.img
"""
    gh = _mock_github(yaml_content)
    cfg = resolve_job_config(gh, "o", "r", "sha", "some-job")
    assert cfg.instance_type == "gpu.a100-80"
    assert cfg.image_url == "https://example.com/a100.img"
    assert cfg.with_public_ip is False


def test_job_override():
    yaml_content = """
defaults:
  instance_type: generic-gpu.1
  image_url: https://example.com/default.img
jobs:
  gpu-test:
    instance_type: gpu.a100-80
"""
    gh = _mock_github(yaml_content)
    cfg = resolve_job_config(gh, "o", "r", "sha", "gpu-test")
    assert cfg.instance_type == "gpu.a100-80"
    assert cfg.image_url == "https://example.com/default.img"


def test_job_not_listed_uses_defaults_section():
    yaml_content = """
defaults:
  instance_type: gpu.h100-80
  image_url: https://example.com/default.img
jobs:
  gpu-test:
    instance_type: gpu.a100-80
"""
    gh = _mock_github(yaml_content)
    cfg = resolve_job_config(gh, "o", "r", "sha", "other-job")
    assert cfg.instance_type == "gpu.h100-80"


def test_missing_instance_type_raises():
    yaml_content = """
defaults:
  image_url: https://example.com/default.img
"""
    gh = _mock_github(yaml_content)
    with pytest.raises(ConfigError, match="instance_type not specified"):
        resolve_job_config(gh, "o", "r", "sha", "test-job")


def test_missing_image_url_raises():
    yaml_content = """
defaults:
  instance_type: gpu.a100-80
"""
    gh = _mock_github(yaml_content)
    with pytest.raises(ConfigError, match="image_url not specified"):
        resolve_job_config(gh, "o", "r", "sha", "test-job")
