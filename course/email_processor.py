from helpers.helpers import get_config_value
import logging

from django.core.mail import EmailMessage
from django.template.loader import get_template

from course.models import User


def get_email(pennkey):
    try:
        user_email = User.objects.get(username=pennkey).email

        if user_email == "":
            user_email = "None"
    except User.DoesNotExist:
        user_email = ""
        logging.critical(f"ERROR: Could not find {pennkey} in system.")

    return user_email


def feedback(context):
    template = get_template("email/feedback.txt")
    content = template.render(context)
    email = EmailMessage(
        subject="CRF Feedback from " + context["contact_name"],
        body=content,
        to=["mfhodges@upenn.edu"],
    )
    email.send()


def course_created_canvas(context):
    template = get_template("email/course_created_canvas.txt")
    content = template.render(context)
    email = EmailMessage(
        subject="CRF Notification: Course Request Completed ("
        + context["course_code"]
        + ")",
        body=content,
        to=list(map(lambda x: get_email(x), listcontext["instructors"]))
        + get_email(context["requestor"]),
    )
    email.send()


def admin_lock(context):
    admin_email = get_config_value("users", "email")
    template = get_template("email/admin_lock.txt")
    content = template.render(context)
    email = EmailMessage(
        subject="CRF notification locked request",
        body=content,
        to=[admin_email],
    )
    email.send()


def request_submitted_onbehalf(context):
    template = get_template("email/request_submitted_onbehalf.txt")
    content = template.render(context)
    email = EmailMessage(
        subject="CRF Notification: Course Request (" + context["course_code"] + ")",
        cc=[context["requestor"]],
        body=content,
        to=[get_email(context["masquerade"])],
    )
    email.send()


def request_submitted(context):
    template = get_template("email/request_submitted.txt")
    content = template.render(context)
    email = EmailMessage(
        subject="CRF Notification: Course Request (" + context["course_code"] + ")",
        body=content,
        to=[get_email(context["requestor"])],
    )
    email.send()


def autoadd_contact(context):
    template = get_template("email/autoadd_contact.txt")
    content = template.render(context)
    email = EmailMessage(
        subject="CRF Notification: Added as Auto-Add Contact",
        body=content,
        to=[get_email(context["user"])],
    )
    email.send()


def added_to_request(context):
    template = get_template("email/added_to_request.txt")
    content = template.render(context)
    email = EmailMessage(
        subject="CRF Notification: Added to Course Request",
        body=content,
        to=[get_email(context["user"])],
    )
    email.send()


def main():
    logging.basicConfig(
        filename="course/static/logs/emails.log", format="%(asctime)s %(message)s"
    )
