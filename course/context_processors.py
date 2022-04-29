def user_permissions(request):
    return {"staff": request.user.is_staff}
