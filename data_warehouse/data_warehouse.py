from configparser import ConfigParser
from datetime import datetime
from logging import getLogger
from re import findall, search, sub

from cx_Oracle import connect

from course.models import Activity, Course, Profile, School, Subject, User
from course.terms import CURRENT_YEAR_AND_TERM, TWENTY_TWO_A
from open_data.open_data import OpenData

logger = getLogger(__name__)


def get_cursor():
    config = ConfigParser()
    config.read("config/config.ini")
    values = dict(config.items("data_warehouse"))
    connection = connect(values["user"], values["password"], values["service"])
    return connection.cursor()


def get_banner_course(srs_course_id, search_term):
    srs_course_id = srs_course_id.replace(" ", "").replace("-", "").replace("_", "")
    subject = "".join(character for character in srs_course_id if character.isalpha())
    if len(subject) == 3:
        srs_course_id = srs_course_id.replace(subject, f"{subject} ")
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            banner.subject, banner.course_num, banner.section_num, banner.term
        FROM
            dwngss.xwalk_crse_number xwalk
        JOIN
            dwngss_ps.crse_section banner
        ON xwalk.ngss_course_id=banner.course_id
        WHERE
            srs_course_id = :srs_course_id
        """,
        srs_course_id=srs_course_id,
    )
    results = list()
    for subject, course_num, section_num, term in cursor:
        if not search_term or term[-2:] == search_term:
            results.append(f"{subject}-{course_num}-{section_num} {term}")
    return results


def format_title(title):
    roman_numeral_regex = (
        r"(?=[MDCLXVI].)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})\)?$"
    )
    numbers_regex = r"\d(?:S|Nd|Rd|Th|)"
    words_to_capitalize = ["Bc", "Bce", "Ce", "Ad", "Ai", "Snf", "Asl"]
    dividers = ["/", "-", ":"]

    def capitalize_roman_numerals(title):
        title = title.upper()
        roman_numerals = search(roman_numeral_regex, title)
        if roman_numerals:
            roman_numerals = roman_numerals.group()
            title_base = sub(roman_numerals, "", title)
            title = f"{title_base.title()}{roman_numerals}"
        else:
            title = title.title()
        for word in words_to_capitalize:
            if word in title.split():
                title = title.replace(word, word.upper())
        return title

    for divider in dividers:
        titles = title.split(divider)
        title = divider.join([capitalize_roman_numerals(title) for title in titles])
        if divider == ":" and findall(r":[^ ]", title):
            title = sub(r":", ": ", title)
    numbers = findall(numbers_regex, title)
    if numbers:
        for number in numbers:
            title = sub(number, number.lower(), title)
    return title


def get_staff_account(penn_key=None, penn_id=None):
    cursor = get_cursor()
    if not penn_key and not penn_id:
        logger.warning("Checking Data Warehouse: NO PENNKEY OR PENN ID PROVIDED.")
        return False
    elif penn_key:
        logger.info(f"Checking Data Warehouse for pennkey {penn_key}...")
        cursor.execute(
            """
            SELECT
                first_name, last_name, email_address, penn_id
            FROM
                employee_general
            WHERE
                pennkey = :pennkey
            """,
            pennkey=penn_key,
        )
        for first_name, last_name, email, dw_penn_id in cursor:
            logger.info(
                f'FOUND "{penn_key}": {first_name} {last_name} ({dw_penn_id})'
                f" {email.strip() if email else email}"
            )
            return {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "penn_id": dw_penn_id,
            }
    elif penn_id:
        logger.info(f"Checking Data Warehouse for penn id {penn_id}...")
        cursor.execute(
            """
            SELECT
                first_name, last_name, email_address, pennkey
            FROM
                employee_general
            WHERE
                penn_id = :penn_id
            """,
            penn_id=penn_id,
        )
        for first_name, last_name, email, penn_key in cursor:
            logger.info(
                f'FOUND "{penn_id}": {first_name} {last_name} ({penn_key})'
                f" {email.strip() if email else email}"
            )
            return {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "penn_key": penn_key,
            }


def get_student_account(penn_key):
    cursor = get_cursor()
    logger.info(f"Checking Data Warehouse for pennkey {penn_key}...")
    cursor.execute(
        """
        SELECT
            first_name, last_name, email_address, penn_id
        FROM
            person_all_v
        WHERE
            pennkey = :pennkey
        """,
        pennkey=penn_key,
    )
    for first_name, last_name, email, dw_penn_id in cursor:
        logger.info(
            f'FOUND "{penn_key}": {first_name} {last_name} ({dw_penn_id})'
            f" {email.strip() if email else email}"
        )
        return {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "penn_id": dw_penn_id,
        }


def get_user_by_pennkey(pennkey):
    if isinstance(pennkey, str):
        pennkey = pennkey.lower()
    try:
        user = User.objects.get(username=pennkey)
    except User.DoesNotExist:
        account_values = get_staff_account(penn_key=pennkey)
        if account_values:
            first_name = account_values["first_name"].title()
            last_name = account_values["last_name"].title()
            user = User.objects.create_user(
                username=pennkey,
                first_name=first_name,
                last_name=last_name,
                email=account_values["email"],
            )
            Profile.objects.create(user=user, penn_id=account_values["penn_id"])
            logger.info(f'CREATED Profile for "{pennkey}".')
        else:
            user = None
            logger.error(f'FAILED to create Profile for "{pennkey}".')
    return user


def get_course(section, term=None):
    section = (
        section.replace("SRS_", "")
        .replace("BAN_", "")
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


def get_instructor(pennkey, term=CURRENT_YEAR_AND_TERM):
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
        return {
            "first name": first_name,
            "last name": last_name,
            "pennkey": pennkey,
            "penn id": penn_id,
            "email": email,
            "section": section_id,
            "term": term,
        }


def get_data_warehouse_courses(term=CURRENT_YEAR_AND_TERM, logger=logger):
    logger.info(") Pulling courses from the Data Warehouse...")
    term = term.upper()
    open_data = OpenData()
    cursor = get_cursor()
    old_term = next((character for character in term if character.isalpha()), None)
    if old_term:
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
    else:
        cursor.execute(
            """
            SELECT
                section_id || term,
                term,
                subject,
                school,
                xlist_enrlmt,
                xlist_family,
                schedule_type,
                trim(title)
            FROM
                dwngss_ps.crse_section
            WHERE schedule_type IN (
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
            AND term = :term
            """,
            term=term,
        )
    for (
        course_code,
        term,
        subject_area,
        school,
        crosslist,
        crosslist_code,
        activity,
        title,
    ) in cursor:
        course_code = course_code.replace(" ", "")
        subject_area = subject_area.replace(" ", "")
        crosslist_code = crosslist_code.replace(" ", "") if crosslist_code else ""
        primary_crosslist = ""
        try:
            subject = Subject.objects.get(abbreviation=subject_area)
        except Exception:
            try:
                school_code = open_data.get_school_by_subject(subject_area)
                school = School.objects.get(open_data_abbreviation=school_code)
                subject = Subject.objects.create(
                    abbreviation=subject_area, name=subject_area, schools=school
                )
            except Exception as error:
                subject = ""
                logger.error(
                    f"{course_code}: Subject {subject_area} not found ({error})"
                )
        if crosslist:
            if crosslist == "S":
                primary_crosslist = f"{crosslist_code}{term}"
            p_subj = crosslist_code[:-6]
            try:
                primary_subject = Subject.objects.get(abbreviation=p_subj)
            except Exception:
                try:
                    school_code = open_data.get_school_by_subject(p_subj)
                    school = School.objects.get(open_data_abbreviation=school_code)
                    primary_subject = Subject.objects.create(
                        abbreviation=p_subj, name=p_subj, schools=school
                    )
                except Exception as error:
                    primary_subject = ""
                    logger.error(f"{course_code}: Primary subject not found ({error})")
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
                activity = ""
                logger.error(f"{course_code}: Activity not found")
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
                    "course_term": term[-1] if old_term else term[-2:],
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
            logger.info(
                f"- Added course {course_code}"
                if created
                else f"- Updated course {course_code}"
            )
        except Exception as error:
            logger.error(
                f"- ERROR: Failed to add or update course {course_code} ({error})"
            )
    logger.info("FINISHED")


def get_data_warehouse_instructors(term=CURRENT_YEAR_AND_TERM, logger=logger):
    logger.info(") Pulling instructors...")
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
                f"(section: {section_id}) Failed to create account for"
                f" {first_name} {last_name} (missing pennkey)"
            )
            logger.error(message)
        else:
            try:
                course = Course.objects.get(course_code=course_code)
                if not course.requested:
                    error_message = ""
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
                            f"(section: {section_id}) Failed to create account"
                            f" for: {first_name} {last_name} ({error_message})"
                        )
                        logger.error(message)
            except Exception:
                message = f"Failed to find course {course_code}"
                logger.error(message)
    for course_code, instructors in NEW_INSTRUCTOR_VALUES.items():
        try:
            course = Course.objects.get(course_code=course_code)
            course.instructors.clear()
            for instructor in instructors:
                course.instructors.add(instructor)
            course.save()
            logger.info(
                f"- Updated {course_code} with instructors:"
                f" {', '.join([instructor.username for instructor in instructors])}"
            )
        except Exception as error:
            message = f"Failed to add new instructor(s) to course ({error})"
            logger.error(message)
    logger.info("FINISHED")


def delete_data_warehouse_canceled_courses(
    term=CURRENT_YEAR_AND_TERM,
    log_path="course/static/log/canceled_courses.log",
    logger=logger,
):
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            cs.section_id || cs.term section,
            cs.term,
            cs.subject_area subject_id,
            cs.xlist_primary
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
        AND cs.term = :term
        """,
        term=term,
    )
    start = datetime.now().strftime("%Y-%m-%d")
    with open(log_path, "a") as log:
        log.write(f"-----{start}-----\n")
        for (
            course_code,
            term,
            subject_area,
            crosslist_code,
        ) in cursor:
            course_code = course_code.replace(" ", "")
            subject_area = subject_area.replace(" ", "")
            crosslist_code = crosslist_code.replace(" ", "")
            try:
                course = Course.objects.get(course_code=course_code)
                if course.requested:
                    try:
                        canvas_site = course.request.canvas_instance
                    except Exception:
                        logger.info(f"- No main request for {course.course_code}.")
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
                    logger.info(") Deleting {course_code}...")
                    course.delete()
            except Exception:
                logger.info(
                    f"- The canceled course {course_code} doesn't exist in the CRF yet."
                )
