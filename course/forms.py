from dal.autocomplete import ModelSelect2
from django.contrib.auth.models import User
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

from course.models import CanvasSite, Subject


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
        "email_mismatch": "The two email addresses fields didn't match.",
        "not_changed": "The email address is the same as the one already defined.",
    }
    new_email_one = EmailField(
        label="New email address",
        widget=EmailInput,
    )
    new_email_two = EmailField(
        label="New email address confirmation",
        widget=EmailInput,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(EmailChangeForm, self).__init__(*args, **kwargs)

    def clean_new_email1(self):
        old_email = self.user.email
        new_email = self.cleaned_data.get("new_email1")

        if new_email and old_email and new_email == old_email:
            raise ValidationError(
                self.error_messages["not_changed"],
                code="not_changed",
            )

        return new_email

    def clean_new_email2(self):
        new_email_one = self.cleaned_data.get("new_email1")
        new_email_two = self.cleaned_data.get("new_email2")
        if new_email_one and new_email_two and new_email_one != new_email_two:
            raise ValidationError(
                self.error_messages["email_mismatch"],
                code="email_mismatch",
            )

        return new_email_two

    def save(self, commit=True):
        email = self.cleaned_data["new_email1"]
        self.user.email = email

        if commit:
            self.user.save()

        return self.user
