import csv
import sys

from course.models import Course
from open_data.open_data import get_open_data_connection


def find_crosslistings(year_term):
    open_data = get_open_data_connection()
    courses = open_data.get_courses_by_term(year_term)
    page = 1
    crosslisting_fix = list()

    while courses is not None:
        print(f"\n\tSTARTING PAGE: {page}")

        if courses == "ERROR":
            print("ERROR")
            sys.exit()

        if isinstance(courses, dict):
            courses = [courses]

        for course in courses:
            course["section_id"] = course["section_id"].replace(" ", "")
            course["crosslist_primary"] = course["crosslist_primary"].replace(" ", "")

            if (
                course["section_id"] != course["crosslist_primary"]
                and course["crosslist_primary"] != ""
            ):
                section_id = course["section_id"][-6:][:3]
                crosslist_primary = course["crosslist_primary"][-6:][:3]

                if crosslist_primary != section_id:
                    crosslisting_fix.append(
                        [course["section_id"], course["crosslist_primary"]]
                    )
                    print(course["section_id"], course["crosslist_primary"])

        page += 1
        courses = open_data.next_page()


def fix_crosslistings(courses, year_and_term):
    with open("crosslisting_check.csv", mode="w") as check:
        check = csv.writer(check, delimiter=",", quotechar='"')

        for course in courses:
            section = f"{course[0]}{year_and_term}"
            primary = f"{course[1]}{year_and_term}"

            try:
                crf_course = Course.objects.get(course_code=section)
            except Exception:
                crf_course = None
            try:
                crf_primary = Course.objects.get(course_code=primary)
            except Exception:
                crf_primary = None

            if crf_course and crf_primary:
                crf_course.primary_crosslist = primary

                if crf_course.requested or crf_primary.requested:
                    check.writerow(["needs_review", section, primary])
                elif not crf_course.requested and not crf_primary.requested:
                    print("adding", section, primary)
                    crf_course.crosslisted.add(crf_primary)
                    check.writerow(["added_cx", section, primary])
                crf_course.save()
            else:
                if crf_course:
                    crf_course.crosslist_primary = crf_primary
                    crf_course.save()
                    print(primary, " doesnt exits")
                elif crf_primary:
                    print(section, " doesnt exits")
                else:
                    check.writerow(["neither exist", section, primary])
