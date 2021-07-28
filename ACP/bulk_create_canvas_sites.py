from configparser import ConfigParser
from datetime import datetime

from canvasapi.exceptions import CanvasException

from canvas.api import get_canvas
from course.models import Course, Request, School, User
from course.tasks import create_canvas_sites

from .logger import canvas_logger, crf_logger

config = ConfigParser()
config.read("config/config.ini")
OWNER = User.objects.get(username=config.items("users")[0][0])


def get_unrequested_courses(year_and_term, school_abbreviation):
    print(") Finding unrequested courses...")

    term = year_and_term[-1]
    year = year_and_term[:-1]

    if school_abbreviation:
        school = School.objects.get(abbreviation=school_abbreviation)
        unrequested_courses = Course.objects.filter(
            course_term=term,
            year=year,
            requested=False,
            requested_override=False,
            primary_crosslist="",
            course_schools__visible=True,
            course_schools=school,
        )
    else:
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

    return list(unrequested_courses)


def should_request(sis_id, test=False):
    try:
        canvas = get_canvas(test)
        canvas.get_section(sis_id, use_sis_id=True)

        return False
    except CanvasException:

        return True


def request_course(course, status="APPROVED", verbose=True):
    request = Request.objects.create(
        course_requested=course,
        additional_instructions=(
            "Request automatically generated; contact Courseware Support"
            " for more information."
        ),
        owner=OWNER,
        created=datetime.now(),
        reserves=True,
    )
    request.status = status
    request.save()
    course.save()
    if verbose:
        print("\t* Request complete.")

    return [request]


def enable_tools(canvas_id, tools, label, test):
    for tool in tools:
        print(f"\t> Enabling {tool}...")

        try:
            canvas = get_canvas(test)
            canvas_site = canvas.get_course(canvas_id)
            tabs = canvas_site.get_tabs()

            if label:
                tool_tab = next(filter(lambda tab: tab.label == tool, tabs), None)
            else:
                tool_tab = next(filter(lambda tab: tab.id == tool, tabs), None)

            if tool_tab.visibility != "public":
                tool_tab.update(hidden=False, position=3)
                print(f"\t* Enabled {tool_tab.label}.")
            else:
                print(f"\t* {tool_tab.label} already enabled for course.")
        except Exception as error:
            print(f"\t* ERROR: Failed to enable {tool} ({error}).")
            canvas_logger.info(
                f"ERROR: Failed to enable {tool} for {canvas_id} ({error})."
            )


def bulk_create_canvas_sites(
    year_and_term,
    school="SEAS",
    enable=True,
    tools={
        "context_external_tool_90311": "Class Recordings",
        "context_external_tool_231623": "Zoom",
        "context_external_tool_132117": "Gradescope",
    },
    label=True,
    test=False,
):
    if type(tools) == dict and label:
        tools = [tool for tool in tools.values()]
    elif type(tools) == dict:
        tools = [tool for tool in tools.keys()]

    if not school or (school and type(school) == str):
        unrequested_courses = get_unrequested_courses(year_and_term, school)
    else:
        unrequested_courses = list()

        for abbreviation in school:
            unrequested_courses.extend(
                get_unrequested_courses(year_and_term, abbreviation)
            )

    print(") Processing courses...")

    for index, course in enumerate(unrequested_courses):
        print(f"- ({index + 1}/{len(unrequested_courses)}): {course}")

        sis_id = f"SRS_{course.srs_format_primary()}"

        if should_request(sis_id):
            try:
                print("\t> Requesting course...")
                course_request = request_course(course)

                print("\t> Finding course sections...")
                sections = list(course.sections.all())[1:]

                print("\t> Creating Canvas site...")
                create_canvas_sites(
                    course_request, sections=sections, test=test, verbose=False
                )

                print("\t> Confirming site creation...")
                request = Request.objects.get(course_requested=course)

                if request.status == "COMPLETED":
                    print(f"\t* COMPLETED: ({request.canvas_instance.canvas_id})")
                else:
                    print(f"\t* ERROR: Request incomplete. ({request.process_notes})")
                    canvas_logger.info(
                        f"ERROR: Request incomplete for {course}"
                        f" ({request.process_notes})."
                    )
                    continue

                if enable:
                    canvas_id = request.canvas_instance.canvas_id
                    enable_tools(canvas_id, tools, label, test)
            except Exception as error:
                print(f"\t* ERROR: Failed to create site. ({error})")
                crf_logger.info(f"ERROR: Failed to create site for {course} ({error}).")
        else:
            print(f"\t* SKIPPING: {sis_id} is already in use.")
            canvas_logger.warning(f"{sis_id} is already in use.")

            if not course.requested:
                request_course(course, "COMPLETED", False)

    print("FINISHED")
