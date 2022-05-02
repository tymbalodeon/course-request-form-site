from logging import getLogger

from canvas.api import (
    ENROLLMENT_TYPES,
    LIBRARIAN_ROLE_ID,
    MAIN_ACCOUNT_ID,
    add_request_process_notes,
    create_canvas_user,
    create_section,
    get_canvas_course,
    get_school_account,
    get_section_code,
    get_term_id,
    get_user_by_login_id,
    migrate_course,
    set_reserves,
    set_storage_quota,
)
from course.models import Course, Request, User
from course.serializers import RequestSerializer

logger = getLogger(__name__)
SIS_PREFIX = "BAN"


def enroll_user(request, canvas_course, section, user, role):
    try:
        username = user.username
        penn_id = user.penn_id
        email = user.email_address
        full_name = (f"{user.first_name} {user.last_name}",)
    except Exception:
        crf_user = User.objects.get(username=user)
        username = user
        penn_id = crf_user.profile.penn_id
        email = crf_user.email
        full_name = f"{crf_user.first_name} {crf_user.last_name}"
    canvas_user = get_user_by_login_id(username)
    if canvas_user is None:
        try:
            canvas_user = create_canvas_user(
                username,
                penn_id,
                email,
                full_name,
            )
            add_request_process_notes(f"created account for user: {username}", request)
        except Exception as error:
            add_request_process_notes(
                f"failed to create account for user: {username} ({error})", request
            )
    enrollment = {"enrollment_state": "active", "course_section_id": section}
    if role == "LIB" or role == "librarian":
        enrollment["role_id"] = LIBRARIAN_ROLE_ID
        try:
            canvas_course.enroll_user(
                canvas_user,
                ENROLLMENT_TYPES[role],
                enrollment=enrollment,
            )
        except Exception as error:
            add_request_process_notes(f"failed to add user: {user} ({error})", request)
    else:
        try:
            canvas_course.enroll_user(
                canvas_user,
                ENROLLMENT_TYPES[role],
                enrollment=enrollment,
            )
        except Exception as error:
            add_request_process_notes(
                f"failed to add user: {username} ({error})", request
            )


def create_canvas_sites(requested_courses=None, sections=None):
    logger.info("Creating Canvas sites for requested courses...")
    if requested_courses is None:
        requested_courses = Request.objects.filter(status="APPROVED")
    if not requested_courses:
        logger.info("SUMMARY")
        logger.info("- No requested courses found.")
        logger.info("FINISHED")
        return
    section_already_exists = False
    for request in requested_courses:
        course_requested = request.course_requested
        if not (
            course_requested.course_term.isnumeric()
            or len(course_requested.course_number) == 4
        ):
            request.status = "LOCKED"
            continue
        request.status = "IN_PROCESS"
        request.save()
        serialized = RequestSerializer(request)
        additional_sections = list()
        logger.info(f"Creating Canvas site for {course_requested}...")
        account = get_school_account(request, course_requested)
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
        sis_course_id = f"{SIS_PREFIX}_{course_requested.sis_format_primary()}"
        term_id = get_term_id(
            MAIN_ACCOUNT_ID, f"{course_requested.year}{course_requested.course_term}"
        )
        course = {
            "name": name,
            "sis_course_id": sis_course_id,
            "course_code": sis_course_id,
            "term_id": term_id,
        }
        already_exists, canvas_course = get_canvas_course(
            request, account, course, sis_course_id
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
        )
        section = next(
            (section for section in canvas_course.get_sections()), canvas_course
        ).id
        for enrollment in serialized.data["additional_enrollments"]:
            enroll_user(
                request,
                canvas_course,
                section,
                enrollment["user"],
                enrollment["role"],
            )
        if serialized.data["reserves"]:
            set_reserves(request, canvas_course)
        if serialized.data["copy_from_course"]:
            migrate_course(canvas_course, serialized)
        request.status = "COMPLETED"
        request.save()
        logger.info(f"UPDATED Canvas site: {canvas_course}")
    logger.info("FINISHED")
    return True if section_already_exists else False


def handle_sections(
    request, serialized, canvas_course, course_title, additional_sections, sections
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
            f"{section_course.sis_format_primary(sis_id=False)} {course_title}"
        )
        sis_section = f"{SIS_PREFIX}_{section_course.sis_format_primary()}"
        additional_sections = create_section(
            request,
            section_course,
            canvas_course,
            course_title,
            sis_section,
            additional_sections,
        )[1]
    for section in additional_sections:
        for user in section["instructors"]:
            enroll_user(
                request, canvas_course, section["course_section"].id, user, "instructor"
            )
