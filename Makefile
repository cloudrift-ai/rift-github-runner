.PHONY: setup test lint fmt deploy-init deploy deploy-destroy docker-build docker-up docker-down

TF_DIR := deploy/terraform

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	@if ! command -v terraform >/dev/null 2>&1; then \
		echo "Terraform not found, installing..."; \
		if command -v apt-get >/dev/null 2>&1; then \
			sudo apt-get update && sudo apt-get install -y gnupg software-properties-common && \
			wget -qO- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
			echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $$(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list && \
			sudo apt-get update && sudo apt-get install -y terraform; \
		elif command -v brew >/dev/null 2>&1; then \
			brew tap hashicorp/tap && brew install hashicorp/tap/terraform; \
		else \
			echo "ERROR: Could not install Terraform. Install it manually: https://developer.hashicorp.com/terraform/install"; \
			exit 1; \
		fi; \
	else \
		echo "Terraform already installed: $$(terraform version -json | head -1)"; \
	fi
	@if [ ! -d "$(TF_DIR)/.terraform" ]; then \
		echo "Running terraform init..."; \
		cd $(TF_DIR) && terraform init; \
	fi

test:
	.venv/bin/pytest -vv

lint:
	.venv/bin/ruff check rift_github_runner/ tests/
	.venv/bin/ruff format --check rift_github_runner/ tests/

fmt:
	.venv/bin/ruff format rift_github_runner/ tests/
	.venv/bin/ruff check --fix rift_github_runner/ tests/

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

deploy-init:
	cd $(TF_DIR) && terraform init

deploy:
	cd $(TF_DIR) && terraform apply

deploy-destroy:
	cd $(TF_DIR) && terraform destroy
