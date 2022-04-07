from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from logging import getLogger
from re import findall, search, sub

from cx_Oracle import connect
from django.contrib.auth.models import User

from config.config import USERNAME
from course.models import Activity, Course, Profile, School, Subject
from course.terms import CURRENT_YEAR_AND_TERM, split_year_and_term
from open_data.open_data import OpenData

logger = getLogger(__name__)
OWNER = User.objects.get(username=USERNAME)


def get_cursor():
    config = ConfigParser()
    config.read("config/config.ini")
    values = dict(config.items("data_warehouse"))
    connection = connect(values["user"], values["password"], values["service"])
    return connection.cursor()


def get_data_warehouse_schools():
    school_codes = {school.open_data_abbreviation for school in School.objects.all()}
    cursor = get_cursor()
    cursor.execute("SELECT legacy_school_code, school_desc_long FROM dwngss.v_school")
    for abbreviation, name in cursor:
        if not abbreviation in school_codes:
            logger.info(f') Creating school "{name}"...')
            School.objects.create(
                abbreviation=abbreviation,
                open_data_abbreviation=abbreviation,
                name=name,
            )


def get_data_warehouse_school(school_code: str) -> str:
    cursor = get_cursor()
    cursor.execute(
        "SELECT legacy_school_code  FROM dwngss.v_school WHERE school_code ="
        " :school_code",
        school_code=school_code,
    )
    legacy_school_code = ""
    for value in cursor:
        legacy_school_code = next((code for code in value), "")
    return legacy_school_code


def get_data_warehouse_subjects():
    subject_codes = {subject.abbreviation for subject in Subject.objects.all()}
    cursor = get_cursor()
    cursor.execute(
        "SELECT subject_code, subject_desc_long, school_code FROM dwngss.v_subject"
    )
    for abbreviation, name, school_code in cursor:
        if not abbreviation in subject_codes:
            if name is None:
                name = abbreviation
            logger.info(f') Creating subject "{name}"...')
            if school_code is not None:
                legacy_school_code = get_data_warehouse_school(school_code)
                school = School.objects.get(open_data_abbreviation=legacy_school_code)
                Subject.objects.create(
                    abbreviation=abbreviation, name=name, schools=school
                )
            else:
                Subject.objects.create(abbreviation=abbreviation, name=name)


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


def capitalize_roman_numerals(title: str) -> str:
    title = title.upper()
    roman_numeral_regex = (
        r"(?=[MDCLXVI].)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})\)?[^)]$"
    )
    roman_numerals = search(roman_numeral_regex, title)
    if roman_numerals:
        roman_numerals = roman_numerals.group()
        title_base = sub(roman_numerals, "", title)
        title = f"{title_base.title()}{roman_numerals}"
    else:
        title = title.title()
    words_to_capitalize = ["Bc", "Bce", "Ce", "Ad", "Ai", "Snf", "Asl"]
    for word in words_to_capitalize:
        if word in title.split():
            title = title.replace(word, word.upper())
    return title


def format_title(title: str) -> str:
    if not title:
        return "[TBD]"
    try:
        dividers = ["/", "-", ":"]
        parenthesis_regex = r"\(([^\)]+)\)"
        parenthetical = search(parenthesis_regex, title)
        placeholder = "[...]"
        if parenthetical:
            parenthetical = parenthetical.group()
            title = title.replace(parenthetical, placeholder)
        for divider in dividers:
            titles = title.split(divider)
            title = divider.join([capitalize_roman_numerals(title) for title in titles])
            if divider == ":" and findall(r":[^ ]", title):
                title = sub(r":", ": ", title)
        numbers_regex = r"\d(?:S|Nd|Rd|Th|)"
        numbers = findall(numbers_regex, title)
        if numbers:
            for number in numbers:
                title = sub(number, number.lower(), title)
        if parenthetical:
            title = title.replace(placeholder, parenthetical)
        return title
    except Exception as error:
        logger.error(f'- ERROR: Failed to format title "{title}" ({error})')
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


