run:
	python manage.py runserver

migration:
	python manage.py makemigrations

migrate:
	python manage.py migrate

superuser:
	python manage.py createsuperuser

.PHONY: static
static:
	python manage.py collectstatic --no-input
