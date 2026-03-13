from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 30


class CloudRiftClient:
    def __init__(self, api_url: str, api_key: str):
        self._base = api_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {api_key}"
        self._session.headers["Content-Type"] = "application/json"

    def check_availability(self, instance_type: str) -> bool:
        resp = self._session.post(
            f"{self._base}/api/v1/instance-types/list",
            json={},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        for it in resp.json().get("instance_types", []):
            if it.get("name") == instance_type:
                return it.get("available_nodes", 0) > 0
        logger.warning("Instance type %s not found in API response", instance_type)
        return False

    def rent_instance(
        self,
        name: str,
        instance_type: str,
        image_url: str,
        with_public_ip: bool,
        cloudinit_script: str,
    ) -> str | None:
        body = {
            "name": name,
            "instance_type": instance_type,
            "image_url": image_url,
            "with_public_ip": with_public_ip,
            "cloud_init": cloudinit_script,
        }
        try:
            resp = self._session.post(
                f"{self._base}/api/v1/instances/rent",
                json=body,
                timeout=_TIMEOUT,
            )
        except requests.RequestException:
            logger.exception("Failed to rent instance")
            return None

        if resp.status_code == 503:
            logger.warning("No capacity (503) for instance type %s", instance_type)
            return None

        resp.raise_for_status()
        return resp.json()["instance_id"]

    def terminate_instance(self, instance_id: str) -> None:
        resp = self._session.post(
            f"{self._base}/api/v1/instances/terminate",
            json={"instance_id": instance_id},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("Terminated instance %s", instance_id)
