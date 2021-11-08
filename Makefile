MANAGE = python manage.py
REQUIREMENTS = requirements.txt
LOCAL_PORT = http://localhost:8000
TEST = test tests
COVERAGE = coverage run manage.py $(TEST) && coverage report --skip-covered --sort=cover
YEAR := $(shell date +%Y)
MONTH := $(shell date +%m)
TERM := $(shell if (( $(MONTH) > 8 )); \
					then echo "C"; \
				elif (( $(MONTH) -gt 5 )); \
					then echo "B"; \
				else echo "A"; \
				fi)
ifeq (TERM, A)
NEXT_TERM = B
NEXT_YEAR = $(YEAR)
else ifeq (TERM, B)
NEXT_TERM = C
NEXT_YEAR = $(YEAR)
else
NEXT_TERM = A
NEXT_YEAR := $(shell expr $(YEAR) + 1)
endif
LOG_PROGRAM = '$$1==level {for (i = 4; i < 7; i++) $$i=""; gsub(/ {2,}/, " "); print $$0}'
LOG_FILE = ./logs/crf.log
TAIL = $(TAIL)

all: help
black: ## Format code
	black --experimental-string-processing ./

check: ## Check for problems
	pre-commit run -a

check-django: ## Check for Django project problems
	$(MANAGE) check

courses: ## Populate the database with the current term's courses
	$(MANAGE) add_courses -t $(YEAR)$(TERM) -odi && \
	$(MANAGE) add_courses -t $(NEXT_YEAR)$(NEXT_TERM) -odi

coverage: ## Show the coverage report
ifdef fail-under
	$(COVERAGE) --fail-under $(fail-under)
else ifdef search
	$(COVERAGE) -m | grep $(search)
else
	$(COVERAGE)
endif

coverage-html: ## Open the coverage report in the browser
	coverage html && open htmlcov/index.html

coverage-missing: ## Show the coverage report with missing-lines
	$(COVERAGE) -m

db: ## Open the database shell
	$(MANAGE) dbshell

flake: ## Lint code
	flake8 ./

format: isort black ## Format code

freeze: ## Freeze the dependencies to the requirements.txt file
	pip freeze > $(REQUIREMENTS)

help: ## Display the help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## Install the dependencies from the requirements.txt file
	pip install -r $(REQUIREMENTS)

isort: ## Sort imports
	isort ./

launch: ## Run the app and open the browser
	open $(LOCAL_PORT) && $(MANAGE) runserver

live: ## Start the livereload server
	$(MANAGE) livereload

log-apache: ## Print the tail of the apache log file
	$(TAIL) /var/log/crf2/crf2_error.log

log: ## Print the tail of the crf log
	$(TAIL) $(LOG_FILE)

log-error: ## Print the tail of only ERROR messages in the crf log
	awk -v level="[ERROR]" $(LOG_PROGRAM) $(LOG_FILE) | $(TAIL)

log-info: ## Print the tail of only  INFO messages in the crf log
	awk -v level="[INFO]" $(LOG_PROGRAM) $(LOG_FILE) | $(TAIL)

log-warning: ## Print the tail of only WARNING messages in the crf log
	awk -v level="[WARNING]" $(LOG_PROGRAM) $(LOG_FILE) | $(TAIL)

migrate: ## Migrate the database
	$(MANAGE) migrate

migration: ## Make the database migrations
	$(MANAGE) makemigrations

migrations: migration migrate ## Make migrations and migrate

mypy: ## Type-check code
	pre-commit install && pre-commit run mypy -a

populate: schools subjects courses ## Populate the database with schools, subjects, and courses

restart: migrations static ## Restart the app
	touch /home/django/crf2/crf2/wsgi.py

run: ## Run the app
	$(MANAGE) runserver

schools: ## Populate the database with schools
	$(MANAGE) add_schools

shell: ## Open an app-aware python shell
	$(MANAGE) shell_plus

.PHONY: static
static: ## Collect static files
	$(MANAGE) collectstatic --no-input

start: install migrations superuser populate run ## Run everything necessary to start the project from scratch

subjects: ## Populate the database with subjects
	$(MANAGE) add_subjects -o

superuser: ## Create a user with admin privileges
	$(MANAGE) createsuperuser

test: ## Run the test suite
	$(MANAGE) $(TEST) -v 2
