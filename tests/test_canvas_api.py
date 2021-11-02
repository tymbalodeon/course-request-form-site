from django.test import TestCase

from canvas.api import get_user_by_sis
from helpers.helpers import get_config_username


class CanvasAPITest(TestCase):
    username = get_config_username()

    def setUp(self):
        pass

    def test_get_user_by_sis(self):
        canvas_user = get_user_by_sis(self.username)
        self.assertTrue(bool(canvas_user))
        self.assertEqual(canvas_user.login_id, self.username)
        none_user = get_user_by_sis("noneuser")
        self.assertFalse(bool(none_user))
