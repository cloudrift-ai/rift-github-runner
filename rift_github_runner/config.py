from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    cloudrift_api_key: str
    cloudrift_api_url: str
    runner_label: str
    max_runner_lifetime_minutes: int
    github_pat: str
    github_webhook_secret: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            cloudrift_api_key=_require("CLOUDRIFT_API_KEY"),
            cloudrift_api_url=os.environ.get("CLOUDRIFT_API_URL", "https://api.cloudrift.ai"),
            runner_label=os.environ.get("RUNNER_LABEL", "cloudrift"),
            max_runner_lifetime_minutes=int(os.environ.get("MAX_RUNNER_LIFETIME_MINUTES", "120")),
            github_pat=_require("GITHUB_PAT"),
            github_webhook_secret=_require("GITHUB_WEBHOOK_SECRET"),
        )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value
