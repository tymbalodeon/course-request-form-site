from datetime import datetime
import os
import sys
from configparser import ConfigParser

import pandas
from canvas.api import get_canvas
from course.models import Course, Request, User
from course.tasks import create_canvas_site

from .logger import canvas_logger, crf_logger

CONFIG = ConfigParser()
CONFIG.read("config/config.ini")
OWNER = CONFIG.items("users")[0][0]


def create_unrequested_list(year_and_term, copy_site, tools=None, test=False):
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

    for course in unrequested_courses:
        try:
            request = Request.objects.create(
                course_requested=course,
                copy_from_course=copy_site,
                additional_instructions=(
                    "Request automatically generated; contact Courseware Support for additional information."
                ),
                owner=OWNER,
                created=datetime.now(),
            )
            request.status = "APPROVED"
            request.save()
            course.save()
            print(f"- Created request for {course}.")
        except Exception:
            print(f"- ERROR: Failed to create request for: {course")
            crf_logger.info(f"- ERROR: Failed to create request for: {course")

    create_canvas_site()

    if tools:
        for tool in tools:
            enable_lti(tool, test)


def enable_lti(tool, test=False):
    print(") Enabling LTI for courses...")

    canvas = get_canvas(test)

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

    if config:
        config_sites(
            input_file=input_file,
            capacity=capacity,
            publish=publish,
            tool=tool,
            source_site=source_site,
            test=test,
        )
