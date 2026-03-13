from __future__ import annotations

import pytest

from rift_github_runner.config import Config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove all config env vars so tests start clean."""
    for key in [
        "CLOUDRIFT_API_KEY",
        "CLOUDRIFT_API_URL",
        "CLOUDRIFT_WITH_PUBLIC_IP",
        "RUNNER_LABEL",
        "MAX_RUNNER_LIFETIME_MINUTES",
        "GITHUB_PAT",
        "GITHUB_WEBHOOK_SECRET",
    ]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def config() -> Config:
    return Config(
        cloudrift_api_key="test-api-key",
        cloudrift_api_url="https://api.test.cloudrift.ai",
        cloudrift_with_public_ip=False,
        runner_label="cloudrift",
        max_runner_lifetime_minutes=120,
        github_pat="ghp_testtoken",
        github_webhook_secret="test-secret",
    )


def make_workflow_job_payload(
    action: str = "queued",
    job_id: int = 12345,
    job_name: str = "gpu-test",
    run_id: int = 67890,
    labels: list[str] | None = None,
    repo_full_name: str = "myorg/myrepo",
    head_sha: str = "abc123",
    conclusion: str | None = None,
) -> dict:
    if labels is None:
        labels = ["self-hosted", "cloudrift"]
    owner, name = repo_full_name.split("/")
    payload = {
        "action": action,
        "workflow_job": {
            "id": job_id,
            "name": job_name,
            "run_id": run_id,
            "labels": labels,
            "head_sha": head_sha,
            "conclusion": conclusion,
        },
        "repository": {
            "full_name": repo_full_name,
            "owner": {"login": owner},
            "name": name,
        },
        "sender": {"login": "testuser"},
    }
    return payload
