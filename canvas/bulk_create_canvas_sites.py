from os import path, remove

from canvasapi.exceptions import CanvasException
from django.utils import timezone

from canvas.api import get_canvas
from canvas.helpers import create_canvas_sites
from config.config import USERNAME
from course.models import SIS_PREFIX, Course, Request, School, User
from course.utils import DATA_DIRECTORY_NAME, get_data_directory, split_year_and_term

OWNER = User.objects.get(username=USERNAME)
LOG_PATH = "/home/django/crf2/data/bulk_creation_log.csv"


def print_item(index, total, message):
    print(f"- ({index + 1:,}/{total:,}) {message}")


def get_courses(
    year_and_term, school_abbreviation, requested=False, exclude_crosslist=True
):
    requested_display = "requested" if requested else "unrequested"
    print(f") Finding {requested_display} courses...")
    year, term = split_year_and_term(year_and_term)
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
    courses = get_courses(year_and_term, school)
    all_sections = set()
    SECTIONS = dict()
    print(") Consolidating sections into a single course number...")
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


def remove_courses_with_site(courses):
    print(") Removing courses with a pre-existing Canvas site...")

    def should_request_with_remove(sis_id, course, index):
        should = should_request(sis_id)
        if not should:
            message = (
                f"Canvas site ALREADY EXISTS for {course.course_code}. Removing from"
                " list..."
            )
            print_item(index, TOTAL_START, message)
            if not course.requested:
                request_course(course, False, "COMPLETED", False)
        else:
            message = f"Canvas site NOT FOUND for {course.course_code}."
            print_item(index, TOTAL_START, message)
        return should

    TOTAL_START = len(courses)
    courses = [
        course
        for index, course in enumerate(courses)
        if should_request_with_remove(
            f"{SIS_PREFIX}_{course.sis_format_primary()}", course, index
        )
    ]
    total_end = len(courses)
    print(f"FOUND {total_end} COURSES WITH NO CANVAS SITE.")
    return courses


