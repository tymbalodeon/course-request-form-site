import os
import sys
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path

import pandas
from canvas.api import get_canvas
from canvasapi.exceptions import CanvasException
from course.models import Course, Request, User
from course.tasks import create_canvas_site

from .logger import canvas_logger, crf_logger

config = ConfigParser()
config.read("config/config.ini")
OWNER = config.items("user")[0][0]


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

    course_srs_codes = list()
    total = len(unrequested_courses)

    for index, course in enumerate(unrequested_courses):
        course_srs_codes.append(course.srs_format_primary())
        print(f"- ({index + 1}/{total}) {course.srs_format_primary()}")

    return pandas.DataFrame(
        course_srs_codes,
        columns=["srs format primary"],
    )


def filter_out_used_ids(courses, test=False):
    print(") Finding unused sis ids...")

    for course in courses.itertuples():
        sis_id = f"SRS_{course['srs format primary']}"

        try:
            canvas = get_canvas(test)
            section = canvas.get_section(sis_id, use_sis_id=True)
            print(f"- {sis_id} is already in use. Removing from requests list...")
            canvas_logger.warning(
                f"{sis_id} is already in use. Removed from requests list."
            )
            courses.drop(course[0], inplace=True)
        except CanvasException:
            print(f"- Requesting site for {sis_id}...")

    return courses


def create_requests(courses, copy_site=""):
    print(") Creating requests...")

    for course in courses.itertuples():
        course_id = "".join(
            character
            for character in course["srs format primary"]
            if character.isalnum()
        ).strip()

        try:
            course = Course.objects.get(course_code=course_id)
            request = Request.objects.create(
                course_requested=course,
                copy_from_course=copy_site,
                additional_instructions=(
                    "Request automatically generated; contact Courseware Support for more information."
                ),
                owner=OWNER,
                created=datetime.now(),
            )
            request.status = "APPROVED"
            request.save()
            course.save()
            print(f"- Created request for {course}.")
        except Exception as error:
            print(f"- ERROR: Failed to create request for: {course_id} ({error})")
            crf_logger.info(
                f"- ERROR: Failed to create request for: {course_id} ({error})"
            )


def gather_request_process_notes(courses):
    print(") Gathering request process notes...")

    canvas_site_ids = list()
    request_process_notes = list()

    for course in courses.itertuples():
        course_id = "".join(
            character
            for character in course["srs format primary"]
            if character.isalnum()
        ).strip()

        try:
            course = Course.objects.get(course_code=course_id)
            request = Request.objects.get(course_requested=course)

            if request.status == "COMPLETED":
                canvas_site_ids.append(f"{request.canvas_instance.canvas_id}")
                request_process_notes.append(f"{request.process_notes}")
                print(
                    f"- COMPLETED: {course['srs format primary']} | {request.canvas_instance.canvas_id} |"
                    f" {request.process_notes}"
                )
            else:
                canvas_logger.info(f"- ERROR: Request incomplete for {course_id}")
                print(f"- ERROR: Request incomplete for {course_id}")
        except Exception as error:
            print(f"- ERROR: {error}")


def process_requests():
    print(") Creating canvas sites...")

    create_canvas_site()
    gather_request_process_notes()


def enable_lti(input_file, tool, test=False):
    print(") Enabling LTI for courses...")

    canvas = get_canvas(test)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", input_file)

    with open(file_path, "r") as dataFile:
        for line in dataFile:
            canvas_id = line.replace("\n", "").strip()

            try:
                course_site = canvas.get_course(canvas_id)
            except Exception:
                print(f"- ERROR: Failed to find site {canvas_id}")
                canvas_logger.info(f"- ERROR: Failed to find site {canvas_id}")
                course_site = None

            if course_site:
                tabs = course_site.get_tabs()

                for tab in tabs:
                    if tab.id == tool:
                        try:
                            if tab.visibility != "public":
                                tab.update(hidden=False, position=3)
                                print(f"- {tool} enabled. ")
                            else:
                                print(f"- {tool} already enabled.")
                        except Exception:
                            print(f"- ERROR: Failed to enable {tool} for {canvas_id}")


def copy_content(input_file, source_site, test=False):
    print(") Copying course content...")

    canvas = get_canvas(test)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", input_file)

    with open(file_path, "r") as dataFile:
        for line in dataFile:
            canvas_id = line.replace("\n", "").split(",")[-1]

            try:
                course_site = canvas.get_course(canvas_id)
            except Exception:
                canvas_logger.info(f"- ERROR: Failed to find site {canvas_id}")
                course_site = None

            if course_site:
                course_site.create_content_migration(
                    migration_type="course_copy_importer",
                    settings={"[source_course_id": source_site},
                )
                print(f"- Created content migration for {canvas_id}.")


def config_sites(
    input_file="canvas_sites.txt",
    capacity=2,
    publish=False,
    tool=None,
    source_site=None,
    test=False,
):
    print(") Configuring sites...")

    if source_site:
        copy_content(input_file, source_site)

    if tool:
        enable_lti(input_file, tool)

    config = {}

    if capacity:
        config["storage_quota_mb"] = capacity

    if publish:
        config["event"] = "offer"

    if publish or capacity:
        canvas = get_canvas(test)
        my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        file_path = os.path.join(my_path, "ACP/data", input_file)

        with open(file_path, "r") as dataFile:
            for line in dataFile:
                canvas_id = line.replace("\n", "").split(",")[-1]

                try:
                    course_site = canvas.get_course(canvas_id)
                except Exception as error:
                    canvas_logger.info(
                        f"- ERROR: Failed to find site {canvas_id} ({error})"
                    )
                    course_site = None

                if course_site:
                    course_site.update(course=config)
                    print(f"- Course {course_site} updated with config: {config}")


def bulk_create_sites(
    term,
    copy_site="",
    config=False,
    input_file="canvas_sites.txt",
    capacity=2,
    publish=False,
    tool=None,
    source_site=None,
    test=False,
):
    print(") Bulk creating sites...")

    create_unrequested_list(term)
    create_unused_sis_list()
    create_requests(copy_site=copy_site)
    process_requests()

    if config:
        config_sites(
            input_file=input_file,
            capacity=capacity,
            publish=publish,
            tool=tool,
            source_site=source_site,
            test=test,
        )
