# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

SHELL := /bin/bash -e
SCRIPTS := $(realpath ../scripts)
FIND_PYTHON_FILES := $(SCRIPTS)/find-python-files
FIND_SHELL_FILES := $(SCRIPTS)/find-shell-files
PIPENV := $(SCRIPTS)/run-pipenv
PYTEST := $(PIPENV) run pytest $(PYTEST_ARGS)
CYCLES := $(PIPENV) run py_import_cycles
PYTEST_OPTS_UNIT_SKIP_SLOW = -m "not slow"
PYTEST_OPTS_UNIT_SLOW_ONLY = -m "slow"
BLACK  := $(SCRIPTS)/run-black
THREE_TO_TWO := $(PIPENV) run 3to2
BANDIT := $(PIPENV) run bandit
FIND_INVALID_TEST_FILES := $(SCRIPTS)/find-invalid-autogen-files
ADDITIONAL_MYPY_ARGS := $(JUNIT_XML)
# Please note: We can currently not include defines.make as it would override
# the EDITIONS environment variable handed over by some jenkins test jobs.
# Looks like we need to cleanup the EDITION handling here.
GCC_TOOLCHAIN := /opt/gcc-$(shell make --no-print-directory --file=../defines.make print-GCC_VERSION)
AGENT_PLUGIN_PYTHON_VERSIONS := $(shell make --no-print-directory --file=../defines.make print-AGENT_PLUGIN_PYTHON_VERSIONS)

# A random time zone between UTC-11...UTC+14. Note the recursively expanded
# variable assignment to get a new time zone on every access.
RANDOM_TZ = $(shell printf "UTC%+d\n" $$(( $$RANDOM / 1261 - 11 )) )

SYSTEM_TESTS := \
    test-integration \
    test-composition \
    test-update-cee \
    test-update-cce \
    test-update-cse \
    test-update-cross-edition-cce \
    test-update-cross-edition-cme \
    test-schemathesis-openapi \
    test-plugins \
    test-plugins-piggyback \
    test-gui-crawl \
    test-xss-crawl \
    test-gui-e2e \
    test-extension-compatibility
PYTEST_SYSTEM_TEST_ARGS := -p "no:cov"

# Since the unit tests (that are written for Python 3) are executed with Python
# 2.7, we need to convert them, just like it is done for the agent plugins (see
# agents/plugins/Makefile)
AGENT_PLUGIN_UNIT_TEST_FILES := $(wildcard agent-plugin-unit/test_*.py)
AGENT_PLUGIN_UNIT_TEST_FILES_PY2 := $(subst agent-plugin-unit,agent-plugin-unit/py2,$(AGENT_PLUGIN_UNIT_TEST_FILES))

.PHONY: clean format-shell help prepare-protobuf-files prepare-playwright  bandit.ini \
	$(foreach VERS,$(AGENT_PLUGIN_PYTHON_VERSIONS),test-agent-plugin-unit-py$(VERS)-docker) \
	test-bandit test-code-quality test-code-quality-docker
	test-docker test-docker-docker test-format-python test-format-python-docker \
	test-format-shell \
	$(SYSTEM_TESTS) \
	$(foreach TEST,$(SYSTEM_TESTS),$(TEST)-docker) \
	container-debug \
	$(foreach TEST,$(SYSTEM_TESTS),$(TEST)-docker-debug) \
	test-mypy test-mypy-raw itest-mypy-docker test-packaging test-pipenv-deps test-pylint test-pylint-docker \
	test-unit test-unit-all test-unit-docker test-unit-coverage-html \
	test-unit-shell test-unit-shell-docker test-shellcheck test-shellcheck-docker test-cycles test-cycles-docker \
	test-unit-omdlib test-unit-doctests \
	test-tidy-core test-tidy-docker test-iwyu-core test-iwyu-docker \
	test-unit-neb test-unit-core test-flake8

clean:
	$(RM) -r .mypy_cache $(AGENT_PLUGIN_UNIT_TEST_FILES_PY2)

