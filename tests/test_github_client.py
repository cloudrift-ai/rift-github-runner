from __future__ import annotations

import base64

import responses

from rift_github_runner.github_client import GitHubClient


class TestCreateJitRunner:
    @responses.activate
    def test_success(self):
        responses.post(
            "https://api.github.com/repos/myorg/myrepo/actions/runners/generate-jitconfig",
            json={
                "encoded_jit_config": "base64encodedconfig",
                "runner": {"id": 42, "name": "cloudrift-runner-123"},
            },
        )
        client = GitHubClient("ghp_test")
        jit = client.create_jit_runner(
            owner="myorg",
            repo="myrepo",
            name="cloudrift-runner-123",
            labels=["self-hosted", "cloudrift"],
        )
        assert jit.encoded_jit_config == "base64encodedconfig"
        assert jit.runner_id == 42
        assert jit.runner_name == "cloudrift-runner-123"


class TestFetchFile:
    @responses.activate
    def test_found(self):
        content = base64.b64encode(b"instance_type: gpu.a100").decode()
        responses.get(
            "https://api.github.com/repos/myorg/myrepo/contents/.cloudrift-runner.yml",
            json={"content": content, "encoding": "base64"},
        )
        client = GitHubClient("ghp_test")
        result = client.fetch_file("myorg", "myrepo", ".cloudrift-runner.yml", "abc123")
        assert result == "instance_type: gpu.a100"

    @responses.activate
    def test_not_found(self):
        responses.get(
            "https://api.github.com/repos/myorg/myrepo/contents/.cloudrift-runner.yml",
            status=404,
            json={"message": "Not Found"},
        )
        client = GitHubClient("ghp_test")
        result = client.fetch_file("myorg", "myrepo", ".cloudrift-runner.yml", "abc123")
        assert result is None
