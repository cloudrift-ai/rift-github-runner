from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from rift_github_runner.webhook import WebhookError, parse_event, verify_signature
from tests.conftest import make_workflow_job_payload


class TestVerifySignature:
    def test_valid_signature(self):
        payload = b'{"test": true}'
        secret = "mysecret"
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        verify_signature(payload, sig, secret)

    def test_invalid_signature(self):
        with pytest.raises(WebhookError, match="Invalid webhook signature"):
            verify_signature(b"payload", "sha256=bad", "secret")

    def test_missing_header(self):
        with pytest.raises(WebhookError, match="Missing"):
            verify_signature(b"payload", "", "secret")

    def test_bad_format(self):
        with pytest.raises(WebhookError, match="Invalid signature format"):
            verify_signature(b"payload", "md5=abc", "secret")


class TestParseEvent:
    def test_queued_event(self):
        payload = make_workflow_job_payload(action="queued")
        body = json.dumps(payload).encode()
        headers = {"X-GitHub-Event": "workflow_job"}

        event = parse_event(headers, body)

        assert event is not None
        assert event.action == "queued"
        assert event.job_id == 12345
        assert event.job_name == "gpu-test"
        assert event.run_id == 67890
        assert event.labels == ["self-hosted", "cloudrift"]
        assert event.repo_full_name == "myorg/myrepo"
        assert event.repo_owner == "myorg"
        assert event.repo_name == "myrepo"

    def test_completed_event(self):
        payload = make_workflow_job_payload(action="completed", conclusion="success")
        body = json.dumps(payload).encode()
        headers = {"X-GitHub-Event": "workflow_job"}

        event = parse_event(headers, body)

        assert event is not None
        assert event.action == "completed"
        assert event.conclusion == "success"

    def test_ignores_non_workflow_job(self):
        body = json.dumps({"action": "opened"}).encode()
        headers = {"X-GitHub-Event": "pull_request"}
        assert parse_event(headers, body) is None

    def test_ignores_in_progress(self):
        payload = make_workflow_job_payload(action="in_progress")
        body = json.dumps(payload).encode()
        headers = {"X-GitHub-Event": "workflow_job"}
        assert parse_event(headers, body) is None
