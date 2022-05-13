MANAGE = python manage.py
REQUIREMENTS = requirements.txt
TEST = test tests
TEST_VERBOSE_LEVEL = -v 2
COVERAGE = coverage run manage.py $(TEST) && coverage report -m
SYNC = $(MANAGE) sync

all: help

package:
	pip install $(package)

add: package freeze ## pip install package and freeze it into requirements file (arg: `package`)

check: ## Check for Django project problems
	$(MANAGE) check

coverage: ## Show the coverage report (arg: `fail-under`)
ifdef fail-under
	$(COVERAGE) --fail-under $(fail-under)
else ifdef search
	$(COVERAGE) -m | grep $(search)
else
	$(COVERAGE)
endif

coverage-html: ## Open the coverage report in the browser
	coverage html && open htmlcov/index.html

help: ## Display the help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

freeze: ## Freeze the dependencies to the requirements.txt file
	pip freeze > $(REQUIREMENTS)

install: ## Install the dependencies from the requirements.txt file
	pip install -r $(REQUIREMENTS)

migrations: ## Make migrations and migrate
	$(MANAGE) makemigrations && $(MANAGE) migrate

run: ## Run the development server
	$(MANAGE) runserver

sections: ## Sync sections from Pennant Student Records
	$(SYNC) --sections

schedule-types: ## Sync schedule types from Pennant Student Records
	$(SYNC) --schedule-types

schools: ## Sync schools from Pennant Student Records
	$(SYNC) --schools

shell: ## Open an app-aware python shell
	$(MANAGE) shell_plus --bpython

.PHONY: static
static: ## Collect static files
	$(MANAGE) collectstatic --clear --no-input

subjects: ## Sync subjects from Pennant Student Records
	$(SYNC) --subjects

sync: ## Sync data from Pennant Student Records
	$(SYNC)

sync-constants: schedule-types schools subjects ## Sync schedule types, schools, and subjects

test: ## Run the test suite (args: `module`, `class`)
ifdef module
ifdef class
ifdef method
	$(MANAGE) $(TEST).test_$(module).$(class)Test.test_$(method) $(TEST_VERBOSE_LEVEL)
else
	$(MANAGE) $(TEST).test_$(module).$(class)Test $(TEST_VERBOSE_LEVEL)
endif
else
	$(MANAGE) $(TEST).test_$(module) $(TEST_VERBOSE_LEVEL)
endif
else
	$(MANAGE) $(TEST) $(TEST_VERBOSE_LEVEL)
endif
