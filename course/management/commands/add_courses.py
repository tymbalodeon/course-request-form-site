from json import load
from logging import getLogger

from django.core.management.base import BaseCommand

from course.models import Course, ScheduleType, School, Subject, User
from course.utils import split_year_and_term
from data_warehouse.data_warehouse import (
    get_data_warehouse_courses,
    get_data_warehouse_instructors,
)
from open_data.open_data import OpenData

logger = getLogger(__name__)


def pull_from_local_store():
    logger.info(") Pulling courses from the local store...")
    with open("open_data/open_data.json") as json_file:
        courses = load(json_file)
        for school, subjects in courses["school_subj_map"].items():
            try:
                school_object = School.objects.get(open_data_abbreviation=school)
                try:
                    for subject in subjects:
                        subject_name = courses["departments"][subject]
                        (subject_object, created,) = Subject.objects.update_or_create(
                            name=subject_name,
                            abbreviation=subject,
                            visible=True,
                            defaults={"schools": school_object},
                        )
                        logger.info(
                            f"- {'CREATED' if created else 'UPDATED'} subject:"
                            f" {subject_object}."
                        )
                except Exception as error:
                    logger.error(
                        f"- ERROR: Failed to create subject {subject} ({error})"
                    )
            except Exception as error:
                logger.error(f"- ERROR: Failed to locate school {school} ({error})")


def get_user_from_full_name(full_name):
    try:
        first_name, last_name = full_name.split()
        return User.objects.get(first_name=first_name, last_name=last_name)
    except Exception:
        return None


def get_open_data_courses(year_and_term, logger=logger):
    logger.info(") Pulling courses from Open Data...")
    year, term = split_year_and_term(year_and_term)
    open_data = OpenData()
    courses = open_data.get_courses_by_term(year_and_term)
    page = 1
    while courses is not None:
        logger.info(f"PAGE {page}")
        if courses == "ERROR":
            logger.error("ERROR")
            return
        if isinstance(courses, dict):
            courses = [courses]
        for course in courses:
            course["section_id"] = course["section_id"].replace(" ", "")
            course["crosslist_primary"] = course["crosslist_primary"].replace(" ", "")
            try:
                subject = Subject.objects.get(abbreviation=course["course_department"])
            except Exception:
                try:
                    school_code = open_data.get_school_by_subject(
                        course["course_department"]
                    )
                    school = School.objects.get(open_data_abbreviation=school_code)
                    subject = Subject.objects.create(
                        abbreviation=course["course_department"],
                        name=course["department_description"],
                        schools=school,
                    )
                except Exception as error:
                    message = (
                        "Failed to find and create subject"
                        f" {course['course_department']}"
                    )
                    logger.error(f"{message} ({error})")

            if course["crosslist_primary"]:
                primary_subject = course["crosslist_primary"][:-6]
                try:
                    primary_subject = Subject.objects.get(abbreviation=primary_subject)
                except Exception:
                    try:
                        school_code = open_data.get_school_by_subject(primary_subject)
                        school = School.objects.get(open_data_abbreviation=school_code)
                        primary_subject = Subject.objects.create(
                            abbreviation=primary_subject,
                            name=course["department_description"],
                            schools=school,
                        )
                    except Exception as error:
                        message = (
                            "Failed to find and create primary subject"
                            f" {course['course_department']}"
                        )
                        logger.error(f"{message} ({error})")

            else:
                primary_subject = subject
            school = primary_subject.schools
            try:
                activity = ScheduleType.objects.get(abbr=course["activity"])
            except Exception:
                try:
                    activity = ScheduleType.objects.create(
                        abbr=course["activity"], name=course["activity"]
                    )
                except Exception as error:
                    message = f"Failed to find activity {course['activity']}"
                    logger.error(f"{message} ({error})")
            try:
                course_created = Course.objects.update_or_create(
                    course_code=f"{course['section_id']}{year_and_term}",
                    defaults={
                        "owner": User.objects.get(username="benrosen"),
                        "course_term": term,
                        "course_activity": activity,
                        "course_subject": subject,
                        "course_primary_subject": primary_subject,
                        "primary_crosslist": course["crosslist_primary"],
                        "course_schools": school,
                        "course_number": course["course_number"],
                        "course_section": course["section_number"],
                        "course_name": course["course_title"],
                        "year": year,
                    },
                )
                course_object, created = course_created
                if course["instructors"] and not course_object.requested:
                    try:
                        instructors = [
                            get_user_from_full_name(instructor["name"])
                            for instructor in course["instructors"]
                            if get_user_from_full_name(instructor["name"])
                        ]
                        if instructors:
                            course_object.instructors.clear()
                            for instructor in instructors:
                                course_object.instructors.add(instructor)
                                course_object.save()
                            instructors_display = ", ".join(
                                [instructor.username for instructor in instructors]
                            )
                            logger.info(
                                f"- Updated {course['section_id']} with instructors: "
                                f"{instructors_display}"
                            )
                    except Exception as error:
                        logger.error(
                            f"Failed to update instructors from Open Data ({error})"
                        )
                logger.info(
                    f"- {'CREATED' if created else 'UPDATED'} {course['section_id']}"
                )
                if course["is_cancelled"]:
                    course_object.delete()
            except Exception as error:
                logger.error(error)
        page += 1
        courses = open_data.next_page()
    logger.info("FINISHED")


class Command(BaseCommand):
    help = "Add courses."

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--term",
            type=str,
            help=(
                "Limit to a term in the format YYYYT where T is A for Spring, B for"
                " Summer, C for Fall."
            ),
        )
        parser.add_argument(
            "-o", "--open-data", action="store_true", help="Pull from the OpenData API."
        )
        parser.add_argument(
            "-d",
            "--data-warehouse",
            action="store_true",
            help="Pull from the Data Warehouse.",
        )
        parser.add_argument(
            "-i",
            "--instructors",
            action="store_true",
            help="Pull course instructors from the Data Warehouse.",
        )
        parser.add_argument(
            "-l",
            "--local",
            action="store_true",
            help="Pull from the local store.",
        )

    def handle(self, **kwargs):
        open_data = kwargs["open_data"]
        data_warehouse = kwargs["data_warehouse"]
        instructors = kwargs["instructors"]
        local = kwargs["local"]
        if local or (
            not open_data and not data_warehouse and not get_data_warehouse_instructors
        ):
            pull_from_local_store()
            return
        year_and_term = kwargs["term"].upper()
        if open_data:
            get_open_data_courses(year_and_term)
        if data_warehouse:
            get_data_warehouse_courses(year_and_term)
        if instructors:
            get_data_warehouse_instructors(year_and_term)
