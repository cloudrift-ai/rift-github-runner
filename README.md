# cloudrift-github-runner

Serverless GCP controller for ephemeral GitHub Actions runners on [CloudRift](https://cloudrift.ai) VMs. Provision GPU-enabled self-hosted runners on demand — VMs are created when jobs are queued and terminated when they complete.

## How It Works

1. A GitHub Actions workflow requests a `cloudrift`-labeled runner
2. GitHub sends a `workflow_job` webhook to a GCP Cloud Function
3. The function checks GPU availability, provisions a CloudRift VM with a JIT runner, and stores state in Firestore
4. The runner picks up the job, executes it, and shuts down
5. On the `completed` webhook, the function terminates the VM
6. A scheduled cleanup function catches any orphaned VMs

## Quick Start

### Prerequisites

- GCP project with billing enabled, `gcloud` CLI authenticated
- [Terraform](https://www.terraform.io/) installed
- [CloudRift](https://cloudrift.ai) account and API key
- GitHub PAT with `administration:write` scope (for runner registration)

### Deploy

```bash
# 1. Store secrets in GCP Secret Manager (one-time)
echo -n "your-cloudrift-api-key" | gcloud secrets versions add cloudrift-runner-api-key --data-file=-
echo -n "ghp_your_github_pat" | gcloud secrets versions add cloudrift-runner-github-pat --data-file=-
echo -n "your-webhook-secret" | gcloud secrets versions add cloudrift-runner-webhook-secret --data-file=-

# 2. Initialize Terraform (one-time)
make deploy-init

# 3. Deploy (zips source and runs terraform apply)
make deploy
```

Terraform will prompt for `project_id`. To skip the prompt, create `deploy/terraform/terraform.tfvars`:

```hcl
project_id = "my-gcp-project"
```

### Configure GitHub Webhook

1. Go to your repo (or org) Settings > Webhooks > Add webhook
2. Set the Payload URL to the Cloud Function URL (from Terraform/deploy output)
3. Set Content type to `application/json`
4. Set the Secret to the same value as `GITHUB_WEBHOOK_SECRET`
5. Select "Workflow jobs" under events

### Use in a Workflow

```yaml
jobs:
  gpu-test:
    runs-on: [self-hosted, cloudrift]
    steps:
      - uses: actions/checkout@v4
      - run: nvidia-smi
```

## Per-Repo Configuration (Required)

Each repo that uses CloudRift runners **must** have a `.cloudrift-runner.yml` in the repo root. Both `instance_type` and `image_url` are required — there are no env var fallbacks for these.

```yaml
defaults:
  instance_type: generic-gpu.1
  with_public_ip: true  # default is false
  image_url: https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img

jobs:
  gpu-test:
    instance_type: gpu.a100-80
  training:
    instance_type: gpu.h100-80
    image_url: https://storage.googleapis.com/.../rocm-ubuntu-24.04.img
```

- `defaults.instance_type` and `defaults.image_url` are required (unless every job has its own overrides)
- Jobs not listed under `jobs:` use the `defaults` section
- Per-job entries can override `instance_type`, `image_url`, and `with_public_ip`
- If no config file exists, the job is skipped (no runner provisioned)

## Configuration

| Env Var                       | Description                              | Default                    |
|-------------------------------|------------------------------------------|----------------------------|
| `CLOUDRIFT_API_KEY`           | CloudRift API key (via Secret Manager)   | required                   |
| `CLOUDRIFT_API_URL`           | CloudRift API base URL                   | `https://api.cloudrift.ai` |
| `CLOUDRIFT_WITH_PUBLIC_IP`    | Default public IP setting                | `false`                    |
| `RUNNER_LABEL`                | Label to match                           | `cloudrift`                |
| `MAX_RUNNER_LIFETIME_MINUTES` | VM auto-shutdown timeout                 | `120`                      |
| `GITHUB_PAT`                  | GitHub PAT (via Secret Manager)          | required                   |
| `GITHUB_WEBHOOK_SECRET`       | Webhook HMAC secret (via Secret Manager) | required                   |

Instance type and image URL are configured per-repo via `.cloudrift-runner.yml` (see above).

## Availability-Aware Provisioning

Before renting a VM, the controller checks CloudRift instance type availability. If no nodes are available, it returns 200 without registering a runner. GitHub will fall back to other runners per your workflow configuration:

```yaml
runs-on:
  group: cloudrift-gpu
  fallback: ubuntu-latest
```

## Development

```bash
make setup        # create venv + install deps
make test         # run tests
make lint         # check linting + formatting
make fmt          # auto-fix formatting
```

## License

Apache 2.0
