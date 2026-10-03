# Part 2: Product Availability app. Uses the AWS profile in AWS_PROFILE (default: pocs).
AWS_PROFILE ?= pocs
export AWS_PROFILE
PY := .venv/bin/python

.PHONY: install test test-live test-e2e web-install web-test web-lint web-e2e package deploy deploy-web smoke destroy

install:
	uv venv --python 3.12 .venv
	uv pip install -r requirements-dev.txt -r infrastructure/requirements.txt

test:            ## backend unit tests (no AWS needed)
	$(PY) -m pytest --cov=src --cov-report=term-missing:skip-covered

test-live:       ## realistic questions against real Amazon Bedrock
	$(PY) -m pytest -m live tests/live

test-e2e:        ## API contract tests against the deployed stack
	$(PY) -m pytest -m e2e tests/e2e

web-install:
	cd src/app && npm ci

web-test:        ## front-end unit tests, types and lint
	cd src/app && npx tsc --noEmit && npx eslint && npx vitest run

web-e2e:         ## browser tests (BASE_URL=https://xpand.medgan.ai to test the deployed app)
	cd src/app && npx playwright test

package:
	infrastructure/scripts/package_agent.sh

deploy:
	infrastructure/scripts/deploy.sh

deploy-web:
	infrastructure/scripts/deploy_web.sh

smoke:
	infrastructure/scripts/smoke_test.sh

destroy:
	infrastructure/scripts/destroy.sh
