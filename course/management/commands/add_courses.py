import json
import logging

from course.models import Activity, Course, School, Subject, User
from django.core.management.base import BaseCommand
from helpers.helpers import get_config_items
from open_data.open_data import OpenData


class Command(BaseCommand):
    help = "Add courses."

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--term",
            type=str,
            help="Limit to a term in the format YYYYT where T is A for Spring, B for Summer, C for Fall.",
        )
        parser.add_argument(
            "-o", "--open-data", action="store_true", help="Pull from the OpenData API."
        )
        parser.add_argument(
            "-l",
            "--local-store",
            action="store_true",
            help="Pull from the local store.",
        )

    def handle(self, **kwargs):
        print(") Adding courses...")

        opendata = kwargs["opendata"]
        year_and_term = kwargs["term"]
        year = year_and_term[:-1]
        term = year_and_term[-1]

        if opendata:
            open_data_id, key, domain = get_config_items("opendata")[:3]
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
                    course["crosslist_primary"] = course["crosslist_primary"].replace(
                        " ", ""
                    )
                    print(f"- Adding {course['section_id']}...")

                    try:
                        subject = Subject.objects.get(
                            abbreviation=course["course_department"]
                        )
                    except Exception:
                        try:
                            school_code = Open_Data.find_school_by_subj(
                                course["course_department"]
                            )
                            school = School.objects.get(opendata_abbr=school_code)
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
                            primary_subject = Subject.objects.get(
                                abbreviation=primary_subject
                            )
                        except Exception:
                            try:
                                school_code = Open_Data.find_school_by_subj(
                                    primary_subject
                                )
                                school = School.objects.get(opendata_abbr=school_code)
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

                        course, created = course_created

                        if created:
                            print("\t* Course CREATED")
                        else:
                            print("\t* Course UPDATED")

                        if course["is_cancelled"]:
                            course.delete()
                    except Exception as error:
                        logging.getLogger("error_logger").error(error)
                        print(f"- ERROR:{error}")

                page += 1
                courses = Open_Data.next_page()

            print("FINISHED")
        else:
            with open("open_data/open_data.json") as json_file:
                courses = json.load(json_file)

                for school, subjects in courses["school_subj_map"].items():
                    try:
                        this_school = School.objects.get(opendata_abbr=school)
                    except Exception as error:
                        print(f"- ERROR: {error}")

                    for subject in subjects:
                        if not Subject.objects.filter(abbreviation=subject).exists():
                            try:
                                subject_name = courses["departments"][subject]
                                Subject.objects.create(
                                    name=subject_name,
                                    abbreviation=subject,
                                    visible=True,
                                    schools=this_school,
                                )
                            except Exception:
                                Subject.objects.create(
                                    name=subject + "-- FIX ME",
                                    abbreviation=subject,
                                    visible=True,
                                    schools=this_school,
                                )
