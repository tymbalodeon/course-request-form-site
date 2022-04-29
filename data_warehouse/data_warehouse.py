from dataclasses import dataclass
from functools import lru_cache
from logging import getLogger
from re import findall, search, sub

from config.config import USERNAME
from course.models import Course, ScheduleType, Subject, User
from course.terms import CURRENT_YEAR_AND_TERM, split_year_and_term

from data_warehouse.helpers import get_cursor

logger = getLogger(__name__)
try:
    OWNER = User.objects.get(username=USERNAME)
except Exception:
    OWNER = User.objects.create(username="admin")


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
    if not cursor:
        return
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
        else:
            user = None
            logger.error(f'FAILED to create Profile for "{pennkey}".')
    return user


@dataclass(frozen=True)
class Instructor:
    first_name: str
    last_name: str
    penn_id: str
    penn_key: str
    email: str


@lru_cache
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
        return instructor_object
    except Exception as error:
        logger.error(
            "- ERROR: Failed to create User object for instructor"
            f" {instructor.first_name} {instructor.last_name} ({instructor.penn_id})"
            f" -- {error}"
        )
        return None


def get_instructors(section_id, term):
    cursor = get_cursor()
    if not cursor:
        return
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


def get_data_warehouse_courses(term=CURRENT_YEAR_AND_TERM, logger=logger):
    logger.info(") Pulling courses from the Data Warehouse...")
    term = term.upper()
    cursor = get_cursor()
    if not cursor:
        return
    cursor.execute(
        """
        SELECT
            trim(subject),
            primary_subject,
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
        primary_subject,
        course_num,
        section_num,
        year_and_term,
        schedule_type,
        school,
        title,
        crosslist,
        crosslist_code,
        section_id,
        section_status,
    ) in cursor:
        course_code = f"{subject}{course_num}{section_num}{year_and_term}"
        subject = Subject.objects.get(subject_code=subject)
        primary_subject = Subject.objects.get(subject_code=primary_subject)
        schedule_type = ScheduleType.objects.get(sched_type_code=schedule_type)
        year, term = split_year_and_term(year_and_term)
        title = format_title(title)
        primary_crosslist = ""
        if crosslist and crosslist == "S":
            if crosslist_code:
                crosslist_code = crosslist_code.replace(" ", "")
            primary_crosslist = f"{crosslist_code}{term}"
        school = primary_subject.schools if primary_subject else subject.schools
        primary_subject = primary_subject or subject
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
                    "course_number": course_num,
                    "course_section": section_num,
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
                if instructors:
                    instructors = [
                        get_instructor_object(instructor) for instructor in instructors
                    ]
                    instructors = [
                        instructor for instructor in instructors if instructor
                    ]
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
        if section_status != "A" and course:
            logger.info(f") Deleting canceled course '{course_code}'...")
            course.delete()
    logger.info("FINISHED")
