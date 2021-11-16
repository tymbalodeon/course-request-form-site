from json import load

from django.conf import settings
from django.test import TestCase

from course.terms import CURRENT_YEAR_AND_TERM, NEXT_YEAR_AND_TERM
from open_data.open_data import DEFAULT_PARAMS, OpenData

LOCAL_DATA = settings.BASE_DIR / "open_data/open_data.json"


class OpenDataTest(TestCase):
    open_data = OpenData()

    def test_get_available_terms(self):
        terms = self.open_data.get_available_terms()
        self.assertEqual(terms, [NEXT_YEAR_AND_TERM, CURRENT_YEAR_AND_TERM])

    def test_get_courses_by_term(self):
        courses = self.open_data.get_courses_by_term(CURRENT_YEAR_AND_TERM)
        course_keys = {
            "activity",
            "activity_description",
            "corequisite_activity",
            "corequisite_activity_description",
            "course_department",
            "course_description",
            "course_description_url",
            "course_meeting_message",
            "course_notes",
            "course_notes_message",
            "course_number",
            "course_terms_offered",
            "course_title",
            "credit_and_grade_type",
            "credit_connector",
            "credit_type",
            "credits",
            "crosslist_primary",
            "crosslistings",
            "department_description",
            "department_url",
            "end_date",
            "first_meeting_days",
            "fulfills_college_requirements",
            "grade_type",
            "important_notes",
            "instructors",
            "is_cancelled",
            "is_crosslist_primary",
            "is_not_scheduled",
            "is_special_session",
            "labs",
            "lectures",
            "max_enrollment",
            "max_enrollment_crosslist",
            "maximum_credit",
            "meetings",
            "minimum_credit",
            "prerequisite_notes",
            "primary_instructor",
            "recitations",
            "requirements",
            "requirements_title",
            "section_id",
            "section_id_normalized",
            "section_number",
            "section_title",
            "start_date",
            "syllabus_url",
            "term",
            "term_normalized",
            "term_session",
            "third_party_links",
        }
        self.assertSetEqual(set(next(iter(courses)).keys()), course_keys)

    def test_next_page(self):
        default_page_number = DEFAULT_PARAMS["page_number"]
        self.assertEqual(
            self.open_data.params["page_number"], DEFAULT_PARAMS["page_number"]
        )
        self.open_data.next_page()
        self.assertEqual(self.open_data.params["page_number"], default_page_number + 1)

    def test_get_school_by_subject(self):
        with open(LOCAL_DATA) as local_data:
            school_subject_map = load(local_data)["school_subj_map"]
            local_school = next(iter(school_subject_map.keys()))
            local_subject = next(iter(school_subject_map[local_school]))
        fetched_school = self.open_data.get_school_by_subject(local_subject)
        self.assertEqual(fetched_school, local_school)

    def test_get_available_activities(self):
        fetched_activities = self.open_data.get_available_activities()
        with open(LOCAL_DATA) as local_data:
            local_activities = load(local_data)["activity_map"]
        self.assertEqual(fetched_activities, local_activities)

    def test_get_available_subjects(self):
        fetched_subjects = self.open_data.get_available_subjects()
        with open(LOCAL_DATA) as local_data:
            local_subjects = load(local_data)["departments"]
        self.assertEqual(fetched_subjects, local_subjects)
