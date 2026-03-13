from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 15


@dataclass(frozen=True)
class JitRunnerConfig:
    encoded_jit_config: str
    runner_id: int
    runner_name: str


class GitHubClient:
    def __init__(self, pat: str):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"token {pat}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def create_jit_runner(
        self,
        owner: str,
        repo: str,
        name: str,
        labels: list[str],
    ) -> JitRunnerConfig:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runners/generate-jitconfig"
        body = {
            "name": name,
            "runner_group_id": 1,
            "labels": labels,
            "work_folder": "_work",
        }
        resp = self._session.post(url, json=body, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        runner = data["runner"]
        return JitRunnerConfig(
            encoded_jit_config=data["encoded_jit_config"],
            runner_id=runner["id"],
            runner_name=runner["name"],
        )

    def fetch_file(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        resp = self._session.get(url, params={"ref": ref}, timeout=_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        import base64

        return base64.b64decode(resp.json()["content"]).decode()