def get_penn_key_from_penn_id(penn_id):
    cursor = get_cursor()
    logger.info(f"Checking Data Warehouse for penn id {penn_id}...")
    cursor.execute(
        """
        SELECT
            first_name, last_name, pennkey
        FROM
            employee_general
        WHERE
            penn_id = :penn_id
        """,
        penn_id=penn_id,
    )
    for first_name, last_name, penn_key in cursor:
        logger.info(
            f'FOUND PennKey "{penn_key}" for {penn_id} ({first_name} {last_name})'
        )
        return penn_key


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


def pull_srs_courses(cursor, term, open_data):
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
                    "owner": OWNER,
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


def get_subject_object(subject, course_code, crosslist=False):
    try:
        return Subject.objects.get(abbreviation=subject)
    except Exception:
        try:
            school_code = OpenData().get_school_by_subject(subject)
            school = School.objects.get(open_data_abbreviation=school_code)
            return Subject.objects.create(
                abbreviation=subject, name=subject, schools=school
            )
        except Exception as error:
            logger.error(
                f"{course_code}:"
                f" {'Primary subject' if crosslist else 'Subject'} {subject} not found"
                f" ({error})"
            )
            return ""


def get_schedule_type_object(schedule_type, course_code):
    try:
        return Activity.objects.get(abbr=schedule_type)
    except Exception:
        try:
            return Activity.objects.create(abbr=schedule_type, name=schedule_type)
        except Exception:
            logger.error(f"{course_code}: Activity {schedule_type} not found")
            return ""


def get_instructors(section_id, term):
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            instructor.instructor_first_name,
            instructor.instructor_last_name,
            instructor.instructor_penn_id,
            employee.pennkey,
            instructor.instructor_email
        FROM dwngss_ps.crse_sect_instructor instructor
        JOIN employee_general_v employee
        ON instructor.instructor_penn_id = employee.penn_id
        WHERE section_id = :section_id
        AND term = :term
        """,
        section_id=section_id,
        term=term,
    )
    instructors = list()
    for first_name, last_name, penn_id, penn_key, email in cursor:
        instructor = Instructor(first_name, last_name, penn_id, penn_key, email)
        instructors.append(instructor)
    return instructors


def get_school_codes_and_descriptions():
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT
            school_code,
            legacy_school_code,
            school_desc_long
        FROM dwngss.v_school_v
        """
    )
    schools = dict()
    for school_code, legacy_school_code, school_desc_long in cursor:
        schools[school_code] = dict()
        schools[school_code]["school_code"] = school_code
        schools[school_code]["legacy_school_code"] = legacy_school_code
        schools[school_code]["school_desc_long"] = school_desc_long
    return schools


@dataclass(frozen=True)
class Instructor:
    first_name: str
    last_name: str
    penn_id: str
    penn_key: str
    email: str


@lru_cache(maxsize=128)
def get_instructor_object(instructor: Instructor):
    try:
        instructor_object = User.objects.update_or_create(
            username=instructor.penn_key,
            defaults={
                "first_name": instructor.first_name,
                "last_name": instructor.last_name,
                "email": instructor.email or "",
            },
        )[0]
        Profile.objects.update_or_create(
            user=instructor_object,
            defaults={"penn_id": instructor.penn_id},
        )
        return instructor_object
    except Exception as error:
        logger.error(
            "- ERROR: Failed to create User object for instructor"
            f" {instructor.first_name} {instructor.last_name} ({instructor.penn_id})"
            f" -- {error}"
        )
        return None


