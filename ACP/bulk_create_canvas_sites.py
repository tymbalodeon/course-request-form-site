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

    print(f") Consolidating sections into a single course number...")

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

    total = len(SECTIONS)

    print(f"FOUND {total} UNIQUE COURSE NUMBERS.")

    return list(SECTIONS)


def get_data_directory():
    DATA_DIRECTORY = Path.cwd() / "data"

    if not DATA_DIRECTORY.exists():
        mkdir(DATA_DIRECTORY)

    return DATA_DIRECTORY


def remove_courses_with_site(courses):
    print(f") Removing courses with a pre-existing Canvas site...")

    def should_request_with_remove(sis_id, course, index):
        should = should_request(sis_id)

        if not should:
            print(
                f"- ({index + 1}/{TOTAL_START}) Canvas site ALREADY EXISTS for {course.course_code}. Removing from list..."
            )

            if not course.requested:
                request_course(course, False, "COMPLETED", False)
        else:
            print(
                f"- ({index + 1}/{TOTAL_START}) Canvas site NOT FOUND for {course.course_code}."
            )

        return should

    TOTAL_START = len(courses)

    courses = [
        course
        for index, course in enumerate(courses)
        if should_request_with_remove(
            f"SRS_{course.srs_format_primary()}", course, index
        )
    ]

    total_end = len(courses)

    print(f"FOUND {total_end} COURSES WITH NO CANVAS SITE.")

    return courses


def write_courses(year_and_term, school_abbreviation):
    unrequested_courses = get_requested_or_unrequested_courses(
        year_and_term, school_abbreviation
    )

    print(") Checking unrequested courses for existing sites..")

    siteless_unrequested_courses = [
        course
        for course in unrequested_courses
        if should_request(f"SRS_{course.srs_format_primary()}")
    ]

    print("FOUND {len(siteless_unrequested_courses)} SITELESS UNREQUESTED COURSES.")

    consolidated_sections = group_sections(year_and_term, school_abbreviation)

    print(") Checking consolidated courses for existing sites..")

    siteless_consolidated_courses = [
        course
        for course in consolidated_sections
        if should_request(f"SRS_{course.srs_format_primary()}")
    ]

    print("FOUND {len(siteless_consolidated_courses)} SITELESS CONSOLIDATED COURSES.")

    DATA_DIRECTORY = get_data_directory()

    course_lists = {
        "unrequested_courses": unrequested_courses,
        "siteless_unrequested_courses": siteless_unrequested_courses,
        "consolidated_sections": consolidated_sections,
        "siteless_consolidated_courses": siteless_consolidated_courses,
    }

    for key, value in course_lists.items():
        lines = "course code\n" + "\n".join([course.course_code for course in value])

        with open(
            DATA_DIRECTORY / f"{school_abbreviation}_{key}_{year_and_term}.csv",
            "w",
        ) as writer:
            writer.write(lines)


def write_request_statuses(year_and_term, school_abbreviation, verbose=True):
    def get_request(course):
        try:
            return Request.objects.get(course_requested=course)
        except Exception:
            return course

    def list_instructors(course):
        try:
            return f'"{", ".join([user.username for user in list(course.instructors.all())])}"'
        except Exception:
            return "STAFF"

    def has_canvas_site(request):
        try:
            site = request.canvas_instance.canvas_id
        except Exception:
            try:
                site = (
                    get_canvas()
                    .get_course(f"SRS_{request.srs_format_primary()}", True)
                    .id
                )
            except Exception:
                try:
                    site = (
                        get_canvas()
                        .get_section(f"SRS_{request.srs_format_primary()}", True)
                        .id
                    )
                except Exception:
                    site = None

        if verbose:
            print(f"- Canvas site for course {request}: {site}")

        return site

    def make_rows(course):
        if not isinstance(course, Course):
            course = course.course_requested

        row = [
            course.course_code,
            f'"{course.course_name}"',
            course.course_activity.name,
            list_instructors(course),
            course.requested,
            has_canvas_site(course),
        ]

        return [str(item) for item in row]

    unrequested_courses = get_requested_or_unrequested_courses(
        year_and_term, school_abbreviation
    )
    requested_courses = get_requested_or_unrequested_courses(
        year_and_term, school_abbreviation, requested=True
    )

    print(") Finding request objects for requested courses...")

    requested_courses = [get_request(course) for course in requested_courses]
    courses = unrequested_courses + requested_courses

    print(") Checking for Canvas sites...")

    courses = [make_rows(course) for course in courses]

    DATA_DIRECTORY = get_data_directory()
    COLUMNS = [
        "Section",
        "Title",
        "Activity",
        "Instructor(s)",
        "Requested",
        "Canvas Site",
    ]

    with open(
        DATA_DIRECTORY
        / f"{school_abbreviation}_courses_request_and_site_statuses_{year_and_term}.csv",
        "w",
    ) as writer:
        writer.write(f"{','.join(COLUMNS)}\n")

        for course in courses:
            writer.write(f"{','.join(course)}\n")

    print("FINISHED")


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
    courses=[],
    include_sections=False,
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

    if not courses:
        if not school or (school and type(school) == str):
            courses = group_sections(year_and_term, school)
        else:
            courses = list()

            for abbreviation in school:
                courses.extend(group_sections(year_and_term, abbreviation))

        courses = remove_courses_with_site(courses)

    print(") Processing courses...")

    for index, course in enumerate(courses):
        print(f"- ({index + 1}/{len(courses)}): {course}")

        try:
            course_request = request_course(course, reserves)
            sections = None if not include_sections else list(course.sections.all())
            creation_error = create_canvas_sites(
                course_request, sections=sections, test=test, verbose=False
            )

            if creation_error:
                print("\t> Aborting... (SITE ALREADY EXISTS)")
                canvas_logger.info(
                    f"Failed to create main section for {course} (SITE"
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

    print("FINISHED")