help:
	@echo "container-debug                     - Run container for manual test debugging"
	@echo "format-shell                        - Format shell agents"
	@for i in $(AGENT_PLUGIN_PYTHON_VERSIONS); do \
	    echo "test-agent-plugin-unit-py$${i}-docker - Run Agent plugin tests in container with Python $${i}"; \
	done
	@for i in $(SYSTEM_TESTS); do \
	    echo "$${i}              - Run $${i} locally"; \
	    echo "$${i}-docker       - Run $${i} in container"; \
	done
	@echo "test-bandit                         - Run bandit (security) tests"
	@echo "test-bandit-docker                  - Run bandit (security) tests in docker"
	@echo "test-bandit-nosec-markers           - Check if all bandit #nosec markers are annotated properly"
	@echo "test-code-quality                   - Run code quality tests locally"
	@echo "test-code-quality-docker            - Run code quality tests in container"
	@echo "test-cycles                         - Run cycles check"
	@echo "test-cycles-docker                  - Run cycles check in docker"
	@echo "test-docker                         - Run docker tests"
	@echo "test-docker-docker                  - Run docker tests in docker"
	@echo "test-format-bazel                   - Run the Bazel formatting"
	@echo "test-format-bazel-docker            - Run the Bazel formatting in docker"
	@echo "test-format-python                  - Run formatting tests"
	@echo "test-format-python-docker           - Run formatting tests in docker"
	@echo "test-format-shell                   - Run the shell formatting"
	@echo "test-gui-e2e                        - Run GUI End-to-End locally"
	@echo "test-gui-e2e-docker                 - Run GUI End-to-End in container"
	@echo "test-license-headers                - Run license headers tests"
	@echo "test-license-headers-docker         - Run license headers tests in docker"
	@echo "test-lint-bazel                     - Run the Bazel linting"
	@echo "test-lint-bazel-docker              - Run the Bazel linting in docker"
	@echo "test-lint-groovy                    - Run the Groovy linting"
	@echo "test-lint-groovy-docker             - Run the Groovy linting in docker"
	@echo "test-mypy                           - Run mypy"
	@echo "test-mypy-docker                    - Run mypy in docker"
	@echo "test-mypy-raw                       - Run mypy with raw edition config"
	@echo "test-packaging                      - Run packaging tests"
	@echo "test-pipfile                        - Run Pipfile test"
	@echo "test-pipfile-docker                 - Run Pipfile test in docker"
	@echo "test-pipenv-deps                    - Run pipenv dependency issue test"
	@echo "test-pylint                         - Run pylint based tests"
	@echo "test-pylint-docker                  - Run pylint based tests in docker"
	@echo "test-shellcheck                     - Run shellcheck tests"
	@echo "test-shellcheck-docker              - Run shellcheck tests in docker"
	@echo "test-typescript-types               - Run TypeScript types check"
	@echo "test-typescript-types-docker        - Run TypeScript types check in docker"
	@echo "test-unit                           - Run unit tests"
	@echo "test-unit-all                       - Run unit tests (including those marked as slow)"
	@echo "test-unit-cmc                       - Run unit tests for cmc"
	@echo "test-unit-coverage-html             - Create HTML coverage report for unit tests"
	@echo "test-unit-docker                    - Run unit tests in docker"
	@echo "test-unit-neb                       - Run unit tests for neb"
	@echo "test-unit-shell                     - Run shell unit tests"
	@echo "test-unit-shell-docker              - Run shell unit tests in docker"
	@echo "test-unit-testlib                   - Run doctests present in testlib-modules"
	@echo "test-unit-testlib-docker            - Run doctests present in testlib-modules within docker container."
	@echo "test-werks                          - Run Werks tests"
	@echo "test-werks-docker                   - Run Werks tests in docker"

bandit.ini:
	( echo -n -e "[bandit]\ntargets: "; \
	  $(FIND_PYTHON_FILES) | tr '\n' ',' | sed 's/,$$//'; \
	  echo ) > bandit.ini
	( echo exclude: /tests >> bandit.ini )

format-shell:
	docker run --rm -v "$(realpath ..):/sh" -w /sh peterdavehello/shfmt shfmt -w -i 4 -ci $$($(FIND_SHELL_FILES))

agent-plugin-unit/py2/test_%.py: agent-plugin-unit/test_%.py
	mkdir -p "$(dir $@)"
	cat "$<" | gawk -v text="# Do not test generated 2.x files\n# fmt: off\n# type: ignore" '!/^#/ && !p {print text; p=1} 1' > "$@"
	$(THREE_TO_TWO) --nofix=str --nofix=next --nobackups --write "$@" >/dev/null

