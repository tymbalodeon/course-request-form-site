from os import environ

from celery import Celery

environ.setdefault("DJANGO_SETTINGS_MODULE", "crf2.settings")
app = Celery("course")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request}")
