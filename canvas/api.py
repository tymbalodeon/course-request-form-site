from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

from helpers.helpers import get_config_values

URL_PROD, TOKEN_PROD, URL_TEST, TOKEN_TEST = get_config_values("canvas")


def get_canvas(test=False):
    return Canvas(
        URL_PROD if not test else URL_TEST, TOKEN_PROD if not test else TOKEN_TEST
    )


def get_user_by_sis(login_id, test=False):
    canvas = get_canvas(test)

    try:
        login_id_user = canvas.get_user(login_id, "sis_login_id")

        return login_id_user
    except CanvasException:
        return None


def create_canvas_user(penn_key, penn_id, email, full_name, test=False):
    pseudonym = {"sis_user_id": penn_id, "unique_id": penn_key}

    try:
        account = find_account(96678, test=test)

        if not account:
            return None

        user = account.create_user(pseudonym, user={"name": full_name})
        user.edit(user={"email": email})

        return user
    except CanvasException as error:
        print(
            f"- ERROR: Failed to create canvas user {full_name}, {penn_key} ({error}) "
        )

        return None


def get_user_courses(login_id):
    user = get_user_by_sis(login_id)

    if user is None:
        return None

    return user.get_courses(enrollment_type="teacher")


def find_in_canvas(sis_section_id):
    canvas = Canvas(URL_PROD, TOKEN_PROD)

    try:
        section = canvas.get_section(sis_section_id, use_sis_id=True)
    except CanvasException:
        return None

    return section


def find_account(account_id, test=False):
    canvas = get_canvas(test)

    try:
        account = canvas.get_account(account_id)

        return account
    except CanvasException:
        return None


def find_term_id(account_id, sis_term_id, test=False):
    canvas = get_canvas(test)
    account = canvas.get_account(account_id)

    if account:
        response = account._requester.request(
            "GET", f"accounts/{account_id}/terms/sis_term_id:{sis_term_id}"
        )

        if response.status_code == 200:
            return response.json()["id"]
        else:
            return None
    else:
        return None
