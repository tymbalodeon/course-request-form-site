from __future__ import absolute_import, unicode_literals

import time
from datetime import datetime
from logging import getLogger

from canvasapi.tab import Tab
from celery import task

from canvas.api import (
    create_canvas_user,
    get_canvas,
    get_canvas_account,
    get_term_id,
    get_user_by_sis,
)
from course import utils
from course.models import CanvasSite, Course, Request, User
from course.serializers import RequestSerializer
from data_warehouse.data_warehouse import (
    daily_sync,
    delete_canceled_courses,
    pull_instructors,
)
from helpers.helpers import MAIN_ACCOUNT_ID

LPS_ONLINE_ACCOUNT_ID = 132413
LIBRARIAN_ROLE_ID = "1383"
ENROLLMENT_TYPES = {
    "INST": "TeacherEnrollment",
    "instructor": "TeacherEnrollment",
    "TA": "TaEnrollment",
    "ta": "TaEnrollment",
    "DES": "DesignerEnrollment",
    "designer": "DesignerEnrollment",
    "LIB": "DesignerEnrollment",
    "librarian": "DesignerEnrollment",
}


@task()
def task_nightly_sync(term):
    start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    daily_sync(term)
    end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open("course/static/log/night_sync.log", "a") as log:
        log.write(f"Nighly Update for {term}: {start} - {end} \n")


@task()
def task_pull_instructors(term):
    pull_instructors(term)


@task()
def task_process_canvas():
    utils.process_canvas()


@task()
def task_update_sites_info(term):
    print(") Updating site info for {term} courses...")
    utils.sync_crf_canvas_sites(term)
    print("FINISHED")


@task()
def task_delete_canceled_courses(term):
    delete_canceled_courses(term)


@task()
def delete_canceled_requests():
    canceled_requests = Request.objects.filter(status="CANCELED")

    for request in canceled_requests:
        request.delete()


@task()
def check_for_account(penn_key):
    user = get_user_by_sis(penn_key)

    if user is None:
        try:
            crf_account = User.objects.get(username=penn_key)
            email = crf_account.email
            penn_id = crf_account.profile.pennid
            full_name = crf_account.get_full_name()
            canvas_account = create_canvas_user(penn_key, penn_id, email, full_name)

            return canvas_account if canvas_account else None
        except Exception as error:
            print(f"- ERROR: Failed to create canvas account for {penn_key} ({error}).")


def add_request_process_notes(message, request):
    start = ", " if request.process_notes else ""
    request.process_notes += f"{start}{message}"
    request.save()


def get_school_account(request, course_requested, test, verbose):
    account = get_canvas_account(
        LPS_ONLINE_ACCOUNT_ID
        if request.lps_online and course_requested.course_schools.abbreviation == "SAS"
        else course_requested.course_schools.canvas_subaccount,
        test=test,
    )

    if not account:
        add_request_process_notes("failed to locate Canvas Account", request)
        message = "\t- ERROR: failed to locate Canvas Account"
        getLogger("error_logger").error(message)

        if verbose:
            print(message)

    return account


def get_section_code(request, course_requested):
    if (
        course_requested.course_primary_subject.abbreviation
        == course_requested.course_subject.abbreviation
    ):
        return (
            f"{course_requested.course_subject.abbreviation}"
            f" {course_requested.course_number}-"
            f"{course_requested.course_section}"
            f" {course_requested.year}{course_requested.course_term}"
        )
    elif course_requested.primary_crosslist:
        return course_requested.srs_format_primary()
    else:
        add_request_process_notes("Primary crosslist not set", request)

        return None


def get_canvas_course(request, account, course, sis_course_id, test, verbose):
    already_exists = False
    canvas_course = None

    try:
        canvas_course = account.create_course(course=course)
    except Exception:
        try:
            canvas_course = get_canvas(test).get_course(sis_course_id, use_sis_id=True)
            canvas_course.update(course=course)
            already_exists = True
        except Exception as error:
            add_request_process_notes(
                "course site creation failed--check if it already exists",
                request,
            )
            message = f"\t- ERROR: failed to create site ({error})"
            getLogger("error_logger").error(message)

            if verbose:
                print(message)

    return already_exists, canvas_course


def set_storage_quota(request, canvas_course):
    try:
        canvas_course.update(course={"storage_quota_mb": 2000})
    except Exception:
        add_request_process_notes("course site quota not raised", request)


def create_section(
    request,
    course_requested,
    canvas_course,
    section_name,
    sis_course_id,
    additional_sections,
    verbose,
):
    try:
        section = {
            "course_section": canvas_course.create_course_section(
                course_section={
                    "name": section_name,
                    "sis_section_id": sis_course_id,
                },
                enable_sis_reactivation=True,
            ),
            "instructors": course_requested.instructors.all(),
        }
        created_section = section["course_section"]
        additional_sections += [section]

        return created_section, additional_sections
    except Exception as error:
        add_request_process_notes("failed to create section", request)
        message = f"\t- ERROR: failed to create section ({error})"
        getLogger("error_logger").error(message)

        if verbose:
            print(message)

        return "already exists", additional_sections


