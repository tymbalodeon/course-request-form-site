import datetime
import os
import sys

from canvas.api import get_canvas
from course.models import Course, Request, User
from course.tasks import create_canvas_site

from .logger import canvas_logger, crf_logger


def create_unrequested_list(term, outputfile="unrequested_courses.txt"):
    print(") Finding unrequested courses...")

    term = term[-1]
    year = term[:-1]
    courses = Course.objects.filter(
        course_term=term,
        year=year,
        requested=False,
        requested_override=False,
        primary_crosslist="",
        course_schools__visible=True,
    )

    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data/", outputfile)

    with open(file_path, "w+") as output_file:
        for course in courses:
            output_file.write(
                f"{course.srs_format_primary()}, {course.course_schools.abbreviation}\n"
            )
            print(
                f"- {course.srs_format_primary()}, {course.course_schools.abbreviation}"
            )

    print(f"- Found {len(courses)} unrequested courses.")


def create_unused_sis_list(
    inputfile="unrequested_courses.txt", outputfile="unused_sis_ids.txt"
):
    print(") Finding unused sis ids...")

    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", inputfile)

    with open(file_path, "r") as dataFile:
        for line in dataFile:
            sis_id, school = line.replace("\n", "").split(",")
            print(f"- {sis_id}, {school}")


def create_requests(inputfile="unused_sis_ids.txt", copy_site=""):
    print(") Creating requests...")

    owner = User.objects.get(username="benrosen")
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", inputfile)

    with open(file_path, "r") as dataFile:
        for line in dataFile:
            course_id = line.replace("\n", "").replace(" ", "").replace("-", "")
            course_id = course_id.strip()

            try:
                course = Course.objects.get(course_code=course_id)
            except Exception:
                course = None

            if course:
                try:
                    request = Request.objects.create(
                        course_requested=course,
                        copy_from_course=copy_site,
                        additional_instructions=(
                            "Created automatically, contact courseware support for info"
                        ),
                        owner=owner,
                        created=datetime.datetime.now(),
                    )
                    request.status = "APPROVED"
                    request.save()
                    course.save()
                    print(f"- Created request for {course}.")
                except Exception:
                    print(f"- ERROR: Failed to create request for: {course_id}")
                    crf_logger.info(
                        f"- ERROR: Failed to create request for: {course_id}"
                    )

            else:
                print(f"- ERROR: Course not in CRF ({course_id})")
                crf_logger.info(f"- ERROR: Course not in CRF ({course_id})")


def gather_request_process_notes(inputfile="unused_sis_ids.txt"):
    print(") Gathering request process notes...")

    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", inputfile)

    dataFile = open(file_path, "r")
    request_results_file = open(
        os.path.join(my_path, "ACP/data", "request_process_notes.txt"), "w+"
    )
    canvas_sites_file = open(
        os.path.join(my_path, "ACP/data", "canvas_sites_file.txt"), "w+"
    )

    for line in dataFile:
        course_id = line.replace("\n", "").replace(" ", "").replace("-", "")

        try:
            course = Course.objects.get(course_code=course_id)
        except Exception:
            course = None

        try:
            request = Request.objects.get(course_requested=course)
        except Exception:
            request = None

        if request:
            if request.status == "COMPLETED":
                canvas_sites_file.write(
                    f"{course_id}, {request.canvas_instance.canvas_id}\n"
                )
                request_results_file.write(f"{course_id} | {request.process_notes}\n")
                print(
                    f"- {course_id} | {request.canvas_instance.canvas_id} |"
                    f" {request.process_notes}"
                )
            else:
                canvas_logger.info(f"request incomplete for {course_id}")
                print(f"- request incomplete for {course_id}")
        else:
            crf_logger.info(f"- ERROR: Couldn't find request for {course_id}")
            print(f"- ERROR: Couldn't find request for {course_id}")


def process_requests(input_file="unused_sis_ids.txt"):
    print(") Creating canvas sites...")

    create_canvas_site()
    gather_request_process_notes(input_file)


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
