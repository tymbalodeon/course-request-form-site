from django.forms import ValidationError
from django.test import TestCase

from config.config import EMAIL, USERNAME
from course.forms import EmailChangeForm
from course.models import User


class FormsTest(TestCase):
    new_email = f"test_{EMAIL}"
    new_email_confirmation = f"new_{EMAIL}"

    def setUp(self):
        User.objects.create_user(username=USERNAME, email=EMAIL)

    def get_validated_form(self, new_email, new_email_confirmation):
        form = EmailChangeForm(
            user=User.objects.get(username=USERNAME),
            data={
                "new_email": new_email,
                "new_email_confirmation": new_email_confirmation,
            },
        )
        form.is_valid()

        return form

    def get_validated_email(self, new_email, new_email_confirmation):
        form = self.get_validated_form(new_email, new_email_confirmation)

        return form.clean_new_email()

    def test_clean_new_email(self):
        self.get_validated_email(EMAIL, EMAIL)
        self.assertRaises(ValidationError)
        email = self.get_validated_email(self.new_email, self.new_email)
        self.assertEqual(email, self.new_email)

    def test_clean_new_email_confirmation(self):
        self.get_validated_email(self.new_email, self.new_email_confirmation)
        self.assertRaises(ValidationError)
        email = self.get_validated_email(self.new_email, self.new_email)
        self.assertEqual(email, self.new_email)

    def test_save(self):
        form = self.get_validated_form(self.new_email, self.new_email)
        user = form.save()
        self.assertEqual(user, User.objects.get(username=USERNAME))