$(foreach VERS,$(filter 2.%,$(AGENT_PLUGIN_PYTHON_VERSIONS)),test-agent-plugin-unit-py$(VERS)-docker): $(AGENT_PLUGIN_UNIT_TEST_FILES_PY2)

$(foreach VERS,$(AGENT_PLUGIN_PYTHON_VERSIONS),test-agent-plugin-unit-py$(VERS)-docker):
	@if [ -z ${DOCKER_REGISTRY_NO_HTTPS} ]; then \
  	   echo "DOCKER_REGISTRY_NO_HTTPS is not set, please export this environment variable during make target call."; \
  	   echo "Hint: export DOCKER_REGISTRY_NO_HTTPS=artifacts.lan.tribe29.com:4000"; \
  	   exit 1; \
  	fi; \
	# Clean up auto-generated files, which do not have a corresponding source file anymore
	flock ./agent-plugin-unit $(FIND_INVALID_TEST_FILES)
	# Recursive Makefiles suck big time...
	flock ../agents/plugins $(MAKE) -C ../agents/plugins
	PYTHON_VERSION="$(patsubst test-agent-plugin-unit-py%-docker,%,$@)" ; \
	case $$PYTHON_VERSION in \
	    2.*) SUFFIX="/py2" ;; \
	    *) SUFFIX="" ;; \
	esac ; \
	TEST_PATH="$(realpath agent-plugin-unit)$$SUFFIX" ; \
	IMAGE_HASH="$$(docker build --build-arg DOCKER_REGISTRY="${DOCKER_REGISTRY_NO_HTTPS}" --build-arg PYTHON_VERSION_MAJ_MIN="$$PYTHON_VERSION" -q "$(realpath agent-plugin-unit)")" && \
	echo "Docker image: $$IMAGE_HASH" && \
	docker run \
	    --rm \
	    $(DOCKER_ADDOPTS) \
	    -e "PYTEST_ADDOPTS" \
	    -e "CI" \
	    -u $$(id -u):$$(id -g) \
	    -v "$$TEST_PATH:/tests" \
	    -v "$(realpath agent-plugin-unit)/datasets:/tests/datasets" \
	    -v "$(realpath ../agents):/agents" \
	    $$IMAGE_HASH \
	    python$$PYTHON_VERSION -m pytest --ignore=tests/py2/ "/tests"

test-bandit: bandit.ini
# Currently only care about high severity reported issues. Once this is reached,
# go and enable the medium/low checks.
	$(BANDIT) -c ../bandit.yaml -r -ll --ini bandit.ini $(BANDIT_OUTPUT_ARGS)

test-bandit-docker:
	../scripts/run-in-docker.sh make test-bandit

test-bandit-nosec-markers:
	$(PIPENV) run python bandit-nosec-markers/nosec_reason.py --doc bandit-nosec-markers/bandit-exclusions.md check $(realpath ..)

prepare-protobuf-files:
	$(MAKE) -C .. protobuf-files

prepare-playwright:
	../scripts/run-pipenv run playwright install-deps "chromium";
	../scripts/run-pipenv run playwright install "chromium";

test-docker-docker:
	DOCKER_RUN_ADDOPTS="-v $$HOME/.docker/config.json:$$HOME/.docker/config.json -v $$HOME/.cmk-credentials:$$HOME/.cmk-credentials --network=host -e BRANCH -e HOME -e WORKSPACE -e VERSION -e EDITION" \
	    ../scripts/run-in-docker.sh make --quiet test-docker

test-docker:
	docker run --rm -i $$(../buildscripts/docker_image_aliases/resolve.py IMAGE_HADOLINT) < ../docker_image/Dockerfile
	shellcheck -x $(SHELLCHECK_OUTPUT_ARGS) ../docker_image/docker-entrypoint.sh
	$(PYTEST) -x -T docker --log-cli-level=INFO docker

test-format-python: test-format-python-isort test-format-python-black

