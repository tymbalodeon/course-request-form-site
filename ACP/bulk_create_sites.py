from configparser import ConfigParser
from datetime import datetime

from canvasapi.exceptions import CanvasException

from canvas.api import get_canvas
from course.models import Course, Request
from course.tasks import create_canvas_site

from .logger import canvas_logger, crf_logger

config = ConfigParser()
config.read("config/config.ini")
OWNER = config.items("user")[0][0]


def should_request(course, index, total, test=False):
    sis_id = f"SRS_{course.srs_format_primary()}"

    try:
        canvas = get_canvas(test)
        canvas.get_section(sis_id, use_sis_id=True)
        print(
            f"- ({index + 1}/{total}) {sis_id} is already in use. Removing from"
            " requests list..."
        )
        canvas_logger.warning(
            f"{sis_id} is already in use. Removed from requests list."
        )

        return False
    except CanvasException:
        print(f"- ({index + 1}/{total}) Adding {sis_id} to requests list...")

        return True


def enable_lti(canvas_ids, tool, test=False):
    print(") Enabling LTI for courses...")

    canvas = get_canvas(test)
    total_enabled = 0
    total_already_enabled = 0

    for index, canvas_id in enumerate(canvas_ids):
        try:
            canvas_site = canvas.get_course(canvas_id)
            tabs = canvas_site.get_tabs()

            for tab in tabs:
                if tab.id == tool:
                    try:
                        if tab.visibility != "public":
                            tab.update(hidden=False, position=3)
                            print(
                                f"- ({index + 1}/{len(canvas_ids)}) {tool} enabled for"
                                f" {canvas_id}. "
                            )
                            total_enabled += 1
                        else:
                            print(
                                f"- ({index + 1}/{len(canvas_ids)}) {tool} already"
                                f" enabled for {canvas_id}."
                            )
                            total_already_enabled += 1
                    except Exception:
                        print(
                            f"- ({index + 1}/{len(canvas_ids)}) ERROR: Failed to enable"
                            f" {tool} for {canvas_id}."
                        )
                        canvas_logger.info(
                            f"ERROR: Failed to enable {tool} for {canvas_id}."
                        )
        except Exception:
            print(
                f"- ({index + 1}/{len(canvas_ids)}) ERROR: Failed to find site"
                f" {canvas_id}"
            )
            canvas_logger.info(f"ERROR: Failed to find site {canvas_id}")

    print(f"{tool} ALREADY ENABLED FOR {total_already_enabled} COURSES.")
    print(f"{tool} ENABLED FOR {total_enabled} COURSES.")
    print(
        f"{tool} NOW ENABLED FOR {total_enabled + total_already_enabled} OUT OF"
        f" {len(canvas_ids)} REQUESTED COURSES."
    )


def copy_content(canvas_ids, source_site, test=False):
    print(") Copying course content...")

    canvas = get_canvas(test)
    total_copied = 0

    for index, canvas_id in enumerate(canvas_ids):
        try:
            canvas_site = canvas.get_course(canvas_id)
            canvas_site.create_content_migration(
                migration_type="course_copy_importer",
                settings={"[source_course_id": source_site},
            )
            print(
                f"- ({index + 1}/{len(canvas_ids)}) Created content migration for"
                f" {canvas_id}."
            )
            total_copied += 1
        except Exception as error:
            print(
                f"- ({index + 1}/{len(canvas_ids)}) ERROR: Failed to create content"
                f" migration for {canvas_id} ({error})."
            )
            canvas_logger.info(f"ERROR: Failed to find site {canvas_id} ({error})")

    print(
        f"CREATED CONTENT MIGRATIONS FOR {total_copied} OUT OF {len(canvas_ids)}"
        " REQUESTED COURSES."
    )


