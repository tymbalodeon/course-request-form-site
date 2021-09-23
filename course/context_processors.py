from django.contrib.auth.models import User
from rest_framework import generics, permissions


def user_permissions(request):
    value = request.user.is_staff

    return {
        "staff": value,
    }