test-format-python-isort: ../pyproject.toml
	if test -z "$$PYTHON_FILES"; then $(FIND_PYTHON_FILES); else echo "$$PYTHON_FILES"; fi | \
	xargs -n 1500 $(PIPENV) run isort --settings-path ../pyproject.toml --check-only --diff \
	exit $${PIPESTATUS[1]}

test-format-python-black: ../pyproject.toml
	if test -z "$$PYTHON_FILES"; then $(FIND_PYTHON_FILES); else echo "$$PYTHON_FILES"; fi | \
	xargs -n 1500 $(BLACK) --check --diff ;\
	exit $${PIPESTATUS[1]}

test-format-python-docker:
	../scripts/run-in-docker.sh make --quiet test-format-python

test-format-shell:
	docker run --rm -v "$(realpath ..):/sh" -w /sh peterdavehello/shfmt shfmt -d -i 4 -ci $$($(FIND_SHELL_FILES))

test-lint-bazel:
	../scripts/run-buildifier --lint=warn --mode=check

test-lint-bazel-docker:
	../scripts/run-in-docker.sh make --quiet test-lint-bazel

test-format-bazel:
	../scripts/run-buildifier --mode=check

test-format-bazel-docker:
	../scripts/run-in-docker.sh make --quiet test-format-bazel

test-lint-groovy:
	cd ..; scripts/run-groovy-lint --loglevel warning --failon error $(GROOVYLINT_OUTPUT_ARGS)

test-lint-groovy-docker:
	../scripts/run-in-docker.sh make --quiet test-lint-groovy

test-gui-crawl: prepare-playwright
	$(PYTEST) -T gui_crawl $(PYTEST_SYSTEM_TEST_ARGS) $(realpath gui_crawl/test_gui_crawl.py)

test-xss-crawl: prepare-playwright
	XSS_CRAWL=1 $(PYTEST) -T gui_crawl $(PYTEST_SYSTEM_TEST_ARGS) $(realpath gui_crawl/test_gui_crawl.py) --numprocesses=2

test-gui-e2e: prepare-playwright
	$(PYTEST) -T gui_e2e --screenshot=only-on-failure --output="$$RESULT_PATH/" $(PYTEST_SYSTEM_TEST_ARGS) $(realpath gui_e2e/)  --numprocesses=1

test-integration:
	$(PYTEST) -T integration $(PYTEST_SYSTEM_TEST_ARGS) $(realpath integration)

test-composition:
	$(PYTEST) -T composition $(PYTEST_SYSTEM_TEST_ARGS) $(realpath composition)

test-extension-compatibility:
	$(PYTEST) -vv -T extension_compatibility $(PYTEST_SYSTEM_TEST_ARGS) $(realpath extension_compatibility)

test-update-cee:
	$(PYTEST) -T update $(PYTEST_SYSTEM_TEST_ARGS) $(realpath update) -m cee --log-cli-level=INFO

test-update-cce:
	$(PYTEST) -T update $(PYTEST_SYSTEM_TEST_ARGS) $(realpath update) -m cce --log-cli-level=INFO

test-update-cse:
	$(PYTEST) -T update $(PYTEST_SYSTEM_TEST_ARGS) $(realpath update) -m cse --log-cli-level=INFO \
	--disable-interactive-mode

test-update-cross-edition-cce: # from CEE to CCE
	$(PYTEST) -T update $(PYTEST_SYSTEM_TEST_ARGS) $(realpath update/test_update.py) -m cee --log-cli-level=INFO \
	--latest-base-version --target-edition=CCE --disable-interactive-mode

test-update-cross-edition-cme: # from CEE to CME
	$(PYTEST) -T update $(PYTEST_SYSTEM_TEST_ARGS) $(realpath update/test_update.py) -m cee --log-cli-level=INFO \
	--latest-base-version --target-edition=CME --disable-interactive-mode

test-schemathesis-openapi:
	$(PYTEST) -T schemathesis_openapi $(PYTEST_SYSTEM_TEST_ARGS) $(realpath schemathesis_openapi)

test-plugins:
	$(PYTEST) -T plugins_integration $(PYTEST_SYSTEM_TEST_ARGS) $(realpath plugins_integration)

test-plugins-piggyback:
	$(PYTEST) -T plugins_integration $(PYTEST_SYSTEM_TEST_ARGS) $(realpath plugins_integration) \
	plugins_integration/test_plugin.py --enable-piggyback