def write_courses(year_and_term, school_abbreviation):
    """
    Generates 4 csv files with a single column of course codes, for the
    following parameters:

    1. Unrequested courses
    2. Unrequested courses with no Canvas site
    3. Unrequested unique course numbers consolidated
    4. Unrequested unique course numbers consolidated with no Canvas site
    """
    unrequested_courses = get_courses(year_and_term, school_abbreviation)
    print(") Checking unrequested courses for existing sites..")
    siteless_unrequested_courses = [
        course
        for course in unrequested_courses
        if should_request(f"{SIS_PREFIX}_{course.sis_format_primary()}")
    ]
    print(f"FOUND {len(siteless_unrequested_courses)} SITELESS UNREQUESTED COURSES.")
    consolidated_sections = group_sections(year_and_term, school_abbreviation)
    print(") Checking consolidated courses for existing sites..")
    siteless_consolidated_courses = [
        course
        for course in consolidated_sections
        if should_request(f"{SIS_PREFIX}_{course.sis_format_primary()}")
    ]
    print(f"FOUND {len(siteless_consolidated_courses)} SITELESS CONSOLIDATED COURSES.")
    DATA_DIRECTORY = get_data_directory(DATA_DIRECTORY_NAME)
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
    """
    Params: year_and_term ('2021C'), school_abbreviaton ('SAS'), verbuse=True

    Generates a csv file listing the request status and Cavnas site for all
    courses in the given school and term.

    Columns: Section / Title / Activity / Instructor(s) / Requested / Canvas Site
    """

    def get_request(course):
        try:
            return Request.objects.get(course_requested=course)
        except Exception:
            return course

    def list_instructors(course):
        instructors_string = ", ".join(
            [user.username for user in list(course.instructors.all())]
        )
        try:
            return f'"{instructors_string}"'
        except Exception:
            return "STAFF"

    def has_canvas_site(request):
        try:
            site = request.canvas_instance.canvas_id
        except Exception:
            try:
                site = (
                    get_canvas()
                    .get_course(
                        f"{SIS_PREFIX}_{request.sis_format_primary()}",
                        True,
                    )
                    .id
                )
            except Exception:
                try:
                    site = (
                        get_canvas()
                        .get_section(
                            f"{SIS_PREFIX}_{request.sis_format_primary()}",
                            True,
                        )
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
            course.schedule_type.name,
            list_instructors(course),
            course.requested,
            has_canvas_site(course),
        ]
        return [str(item) for item in row]

    unrequested_courses = get_courses(year_and_term, school_abbreviation)
    requested_courses = get_courses(year_and_term, school_abbreviation, requested=True)
    print(") Finding request objects for requested courses...")
    requested_courses = [get_request(course) for course in requested_courses]
    courses = unrequested_courses + requested_courses
    print(") Checking for Canvas sites...")
    courses = [make_rows(course) for course in courses]
    DATA_DIRECTORY = get_data_directory(DATA_DIRECTORY_NAME)
    COLUMNS = [
        "Section",
        "Title",
        "Activity",
        "Instructor(s)",
        "Requested",
        "Canvas Site",
    ]
    path_string = (
        f"{school_abbreviation}_courses_request_and_site_statuses_{year_and_term}.csv"
    )
    with open(
        DATA_DIRECTORY / path_string,
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
        if isinstance(course, Course):
            course.save()
        if verbose:
            print("\t* Request created.")
        return [request]
    except Exception as error:
        print(f"\t* ERROR: Unable to request {course}: ({error})")
        return False


def enable_tools(canvas_id, tools, label):
    for tool in tools:
        try:
            canvas = get_canvas()
            canvas_site = canvas.get_course(canvas_id)
            tabs = canvas_site.get_tabs()
            if label:
                tool_tab = next((tab for tab in tabs if tab.label == tool), None)
            else:
                tool_tab = next((tab for tab in tabs if tab.id == tool), None)
            if tool_tab and tool_tab.visibility != "public":
                tool_tab.update(hidden=False, position=3)
                print(f"\t* Enabled {tool_tab.label}.")
            elif tool_tab:
                print(f"\t* {tool_tab.label} already enabled for course.")
        except Exception as error:
            print(f"\t* ERROR: Failed to enable {tool} ({error}).")


def publish_site(canvas_id):
    canvas_site = None
    try:
        canvas = get_canvas()
        canvas_site = canvas.get_course(canvas_id)
        canvas_site.update(course={"event": "offer"})
        print(f"\t* Published {canvas_site}.")
    except Exception as error:
        print(
            f"\t* ERROR: Failed to publish {canvas_site}: ({error})"
            if canvas_site
            else "\t* ERROR: Failed to find Canvas site ({error})"
        )


def read_course_list_from_csv(csv_path):
    with open(csv_path) as reader:
        courses = reader.readlines()
        courses = [course.replace("\n", "").replace('"', "") for course in courses]
        courses.remove("")
        return courses


def bulk_create_canvas_sites(
    year_and_term=None,
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
    publish=False,
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
    else:
        if path.exists(LOG_PATH):
            remove(LOG_PATH)

        def get_course_object_or_empty(course):
            try:
                return Course.objects.get(course_code=course)
            except Exception:
                with open(LOG_PATH, "a") as output:
                    output.write(f"{course}\n")
                return None

        courses = [get_course_object_or_empty(course) for course in courses]
        courses = [course for course in courses if course]
    print(") Processing courses...")
    for index, course in enumerate(courses):
        print_item(index, len(courses), course)
        try:
            course_request = request_course(course, reserves)
            sections = None if not include_sections else list(course.sections.all())
            creation_error = create_canvas_sites(course_request, sections=sections)
            if creation_error:
                print("\t> Aborting... (SITE ALREADY EXISTS)")
                if course_request:
                    course_request[0].status = "COMPLETED"
                    course_request[0].save = "COMPLETED"
                course.save()
                continue
            request = Request.objects.get(course_requested=course)
            if request.status == "COMPLETED":
                print(f"\t* Course created: ({request.canvas_instance.canvas_id})")
            else:
                print(f"\t* ERROR: Request incomplete. ({request.process_notes})")
                continue
            if tools or publish:
                canvas_id = request.canvas_instance.canvas_id
                if tools:
                    enable_tools(canvas_id, tools, label)
                if publish:
                    publish_site(canvas_id)
        except Exception as error:
            print(f"\t* ERROR: Failed to create site ({error}).")
        print("\tCOMPLETE")
    print("FINISHED")
