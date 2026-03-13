from __future__ import annotations

import responses

from rift_github_runner.cloudrift_client import CloudRiftClient

BASE = "https://api.test.cloudrift.ai"


class TestCheckAvailability:
    @responses.activate
    def test_available(self):
        responses.post(
            f"{BASE}/api/v1/instance-types/list",
            json={
                "instance_types": [
                    {"name": "generic-gpu.1", "available_nodes": 3},
                    {"name": "gpu.a100-80", "available_nodes": 0},
                ]
            },
        )
        client = CloudRiftClient(BASE, "key")
        assert client.check_availability("generic-gpu.1") is True

    @responses.activate
    def test_unavailable(self):
        responses.post(
            f"{BASE}/api/v1/instance-types/list",
            json={
                "instance_types": [
                    {"name": "generic-gpu.1", "available_nodes": 0},
                ]
            },
        )
        client = CloudRiftClient(BASE, "key")
        assert client.check_availability("generic-gpu.1") is False

    @responses.activate
    def test_unknown_type(self):
        responses.post(
            f"{BASE}/api/v1/instance-types/list",
            json={"instance_types": []},
        )
        client = CloudRiftClient(BASE, "key")
        assert client.check_availability("nonexistent") is False


class TestRentInstance:
    @responses.activate
    def test_success(self):
        responses.post(
            f"{BASE}/api/v1/instances/rent",
            json={"instance_id": "inst-123"},
        )
        client = CloudRiftClient(BASE, "key")
        result = client.rent_instance(
            name="runner-1",
            instance_type="generic-gpu.1",
            image_url="https://example.com/img",
            with_public_ip=True,
            cloudinit_script="#!/bin/bash\necho hi",
        )
        assert result == "inst-123"

    @responses.activate
    def test_503_returns_none(self):
        responses.post(
            f"{BASE}/api/v1/instances/rent",
            status=503,
            json={"error": "InstanceImpossibleToAllocate"},
        )
        client = CloudRiftClient(BASE, "key")
        result = client.rent_instance(
            name="runner-1",
            instance_type="generic-gpu.1",
            image_url="https://example.com/img",
            with_public_ip=True,
            cloudinit_script="#!/bin/bash\necho hi",
        )
        assert result is None


class TestTerminateInstance:
    @responses.activate
    def test_success(self):
        responses.post(f"{BASE}/api/v1/instances/terminate", json={})
        client = CloudRiftClient(BASE, "key")
        client.terminate_instance("inst-123")
        assert responses.calls[0].request.body is not None
