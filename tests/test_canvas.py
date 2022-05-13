from dataclasses import dataclass
from unittest.mock import patch

from canvasapi.account import Account
from canvasapi.exceptions import CanvasException
from canvasapi.user import User as CanvasUser
from django.test import TestCase

from config.config import TEST_KEY, TEST_URL
from form.canvas import (
    MAIN_ACCOUNT_ID,
    get_all_canvas_accounts,
    get_canvas,
    get_canvas_main_account,
    get_canvas_user_by_login_id,
    get_canvas_user_id_by_pennkey,
)

CANVAS_MODULE = "form.canvas"
GET_CANVAS = f"{CANVAS_MODULE}.get_canvas"
LOGIN_ID = "testuser"
SUB_ACCOUNTS = ["SubAccount"]


@dataclass
class MockCanvas:
    @staticmethod
    def get_user(login_id, login_type):
        if login_id == LOGIN_ID and login_type == "sis_login_id":
            return CanvasUser(None, {"login_id": login_id})
        else:
            raise CanvasException("")

    @staticmethod
    def get_account(account_id):
        if account_id == MAIN_ACCOUNT_ID:
            return Account(None, {"id": MAIN_ACCOUNT_ID})


@dataclass
class MockAccount:
    @staticmethod
    def get_subaccounts(recursive: bool):
        if recursive:
            return SUB_ACCOUNTS


class CanvasApiTest(TestCase):
    user_id = 1234567

    def test_get_canvas(self):
        canvas = get_canvas()
        self.assertEqual(canvas._Canvas__requester.original_url, TEST_URL)
        self.assertEqual(canvas._Canvas__requester.access_token, TEST_KEY)

    @patch(GET_CANVAS)
    def test_get_canvas_main_account(self, mock_get_canvas):
        mock_get_canvas.return_value = MockCanvas()
        main_account = get_canvas_main_account()
        self.assertEqual(main_account.id, MAIN_ACCOUNT_ID)

    @patch(f"{CANVAS_MODULE}.get_canvas_main_account")
    def test_get_all_canvas_accounts(self, mock_get_canvas_main_account):
        mock_get_canvas_main_account.return_value = MockAccount()
        sub_accounts = get_all_canvas_accounts()
        self.assertEqual(sub_accounts, SUB_ACCOUNTS)

    @patch(GET_CANVAS)
    def test_get_canvas_user_by_login_id(self, mock_get_canvas):
        mock_get_canvas.return_value = MockCanvas()
        user = get_canvas_user_by_login_id(LOGIN_ID)
        self.assertIsInstance(user, CanvasUser)
        self.assertEqual(user.login_id, LOGIN_ID)
        user = get_canvas_user_by_login_id("")
        self.assertIsNone(user)

    @patch(f"{CANVAS_MODULE}.get_canvas_user_by_login_id")
    def test_get_canvas_user_id_by_pennkey(self, mock_get_canvas_user_by_login_id):
        mock_get_canvas_user_by_login_id.return_value = CanvasUser(
            None, {"id": self.user_id, "login_id": LOGIN_ID}
        )
        user_id = get_canvas_user_id_by_pennkey(LOGIN_ID)
        self.assertEqual(user_id, self.user_id)
        mock_get_canvas_user_by_login_id.return_value = None
        user_id = get_canvas_user_id_by_pennkey(LOGIN_ID)
        self.assertIsNone(user_id)
