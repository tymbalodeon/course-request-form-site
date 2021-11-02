from __future__ import print_function

from configparser import ConfigParser
from datetime import datetime
from logging import getLogger
from re import findall, sub
from string import capwords

import cx_Oracle

from course import utils
from course.models import Activity, Course, Profile, School, Subject, User
from open_data.open_data import OpenData

ROMAN_NUMERAL_REGEX = (
    r"(?=[MDCLXVI].)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})\)?$"
)
ERA_REGEX = r"\s((B?C{1}E?)|(AD))(\s|$)"


def get_cursor():
    config = ConfigParser()
    config.read("config/config.ini")
    values = dict(config.items("data_warehouse"))
    connection = cx_Oracle.connect(
        values["user"], values["password"], values["service"]
    )

    return connection.cursor()


def get_open_data():
    config = ConfigParser()
    config.read("config/config.ini")
    values = dict(config.items("open_data"))

    return OpenData(base_url=values["domain"], id=values["id"], key=values["key"])


def format_title(title):
    eras = ["Bc", "Bce", "Ce", "Ad"]
    title = title.upper()
    roman_numeral = findall(ROMAN_NUMERAL_REGEX, title)

    if roman_numeral:
        title = sub(ROMAN_NUMERAL_REGEX, "", title)

    title = capwords(title)

    def capwords_with_divider(title, divider):
        titles = title.split(divider)

        def sentence_case_title(title):
            characters = [character for character in title]
            characters[0] = characters[0].upper()

            return "".join(characters)

        titles = [sentence_case_title(title) for title in titles]

        return divider.join(titles)

    dividers = ["/", "-", ":"]

    for divider in dividers:
        if divider in title:
            title = capwords_with_divider(title, divider)

            if divider == ":" and findall(r":[^ ]", title):
                title = sub(r":", ": ", title)

    if roman_numeral:
        roman_numeral_string = "".join([str(value) for value in roman_numeral[0]])
        title = f"{title} {roman_numeral_string}"

    for era in eras:
        if title.endswith(era):
            title = title.replace(era, era.upper())

    return title


def get_user(penn_id):
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT FIRST_NAME, LAST_NAME, EMAIL_ADDRESS, PENNKEY
        FROM EMPLOYEE_GENERAL
        WHERE PENN_ID= :penn_id """,
        penn_id=str(penn_id),
    )

    for first_name, last_name, email, pennkey in cursor:
        return [first_name, last_name, email, pennkey]


def get_course(section, term=None, verbose=True):
    section = (
        section.replace("SRS_", "")
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )

    if len(section) > 10:
        term = section[-5:]
        section = section[:-5]

    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            cs.section_id || cs.term section,
            cs.section_id,
            cs.term,
            cs.subject_area subject_id,
            cs.tuition_school school_id,
            cs.xlist,
            cs.xlist_primary,
            cs.activity,
            cs.section_dept department,
            cs.section_division division,
            trim(cs.title) srs_title,
            cs.status srs_status,
            cs.schedule_revision,
            cs.timetable_instructor
        FROM dwadmin.course_section cs
        WHERE
            cs.activity IN (
                'LEC',
                'REC',
                'LAB',
                'SEM',
                'CLN',
                'CRT',
                'PRE',
                'STU',
                'ONL',
                'HYB'
            )
        AND cs.tuition_school NOT IN ('WH', 'LW')
        AND cs.status in ('O')
        AND cs.section_id = :section
        """,
        section=section,
    )

    if verbose:
        print(
            "course_code, section_id, course_term, subject_area, school, xc, xc_code,"
            " activity, section_dept, section_division, title, status, rev,"
            " instructor(s)\n"
        )

    results = list()

    for (
        course_code,
        section_id,
        course_term,
        subject_area,
        school,
        xc,
        xc_code,
        activity,
        section_dept,
        section_division,
        title,
        status,
        rev,
        instructors,
    ) in cursor:
        if not term:
            if verbose:
                print(
                    course_code,
                    section_id,
                    course_term,
                    subject_area,
                    school,
                    xc,
                    xc_code,
                    activity,
                    section_dept,
                    section_division,
                    title,
                    status,
                    rev,
                    instructors,
                )
            else:
                results.append(
                    [
                        course_code,
                        section_id,
                        course_term,
                        subject_area,
                        school,
                        xc,
                        xc_code,
                        activity,
                        section_dept,
                        section_division,
                        title,
                        status,
                        rev,
                        instructors,
                    ]
                )
        elif course_term == term:
            if verbose:
                print(
                    course_code,
                    section_id,
                    course_term,
                    subject_area,
                    school,
                    xc,
                    xc_code,
                    activity,
                    section_dept,
                    section_division,
                    title,
                    status,
                    rev,
                    instructors,
                )
            else:
                results.append(
                    [
                        course_code,
                        section_id,
                        course_term,
                        subject_area,
                        school,
                        xc,
                        xc_code,
                        activity,
                        section_dept,
                        section_division,
                        title,
                        status,
                        rev,
                        instructors,
                    ]
                )

    return results


