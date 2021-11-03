from dal.autocomplete import ModelSelect2
from django.forms import (
    CharField,
    EmailField,
    EmailInput,
    Form,
    ModelChoiceField,
    ModelForm,
    Textarea,
    ValidationError,
)

from .models import CanvasSite, Subject, User


class ContactForm(Form):
    contact_name = CharField(required=True)
    contact_email = EmailField(required=True)
    content = CharField(required=True, widget=Textarea)


class UserForm(ModelForm):
    username = ModelChoiceField(
        queryset=User.objects.all(),
        widget=ModelSelect2(url="user-autocomplete"),
    )

    class Meta:
        model = User
        fields = "__all__"


class SubjectForm(ModelForm):
    abbreviation = ModelChoiceField(
        label="Abbreviation",
        queryset=Subject.objects.all(),
        required=False,
        widget=ModelSelect2(url="subject-autocomplete"),
    )

    class Meta:
        model = Subject
        fields = "__all__"


class CanvasSiteForm(ModelForm):
    name = ModelChoiceField(
        label="content_copy",
        queryset=CanvasSite.objects.all(),
        required=False,
        widget=ModelSelect2(
            url="canvas_site-autocomplete",
            attrs={"data-placeholder": "Type to search for a course title..."},
        ),
        to_field_name="canvas_id",
    )

    class Meta:
        model = CanvasSite
        fields = "__all__"


class EmailChangeForm(Form):
    error_messages = {
        "email_mismatch": (
            "Confirmation does not match. Please confirm that you input the new email"
            " correctly."
        ),
        "not_changed": (
            "Email is the same as your existing email. Please choose an email different"
            " from the one currently set."
        ),
    }
    new_email = EmailField(
        label="New email address",
        widget=EmailInput,
    )
    new_email_confirmation = EmailField(
        label="Confirm email",
        widget=EmailInput,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(EmailChangeForm, self).__init__(*args, **kwargs)

    def clean_new_email(self):
        old_email = self.user.email
        new_email = self.cleaned_data.get("new_email")

        if new_email and old_email and new_email == old_email:
            raise ValidationError(
                self.error_messages["not_changed"],
                code="not_changed",
            )

        return new_email

    def clean_new_email_confirmation(self):
        new_email = self.cleaned_data.get("new_email")
        new_email_confirmation = self.cleaned_data.get("new_email_confirmation")

        if new_email and new_email_confirmation and new_email != new_email_confirmation:
            raise ValidationError(
                self.error_messages["email_mismatch"],
                code="email_mismatch",
            )

        return new_email_confirmation

    def save(self, commit=True):
        email = self.cleaned_data["new_email"]
        self.user.email = email

        if commit:
            self.user.save()

        return self.user
