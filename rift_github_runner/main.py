from __future__ import annotations

import json
import logging

from flask import Flask, request

from .cleanup import cleanup_orphans
from .cloudinit import generate_cloudinit_script
from .cloudrift_client import CloudRiftClient
from .config import Config
from .github_client import GitHubClient
from .repo_config import ConfigError, resolve_job_config
from .state import StateStore
from .webhook import WebhookError, parse_event, verify_signature

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _json_response(data: dict, status: int = 200) -> tuple[str, int, dict[str, str]]:
    return json.dumps(data), status, {"Content-Type": "application/json"}


def create_app() -> Flask:
    app = Flask(__name__)

    try:
        config = Config.from_env()
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        raise

    state = StateStore()
    cloudrift = CloudRiftClient(config.cloudrift_api_url, config.cloudrift_api_key)
    github = GitHubClient(config.github_pat)

    @app.route("/health", methods=["GET"])
    def health():
        return _json_response({"status": "ok"})

    @app.route("/webhook", methods=["POST"])
    def webhook():
        return handle_webhook(
            request, config=config, cloudrift=cloudrift, github=github, state=state
        )

    @app.route("/cleanup", methods=["POST"])
    def cleanup():
        count = cleanup_orphans(state, cloudrift, config.max_runner_lifetime_minutes)
        return _json_response({"status": "ok", "cleaned": count})

    # Start background cleanup scheduler
    _start_scheduler(state, cloudrift, config)

    return app


def _start_scheduler(state, cloudrift, config):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            lambda: cleanup_orphans(state, cloudrift, config.max_runner_lifetime_minutes),
            "interval",
            minutes=10,
            id="cleanup_orphans",
        )
        scheduler.add_job(
            lambda: state.delete_old_jobs(),
            "interval",
            hours=1,
            id="delete_old_jobs",
        )
        scheduler.start()
        logger.info("Background scheduler started (cleanup every 10m, TTL every 1h)")
    except Exception:
        logger.exception("Failed to start background scheduler")


def handle_webhook(request, *, config=None, cloudrift=None, github=None, state=None):
    if config is None:
        try:
            config = Config.from_env()
        except ValueError as e:
            logger.error("Configuration error: %s", e)
            return _json_response({"error": "server misconfigured"}, 500)

    body = request.get_data()

    try:
        verify_signature(
            body,
            request.headers.get("X-Hub-Signature-256", ""),
            config.github_webhook_secret,
        )
    except WebhookError as e:
        return _json_response({"error": str(e)}, e.status_code)

    event = parse_event(dict(request.headers), body)
    if event is None:
        return _json_response({"status": "ignored"})

    if config.runner_label not in event.labels:
        logger.info(
            "Job %d labels %s do not include '%s', skipping",
            event.job_id,
            event.labels,
            config.runner_label,
        )
        return _json_response({"status": "skipped", "reason": "label mismatch"})

    if cloudrift is None:
        cloudrift = CloudRiftClient(config.cloudrift_api_url, config.cloudrift_api_key)
    if github is None:
        github = GitHubClient(config.github_pat)
    if state is None:
        state = StateStore()

    if event.action == "queued":
        return _handle_queued(config, cloudrift, github, state, event)
    elif event.action == "completed":
        return _handle_completed(cloudrift, state, event)

    return _json_response({"status": "ignored"})


def _handle_queued(config, cloudrift, github, state, event):
    try:
        job_config = resolve_job_config(
            github=github,
            owner=event.repo_owner,
            repo=event.repo_name,
            ref=event.head_sha,
            job_name=event.job_name,
            default_with_public_ip=config.cloudrift_with_public_ip,
        )
    except ConfigError as e:
        logger.warning("Config error for job %d: %s", event.job_id, e)
        return _json_response({"status": "skipped", "reason": "config error"})

    if job_config is None:
        logger.info(
            "No .cloudrift-runner.yml in %s, skipping job %d",
            event.repo_full_name,
            event.job_id,
        )
        return _json_response({"status": "skipped", "reason": "no config file"})

    if not cloudrift.check_availability(job_config.instance_type):
        logger.info(
            "Instance type %s unavailable, skipping job %d",
            job_config.instance_type,
            event.job_id,
        )
        return _json_response({"status": "skipped", "reason": "no capacity"})

    runner_name = f"cloudrift-runner-{event.job_id}"
    jit = github.create_jit_runner(
        owner=event.repo_owner,
        repo=event.repo_name,
        name=runner_name,
        labels=event.labels,
    )

    cloudinit_script = generate_cloudinit_script(
        encoded_jit_config=jit.encoded_jit_config,
        max_lifetime_minutes=config.max_runner_lifetime_minutes,
    )

    instance_id = cloudrift.rent_instance(
        name=runner_name,
        instance_type=job_config.instance_type,
        image_url=job_config.image_url,
        with_public_ip=job_config.with_public_ip,
        cloudinit_script=cloudinit_script,
    )

    if instance_id is None:
        logger.warning("Failed to rent VM for job %d (no capacity)", event.job_id)
        return _json_response({"status": "skipped", "reason": "rent failed"})

    created = state.try_create_job(
        job_id=event.job_id,
        instance_id=instance_id,
        run_id=event.run_id,
        repo=event.repo_full_name,
        labels=event.labels,
    )

    if not created:
        logger.warning("Duplicate job %d, terminating just-rented instance", event.job_id)
        cloudrift.terminate_instance(instance_id)
        return _json_response({"status": "skipped", "reason": "duplicate"})

    logger.info(
        "Provisioned runner for job %d: instance=%s type=%s",
        event.job_id,
        instance_id,
        job_config.instance_type,
    )
    return _json_response({"status": "provisioned", "instance_id": instance_id})


def _handle_completed(cloudrift, state, event):
    record = state.get_job(event.job_id)
    if record is None:
        logger.info("No record for completed job %d, nothing to terminate", event.job_id)
        return _json_response({"status": "no_record"})

    if record.status == "completed":
        logger.info("Job %d already completed", event.job_id)
        return _json_response({"status": "already_completed"})

    try:
        cloudrift.terminate_instance(record.instance_id)
    except Exception:
        logger.exception(
            "Failed to terminate instance %s for job %d", record.instance_id, event.job_id
        )

    state.mark_completed(event.job_id)
    logger.info("Completed job %d, terminated instance %s", event.job_id, record.instance_id)
    return _json_response({"status": "terminated", "instance_id": record.instance_id})


def get_app() -> Flask:
    """Entry point for gunicorn: `gunicorn 'rift_github_runner.main:get_app()'`."""
    return create_app()
