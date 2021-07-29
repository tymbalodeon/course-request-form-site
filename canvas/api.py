from configparser import ConfigParser

from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

config = ConfigParser()
config.read("config/config.ini")
URL_PROD = config.get("canvas", "prod_env")
URL_TEST = config.get("canvas", "test_env")
TOKEN_PROD = config.get("canvas", "prod_key")
TOKEN_TEST = config.get("canvas", "test_key")


def gen_header(test=False):
    return {"Authorization": f"Bearer {TOKEN_TEST if test else TOKEN_PROD}"}


def get_canvas(test=False):
    return Canvas(
        URL_PROD if not test else URL_TEST, TOKEN_PROD if not test else TOKEN_TEST
    )


def get_user_by_sis(login_id, test=False):
    canvas = get_canvas(test)

    try:
        login_id_user = canvas.get_user(login_id, "sis_login_id")

        return login_id_user
    except CanvasException as error:
        return None


def mycreate_user(pennkey, pennid, email, fullname, test=False):
    pseudonym = {"sis_user_id": pennid, "unique_id": pennkey}

    try:
        account = find_account(96678, test=test)
        user = account.create_user(pseudonym, user={"name": fullname})
        user.edit(user={"email": email})

        return user
    except CanvasException as e:

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
    except CanvasException as error:
        return None

    return section


def find_account(account_id, test=False):
    canvas = get_canvas(test)

    try:
        account = canvas.get_account(account_id)

        return account
    except CanvasException as error:
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


def search_course(terms):
    return None
