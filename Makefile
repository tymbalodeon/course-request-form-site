ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
REQUIREMENTS = requirements.txt
MANAGE = python manage.py
YEAR := $(shell date +%Y)
MONTH := $(shell date +%m)
TERM := $(shell if (( $(MONTH) > 8 )); \
					then echo "C"; \
				elif (( $(MONTH) -gt 5 )); \
					then echo "B"; \
				else echo "A"; \
				fi)

all: help

black: ## Format code
	black --experimental-string-processing $(ROOT_DIR)

check: ## Check for problems
	$(MANAGE) check

courses: ## Populate the database with the current term's courses
	$(MANAGE) add_courses -t $(YEAR)$(TERM) -o

db: ## Open the database shell
	$(MANAGE) dbshell

flake: ## Lint code
	flake8 $(ROOT_DIR)

format: isort black flake

freeze: ## Freeze the dependencies to the requirements.txt file
	pip freeze > $(REQUIREMENTS)

help: ## Display the help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## Install the dependencies from the requirements.txt file
	pip install -r $(REQUIREMENTS)

isort: ## Sort imports
	isort $(ROOT_DIR)

live: ## Start the livereload server
	$(MANAGE) livereload

log: ## View the last 100 lines of the log file
	tail -n 100 /var/log/crf2/crf2_error.log

migrate: ## Migrate the database
	$(MANAGE) migrate

migration: ## Make the database migrations
	$(MANAGE) makemigrations

migrations: migration migrate ## Make migrations and migrate

populate: migrations schools subjects courses ## Populate the database with schools, subjects, and courses

restart: migrations static ## Restart the app
	touch /home/django/crf2/crf2/wsgi.py

run: migrations ## Run the app
	$(MANAGE) runserver

schools: ## Populate the database with schools
	$(MANAGE) add_schools

shell: ## Open an app-aware python shell
	$(MANAGE) shell_plus

.PHONY: static
static: ## Collect static files
	$(MANAGE) collectstatic --no-input

subjects: ## Populate the database with subjects
	$(MANAGE) add_subjects -o

superuser: ## Create a user with admin privileges
	$(MANAGE) createsuperuser
