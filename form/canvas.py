from functools import lru_cache
from logging import getLogger
from typing import Optional

from canvasapi import Canvas
from canvasapi.account import Account
from canvasapi.calendar_event import CalendarEvent
from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionTopic
from canvasapi.exceptions import CanvasException
from canvasapi.paginated_list import PaginatedList
from canvasapi.user import User as CanvasUser
from config.config import DEBUG_VALUE, PROD_KEY, PROD_URL, TEST_KEY, TEST_URL

logger = getLogger(__name__)
MAIN_ACCOUNT_ID = 96678


def get_canvas() -> Canvas:
    url = TEST_URL if DEBUG_VALUE else PROD_URL
    key = TEST_KEY if DEBUG_VALUE else PROD_KEY
    return Canvas(url, key)


def get_canvas_account(account_id: int) -> Account:
    return get_canvas().get_account(account_id)


def get_canvas_main_account() -> Account:
    return get_canvas_account(MAIN_ACCOUNT_ID)


@lru_cache
def get_all_canvas_accounts() -> list[Account]:
    return list(get_canvas_main_account().get_subaccounts(recursive=True))


def get_canvas_user_by_login_id(login_id: str) -> Optional[CanvasUser]:
    try:
        return get_canvas().get_user(login_id, "sis_login_id")
    except CanvasException:
        return None


def get_canvas_user_by_pennkey(pennkey: str) -> Optional[CanvasUser]:
    return get_canvas_user_by_login_id(pennkey)


def get_canvas_user_id_by_pennkey(pennkey: str) -> Optional[int]:
    user = get_canvas_user_by_pennkey(pennkey)
    return user.id if user else None


def get_canvas_enrollment_term_id(term: int) -> Optional[int]:
    term_name = str(term)
    account = get_canvas().get_account(MAIN_ACCOUNT_ID)
    enrollment_terms = account.get_enrollment_terms()
    enrollment_term_ids = (
        term.id for term in enrollment_terms if term_name in term.name
    )
    return next(enrollment_term_ids, None)


def create_course_section(name: str, sis_course_id: str, canvas_course: Course):
    course_section = {"name": name, "sis_section_id": sis_course_id}
    canvas_course.create_course_section(
        course_section=course_section, enable_sis_reactivation=True
    )


def update_canvas_course(course: dict) -> Optional[Course]:
    sis_course_id = course["sis_course_id"]
    try:
        canvas_course = get_canvas().get_course(sis_course_id, use_sis_id=True)
        canvas_course.update(course=course)
        return canvas_course
    except Exception as error:
        logger.error(f"FAILED to update Canvas course '{sis_course_id}': {error}")
        return None


def update_or_create_canvas_course(
    course: dict, account_id: int
) -> tuple[bool, Optional[Course]]:
    created = True
    try:
        account = get_canvas_account(account_id)
        canvas_course = account.create_course(course=course)
        name = canvas_course.name
        sis_course_id = canvas_course.sis_course_id
        create_course_section(name, sis_course_id, canvas_course)
        return created, canvas_course
    except Exception:
        created = False
        return created, update_canvas_course(course)


def get_calendar_events(course_id: int) -> PaginatedList:
    context_codes = [f"course_{course_id}"]
    canvas = get_canvas()
    return canvas.get_calendar_events(context_codes=context_codes, all_events=True)


def contains_zoom(event_property: Optional[str]) -> bool:
    return bool(event_property and "zoom" in event_property.lower())


def is_zoom_event(event: CalendarEvent) -> bool:
    return (
        contains_zoom(event.location_name)
        or contains_zoom(event.description)
        or contains_zoom(event.title)
    )


def delete_zoom_event(event_id: int):
    event = get_canvas().get_calendar_event(event_id)
    cancel_reason = "Content migration"
    deleted = event.delete(cancel_reason=cancel_reason)
    deleted = deleted.title.encode("ascii", "ignore")
    logger.info(f"DELETED event '{deleted}'")


def delete_announcement(announcement: DiscussionTopic):
    announcement.delete()
    logger.info(f"DELETED announcement '{announcement.title}'")


def delete_zoom_events(canvas_course):
    logger.info("Deleting Zoom events...")
    events = get_calendar_events(canvas_course.id)
    zoom_events = [event.id for event in events if is_zoom_event(event)]
    for event_id in zoom_events:
        delete_zoom_event(event_id)


def delete_announcements(canvas_course):
    logger.info("Deleting Announcements...")
    announcements = canvas_course.get_discussion_topics(only_announcements=True)
    announcements = [announcement for announcement in announcements]
    for announcement in announcements:
        delete_announcement(announcement)


def get_canvas_course(course_id: int) -> Course:
    return get_canvas().get_course(course_id)


def get_user_canvas_sites(user: str) -> Optional[list[Course]]:
    instructor = get_canvas_user_by_pennkey(user)
    if not instructor:
        return None
    enrollments = instructor.get_enrollments(
        role=[
            "TeacherEnrollment",
            "TaEnrollment",
            "ObserverEnrollment",
            "DesignerEnrollment",
        ]
    )
    courses = [get_canvas_course(enrollment.course_id) for enrollment in enrollments]
    return courses
