from __future__ import print_function

import logging

import cx_Oracle
from canvas.api import create_canvas_user, get_canvas, get_user_by_sis, get_user_courses
from django.db.models import Q
from helpers.helpers import get_config_items

from course.models import CanvasSite, Profile, Request, User

LOG_FILENAME = "users.log"
logging.basicConfig(
    filename=LOG_FILENAME,
    format="(%(asctime)s) %(levelname)s:%(message)s",
    level=logging.DEBUG,
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


def data_warehouse_lookup(penn_key=None, penn_id=None):
    user, password, service = get_config_items("datawarehouse")
    connection = cx_Oracle.connect(user, password, service)
    cursor = connection.cursor()

    if penn_key:
        print(f"Checking Data Warehouse for pennkey {penn_key}...")

        cursor.execute(
            """
            SELECT
                first_name, last_name, email_address, penn_id
            FROM
                employee_general
            WHERE
                pennkey = :pennkey
            """,
            pennkey=penn_key,
        )

        for first_name, last_name, email, dw_penn_id in cursor:
            print(
                f'FOUND "{penn_key}": {first_name} {last_name} ({dw_penn_id})'
                f" {email.strip()}"
            )

            return {
                "firs_tname": first_name,
                "last_name": last_name,
                "email": email,
                "penn_id": dw_penn_id,
            }
    elif penn_id:
        print(f"Checking Data Warehouse for penn id {penn_id}...")

        cursor.execute(
            """
            SELECT
                first_name, last_name, email_address, pennkey
            FROM
                employee_general
            WHERE
                penn_id = :penn_id
            """,
            penn_id=penn_id,
        )

        for first_name, last_name, email, dw_penn_key in cursor:
            print(
                f'FOUND "{penn_id}": {first_name} {last_name} ({dw_penn_key})'
                f" {email.strip()}"
            )

            return {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "penn_key": penn_key,
            }
    else:
        print("Checking Data Warehouse: NO PENNKEY OR PENN ID PROVIDED.")

    return False


def validate_pennkey(pennkey):
    if isinstance(pennkey, str):
        pennkey = pennkey.lower()

    try:
        user = User.objects.get(username=pennkey)
    except User.DoesNotExist:
        userdata = data_warehouse_lookup(penn_key=pennkey)
        logging.warning(userdata)

        if userdata:
            first_name = userdata["first_name"].title()
            last_name = userdata["last_name"].title()
            user = User.objects.create_user(
                username=pennkey,
                first_name=first_name,
                last_name=last_name,
                email=userdata["email"],
            )
            Profile.objects.create(user=user, penn_id=userdata["penn_id"])
            print(f'CREATED Profile for "{pennkey}".')
        else:
            user = None
            print(f'FAILED to create Profile for "{pennkey}".')

    return user


def check_by_penn_id(PENN_ID):
    try:
        return Profile.objects.get(penn_id=PENN_ID).user
    except Exception:
        user_data = data_warehouse_lookup(penn_id=PENN_ID)

        if user_data:
            first_name = user_data["first_name"].title()
            last_name = user_data["last_name"].title()
            user = User.objects.create_user(
                username=user_data["penn_key"],
                first_name=first_name,
                last_name=last_name,
                email=user_data["email"],
            )
            Profile.objects.create(user=user, penn_id=PENN_ID)
        else:
            user = None
        return user


def update_user_courses(penn_key):
    canvas_courses = get_user_courses(penn_key)

    if canvas_courses:
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


def find_no_canvas_account():
    users = User.objects.all()

    for user in users:
        this_user = get_user_by_sis(user.username)

        if this_user is None:
            print(user.username)

            try:
                create_canvas_user(
                    user.username,
                    user.profile.penn_id,
                    user.email,
                    user.first_name + " " + user.last_name,
                )
            except Exception:
                userdata = data_warehouse_lookup(penn_key=user.username)

                if userdata:
                    Profile.objects.create(user=user, penn_id=userdata["penn_id"])
                    create_canvas_user(
                        user.username,
                        user.profile.penn_id,
                        user.email,
                        user.first_name + " " + user.last_name,
                    )


def update_sites_info(year_and_term):
    year = year_and_term[:4]
    year_and_term = year_and_term[-1]
    canvas_sites = Request.objects.filter(~Q(canvas_instance__isnull=True)).filter(
        status="COMPLETED",
        course_requested__year=year,
        course_requested__course_term=year_and_term,
    )

    for _canvas_site in canvas_sites:
        crf_canvas_site = _canvas_site.canvas_instance
        canvas = get_canvas()

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


def process_canvas():
    for user in User.objects.all():
        print(f") Adding courses for {user.username}...")
        update_user_courses(user.username)
