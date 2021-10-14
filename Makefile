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

courses:
	$(MANAGE) add_courses -t $(YEAR)$(TERM) -o

db:
	$(MANAGE) dbshell

deploy: install restart

freeze:
	pip freeze > $(REQUIREMENTS)

install:
	pip install -r $(REQUIREMENTS)

live:
	$(MANAGE) livereload

log:
	tail -n 100 /var/log/crf2/crf2_error.log

migrate:
	$(MANAGE) migrate

migration:
	$(MANAGE) makemigrations

migrations: migration migrate

populate: migrations schools subjects courses

pull:
	cd /home/django/crf2 && git pull

restart: migrations static
	touch /home/django/crf2/crf2/wsgi.py

run: migrations
	$(MANAGE) runserver

schools:
	$(MANAGE) add_schools

shell:
	$(MANAGE) shell

.PHONY: static
static:
	$(MANAGE) collectstatic --no-input

subjects:
	$(MANAGE) add_subjects -o

superuser:
	$(MANAGE) createsuperuser