def get_instructor(pennkey, term):
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            e.FIRST_NAME,
            e.LAST_NAME,
            e.PENNKEY,
            e.PENN_ID,
            e.EMAIL_ADDRESS,
            cs.Section_Id,
            cs.term
        FROM dwadmin.course_section_instructor cs
        JOIN dwadmin.employee_general_v e
        ON cs.Instructor_Penn_Id=e.PENN_ID
        WHERE e.PENNKEY = :pennkey
        AND cs.term = :term
        """,
        pennkey=pennkey,
        term=term,
    )

    for first_name, last_name, pennkey, penn_id, email, section_id, term in cursor:
        print("first name, last name, pennkey, penn id, email, section, term\n")
        print(first_name, last_name, pennkey, penn_id, email, section_id, term)


def pull_courses(term):
    print(") Pulling courses from the Data Warehouse...")

    term = term.upper()
    open_data = get_open_data()
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            section.section_id || section.term section,
            section.term,
            section.subject_area subject_id,
            section.tuition_school school_id,
            section.xlist,
            section.xlist_primary,
            section.activity,
            trim(section.title) srs_title
        FROM
            dwadmin.course_section section
        WHERE section.activity IN (
            'LEC',
            'REC',
            'LAB',
            'SEM',
            'CLN',
            'CRT',
            'PRE',
            'STU',
            'ONL',
            'HYB'
        )
        AND section.tuition_school NOT IN ('WH', 'LW')
        AND section.status IN ('O')
        AND section.term = :term
        """,
        term=term,
    )

    for (
        course_code,
        term,
        subject_area,
        school,
        xc,
        xc_code,
        activity,
        title,
    ) in cursor:
        course_code = course_code.replace(" ", "")
        subject_area = subject_area.replace(" ", "")
        xc_code = xc_code.replace(" ", "")
        primary_crosslist = ""

        try:
            subject = Subject.objects.get(abbreviation=subject_area)
        except Exception:
            try:
                school_code = open_data.find_school_by_subj(subject_area)
                school = School.objects.get(open_data_abbreviation=school_code)
                subject = Subject.objects.create(
                    abbreviation=subject_area, name=subject_area, schools=school
                )
            except Exception as error:
                getLogger("error_logger").error(
                    f"couldnt find subject {subject_area}: {error}"
                )
                subject = ""
                print(f"{course_code}: Subject {subject_area} not found ({error})")

        if xc:
            if xc == "S":
                primary_crosslist = xc_code + term

            p_subj = xc_code[:-6]

            try:
                primary_subject = Subject.objects.get(abbreviation=p_subj)
            except Exception:
                try:
                    school_code = open_data.find_school_by_subj(p_subj)
                    school = School.objects.get(open_data_abbreviation=school_code)
                    primary_subject = Subject.objects.create(
                        abbreviation=p_subj, name=p_subj, schools=school
                    )
                except Exception as error:
                    getLogger("error_logger").error(
                        f"couldnt find subject {p_subj}: {error}"
                    )
                    primary_subject = ""
                    print(f"{course_code}: Primary subject not found")
        else:
            primary_subject = subject

        if primary_subject:
            school = primary_subject.schools
        else:
            school = ""

        try:
            activity = Activity.objects.get(abbr=activity)
        except Exception:
            try:
                activity = Activity.objects.create(abbr=activity, name=activity)
            except Exception:
                getLogger("error_logger").error("couldnt find activity %s ", activity)
                activity = ""
                print(f"{course_code}: Activity not found")

        course_number_and_section = course_code[:-5][-6:]
        course_number = course_number_and_section[:3]
        section_number = course_number_and_section[-3:]
        year = term[:4]

        try:
            title = format_title(title) if title else title
            created = Course.objects.update_or_create(
                course_code=course_code,
                defaults={
                    "owner": User.objects.get(username="benrosen"),
                    "course_term": term[-1],
                    "course_activity": activity,
                    "course_subject": subject,
                    "course_primary_subject": primary_subject,
                    "primary_crosslist": primary_crosslist,
                    "course_schools": school,
                    "course_number": course_number,
                    "course_section": section_number,
                    "course_name": title,
                    "year": year,
                },
            )[1]

            print(
                f"- Added course {course_code}"
                if created
                else f"- Updated course {course_code}"
            )

        except Exception as error:
            print(f"- ERROR: Failed to add or update course {course_code} ({error})")

    print("FINISHED")


