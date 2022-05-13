from dataclasses import dataclass
from unittest.mock import patch

from django.test import TestCase

from form.models import Request, ScheduleType, School, Section, Subject, User
from form.terms import CURRENT_TERM, TWO_TERMS_AHEAD

EXECUTE_QUERY = "form.models.execute_query"
GET_CANVAS_USER_ID_BY_PENNKEY = "form.models.get_canvas_user_id_by_pennkey"
GET_ALL_CANVAS_ACCOUNTS = "form.models.get_all_canvas_accounts"
PENNKEY = "testuser"
FIRST_NAME = "Test"
LAST_NAME = "User"
PENN_ID = 1234567
EMAIL = "testuser@upenn.edu"
CANVAS_ID = 7654321
SCHED_TYPE_CODE = "SCH"
SCHED_TYPE_DESC = "Schedule Type Description"
SCHOOL_CODE = "SCHL"
SCHOOL_DESC_LONG = "School Description"
SUBJECT_CODE = "SUBJ"
SUBJECT_DESC_LONG = "Subject Description"
COURSE_NUM = 1000
SECTION_NUM = 200
TERM = CURRENT_TERM
TITLE = "Course Title"
INSTRUCTORS = (
    (PENNKEY, FIRST_NAME, LAST_NAME, PENN_ID, EMAIL),
    (None, None, None, None, None),
)
PRIMARY_SUBJECT_CODE = "PRIM"
PRIMARY_SUBJECT_DESC_LONG = f"Primary {SUBJECT_DESC_LONG}"


def create_user():
    return User.objects.create(
        username=PENNKEY, first_name=FIRST_NAME, last_name=LAST_NAME
    )


def get_mock_code_and_description(model: str) -> tuple:
    description = "Description"
    return (
        ("ABCD", f"First {model} {description}"),
        ("EFGH", f"Second {model} {description}"),
        ("IJKL", f"Third {model} {description}"),
        (None, None),
    )


def create_section(
    school_code,
    school_desc_long,
    subject_code,
    subject_desc_long,
    sched_type_code,
    sched_type_desc,
    course_num,
    section_num,
    term,
    title,
):
    school, _ = School.objects.update_or_create(
        school_code=school_code, school_desc_long=school_desc_long
    )
    subject, _ = Subject.objects.update_or_create(
        subject_code=subject_code, subject_desc_long=subject_desc_long
    )
    schedule_type, _ = ScheduleType.objects.update_or_create(
        sched_type_code=sched_type_code, sched_type_desc=sched_type_desc
    )
    section_id = f"{subject.subject_code}{course_num}{section_num}"
    section_code = f"{section_id}{term}"
    return Section.objects.create(
        section_code=section_code,
        section_id=section_id,
        school=school,
        subject=subject,
        primary_subject=subject,
        course_num=course_num,
        section_num=section_num,
        term=term,
        title=title,
        schedule_type=schedule_type,
    )


def get_mock_values_success_count(values: tuple) -> int:
    number_of_succes_fields = 2
    success_values = [value for value in values if all(value[:number_of_succes_fields])]
    return len(success_values)


class UserTest(TestCase):
    new_first_name = "New"
    new_last_name = "Name"
    new_penn_id = 1234568
    new_email = "newname@upenn.edu"
    new_canvas_id = 7654322

    @classmethod
    def get_mock_data_warehouse_response(cls, new=False, blank=False):
        if new:
            return (
                (
                    cls.new_first_name.upper(),
                    cls.new_last_name.upper(),
                    cls.new_penn_id,
                    f"{cls.new_email}    ",
                ),
            )
        elif blank:
            return ((None, None, None, None),)
        else:
            return (
                (
                    FIRST_NAME.upper(),
                    LAST_NAME.upper(),
                    PENN_ID,
                    f"{EMAIL}    ",
                ),
            )

    @patch(EXECUTE_QUERY)
    @patch(GET_CANVAS_USER_ID_BY_PENNKEY)
    def test_str(self, mock_get_canvas_user_id_by_pennkey, mock_execute_query):
        mock_execute_query.return_value = self.get_mock_data_warehouse_response()
        mock_get_canvas_user_id_by_pennkey.return_value = CANVAS_ID
        user = create_user()
        user_string = str(user)
        user_first_and_last_and_username = "Test User (testuser)"
        self.assertEqual(user_string, user_first_and_last_and_username)

    @patch(EXECUTE_QUERY)
    @patch(GET_CANVAS_USER_ID_BY_PENNKEY)
    def test_create_user(self, mock_get_canvas_user_id_by_pennkey, mock_execute_query):
        mock_execute_query.return_value = self.get_mock_data_warehouse_response()
        mock_get_canvas_user_id_by_pennkey.return_value = CANVAS_ID
        user = User(username=PENNKEY)
        empty_values = (
            user.first_name,
            user.last_name,
            user.penn_id,
            user.email,
        )
        self.assertFalse(any(empty_values))
        user.save()
        self.assertEqual(user.first_name, FIRST_NAME)
        self.assertEqual(user.last_name, LAST_NAME)
        self.assertEqual(user.penn_id, PENN_ID)
        self.assertEqual(user.email, EMAIL)

    @patch(EXECUTE_QUERY)
    @patch(GET_CANVAS_USER_ID_BY_PENNKEY)
    def test_sync_dw_info(self, mock_get_canvas_user_id_by_pennkey, mock_execute_query):
        mock_execute_query.return_value = self.get_mock_data_warehouse_response()
        mock_get_canvas_user_id_by_pennkey.return_value = CANVAS_ID
        user = create_user()
        mock_execute_query.return_value = self.get_mock_data_warehouse_response(
            new=True
        )
        user.sync_dw_info()
        self.assertEqual(user.first_name, self.new_first_name)
        self.assertEqual(user.last_name, self.new_last_name)
        self.assertEqual(user.penn_id, self.new_penn_id)
        self.assertEqual(user.email, self.new_email)
        mock_execute_query.return_value = self.get_mock_data_warehouse_response(
            blank=True
        )
        user.sync_dw_info()
        self.assertFalse(user.first_name)
        self.assertFalse(user.last_name)
        self.assertIsNone(user.penn_id)
        self.assertFalse(user.email)


class ScheduleTypeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.schedule_type = ScheduleType.objects.create(
            sched_type_code=SCHED_TYPE_CODE, sched_type_desc=SCHED_TYPE_DESC
        )

    def test_str(self):
        schedule_type_string = str(self.schedule_type)
        sched_type_desc_and_code = "Schedule Type Description (SCH)"
        self.assertEqual(schedule_type_string, sched_type_desc_and_code)

    @patch(EXECUTE_QUERY)
    def test_sync_all(self, mock_execute_query):
        schedule_type_count = ScheduleType.objects.count()
        self.assertEqual(schedule_type_count, 1)
        mock_schedule_types = get_mock_code_and_description("Schedule Type")
        mock_execute_query.return_value = mock_schedule_types
        ScheduleType.sync_all()
        success_schedule_type_count = get_mock_values_success_count(mock_schedule_types)
        expected_schedule_type_count = success_schedule_type_count + schedule_type_count
        schedule_type_count = ScheduleType.objects.count()
        self.assertEqual(schedule_type_count, expected_schedule_type_count)

    @patch(EXECUTE_QUERY)
    def test_sync_schedule_type(self, mock_execute_query):
        new_sched_type_desc = "New Schedule Type Description"
        mock_execute_query.return_value = ((SCHED_TYPE_CODE, new_sched_type_desc),)
        ScheduleType.sync_schedule_type(SCHED_TYPE_CODE)
        schedule_type = ScheduleType.objects.get(sched_type_code=SCHED_TYPE_CODE)
        self.assertEqual(schedule_type.sched_type_desc, new_sched_type_desc)


@dataclass
class MockAccount:
    id: int
    name: str


class SchoolTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(
            school_code=SCHOOL_CODE, school_desc_long=SCHOOL_DESC_LONG
        )

    def test_str(self):
        school_string = str(self.school)
        school_desc_and_code = "School Description (SCHL)"
        self.assertEqual(school_string, school_desc_and_code)

    def test_save(self):
        school = self.school
        self.assertFalse(school.get_subjects())
        Subject.objects.create(
            subject_code=SUBJECT_CODE,
            subject_desc_long=SUBJECT_DESC_LONG,
            school=school,
        )
        school.save()
        subjects = school.get_subjects()
        subject = next(subject for subject in subjects)
        self.assertTrue(subjects)
        self.assertTrue(len(subjects), 1)
        self.assertEqual(subject.subject_code, SUBJECT_CODE)

    @patch(EXECUTE_QUERY)
    @patch(GET_ALL_CANVAS_ACCOUNTS)
    def test_sync_all(self, mock_get_all_canvas_accounts, mock_execute_query):
        school_count = School.objects.count()
        self.assertEqual(school_count, 1)
        mock_schools = get_mock_code_and_description("School")
        mock_execute_query.return_value = mock_schools
        mock_get_all_canvas_accounts.return_value = [
            MockAccount(id=1, name=f"First {SCHOOL_DESC_LONG}")
        ]
        School.sync_all()
        success_school_count = get_mock_values_success_count(mock_schools)
        expected_school_count = success_school_count + school_count
        school_count = School.objects.count()
        self.assertEqual(school_count, expected_school_count)


class SubjectTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(
            subject_code=SUBJECT_CODE, subject_desc_long=SUBJECT_DESC_LONG
        )

    def test_str(self):
        subject_string = str(self.subject)
        subject_desc_and_code = "Subject Description (SUBJ)"
        self.assertEqual(subject_string, subject_desc_and_code)

    @patch(EXECUTE_QUERY)
    @patch(GET_ALL_CANVAS_ACCOUNTS)
    def test_sync_all(self, mock_get_all_canvas_accounts, mock_execute_query):
        subject_count = Subject.objects.count()
        self.assertEqual(subject_count, 1)
        mock_subjects = (
            ("ABCD", f"First {SUBJECT_DESC_LONG}", SCHOOL_CODE),
            ("EFGH", f"Second {SUBJECT_DESC_LONG}", SCHOOL_CODE),
            ("IJKL", f"Third {SUBJECT_DESC_LONG}", ()),
            (None, None, None),
        )
        mock_school = ((SCHOOL_CODE, SCHOOL_DESC_LONG),)
        mock_school_not_found = ((None, None),)
        mock_execute_query.side_effect = [
            mock_subjects,
            mock_school,
            mock_school_not_found,
        ]
        mock_get_all_canvas_accounts.return_value = [MockAccount(1, SCHOOL_DESC_LONG)]
        Subject.sync_all()
        success_subject_count = get_mock_values_success_count(mock_subjects)
        expected_subject_count = success_subject_count + subject_count
        subject_count = Subject.objects.count()
        self.assertEqual(subject_count, expected_subject_count)


class SectionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.section = create_section(
            SCHOOL_CODE,
            SCHOOL_DESC_LONG,
            SUBJECT_CODE,
            SUBJECT_DESC_LONG,
            SCHED_TYPE_CODE,
            SCHED_TYPE_DESC,
            COURSE_NUM,
            SECTION_NUM,
            TERM,
            TITLE,
        )

    def test_str(self):
        section_string = str(self.section)
        section_code = f"SUBJ1000200{TERM}"
        self.assertEqual(section_string, section_code)

    @patch(EXECUTE_QUERY)
    def test_sync_instructors(self, mock_execute_query):
        mock_execute_query.return_value = INSTRUCTORS
        self.assertFalse(self.section.instructors.exists())
        self.section.sync_instructors()
        section = Section.objects.get(section_code=self.section.section_code)
        self.assertTrue(section.instructors.exists())

    @patch(EXECUTE_QUERY)
    def test_sync_also_offered_as_sections(self, mock_execute_query):
        related_code = "REL"
        related_description = "Related"
        related_section = create_section(
            SCHOOL_CODE,
            SCHOOL_DESC_LONG,
            f"{related_code}{SUBJECT_CODE}",
            f"{related_description}{SUBJECT_DESC_LONG}",
            f"{related_code}{SCHED_TYPE_CODE}",
            f"{related_description}{SCHED_TYPE_DESC}",
            COURSE_NUM,
            SECTION_NUM,
            TERM,
            TITLE,
        )
        mock_execute_query.return_value = ((related_section.section_id,),)
        self.assertFalse(self.section.also_offered_as.exists())
        self.section.sync_also_offered_as_sections()
        section = Section.objects.get(section_code=self.section.section_code)
        self.assertTrue(section.also_offered_as.exists())

    @patch(EXECUTE_QUERY)
    def test_sync_course_sections(self, mock_execute_query):
        related_code = "REL"
        related_description = "Related"
        related_section = create_section(
            SCHOOL_CODE,
            SCHOOL_DESC_LONG,
            SUBJECT_CODE,
            SUBJECT_DESC_LONG,
            f"{related_code}{SCHED_TYPE_CODE}",
            f"{related_description}{SCHOOL_DESC_LONG}",
            COURSE_NUM,
            321,
            TERM,
            TITLE,
        )
        mock_execute_query.return_value = ((related_section.section_id,),)
        self.assertFalse(self.section.course_sections.exists())
        self.section.sync_course_sections()
        section = Section.objects.get(section_code=self.section.section_code)
        self.assertTrue(section.course_sections.exists())

    @classmethod
    def get_mock_section_data(
        cls, scheduled_with=False, active=True, unsynced=False, new_schedule_type=False
    ):
        primary_course_id = f"{PRIMARY_SUBJECT_CODE}{COURSE_NUM}"
        course_id = (
            f"{SUBJECT_CODE}{COURSE_NUM}" if scheduled_with else primary_course_id
        )
        primary_section_id = f"{primary_course_id}{SECTION_NUM}"
        section_id = (
            f"{course_id}{SECTION_NUM}" if scheduled_with else primary_section_id
        )
        section_code = "RAND1234567" if unsynced else f"{section_id}{TERM}"
        primary_subject = PRIMARY_SUBJECT_CODE
        subject = SUBJECT_CODE if scheduled_with else primary_subject
        schedule_type = "NEW" if new_schedule_type else SCHED_TYPE_CODE
        status_code = "A" if active else "X"
        xlist_family = f"{CURRENT_TERM}A1234"
        return (
            section_code,
            section_id,
            SCHOOL_CODE,
            subject,
            COURSE_NUM,
            SECTION_NUM,
            TERM,
            TITLE,
            schedule_type,
            status_code,
            primary_course_id,
            primary_section_id,
            primary_subject,
            course_id,
            xlist_family,
        )

    def test_get_terms_query_and_bindings(self):
        _, bindings = Section.get_terms_query_and_bindings(TWO_TERMS_AHEAD)
        terms = bindings.values()
        self.assertTrue(TWO_TERMS_AHEAD in terms)
        self.assertFalse(CURRENT_TERM in terms)
        _, bindings = Section.get_terms_query_and_bindings([TWO_TERMS_AHEAD])
        self.assertTrue(TWO_TERMS_AHEAD in terms)
        self.assertFalse(CURRENT_TERM in terms)

    @patch(EXECUTE_QUERY)
    def test_sync_all(self, mock_execute_query):
        Subject.objects.create(
            subject_code=PRIMARY_SUBJECT_CODE,
            subject_desc_long=PRIMARY_SUBJECT_DESC_LONG,
        )
        instructors = INSTRUCTORS[0]
        mock_active_section = self.get_mock_section_data()
        mock_canceled_section = self.get_mock_section_data(active=False)
        mock_unsynced_canceled_section = self.get_mock_section_data(
            active=False, unsynced=True
        )
        mock_scheduled_with_section = self.get_mock_section_data(scheduled_with=True)
        mock_new_schedule_type_section = self.get_mock_section_data(
            new_schedule_type=True
        )
        also_offered_with = (("PRIM1000200",),)
        course_sections = (("SUBJ1000201",),)
        new_schedule_type = (("NEW", f"New {SCHED_TYPE_DESC}"),)
        mock_execute_query.side_effect = [
            (
                mock_active_section,
                mock_canceled_section,
                mock_unsynced_canceled_section,
                mock_scheduled_with_section,
                mock_new_schedule_type_section,
            ),
            (instructors,),
            (mock_active_section,),
            (mock_active_section,),
            (instructors,),
            (mock_active_section,),
            (mock_active_section,),
            (instructors,),
            course_sections,
            (mock_active_section,),
            (instructors,),
            (mock_active_section,),
            (instructors,),
            new_schedule_type,
            (mock_active_section,),
            (instructors,),
            (mock_active_section,),
            new_schedule_type,
            (instructors,),
            also_offered_with,
            course_sections,
            (mock_active_section,),
        ]
        Section.sync_all()

    @patch(EXECUTE_QUERY)
    def test_sync(self, mock_execute_query):
        mock_execute_query.side_effect = [
            (self.get_mock_section_data(scheduled_with=True),),
            ((PRIMARY_SUBJECT_CODE, PRIMARY_SUBJECT_DESC_LONG, SCHOOL_CODE),),
            (self.get_mock_section_data(),),
        ]
        self.section.sync()
        section = Section.objects.get(section_code=self.section.section_code)
        self.assertEqual(
            section.primary_section.section_code, f"PRIM1000200{CURRENT_TERM}"
        )
        self.assertEqual(section.primary_section.section_id, "PRIM1000200")
        self.assertEqual(section.primary_section_id, f"PRIM1000200{CURRENT_TERM}")
        self.assertEqual(section.primary_subject.subject_code, PRIMARY_SUBJECT_CODE)
        self.assertEqual(section.primary_course_id, f"{PRIMARY_SUBJECT_CODE}1000")


class RequestTest(TestCase):
    @classmethod
    @patch(EXECUTE_QUERY)
    @patch(GET_CANVAS_USER_ID_BY_PENNKEY)
    def setUpTestData(cls, mock_get_canvas_user_id_by_pennkey, mock_execute_query):
        mock_execute_query.return_value = (
            (
                FIRST_NAME.upper(),
                LAST_NAME.upper(),
                PENN_ID,
                f"{EMAIL}    ",
            ),
        )
        mock_get_canvas_user_id_by_pennkey.return_value = CANVAS_ID
        section = create_section(
            SCHOOL_CODE,
            SCHOOL_DESC_LONG,
            SUBJECT_CODE,
            SUBJECT_DESC_LONG,
            SCHED_TYPE_CODE,
            SCHED_TYPE_DESC,
            COURSE_NUM,
            SECTION_NUM,
            TERM,
            TITLE,
        )
        user = create_user()
        cls.request = Request.objects.create(section=section, requester=user)

    def test_str(self):
        request_string = str(self.request)
        section_code = f"SUBJ1000200{TERM}"
        self.assertEqual(request_string, section_code)
