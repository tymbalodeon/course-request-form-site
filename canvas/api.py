from logging import getLogger

from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

from config.config import PROD_KEY, PROD_URL, TEST_KEY, TEST_URL

MAIN_ACCOUNT_ID = 96678

logger = getLogger(__name__)


def get_canvas(test=False):
    return Canvas(TEST_URL if test else PROD_URL, TEST_KEY if test else PROD_KEY)


def get_canvas_account(account_id, test=False):
    try:
        return get_canvas(test).get_account(account_id)
    except CanvasException:
        return None


def create_canvas_user(penn_key, penn_id, email, full_name, test=False):
    pseudonym = {"sis_user_id": penn_id, "unique_id": penn_key}

    try:
        account = get_canvas_account(MAIN_ACCOUNT_ID, test=test)

        if not account:
            return None

        user = account.create_user(pseudonym, user={"name": full_name})
        user.edit(user={"email": email})

        return user
    except CanvasException as error:
        logger.error(
            f"- ERROR: Failed to create canvas user {full_name}, {penn_key} ({error}) "
        )

        return None


def get_user_by_sis(login_id, test=False):
    try:
        return get_canvas(test).get_user(login_id, "sis_login_id")
    except CanvasException:
        return None


def get_user_courses(login_id):
    user = get_user_by_sis(login_id)

    return user.get_courses(enrollment_type="teacher") if user else []


def get_term_id(account_id, sis_term_id, test=False):
    try:
        account = get_canvas_account(account_id, test=test)
        response = account._requester.request(
            "GET", f"accounts/{account_id}/terms/sis_term_id:{sis_term_id}"
        )

        return response.json()["id"]
    except Exception:
        return None