def pull_instructors(term):
    print(") Pulling instructors...")

    term = term.upper()
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            employee.first_name,
            employee.last_name,
            employee.pennkey,
            employee.penn_id,
            employee.email_address,
            instructor.section_id
        FROM dwadmin.employee_general_v employee
        INNER JOIN dwadmin.course_section_instructor instructor
        ON employee.penn_id = instructor.instructor_penn_id
        AND instructor.term = :term
        INNER JOIN dwadmin.course_section section
        ON instructor.section_id = section.section_id
        WHERE section.activity
        IN (
                'LEC',
                'REC',
                'LAB',
                'SEM',
                'CLN',
                'CRT',
                'PRE',
                'STU',
                'ONL',
                'HYB'
            )
        AND section.tuition_school NOT IN ('WH', 'LW')
        AND section.status in ('O')
        AND section.term = :term
        """,
        term=term,
    )

    NEW_INSTRUCTOR_VALUES = dict()

    for first_name, last_name, pennkey, penn_id, email, section_id in cursor:
        course_code = (section_id + term).replace(" ", "")

        if not pennkey:
            message = (
                f"- ERROR: (section: {section_id}) Failed to create account for"
                f" {first_name} {last_name} (missing pennkey)"
            )
            getLogger("error_logger").error(message)
            print(message)
        else:
            try:
                course = Course.objects.get(course_code=course_code)

                if not course.requested:
                    try:
                        instructor = User.objects.get(username=pennkey)
                    except Exception:
                        try:
                            first_name = first_name.title()
                            last_name = last_name.title()
                            instructor = User.objects.create_user(
                                username=pennkey,
                                first_name=first_name,
                                last_name=last_name,
                                email=email,
                            )
                            Profile.objects.create(user=instructor, penn_id=penn_id)
                        except Exception as error:
                            error_message = error
                            instructor = None

                    if instructor:
                        try:
                            NEW_INSTRUCTOR_VALUES[course_code].append(instructor)
                        except Exception:
                            NEW_INSTRUCTOR_VALUES[course_code] = [instructor]
                    else:
                        message = (
                            f"- ERROR: (section: {section_id}) Failed to create account"
                            f" for: {first_name} {last_name} ({error_message})"
                        )
                        getLogger("error_logger").error(message)
                        print(message)
            except Exception:
                message = f"- ERROR: Failed to find course {course_code}"
                getLogger("error_logger").error(message)
                print(message)

    for course_code, instructors in NEW_INSTRUCTOR_VALUES.items():
        try:
            course = Course.objects.get(course_code=course_code)
            course.instructors.clear()

            for instructor in instructors:
                course.instructors.add(instructor)

            course.save()

            print(
                f"- Updated {course_code} with instructors:"
                f" {', '.join([instructor.username for instructor in instructors])}"
            )

        except Exception as error:
            message = f"- ERROR: Failed to add new instructor(s) to course ({error})"
            getLogger("error_logger").error(message)
            print(message)

    print("FINISHED")


def delete_canceled_courses(term):
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            cs.section_id || cs.term section,
            cs.term,
            cs.subject_area subject_id,
            cs.xlist_primary,
        FROM dwadmin.course_section cs
        WHERE
            cs.activity IN (
                'LEC',
                'REC',
                'LAB',
                'SEM',
                'CLN',
                'CRT',
                'PRE',
                'STU',
                'ONL',
                'HYB'
            )
        AND cs.status IN ('X')
        AND cs.tuition_school NOT IN ('WH', 'LW')
        AND cs.term= :term
        """,
        term=term,
    )

    start = datetime.now().strftime("%Y-%m-%d")

    with open("course/static/log/deleted_courses_issues.log", "a") as log:
        log.write(f"-----{start}-----\n")

        for (
            course_code,
            term,
            subject_area,
            xc_code,
        ) in cursor:
            course_code = course_code.replace(" ", "")
            subject_area = subject_area.replace(" ", "")
            xc_code = xc_code.replace(" ", "")

            try:
                course = Course.objects.get(course_code=course_code)

                if course.requested:
                    try:
                        canvas_site = course.request.canvas_instance
                    except Exception:
                        print(f"- No main request for {course.course_code}.")

                        if course.multisection_request:
                            canvas_site = course.multisection_request.canvas_instance
                        elif course.crosslisted_request:
                            canvas_site = course.crosslisted_request.canvas_instance
                        else:
                            canvas_site = None

                    if canvas_site and canvas_site.workflow_state != "deleted":
                        log.write(f"- Canvas site already exists for {course_code}.\n")
                    else:
                        log.write(
                            "- Canceled course requested but no Canvas site for"
                            f" {course_code}.\n"
                        )
                else:
                    print(") Deleting {course_code}...")
                    course.delete()
            except Exception:
                print(
                    "- The canceled course {course_code} doesn't exist in the CRF yet."
                )


def daily_sync(term):
    pull_courses(term)
    pull_instructors(term)
    utils.process_canvas()
    utils.update_sites_info(term)
    delete_canceled_courses(term)