def handle_sections(
    request,
    serialized,
    canvas_course,
    course_title,
    additional_sections,
    sections,
    test,
    verbose,
):
    if sections:
        sections = [section.course_code for section in sections]

        try:
            serialized.data["additonal_sections"] = serialized.data[
                "additional_sections"
            ].extend(sections)
        except Exception:
            serialized.data["additional_sections"] = sections

    for section in serialized.data["additional_sections"]:
        section_course = Course.objects.get(course_code=section)

        if section_course.course_activity.abbr != "LEC":
            course_title = section_course.course_activity.abbr

        course_title = (
            f"{section_course.srs_format_primary(sis_id=False)} {course_title}"
        )
        sis_section = f"SRS_{section_course.srs_format_primary()}"
        additional_sections = create_section(
            request,
            section_course,
            canvas_course,
            course_title,
            sis_section,
            additional_sections,
            verbose,
        )[1]

    for section in additional_sections:
        for user in section["instructors"]:
            enroll_user(
                request,
                canvas_course,
                user,
                "instructor",
                section["course_section"].id,
                test,
            )


def enroll_user(request, canvas_course, user, role, course_section_id, test):
    try:
        username = user.username
        penn_id = user.profile.penn_id
        email = user.email
        full_name = (f"{user.first_name} {user.last_name}",)
    except Exception:
        crf_user = User.objects.get(username=user)
        username = user
        penn_id = crf_user.profile.penn_id
        email = crf_user.email
        full_name = f"{crf_user.first_name} {crf_user.last_name}"

    canvas_user = get_user_by_sis(username, test=test)

    if canvas_user is None:
        try:
            canvas_user = create_canvas_user(
                username,
                penn_id,
                email,
                full_name,
                test=test,
            )

            add_request_process_notes(f"created account for user: {username}", request)
        except Exception:
            add_request_process_notes(
                f"failed to create account for user: {username}",
                request,
            )
    elif role == "LIB" or role == "librarian":
        try:
            canvas_course.enroll_user(
                canvas_user.id,
                ENROLLMENT_TYPES[role],
                enrollment={
                    "course_section_id": course_section_id,
                    "role_id": LIBRARIAN_ROLE_ID,
                    "enrollment_state": "active",
                },
            )
        except Exception:
            add_request_process_notes(f"failed to add user: {user}", request)
    else:
        try:
            canvas_course.enroll_user(
                canvas_user.id,
                ENROLLMENT_TYPES[role],
                enrollment={
                    "course_section_id": course_section_id,
                    "enrollment_state": "active",
                },
            )
        except Exception:
            add_request_process_notes(f"failed to add user: {username}", request)


def set_reserves(request, canvas_course, verbose):
    try:
        tab = Tab(
            canvas_course._requester,
            {
                "course_id": canvas_course.id,
                "id": "context_external_tool_139969",
                "label": "Course Materials @ Penn Libraries",
            },
        )
        tab.update(hidden=False)

        if tab.visibility != "public":
            add_request_process_notes("failed to configure ARES", request)
    except Exception as error:
        message = f"\t- ERROR: {error}"
        getLogger("error_logger").error(message)

        if verbose:
            print(message)

        add_request_process_notes("failed to try to configure ARES", request)


def delete_zoom_events(canvas_course, test, verbose):
    if verbose:
        print("\t* Deleting Zoom events...")

    canvas = get_canvas(test)
    course_string = f"course_{canvas_course.id}"
    events = canvas.get_calendar_events(context_codes=[course_string], all_events=True)
    zoom_events = list()

    for event in events:
        if (
            (event.location_name and "zoom" in event.location_name.lower())
            or (event.description and "zoom" in event.description.lower())
            or (event.title and "zoom" in event.title.lower())
        ):
            zoom_events.append(event.id)

    for event_id in zoom_events:
        event = canvas.get_calendar_event(event_id)
        deleted = event.delete(
            cancel_reason=(
                "Zoom event was copied from a previous term and is no longer relevant"
            )
        )

        if verbose:
            print(f"\t- Event '{deleted}' deleted.")


def delete_announcements(canvas_course, verbose):
    if verbose:
        print("\t* Deleting Announcements...")

    announcements = [
        announcement
        for announcement in canvas_course.get_discussion_topics(only_announcements=True)
    ]

    for announcement in announcements:
        title = announcement.title
        announcement.delete()

        if verbose:
            print(f"\t- Announcement '{title}' deleted.")