$(foreach TEST,$(SYSTEM_TESTS),$(TEST)-docker):
	$(PIPENV) run scripts/run-dockerized.py "$(subst -docker,,$@)"

container-debug $(foreach TEST,$(SYSTEM_TESTS),$(TEST)-docker-debug):
	$(PIPENV) run scripts/run-dockerized.py debug

test-license-headers:
	if test -z "$$PYTHON_FILES"; then $(FIND_PYTHON_FILES); else echo "$$PYTHON_FILES"; fi | \
	xargs -n 1500 --no-run-if-empty $(PYTEST) -T code_quality --log-cli-level=INFO $(realpath code_quality/test_license_headers.py) \
	--python-files;

test-license-headers-docker:
	../scripts/run-in-docker.sh make --quiet test-license-headers

test-pipfile:
	$(PYTEST) -T code_quality --log-cli-level=INFO $(realpath code_quality/test_pipfile.py);

test-pipfile-docker:
	../scripts/run-in-docker.sh make --quiet test-pipfile

test-file-content:
	if test -z "$$CHANGED_FILES_REL_FILE"; then \
	    $(PYTEST) -T code_quality --log-cli-level=INFO $(realpath code_quality/file_content) --test-all-files ; \
	else \
	    cat "$$CHANGED_FILES_REL_FILE" | xargs -n 1500 --no-run-if-empty $(PYTEST) -T code_quality --log-cli-level=INFO $(realpath code_quality/file_content) --changed-files ; \
	fi \

test-file-content-docker:
	../scripts/run-in-docker.sh make --quiet test-file-content

test-werks:
	$(PYTEST) -T code_quality --log-cli-level=INFO $(realpath code_quality/test_werks.py);

test-werks-docker:
	../scripts/run-in-docker.sh make --quiet test-werks

test-code-quality: test-license-headers test-pipfile test-file-content test-werks

test-code-quality-docker:
	../scripts/run-in-docker.sh make --quiet test-code-quality

test-mypy: prepare-protobuf-files
	cd .. ; scripts/run-mypy $(MYPY_ADDOPTS) $(ADDITIONAL_MYPY_ARGS) $$($(FIND_PYTHON_FILES))

test-mypy-raw:
	$(MAKE) test-mypy ADDITIONAL_MYPY_ARGS="--config-file=$(realpath ../mypy-raw.ini)"

test-mypy-docker:
	../scripts/run-in-docker.sh make test-mypy

test-packaging:
	$(PYTEST) -T packaging packaging

test-pipenv-deps:
	$(PIPENV) check

test-pylint: prepare-protobuf-files
	cd ..; $(PIPENV) run pylint --jobs=6 $(PYLINT_ARGS) $$($(FIND_PYTHON_FILES))

test-pylint-docker:
	../scripts/run-in-docker.sh make --quiet test-pylint

test-shellcheck:
	cd .. && shellcheck -x $(SHELLCHECK_OUTPUT_ARGS) $$($(FIND_SHELL_FILES))

test-shellcheck-docker:
	../scripts/run-in-docker.sh make --quiet test-shellcheck

test-cycles:
	$(CYCLES) \
		--packages \
		    cmk \
		    omd/packages/omd/omdlib \
		    packages/cmk-agent-based/cmk/agent_based \
		    packages/cmk-agent-receiver/cmk/agent_receiver \
		    packages/cmk-graphing/cmk/graphing \
		    packages/cmk-werks/cmk/werks \
		    packages/cmk-werks/cmk/trace \
		--project-path $$(realpath -L ..) \
		--strategy johnson \
		--verbose

test-cycles-docker:
	../scripts/run-in-docker.sh make --quiet test-cycles

test-unit-omdlib:
	cd .. && TZ=$(RANDOM_TZ) $(PYTEST) \
		-T unit \
		--config-file=pyproject.toml \
		--doctest-modules \
		--override-ini="pythonpath=. omd/packages/omd/" \
		$(PYTEST_OPTS_UNIT_SKIP_SLOW) \
		-- \
		omd/packages/omd/ \
		tests/unit/omdlib/

