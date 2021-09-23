def user_permissons(request):
    value = request.user.is_staff

    return {
        "staff": value,
    }
