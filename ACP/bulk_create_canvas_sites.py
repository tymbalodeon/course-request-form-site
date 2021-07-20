from configparser import ConfigParser
from datetime import datetime

from canvasapi.exceptions import CanvasException

from canvas.api import get_canvas
from course.models import Course, Request
from course.tasks import create_canvas_site

from .logger import canvas_logger, crf_logger

config = ConfigParser()
config.read("config/config.ini")
OWNER = config.items("users")[0][0]


def get_unrequested_courses(year_and_term):
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

    return unrequested_courses


def should_request(sis_id, test=False):
    try:
        canvas = get_canvas(test)
        canvas.get_section(sis_id, use_sis_id=True)

        return False
    except CanvasException:

        return True


def request_course(course, copy_site):
    request = Request.objects.create(
        course_requested=course,
        copy_from_course=copy_site,
        additional_instructions=(
            "Request automatically generated; contact Courseware Support"
            " for more information."
        ),
        owner=OWNER,
        created=datetime.now(),
    )
    request.status = "APPROVED"
    request.save()
    course.save()

    print("\t* Request complete.")


def enable_lti(canvas_id, tool, test=False):
    print("\t> Enabling {tool}...")

    try:
        canvas = get_canvas(test)
        canvas_site = canvas.get_course(canvas_id)
        tabs = canvas_site.get_tabs()
        tool_tab = next(filter(lambda tab: tab.id == tool, tabs), None)

        if tool_tab.visibility != "public":
            tool_tab.update(hidden=False, position=3)
            print(f"\t* Enabled {tool}.")
        else:
            print(f"\t* {tool} already enabled for course.")
    except Exception as error:
        print(f"\t* ERROR: Failed to enable {tool} ({error}).")
        canvas_logger.info(f"ERROR: Failed to enable {tool} for {canvas_id} ({error}).")


def copy_content(canvas_id, source_site, test=False):
    print("\t> Copying course content from {source_site}...")

    try:
        canvas = get_canvas(test)
        canvas_site = canvas.get_course(canvas_id)
        canvas_site.create_content_migration(
            migration_type="course_copy_importer",
            settings={"[source_course_id": source_site},
        )
        print("\t* Created content migration.")
    except Exception as error:
        print(f"\t* ERROR: Failed to create content migration ({error}).")
        canvas_logger.info(f"ERROR: Failed to find site {canvas_id} ({error})")


def config_sites(canvas_id, capacity, publish, tool, source_site, test):
    if source_site:
        copy_content(canvas_id, source_site, test)

    if tool:
        enable_lti(canvas_id, tool, test)

    config = {}

    if capacity:
        config["storage_quota_mb"] = capacity

    if publish:
        config["event"] = "offer"

    if publish or capacity:
        print(f"\t> Updating with config: {config}...")

        try:
            canvas = get_canvas(test)
            canvas_site = canvas.get_course(canvas_id)
            canvas_site.update(course=config)
            print("\t* Updated complete.")
        except Exception as error:
            print(f"\t* ERROR: Failed to update course ({error}).")
            canvas_logger.info(f"ERROR: Failed to update site {canvas_id} ({error}).")


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
    unrequested_courses = get_unrequested_courses(year_and_term)

    print(") Processing courses...")

    for index, course in enumerate(unrequested_courses):
        print(f"- ({index + 1}/{len(unrequested_courses)}): {course}")

        sis_id = f"SRS_{course.srs_format_primary()}"

        if should_request(sis_id):
            try:
                print("\t> Requesting course...")
                request_course(course, copy_site)

                print("\t> Creating Canvas site...")
                create_canvas_site()

                print("\t> Checking request process notes...")
                request = Request.objects.get(course_requested=course)

                if request.status == "COMPLETED":
                    print(
                        f"\t* COMPLETED: {request.canvas_instance.canvas_id},"
                        f" {request.process_notes}"
                    )
                else:
                    print("\t* ERROR: Request incomplete.")
                    canvas_logger.info(f"ERROR: Request incomplete for {course}.")
                    continue

                if config:
                    canvas_id = request.canvas_instance.canvas_id
                    config_sites(canvas_id, capacity, publish, tool, source_site, test)
            except Exception as error:
                print(f"\t* ERROR: Failed to create site. ({error})")
                crf_logger.info(f"ERROR: Failed to create site for {course} ({error}).")
        else:
            print(f"\t* SKIPPING: {sis_id} is already in use.")
            canvas_logger.warning(f"{sis_id} is already in use.")

    print("FINISHED")
