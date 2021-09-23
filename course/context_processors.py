def user_permissions(request):
    value = request.user.is_staff

    return {
        "staff": value,
    }
