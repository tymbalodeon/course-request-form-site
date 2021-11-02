from __future__ import print_function

import logging

from django.db.models import Q

from canvas.api import get_canvas, get_user_courses
from course.models import CanvasSite, Profile, Request, User
from data_warehouse.data_warehouse import get_staff_account
from helpers.helpers import separate_year_and_term

logging.basicConfig(
    filename="logs/users.log",
    format="(%(asctime)s) %(levelname)s - %(message)s",
    level=logging.DEBUG,
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


def get_user_by_pennkey(pennkey):
    if isinstance(pennkey, str):
        pennkey = pennkey.lower()

    try:
        user = User.objects.get(username=pennkey)
    except User.DoesNotExist:
        account_values = get_staff_account(penn_key=pennkey)

        if account_values:
            first_name = account_values["first_name"].title()
            last_name = account_values["last_name"].title()
            user = User.objects.create_user(
                username=pennkey,
                first_name=first_name,
                last_name=last_name,
                email=account_values["email"],
            )
            Profile.objects.create(user=user, penn_id=account_values["penn_id"])
            print(f'CREATED Profile for "{pennkey}".')
        else:
            user = None
            print(f'FAILED to create Profile for "{pennkey}".')

    return user


def update_sites_info(year_and_term):
    year, term = separate_year_and_term(year_and_term)
    canvas_sites = Request.objects.filter(~Q(canvas_instance__isnull=True)).filter(
        status="COMPLETED",
        course_requested__year=year,
        course_requested__course_term=term,
    )
    canvas = get_canvas()

    for canvas_site in canvas_sites:
        crf_canvas_site = canvas_site.canvas_instance

        try:
            site = canvas.get_course(crf_canvas_site.canvas_id)

            if site.name != crf_canvas_site.name:
                crf_canvas_site.name = site.name
                crf_canvas_site.save()

            if site.workflow_state != crf_canvas_site.workflow_state:
                crf_canvas_site.workflow_state = site.workflow_state
                crf_canvas_site.save()
        except Exception:
            print("ERROR: Failed to find Canvas site: {crf_canvas_site.sis_course_id}")
            crf_canvas_site.workflow_state = "deleted"
            crf_canvas_site.save()


def update_user_courses(penn_key):
    canvas_courses = get_user_courses(penn_key)

    for canvas_course in canvas_courses:
        try:
            course = CanvasSite.objects.update_or_create(
                canvas_id=str(canvas_course.id),
                workflow_state=canvas_course.workflow_state,
                sis_course_id=canvas_course.sis_course_id,
                name=canvas_course.name,
            )
            course[0].owners.add(User.objects.get(username=penn_key))
        except Exception as error:
            print(f"FAILED to add course {canvas_course} ({error}).")


def process_canvas():
    for user in User.objects.all():
        print(f") Adding courses for {user.username}...")
        update_user_courses(user.username)
