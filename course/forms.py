from dal import autocomplete
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

from course.models import AdditionalEnrollment, CanvasSite, Subject


# our new form
class ContactForm(Form):
    contact_name = CharField(required=True)
    contact_email = EmailField(required=True)
    content = CharField(required=True, widget=Textarea)


class UserForm(ModelForm):
    # please only use this when you need to auto complete on the name field !
    username = ModelChoiceField(
        label="user",
        queryset=User.objects.all(),
        # required=False,
        widget=autocomplete.ModelSelect2(url="user-autocomplete"),
    )

    class Meta:
        model = User
        fields = "__all__"


class SubjectForm(ModelForm):
    # please only use this when you need to auto complete on the name field !
    abbreviation = ModelChoiceField(
        label="Abbreviation",
        queryset=Subject.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(url="subject-autocomplete"),
    )

    class Meta:
        model = Subject
        fields = "__all__"


class CanvasSiteForm(ModelForm):
    # please only use this when you need to auto complete on the name field !
    name = ModelChoiceField(
        label="content_copy",
        queryset=CanvasSite.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(url="canvas_site-autocomplete"),
    )

    class Meta:
        model = CanvasSite
        fields = "__all__"


class EmailChangeForm(Form):
    """
    A form that lets a user change set their email while checking for a change in the
    e-mail.
    """

    error_messages = {
        "email_mismatch": "The two email addresses fields didn't match.",
        "not_changed": "The email address is the same as the one already defined.",
    }

    new_email1 = EmailField(
        label="New email address",
        widget=EmailInput,
    )

    new_email2 = EmailField(
        label="New email address confirmation",
        widget=EmailInput,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        # print(self.user)
        super(EmailChangeForm, self).__init__(*args, **kwargs)

    def clean_new_email1(self):
        old_email = self.user.email
        new_email1 = self.cleaned_data.get("new_email1")
        if new_email1 and old_email:
            if new_email1 == old_email:
                raise ValidationError(
                    self.error_messages["not_changed"],
                    code="not_changed",
                )
        return new_email1

    def clean_new_email2(self):
        new_email1 = self.cleaned_data.get("new_email1")
        new_email2 = self.cleaned_data.get("new_email2")
        if new_email1 and new_email2:
            if new_email1 != new_email2:
                # print("yeahgggggg")
                raise ValidationError(
                    self.error_messages["email_mismatch"],
                    code="email_mismatch",
                )
        return new_email2

    def save(self, commit=True):
        email = self.cleaned_data["new_email1"]
        self.user.email = email
        if commit:
            self.user.save()
        return self.user
