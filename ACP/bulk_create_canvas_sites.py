from configparser import ConfigParser
from os import mkdir
from pathlib import Path

from canvas.api import get_canvas
from canvasapi.exceptions import CanvasException
from course.models import Course, Request, School, User
from course.tasks import create_canvas_sites
from django.utils import timezone

from .logger import canvas_logger, crf_logger

config = ConfigParser()
config.read("config/config.ini")
OWNER = User.objects.get(username=config.items("users")[0][0])


def get_requested_or_unrequested_courses(
    year_and_term, school_abbreviation, requested=False, exclude_crosslist=True
):
    requested_display = "requested" if requested else "unrequested"

    print(f") Finding {requested_display} courses...")

    term = year_and_term[-1]
    year = year_and_term[:-1]

    filter_dict = {
        "year": year,
        "course_term": term,
        "requested": requested,
        "course_schools__visible": True,
    }

    if not requested:
        filter_dict["requested_override"] = False

    if exclude_crosslist:
        filter_dict["primary_crosslist"] = ""

    if school_abbreviation:
        school = School.objects.get(abbreviation=school_abbreviation)
        filter_dict["course_schools"] = school

    courses = Course.objects.filter(**filter_dict)
    total = len(courses)

    print(f"FOUND {total} {requested_display.upper()} COURSES.")

    return list(courses)


def group_sections(year_and_term, school):
    courses = get_requested_or_unrequested_courses(year_and_term, school)
    all_sections = set()
    SECTIONS = dict()

    for course in courses:
        if course in all_sections:
            continue

        course_sections = list(course.sections.all())

        if not course_sections:
            SECTIONS[course] = [course]
            all_sections.add(course)
        else:
            SECTIONS[course] = course_sections
            all_sections.update(course_sections)

    return SECTIONS


def get_data_directory():
    DATA_DIRECTORY = Path.cwd() / "data"

    if not DATA_DIRECTORY.exists():
        mkdir(DATA_DIRECTORY)

    return DATA_DIRECTORY


def write_main_sections(year_and_term, school_abbreviation):
    sections = group_sections(year_and_term, school_abbreviation)
    DATA_DIRECTORY = get_data_directory()

    with open(
        DATA_DIRECTORY
        / f"{school_abbreviation}_sites_to_be_bulk_created_{year_and_term}.txt",
        "w",
    ) as writer:
        for section_list in sections.values():
            writer.write(f"{section_list[0].course_code}\n")
            tabbed_sections = [
                f"\t{section.course_code}\n" for section in section_list[1:]
            ]
            writer.write(f"{''.join(section for section in tabbed_sections)}")


def write_request_statuses(year_and_term, school_abbreviation, verbose=True):
    def get_request(course):
        try:
            return Request.objects.get(course_requested=course)
        except Exception:
            return course

    def list_instructors(course):
        try:
            return ", ".join([user.username for user in list(course.instructors.all())])
        except Exception:
            return "STAFF"

    def has_canvas_site(course):
        try:
            site = course.canvas_instance.canvas_id
        except Exception:
            try:
                site = (
                    get_canvas()
                    .get_course(f"SRS_{course.srs_format_primary()}", True)
                    .id
                )
            except Exception:
                site = False

        if verbose:
            print(f"- Canvas site for course {course}: {site}")

        return site

    def make_rows(course):
        if not isinstance(course, Course):
            course = course.course_requested

        return [
            course.course_code,
            course.course_name,
            course.course_activity,
            list_instructors(course),
            course.requested,
            has_canvas_site(course),
        ]

    unrequested_courses = get_requested_or_unrequested_courses(
        year_and_term, school_abbreviation, exclude_crosslist=False
    )
    requested_courses = get_requested_or_unrequested_courses(
        year_and_term, school_abbreviation, requested=True, exclude_crosslist=False
    )

    print(") Finding request objects for requested courses...")

    requested_courses = [get_request(course) for course in requested_courses]
    courses = unrequested_courses + requested_courses

    print(") Checking for Canvas sites...")

    courses = [make_rows(course) for course in courses]

    DATA_DIRECTORY = get_data_directory()
    COLUMNS = (
        [
            "Section",
            "Title",
            "Activity",
            "Instructor(s)",
            "Requested",
            "Canvas Site",
        ],
    )

    with open(
        DATA_DIRECTORY
        / f"{school_abbreviation}_courses_request_and_site_statuses_{year_and_term}.csv",
        "w",
        newline="\n",
    ) as writer:
        writer.write(",".join(COLUMNS))

        for course in courses:
            writer.write(",".join(course))


def should_request(sis_id, test=False):
    try:
        canvas = get_canvas(test)
        canvas.get_section(sis_id, use_sis_id=True)

        return False
    except CanvasException:

        return True


def request_course(course, reserves, status="APPROVED", verbose=True):
    try:
        request = Request.objects.update_or_create(
            course_requested=course,
            defaults={
                "additional_instructions": (
                    "Request automatically generated; contact Courseware Support"
                    " for more information."
                ),
                "owner": OWNER,
                "created": timezone.now(),
                "reserves": reserves,
            },
        )[0]
        request.status = status
        request.save()
        course.save()

        if verbose:
            print("\t* Request created.")

        return [request]
    except Exception as error:
        return error


def enable_tools(canvas_id, tools, label, test):
    for tool in tools:
        try:
            canvas = get_canvas(test)
            canvas_site = canvas.get_course(canvas_id)
            tabs = canvas_site.get_tabs()

            if label:
                tool_tab = next((tab for tab in tabs if tab.label == tool), None)
            else:
                tool_tab = next((tab for tab in tabs if tab.id == tool), None)

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
    reserves=True,
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
        unrequested_courses = group_sections(year_and_term, school).keys()
    else:
        unrequested_courses = list()

        for abbreviation in school:
            unrequested_courses.extend(
                group_sections(year_and_term, abbreviation).keys()
            )

    print(") Processing courses...")

    for index, course in enumerate(unrequested_courses):
        print(f"- ({index + 1}/{len(unrequested_courses)}): {course}")

        sis_id = f"SRS_{course.srs_format_primary()}"

        if should_request(sis_id):
            try:
                course_request = request_course(course, reserves)
                sections = list(course.sections.all())
                creation_error = create_canvas_sites(
                    course_request, sections=sections, test=test, verbose=False
                )

                if creation_error:
                    print("\t> Aborting... (SECTION ALREADY EXISTS)")
                    canvas_logger.info(
                        f"Failed to create main section for {course} (SECTION"
                        " ALREADY EXISTS)"
                    )
                    course_request[0].status = "COMPLETED"
                    course_request[0].save = "COMPLETED"
                    course.save()

                    continue

                request = Request.objects.get(course_requested=course)

                if request.status == "COMPLETED":
                    print(f"\t* Course created: ({request.canvas_instance.canvas_id})")
                else:
                    print(f"\t* ERROR: Request incomplete. ({request.process_notes})")
                    canvas_logger.info(
                        f"Request incomplete for {course} ({request.process_notes})."
                    )

                    continue

                if tools:
                    canvas_id = request.canvas_instance.canvas_id
                    enable_tools(canvas_id, tools, label, test)
            except Exception as error:
                print(f"\t* ERROR: Failed to create site ({error}).")
                canvas_logger.info(f"Failed to create site for {course} ({error}).")

            print("\tCOMPLETE")
        else:
            print(f"\t* SKIPPING: {sis_id} is already in use.")
            canvas_logger.info(f"{sis_id} is already in use.")

            if not course.requested:
                request_course(course, reserves, "COMPLETED", False)

    print("FINISHED")
