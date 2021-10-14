REQUIREMENTS = requirements.txt
MANAGE = python manage.py

freeze:
	pip freeze > $(REQUIREMENTS)

install:
	pip install -r $(REQUIREMENTS)

log:
	tail /var/log/crf2/crf2_error.log

migration:
	$(MANAGE) makemigrations

migrate:
	$(MANAGE) migrate

restart:
	touch /home/django/crf2/crf2/wsgi.py

run:
	$(MANAGE) runserver

shell:
	$(MANAGE) shell

.PHONY: static
static:
	$(MANAGE) collectstatic --no-input

superuser:
	$(MANAGE) createsuperuser
