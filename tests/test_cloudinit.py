from rift_github_runner.cloudinit import generate_cloudinit_script


def test_script_contains_jitconfig():
    script = generate_cloudinit_script("ENCODED_CONFIG_123", max_lifetime_minutes=60)
    assert "ENCODED_CONFIG_123" in script
    assert "--jitconfig ENCODED_CONFIG_123" in script


def test_script_contains_watchdog():
    script = generate_cloudinit_script("cfg", max_lifetime_minutes=30)
    assert "LIFETIME=1800" in script
    assert "shutdown -h now" in script


def test_script_creates_runner_user():
    script = generate_cloudinit_script("cfg", max_lifetime_minutes=120)
    assert "useradd -m -s /bin/bash runner" in script


def test_script_is_bash():
    script = generate_cloudinit_script("cfg", max_lifetime_minutes=120)
    assert script.startswith("#!/bin/bash")
