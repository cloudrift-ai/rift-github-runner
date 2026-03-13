from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest

from rift_github_runner.repo_config import ResolvedJobConfig
from tests.conftest import make_workflow_job_payload


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_request(payload: dict, secret: str, event: str = "workflow_job") -> MagicMock:
    body = json.dumps(payload).encode()
    req = MagicMock()
    req.get_data.return_value = body
    req.headers = {
        "X-Hub-Signature-256": _sign(body, secret),
        "X-GitHub-Event": event,
    }
    return req


def _parse_response(result):
    body_str, status, _headers = result
    return json.loads(body_str), status


_DEFAULT_JOB_CONFIG = ResolvedJobConfig(
    instance_type="generic-gpu.1",
    with_public_ip=False,
    image_url="https://example.com/image.img",
)


@pytest.fixture
def _patch_deps(config):
    """Patch all external dependencies for main handler tests."""
    with (
        patch(
            "rift_github_runner.main.resolve_job_config", return_value=_DEFAULT_JOB_CONFIG
        ) as mock_resolve,
    ):
        cr_inst = MagicMock()
        gh_inst = MagicMock()
        state_inst = MagicMock()

        cr_inst.check_availability.return_value = True
        cr_inst.rent_instance.return_value = "inst-999"
        gh_inst.create_jit_runner.return_value = MagicMock(
            encoded_jit_config="jitcfg123",
            runner_id=1,
            runner_name="cloudrift-runner-12345",
        )
        state_inst.try_create_job.return_value = True
        state_inst.get_job.return_value = MagicMock(instance_id="inst-999", status="running")

        yield {
            "config": config,
            "cloudrift": cr_inst,
            "github": gh_inst,
            "state": state_inst,
            "resolve_config": mock_resolve,
        }


def _call_webhook(deps, req):
    from rift_github_runner.main import handle_webhook

    return handle_webhook(
        req,
        config=deps["config"],
        cloudrift=deps["cloudrift"],
        github=deps["github"],
        state=deps["state"],
    )


class TestHandleWebhook:
    def test_queued_provisions_runner(self, config, _patch_deps):
        payload = make_workflow_job_payload(action="queued")
        req = _make_request(payload, config.github_webhook_secret)

        data, status = _parse_response(_call_webhook(_patch_deps, req))
        assert status == 200
        assert data["status"] == "provisioned"
        assert data["instance_id"] == "inst-999"

        _patch_deps["cloudrift"].check_availability.assert_called_once()
        _patch_deps["cloudrift"].rent_instance.assert_called_once()

    def test_queued_skips_when_unavailable(self, config, _patch_deps):
        _patch_deps["cloudrift"].check_availability.return_value = False
        payload = make_workflow_job_payload(action="queued")
        req = _make_request(payload, config.github_webhook_secret)

        data, status = _parse_response(_call_webhook(_patch_deps, req))
        assert status == 200
        assert data["reason"] == "no capacity"
        _patch_deps["cloudrift"].rent_instance.assert_not_called()

    def test_queued_skips_when_no_config_file(self, config, _patch_deps):
        _patch_deps["resolve_config"].return_value = None
        payload = make_workflow_job_payload(action="queued")
        req = _make_request(payload, config.github_webhook_secret)

        data, status = _parse_response(_call_webhook(_patch_deps, req))
        assert status == 200
        assert data["reason"] == "no config file"
        _patch_deps["cloudrift"].rent_instance.assert_not_called()

    def test_completed_terminates(self, config, _patch_deps):
        payload = make_workflow_job_payload(action="completed")
        req = _make_request(payload, config.github_webhook_secret)

        data, status = _parse_response(_call_webhook(_patch_deps, req))
        assert status == 200
        assert data["status"] == "terminated"
        _patch_deps["cloudrift"].terminate_instance.assert_called_once_with("inst-999")

    def test_invalid_signature_returns_400(self, config, _patch_deps):
        payload = make_workflow_job_payload()
        body = json.dumps(payload).encode()
        req = MagicMock()
        req.get_data.return_value = body
        req.headers = {
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Event": "workflow_job",
        }

        _data, status = _parse_response(_call_webhook(_patch_deps, req))
        assert status == 400

    def test_label_mismatch_skips(self, config, _patch_deps):
        payload = make_workflow_job_payload(labels=["self-hosted", "other-label"])
        req = _make_request(payload, config.github_webhook_secret)

        data, status = _parse_response(_call_webhook(_patch_deps, req))
        assert status == 200
        assert data["reason"] == "label mismatch"

    def test_non_workflow_event_ignored(self, config, _patch_deps):
        body = json.dumps({"action": "opened"}).encode()
        req = MagicMock()
        req.get_data.return_value = body
        req.headers = {
            "X-Hub-Signature-256": _sign(body, config.github_webhook_secret),
            "X-GitHub-Event": "pull_request",
        }

        data, status = _parse_response(_call_webhook(_patch_deps, req))
        assert status == 200
        assert data["status"] == "ignored"
