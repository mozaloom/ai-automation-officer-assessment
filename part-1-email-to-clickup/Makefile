# Part 1 tests run with the Part 2 virtualenv (same dependencies). From this folder: make test
PY := ../part-2-data-to-answers/.venv/bin/python
export AWS_PROFILE ?= pocs

.PHONY: test test-live test-e2e
test:        ## unit tests with mocks and moto (no credentials needed)
	$(PY) -m pytest --cov=src/inbox --cov-report=term-missing:skip-covered
test-live:   ## real ClickUp (and Bedrock) calls: needs the Secrets Manager secret and AWS credentials
	$(PY) -m pytest -m live tests/live
test-e2e:    ## API tests against the deployed stack
	$(PY) -m pytest -m e2e tests/e2e
