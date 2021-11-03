from data_warehouse.data_warehouse import get_staff_account

from .models import Profile, User


def get_user_by_pennkey(pennkey):
    if isinstance(pennkey, str):
        pennkey = pennkey.lower()

    try:
        user = User.objects.get(username=pennkey)
    except User.DoesNotExist:
        account_values = get_staff_account(penn_key=pennkey)

        if account_values:
            first_name = account_values["first_name"].title()
            last_name = account_values["last_name"].title()
            user = User.objects.create_user(
                username=pennkey,
                first_name=first_name,
                last_name=last_name,
                email=account_values["email"],
            )
            Profile.objects.create(user=user, penn_id=account_values["penn_id"])
            print(f'CREATED Profile for "{pennkey}".')
        else:
            user = None
            print(f'FAILED to create Profile for "{pennkey}".')

    return user
