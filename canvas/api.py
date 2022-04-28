from logging import getLogger
from time import sleep
from typing import Optional

from canvasapi import Canvas
from canvasapi.account import Account
from canvasapi.exceptions import CanvasException
from canvasapi.tab import Tab
from canvasapi.user import User as CanvasUser
from config.config import PROD_KEY, PROD_URL, TEST_KEY, TEST_URL, USE_TEST_ENV

MAIN_ACCOUNT_ID = 96678
logger = getLogger(__name__)
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


def get_canvas(test=USE_TEST_ENV):
    return Canvas(TEST_URL if test else PROD_URL, TEST_KEY if test else PROD_KEY)


def get_canvas_main_account() -> Account:
    return get_canvas().get_account(MAIN_ACCOUNT_ID)


def get_canvas_user_id_by_pennkey(login_id: str) -> Optional[int]:
    user = get_user_by_login_id(login_id)
    return user.id if user else None


def get_canvas_account(account_id):
    try:
        return get_canvas().get_account(account_id)
    except CanvasException:
        return None


def create_canvas_user(penn_key, penn_id, email, full_name):
    pseudonym = {"sis_user_id": penn_id, "unique_id": penn_key}
    try:
        account = get_canvas_account(MAIN_ACCOUNT_ID)
        if not account:
            return None
        user = account.create_user(pseudonym, user={"name": full_name})
        user.edit(user={"email": email})
        return user
    except CanvasException as error:
        logger.error(
            f"- ERROR: Failed to create canvas user {full_name}, {penn_key} ({error}) "
        )
        return None


def get_user_by_login_id(login_id: str) -> Optional[CanvasUser]:
    try:
        return get_canvas().get_user(login_id, "sis_login_id")
    except CanvasException:
        return None


def get_user_courses(login_id):
    user = get_user_by_login_id(login_id)
    return user.get_courses(enrollment_type="teacher") if user else []


def get_term_id(account_id, sis_term_id):
    try:
        account = get_canvas_account(account_id)
        if not account:
            return None
        response = account._requester.request(
            "GET", f"accounts/{account_id}/terms/sis_term_id:{sis_term_id}"
        )
        return response.json()["id"]
    except Exception:
        return None


def add_request_process_notes(message, request):
    start = ", " if request.process_notes else ""
    request.process_notes += f"{start}{message}"
    request.save()


def get_school_account(request, course_requested):
    account = get_canvas_account(
        LPS_ONLINE_ACCOUNT_ID
        if request.lps_online and course_requested.course_schools.abbreviation == "SAS"
        else course_requested.course_schools.canvas_subaccount
    )
    if not account:
        add_request_process_notes("failed to locate Canvas Account", request)
        message = "\t- ERROR: failed to locate Canvas Account"
        logger.error(message)
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
        return course_requested.sis_format_primary()
    else:
        add_request_process_notes("Primary crosslist not set", request)
        return None


def get_canvas_course(request, account, course, sis_course_id):
    already_exists = False
    canvas_course = None
    try:
        canvas_course = account.create_course(course=course)
    except Exception:
        try:
            canvas_course = get_canvas().get_course(sis_course_id, use_sis_id=True)
            canvas_course.update(course=course)
            already_exists = True
        except Exception as error:
            add_request_process_notes(
                "course site creation failed--check if it already exists",
                request,
            )
            message = f"\t- ERROR: failed to create site ({error})"
            logger.error(message)
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
        logger.error(message)
        return "already exists", additional_sections


def set_reserves(request, canvas_course):
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
        logger.error(message)
        add_request_process_notes("failed to try to configure ARES", request)


def delete_zoom_events(canvas_course):
    logger.info("\t* Deleting Zoom events...")
    canvas = get_canvas()
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
        deleted = deleted.title.encode("ascii", "ignore")
        logger.info(f"\t- Event '{deleted}' deleted.")


def delete_announcements(canvas_course):
    logger.info("\t* Deleting Announcements...")
    announcements = [
        announcement
        for announcement in canvas_course.get_discussion_topics(only_announcements=True)
    ]
    for announcement in announcements:
        title = announcement.title
        announcement.delete()
        logger.info(f"\t- Announcement '{title}' deleted.")


def migrate_course(canvas_course, serialized):
    try:
        exclude_announcements = serialized.data.get("exclude_announcements", None)
        source_course_id = serialized.data["copy_from_course"]
        announcements = " WITHOUT announcements" if exclude_announcements else ""
        logger.info(
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
            logger.info("\t* Migration running...")
            sleep(8)
        logger.info("\t- MIGRATION COMPLETE")
        delete_zoom_events(canvas_course)
        if exclude_announcements:
            delete_announcements(canvas_course)
    except Exception as error:
        logger.error(error)
