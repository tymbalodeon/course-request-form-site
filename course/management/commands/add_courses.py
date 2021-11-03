import json
import logging

from django.core.management.base import BaseCommand

from config.config import get_config_options
from course.models import Activity, Course, School, Subject, User
from data_warehouse.data_warehouse import pull_courses, pull_instructors
from open_data.open_data import OpenData


def pull_from_local_store():
    print(") Pulling courses from the local store...")

    with open("open_data/open_data.json") as json_file:
        courses = json.load(json_file)

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
                        print(
                            f"- {'CREATED' if created else 'UPDATED'} subject:"
                            f" {subject_object}."
                        )
                except Exception as error:
                    print(f"- ERROR: Failed to create subject {subject} ({error})")
            except Exception as error:
                print(f"- ERROR: Failed to locate school {school} ({error})")


def pull_from_open_data(year_and_term):
    print(") Pulling courses from Open Data...")

    year = year_and_term[:-1]
    term = year_and_term[-1]
    open_data_id, key, domain = get_config_options("open_data")
    Open_Data = OpenData(base_url=domain, id=open_data_id, key=key)
    courses = Open_Data.get_courses_by_term(year_and_term)
    page = 1

    while courses is not None:
        print(f"PAGE {page}")

        if courses == "ERROR":
            print("ERROR")

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
                    school_code = Open_Data.find_school_by_subj(
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
                    logging.getLogger("error_logger").error(message)
                    print(f"- ERROR: {message} ({error})")

            if course["crosslist_primary"]:
                primary_subject = course["crosslist_primary"][:-6]

                try:
                    primary_subject = Subject.objects.get(abbreviation=primary_subject)
                except Exception:
                    try:
                        school_code = Open_Data.find_school_by_subj(primary_subject)
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
                        logging.getLogger("error_logger").error(message)
                        print(f"- ERROR: {message} ({error})")

            else:
                primary_subject = subject

            school = primary_subject.schools

            try:
                activity = Activity.objects.get(abbr=course["activity"])
            except Exception:
                try:
                    activity = Activity.objects.create(
                        abbr=course["activity"], name=course["activity"]
                    )
                except Exception as error:
                    message = f"Failed to find activity {course['activity']}"
                    logging.getLogger("error_logger").error(message)
                    print(f"- ERROR: {message} ({error})")

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

                print(f"- {'CREATED' if created else 'UPDATED'} {course['section_id']}")

                if course["is_cancelled"]:
                    course_object.delete()
            except Exception as error:
                logging.getLogger("error_logger").error(error)
                print(f"- ERROR:{error}")

        page += 1
        courses = Open_Data.next_page()

    print("FINISHED")


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

        if local or (not open_data and not data_warehouse and not pull_instructors):
            pull_from_local_store()

            return

        year_and_term = kwargs["term"].upper()

        if open_data:
            pull_from_open_data(year_and_term)

        if data_warehouse:
            pull_courses(year_and_term)

        if instructors:
            pull_instructors(year_and_term)
