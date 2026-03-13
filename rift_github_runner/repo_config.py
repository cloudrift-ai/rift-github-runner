from __future__ import annotations

import logging
from dataclasses import dataclass

import yaml

from .github_client import GitHubClient

logger = logging.getLogger(__name__)

CONFIG_PATH = ".cloudrift-runner.yml"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedJobConfig:
    instance_type: str
    with_public_ip: bool
    image_url: str


def resolve_job_config(
    github: GitHubClient,
    owner: str,
    repo: str,
    ref: str,
    job_name: str,
    default_with_public_ip: bool,
) -> ResolvedJobConfig | None:
    content = github.fetch_file(owner, repo, CONFIG_PATH, ref)
    if content is None:
        logger.warning("No %s found in %s/%s — cannot provision runner", CONFIG_PATH, owner, repo)
        return None

    return _parse_config(content, job_name, default_with_public_ip)


def _parse_config(
    raw: str,
    job_name: str,
    default_with_public_ip: bool,
) -> ResolvedJobConfig:
    data = yaml.safe_load(raw) or {}
    defaults = data.get("defaults", {})
    jobs = data.get("jobs", {})

    base_instance_type = defaults.get("instance_type")
    base_image_url = defaults.get("image_url")
    base_public_ip = defaults.get("with_public_ip", default_with_public_ip)

    job_overrides = jobs.get(job_name, {})
    instance_type = job_overrides.get("instance_type", base_instance_type)
    image_url = job_overrides.get("image_url", base_image_url)

    if not instance_type:
        raise ConfigError(f"instance_type not specified for job '{job_name}' in {CONFIG_PATH}")
    if not image_url:
        raise ConfigError(f"image_url not specified for job '{job_name}' in {CONFIG_PATH}")

    return ResolvedJobConfig(
        instance_type=instance_type,
        with_public_ip=job_overrides.get("with_public_ip", base_public_ip),
        image_url=image_url,
    )
