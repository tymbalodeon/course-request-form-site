from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .celery import app as celery_app


@receiver(user_logged_in)
def on_login(sender, user, request, **kwargs):
    print(f'"{user.username}" logging in...')
    request.session["on_behalf_of"] = ""
    messages.info(request, "Welcome!")


__all__ = ("celery_app",)
