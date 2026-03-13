from __future__ import annotations

_RUNNER_VERSION = "2.322.0"
_RUNNER_URL = (
    f"https://github.com/actions/runner/releases/download/"
    f"v{_RUNNER_VERSION}/actions-runner-linux-x64-{_RUNNER_VERSION}.tar.gz"
)


def generate_cloudinit_script(
    encoded_jit_config: str,
    max_lifetime_minutes: int,
) -> str:
    lifetime_seconds = max_lifetime_minutes * 60
    return f"""#!/bin/bash
set -euo pipefail

# Watchdog: force shutdown after max lifetime
LIFETIME={lifetime_seconds}
nohup bash -c "sleep $LIFETIME && shutdown -h now 'Runner lifetime exceeded'" &>/dev/null &

# Create runner user
useradd -m -s /bin/bash runner
RUNNER_HOME=/home/runner

# Download and extract runner
mkdir -p "$RUNNER_HOME/actions-runner"
cd "$RUNNER_HOME/actions-runner"
curl -sL "{_RUNNER_URL}" | tar xz

chown -R runner:runner "$RUNNER_HOME"

# Run the ephemeral runner (exits after one job)
su - runner -c 'cd ~/actions-runner && ./run.sh --jitconfig {encoded_jit_config}' || true

# Shut down after the job completes
shutdown -h now "Runner job completed"
"""
