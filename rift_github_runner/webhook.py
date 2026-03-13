from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class WebhookError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class WorkflowJobEvent:
    action: str
    job_id: int
    job_name: str
    run_id: int
    labels: list[str]
    repo_full_name: str
    repo_owner: str
    repo_name: str
    head_sha: str
    sender: str = ""
    conclusion: str | None = None


def verify_signature(payload: bytes, signature_header: str, secret: str) -> None:
    if not signature_header:
        raise WebhookError("Missing X-Hub-Signature-256 header")

    if not signature_header.startswith("sha256="):
        raise WebhookError("Invalid signature format")

    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        raise WebhookError("Invalid webhook signature")


def parse_event(headers: dict[str, str], body: bytes) -> WorkflowJobEvent | None:
    event_type = headers.get("X-GitHub-Event") or headers.get("x-github-event", "")
    if event_type != "workflow_job":
        logger.info("Ignoring event type: %s", event_type)
        return None

    data = json.loads(body)
    action = data.get("action", "")
    if action not in ("queued", "completed"):
        logger.info("Ignoring workflow_job action: %s", action)
        return None

    job = data["workflow_job"]
    repo = data["repository"]

    return WorkflowJobEvent(
        action=action,
        job_id=job["id"],
        job_name=job["name"],
        run_id=job["run_id"],
        labels=job.get("labels", []),
        repo_full_name=repo["full_name"],
        repo_owner=repo["owner"]["login"],
        repo_name=repo["name"],
        head_sha=job.get("head_sha", data.get("head_sha", "")),
        sender=data.get("sender", {}).get("login", ""),
        conclusion=job.get("conclusion"),
    )