test-unit-doctests: prepare-protobuf-files
	# Different files with the same name but in different namespace packages
	# confuse our tooling.  Let's help by removing those caches as indicated
	# in the error message.
	find ../cmk/ -name '__pycache__' -exec rm -rf {} \; 2> /dev/null || true
	# The `consider_namespace_packages` option requires pytest >= 8.1
	cd .. && TZ=$(RANDOM_TZ) $(PYTEST) \
		-T unit \
		--config-file=pyproject.toml \
		--doctest-modules \
		--override-ini="pythonpath=." \
		--override-ini="consider_namespace_packages=true" \
		$(PYTEST_OPTS_UNIT_SKIP_SLOW) \
		-- \
		cmk/

test-unit: prepare-protobuf-files test-unit-doctests
	cd .. && TZ=$(RANDOM_TZ) $(PYTEST) \
		-T unit \
		--config-file=pyproject.toml \
		--override-ini="pythonpath=." \
		--random-order-bucket=global \
		$(PYTEST_OPTS_UNIT_SKIP_SLOW) \
		--ignore=tests/unit/omdlib/ \
		--numprocesses=4 \
		--dist=loadfile \
		-- \
		tests/unit

test-unit-docker:
	../scripts/run-in-docker.sh make --quiet test-unit

test-unit-all: prepare-protobuf-files
	cd .. && TZ=$(RANDOM_TZ) $(PYTEST) \
		-T unit \
		--config-file=pyproject.toml \
		--override-ini="pythonpath=." \
		--random-order-bucket=global \
		--ignore=tests/unit/omdlib/ \
		--numprocesses=4 \
		--dist=loadfile \
		-- \
		tests/unit

test-unit-all-docker:
	../scripts/run-in-docker.sh make --quiet test-unit-all

test-unit-testlib:
	find -name '__pycache__' -exec rm -rf {} \; 2> /dev/null || true
	cd .. && TZ=$(RANDOM_TZ) $(PYTEST) \
		-T testlib \
		--config-file=pyproject.toml \
		--doctest-modules \
		--override-ini="pythonpath=." \
		--override-ini="consider_namespace_packages=true" \
		$(PYTEST_OPTS_UNIT_SKIP_SLOW) \
		-- \
		tests/testlib/

test-unit-testlib-docker:
	../scripts/run-in-docker.sh make test-unit-testlib

test-agent-plugin-docker:
	../scripts/run-in-docker.sh make $(foreach VERS,$(AGENT_PLUGIN_PYTHON_VERSIONS),test-agent-plugin-unit-py$(VERS)-docker)

test-unit-coverage-html: prepare-protobuf-files
	cd .. && TZ=$(RANDOM_TZ) $(PYTEST) \
		-T unit \
		--config-file=pyproject.toml \
		--import-mode=importlib \
		--override-ini="pythonpath=." \
		--cov=cmk \
		--cov-report=html \
		--cov-config="tests/.coveragerc_unit" \
		--no-cov-on-fail \
		$(PYTEST_OPTS_UNIT_SKIP_SLOW) \
		--ignore=tests/unit/omdlib/ \
		-- \
		tests/unit

test-unit-shell:
	./unit-shell/runner.sh

test-unit-shell-docker:
	../scripts/run-in-docker.sh make test-unit-shell

test-unit-neb:
	cd ../packages/neb/test && ./.f12

test-unit-cmc:
	cd ../packages/cmc/test && ./.f12

test-find-dirty-files-in-git:
	scripts/find_dirty_files_in_git

test-flake8: ../.flake8
	cd ..; $(PIPENV) run flake8 --jobs=6 $$($(FIND_PYTHON_FILES))

# Run `validate_changes` in live-mode i.e. not creating a JSON file
# containing build steps to be executed by Jenkins but directly running
# them.
what-gerrit-makes:
	WORKSPACE="$$(git rev-parse --show-toplevel)" ; \
	cd "$$WORKSPACE" ; \
	mkdir -p "$$WORKSPACE/results" ; \
	scripts/run-pipenv run buildscripts/scripts/validate_changes.py \
	    -e BASE_COMMIT_ID=origin/master \
	    -e WORKSPACE="$$WORKSPACE" \
	    -e RESULTS="$$WORKSPACE/results"