def get_data_warehouse_courses(term=CURRENT_YEAR_AND_TERM, logger=logger):
    logger.info(") Pulling courses from the Data Warehouse...")
    term = term.upper()
    open_data = OpenData()
    cursor = get_cursor()
    old_term = next((character for character in term if character.isalpha()), None)
    if old_term:
        pull_srs_courses(cursor, term, open_data)
    else:
        cursor.execute(
            """
            SELECT
                trim(subject),
                course_num,
                section_num,
                term,
                schedule_type,
                school,
                trim(title),
                xlist_enrlmt,
                xlist_family,
                section_id,
                section_status
            FROM
                dwngss_ps.crse_section
            WHERE schedule_type NOT IN (
                'MED',
                'DIS',
                'FLD',
                'F01',
                'F02',
                'F03',
                'F04',
                'IND',
                'I01',
                'I02',
                'I03',
                'I04',
                'MST',
                'SRT'
            )
            AND school NOT IN ('W', 'L')
            AND term = :term
            """,
            term=term,
        )
        for (
            subject,
            course_number,
            section_number,
            year_and_term,
            schedule_type,
            school,
            title,
            crosslist,
            crosslist_code,
            section_id,
            section_status,
        ) in cursor:
            course_code = f"{subject}{course_number}{section_number}{year_and_term}"
            subject = get_subject_object(subject, course_code)
            year, term = split_year_and_term(year_and_term)
            schedule_type = get_schedule_type_object(schedule_type, course_code)
            title = format_title(title)
            crosslist_code = crosslist_code.replace(" ", "") if crosslist_code else ""
            primary_crosslist = ""
            primary_subject = subject
            if crosslist:
                primary_crosslist = (
                    f"{crosslist_code}{term}" if crosslist == "S" else ""
                )
                primary_subject = "".join(
                    character for character in crosslist_code if character.isalpha()
                )
                primary_subject = get_subject_object(
                    primary_subject, course_code, crosslist=True
                )
            school = primary_subject.schools if primary_subject else ""
            try:
                course, created = Course.objects.update_or_create(
                    course_code=course_code,
                    defaults={
                        "owner": OWNER,
                        "course_term": term,
                        "course_activity": schedule_type,
                        "course_subject": subject,
                        "course_primary_subject": primary_subject,
                        "primary_crosslist": primary_crosslist,
                        "course_schools": school,
                        "course_number": course_number,
                        "course_section": section_number,
                        "course_name": title,
                        "year": year,
                    },
                )
                logger.info(
                    f"- Added course {course_code}"
                    if created
                    else f"- Updated course {course_code}"
                )
            except Exception as error:
                course = None
                logger.error(
                    f"- ERROR: Failed to add or update course {course_code} ({error})"
                )
            if course:
                try:
                    instructors = get_instructors(section_id, year_and_term)
                    instructors = [
                        get_instructor_object(instructor) for instructor in instructors
                    ]
                    instructors = [
                        instructor for instructor in instructors if instructor
                    ]
                    if instructors:
                        course.instructors.clear()
                        for instructor in instructors:
                            course.instructors.add(instructor)
                            logger.info(
                                f"- Updated course {course_code} with instructor:"
                                f" {instructor.username}"
                            )
                        course.save()
                except Exception as error:
                    message = f"Failed to add new instructor(s) to course ({error})"
                    logger.error(message)
            if section_status != "A":
                delete_data_warehouse_canceled_courses(
                    term, query=False, course=(course_code, crosslist_code)
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
                f"- Updated course {course_code} with instructors:"
                f" {', '.join([instructor.username for instructor in instructors])}"
            )
        except Exception as error:
            message = f"Failed to add new instructor(s) to course ({error})"
            logger.error(message)
    logger.info("FINISHED")


def delete_canceled_course(course_code, crosslist_code, log, logger):
    course_code = course_code.replace(" ", "")
    crosslist_code = crosslist_code.replace(" ", "")
    try:
        course = Course.objects.get(course_code=course_code)
        if not course.requested:
            logger.info(f") Deleting {course_code}...")
            course.delete()
        else:
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
    except Exception:
        logger.info(
            f"- The canceled course {course_code} doesn't exist in the CRF yet."
        )


def delete_data_warehouse_canceled_courses(
    term=CURRENT_YEAR_AND_TERM,
    log_path="course/static/log/canceled_courses.log",
    logger=logger,
    query=True,
    course=None,
):
    start = datetime.now().strftime("%Y-%m-%d")
    with open(log_path, "a") as log:
        log.write(f"-----{start}-----\n")
        if query:
            cursor = get_cursor()
            cursor.execute(
                """
                SELECT
                    section_id || term section,
                    subject_area subject_id,
                    xlist_primary
                FROM dwadmin.course_section
                WHERE activity IN (
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
                AND status IN ('X')
                AND tuition_school NOT IN ('WH', 'LW')
                AND term = :term
                """,
                term=term,
            )
            for (
                course_code,
                term,
                crosslist_code,
            ) in cursor:
                delete_canceled_course(course_code, crosslist_code, log, logger)
        elif course:
            course_code, crosslist_code = course
            delete_canceled_course(course_code, crosslist_code, log, logger)