def config_sites(canvas_ids, capacity, publish, tool, source_site, test):
    print(") Configuring sites...")

    if source_site:
        copy_content(canvas_ids, source_site, test)

    if tool:
        enable_lti(canvas_ids, tool, test)

    config = {}

    if capacity:
        config["storage_quota_mb"] = capacity

    if publish:
        config["event"] = "offer"

    if publish or capacity:
        canvas = get_canvas(test)

        print(") Updating sites with config: {config}")

        total_updated = 0

        for index, canvas_id in enumerate(canvas_ids):
            try:
                canvas_site = canvas.get_course(canvas_id)
                canvas_site.update(course=config)
                print(f"- ({index + 1}/{len(canvas_id)}) Course {canvas_site} updated.")
                total_updated += 1
            except Exception as error:
                print(
                    f"- ({index + 1}/{len(canvas_id)}) ERROR: Failed to update"
                    f" {canvas_site} ({error})."
                )
                canvas_logger.info(
                    f"ERROR: Failed to update site {canvas_id} ({error})."
                )

    print(f"UPDATED {total_updated} OUT OF {len(canvas_ids)} REQUESTED COURSES.")


def bulk_create_canvas_sites(
    year_and_term,
    copy_site="",
    config=False,
    capacity=2,
    publish=False,
    tool=None,
    source_site=None,
    test=False,
):
    print(") Finding unrequested courses...")

    term = year_and_term[-1]
    year = year_and_term[:-1]

    unrequested_courses = Course.objects.filter(
        course_term=term,
        year=year,
        requested=False,
        requested_override=False,
        primary_crosslist="",
        course_schools__visible=True,
    )

    total_unrequested = len(unrequested_courses)

    print(f"FOUND {total_unrequested} UNREQUESTED COURSES.")
    print(") Filtering out course IDs already in use...")

    requestable_courses = list()

    for index, course in enumerate(unrequested_courses):
        if should_request(course, index, total_unrequested.test):
            course.append(requestable_courses)

    total_requestable = len(requestable_courses)

    print(f"FOUND {total_requestable} COURSE IDS NOT ALREADY IN USE.")
    print(") Requesting courses...")

    requested_courses = list()

    for index, course in enumerate(requestable_courses):
        try:
            request = Request.objects.create(
                course_requested=course,
                copy_from_course=copy_site,
                additional_instructions=(
                    "Request automatically generated; contact Courseware Support for"
                    " more information."
                ),
                owner=OWNER,
                created=datetime.now(),
            )
            request.status = "APPROVED"
            request.save()
            course.save()
            requested_courses.append(course)
            print(f"- ({index + 1}/{total_requestable}) Created request for {course}.")
        except Exception as error:
            print(
                f"- ({index + 1}/{total_requestable}) ERROR: Failed to create request"
                f" for: {course} ({error})"
            )
            crf_logger.info(f"ERROR: Failed to create request for: {course} ({error})")

    total_requested = len(requested_courses)

    print(f"REQUESTED {total_requested} COURSES.")
    print(") Creating Canvas sites for requested courses...")

    create_canvas_site()

    print(") Checking request process notes...")

    canvas_ids = list()

    for index, course in enumerate(requested_courses):
        try:
            request = Request.objects.get(course_requested=course)

            if request.status == "COMPLETED":
                print(
                    f"- ({index + 1}/{total_requestable}) COMPLETED: {course} |"
                    f" {request.canvas_instance.canvas_id} | {request.process_notes}"
                )
                canvas_ids.append(request.canvas_instance.canvas_id)
            else:
                print(
                    f"- ({index + 1}/{total_requestable}) ERROR: Request incomplete for"
                    f" {course}"
                )
                canvas_logger.info(f"ERROR: Request incomplete for {course}")
        except Exception as error:
            print(f"- ({index + 1}/{total_requestable}) ERROR: {error}")
            canvas_logger.info(f"ERROR: {error}")

    total_completed = len(canvas_ids)

    print(
        f"CREATED CANVAS SITES FOR {total_completed} OUT OF {total_requestable}"
        " COURSES."
    )

    if config:
        config_sites(canvas_ids, capacity, publish, tool, source_site, test)

    print("FINISHED")
