# Part 1 tests run with the Part 2 virtualenv (same dependencies). From this folder: make test
PY := ../part-2-data-to-answers/.venv/bin/python
export AWS_PROFILE ?= pocs

.PHONY: test test-live test-e2e test-demo
test:        ## unit tests with mocks and moto (no credentials needed)
	$(PY) -m pytest --cov=src/inbox --cov-report=term-missing:skip-covered
test-live:   ## real ClickUp (and Bedrock) calls: needs the Secrets Manager secret and AWS credentials
	$(PY) -m pytest -m live tests/live
test-e2e:    ## API tests against the deployed stack
	$(PY) -m pytest -m e2e tests/e2e
test-demo:   ## the demo scenario on the real mailbox, webhook, agent and ClickUp (sends itself emails, cleans up after)
	$(PY) -m pytest -m e2e tests/e2e/test_real_mailbox_flow.py -v
