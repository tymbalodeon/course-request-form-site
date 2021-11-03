from logging import getLogger

from django.core.mail import EmailMessage
from django.template.loader import get_template

from config.config import EMAIL

from .models import User

logger = getLogger(__name__)


def get_email(pennkey):
    try:
        user_email = User.objects.get(username=pennkey).email

        if not user_email:
            user_email = None
    except User.DoesNotExist:
        user_email = None
        logger.critical(f"ERROR: Could not find {pennkey} in system.")

    return user_email


def feedback(context):
    template = get_template("email/feedback.txt")
    content = template.render(context)
    email = EmailMessage(
        subject=f"CRF Feedback from {context['contact_name']}",
        body=content,
        to=["mfhodges@upenn.edu"],
    )
    email.send()


def course_created_canvas(context):
    template = get_template("email/course_created_canvas.txt")
    content = template.render(context)
    instructor_emails = [get_email(instructor) for instructor in context["instructors"]]
    email = EmailMessage(
        subject=(
            f"CRF Notification: Course Request Completed ({context['course_code']})"
        ),
        body=content,
        to=instructor_emails.append(get_email(context["requestor"])),
    )
    email.send()


def admin_lock(context):
    admin_email = EMAIL
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
    masquerade_email = get_email(context["masquerade"])
    email = EmailMessage(
        subject=f"CRF Notification: Course Request ({context['course_code']})",
        cc=[context["requestor"]],
        body=content,
        to=[masquerade_email] if masquerade_email else [],
    )
    email.send()


def request_submitted(context):
    template = get_template("email/request_submitted.txt")
    content = template.render(context)
    requestor_email = get_email(context["requestor"])
    email = EmailMessage(
        subject=f"CRF Notification: Course Request ({context['course_code']})",
        body=content,
        to=[requestor_email] if requestor_email else [],
    )
    email.send()


def autoadd_contact(context):
    template = get_template("email/autoadd_contact.txt")
    content = template.render(context)
    user_email = get_email(context["user"])
    email = EmailMessage(
        subject="CRF Notification: Added as Auto-Add Contact",
        body=content,
        to=[user_email] if user_email else [],
    )
    email.send()


def added_to_request(context):
    template = get_template("email/added_to_request.txt")
    content = template.render(context)
    user_email = get_email(context["user"])
    email = EmailMessage(
        subject="CRF Notification: Added to Course Request",
        body=content,
        to=[user_email] if user_email else [],
    )
    email.send()