def migrate_course(canvas_course, serialized, test, verbose):
    try:
        exclude_announcements = serialized.data.get("exclude_announcements", None)
        source_course_id = serialized.data["copy_from_course"]

        if verbose:
            announcements = " WITHOUT announcements" if exclude_announcements else ""
            print(
                "\t* Copying course data from course id"
                f" {source_course_id}"
                f"{announcements}..."
            )

        content_migration = canvas_course.create_content_migration(
            migration_type="course_copy_importer",
            settings={"source_course_id": source_course_id},
        )

        while (
            content_migration.get_progress().workflow_state == "queued"
            or content_migration.get_progress().workflow_state == "running"
        ):
            if verbose:
                print("\t* Migration running...")

            time.sleep(8)

        if verbose:
            print("\t- MIGRATION COMPLETE")

        delete_zoom_events(canvas_course, test, verbose)

        if exclude_announcements:
            delete_announcements(canvas_course, verbose)

    except Exception as error:
        message = f"\t- ERROR: {error}"
        getLogger("error_logger").error(message)

        if verbose:
            print(message)


def add_site_owners(canvas_course, canvas_site):
    instructors = canvas_course.get_enrollments(type="TeacherEnrollment")._elements

    for instructor in instructors:
        try:
            user = User.objects.get(username=instructor)
            canvas_site.owners.add(user)
        except Exception as error:
            print(f"\t- ERROR: Failed to add {instructor} to site owners ({error})")


@task()
def create_canvas_sites(
    requested_courses=None,
    sections=None,
    test=False,
    verbose=True,
):
    if verbose:
        print(") Creating Canvas sites for requested courses...")

    if requested_courses is None:
        requested_courses = Request.objects.filter(status="APPROVED")

    if not requested_courses:
        if verbose:
            print("SUMMARY")
            print("- No requested courses found.")
            print("FINISHED")

        return

    section_already_exists = False

    for request in requested_courses:
        request.status = "IN_PROCESS"
        request.save()
        serialized = RequestSerializer(request)
        additional_sections = list()
        course_requested = request.course_requested

        if verbose:
            print(f") Creating Canvas site for {course_requested}...")

        account = get_school_account(request, course_requested, test, verbose)

        if not account:
            continue

        section_code = get_section_code(request, course_requested)

        if not section_code:
            continue

        name = (
            f"{section_code} {request.title_override[:45]}"
            if request.title_override
            else f"{section_code} {course_requested.course_name}"
        )
        section_name = (
            f"{section_code}{request.title_override[:45]}"
            if request.title_override
            else f"{section_code} {course_requested.course_name}"
        )
        sis_course_id = f"SRS_{course_requested.srs_format_primary()}"
        term_id = get_term_id(
            MAIN_ACCOUNT_ID,
            f"{course_requested.year}{course_requested.course_term}",
            test=test,
        )
        course = {
            "name": name,
            "sis_course_id": sis_course_id,
            "course_code": sis_course_id,
            "term_id": term_id,
        }
        already_exists, canvas_course = get_canvas_course(
            request, account, course, sis_course_id, test, verbose
        )

        if not canvas_course:
            continue

        set_storage_quota(request, canvas_course)

        if not already_exists:
            created_section, additional_sections = create_section(
                request,
                course_requested,
                canvas_course,
                section_name,
                sis_course_id,
                additional_sections,
                verbose,
            )

            if created_section == "already exists":
                section_already_exists = True

                continue

        course_title = (
            request.title_override
            if request.title_override
            else course_requested.course_name
        )

        handle_sections(
            request,
            serialized,
            canvas_course,
            course_title,
            additional_sections,
            sections,
            test,
            verbose,
        )

        for enrollment in serialized.data["additional_enrollments"]:
            enroll_user(
                request,
                canvas_course,
                enrollment["user"],
                enrollment["role"],
                canvas_course.id,
                test,
            )

        if serialized.data["reserves"]:
            set_reserves(request, canvas_course, verbose)

        if serialized.data["copy_from_course"]:
            migrate_course(canvas_course, serialized, test, verbose)

        canvas_site = CanvasSite.objects.update_or_create(
            canvas_id=canvas_course.id,
            defaults={
                "request_instance": request,
                "name": canvas_course.name,
                "sis_course_id": canvas_course.sis_course_id,
                "workflow_state": canvas_course.workflow_state,
            },
        )[0]
        request.canvas_instance = canvas_site
        add_site_owners(canvas_course, canvas_site)
        request.status = "COMPLETED"
        request.process_notes = ""
        request.save()

        if verbose:
            print(
                f"- UPDATED Canvas site: {canvas_course}"
                if already_exists
                else f"- CREATED Canvas site: {canvas_site}."
            )

    if verbose:
        print("FINISHED")

    return True if section_already_exists else False
