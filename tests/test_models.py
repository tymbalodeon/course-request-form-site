from dataclasses import dataclass, field
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


@dataclass
class MockUser:
    id: int
    unique_id: str
    sis_user_id: str
    name: str
    email: str


@dataclass
class MockAccount:
    id: int
    name: str
    users: list[MockUser] = field(default_factory=list)

    def create_user(self, pseudonym, user, communication_channel):
        unique_id = pseudonym["unique_id"]
        sis_user_id = pseudonym["sis_user_id"]
        name = user["name"]
        email = communication_channel["address"]
        user_id = len(self.users) + CANVAS_ID
        user = MockUser(user_id, unique_id, sis_user_id, name, email)
        self.users.append(user)
        return user


def create_user():
    return User.objects.create(
        username=PENNKEY, first_name=FIRST_NAME, last_name=LAST_NAME
    )


def get_mock_code_and_description(model: str) -> tuple:
    description = "Description"
    return (
        ("ABCD", f"First {model} {description}"),
        ("EFGH", f"Second {model} {description}"),
        ("L", f"Third {model} {description}"),
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
    def get_mock_user(cls, updated=False, blank=False):
        user = (
            (
                FIRST_NAME.upper(),
                LAST_NAME.upper(),
                PENN_ID,
                f"{EMAIL}    ",
            ),
        )
        updated_user = (
            (
                (
                    cls.new_first_name.upper(),
                    cls.new_last_name.upper(),
                    cls.new_penn_id,
                    f"{cls.new_email}    ",
                )
            ),
        )
        blank_user = ((None, None, None, None),)
        if updated:
            return updated_user
        elif blank:
            return blank_user
        else:
            return user

    @patch(EXECUTE_QUERY)
    @patch(GET_CANVAS_USER_ID_BY_PENNKEY)
    def test_str(self, mock_get_canvas_user_id_by_pennkey, mock_execute_query):
        mock_execute_query.return_value = self.get_mock_user()
        mock_get_canvas_user_id_by_pennkey.return_value = CANVAS_ID
        user = create_user()
        user_string = str(user)
        user_first_and_last_and_username = "Test User (testuser)"
        self.assertEqual(user_string, user_first_and_last_and_username)

    @patch(EXECUTE_QUERY)
    @patch(GET_CANVAS_USER_ID_BY_PENNKEY)
    def test_create_user(self, mock_get_canvas_user_id_by_pennkey, mock_execute_query):
        mock_execute_query.return_value = self.get_mock_user()
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
    def test_sync_dw_info(self, mock_execute_query):
        mock_user = self.get_mock_user()
        mock_updated_user = self.get_mock_user(updated=True)
        mock_blank_user = self.get_mock_user(blank=True)
        mock_execute_query.side_effect = [mock_user, mock_updated_user, mock_blank_user]
        user = create_user()
        user.sync_dw_info()
        self.assertEqual(user.first_name, self.new_first_name)
        self.assertEqual(user.last_name, self.new_last_name)
        self.assertEqual(user.penn_id, self.new_penn_id)
        self.assertEqual(user.email, self.new_email)
        user.sync_dw_info()
        self.assertFalse(user.first_name)
        self.assertFalse(user.last_name)
        self.assertIsNone(user.penn_id)
        self.assertFalse(user.email)

    @patch(EXECUTE_QUERY)
    @patch(GET_CANVAS_USER_ID_BY_PENNKEY)
    @patch("form.models.get_canvas_main_account")
    def test_get_canvas_id(
        self,
        mock_get_canvas_main_account,
        mock_get_canvas_user_id_by_pennkey,
        mock_execute_query,
    ):
        mock_execute_query.return_value = self.get_mock_user()
        mock_get_canvas_user_id_by_pennkey.side_effect = [None, CANVAS_ID]
        mock_get_canvas_main_account.return_value = MockAccount(1, "Mock Account")
        user = create_user()
        canvas_id = user.get_canvas_id()
        self.assertEqual(canvas_id, CANVAS_ID)
        canvas_id = user.get_canvas_id()
        self.assertEqual(canvas_id, CANVAS_ID)


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

    def test_get_canvas_school_name(self):
        veterinary_medicine_code = "V"
        veterinary_medicine_name = "Veterinary Medicine"
        dental_medicine_code = "D"
        dental_medicine_name = "Dental Medicine"
        school_of_arts_and_sciences_code = "A"
        school_of_arts_and_sciences_name = "School of Arts & Sciences"
        School.objects.create(
            school_code=veterinary_medicine_code,
            school_desc_long=veterinary_medicine_name,
        )
        School.objects.create(
            school_code=dental_medicine_code,
            school_desc_long=dental_medicine_name,
        )
        School.objects.create(
            school_code=school_of_arts_and_sciences_code,
            school_desc_long=school_of_arts_and_sciences_name,
        )
        veterinary_medicine = School.objects.get(school_code=veterinary_medicine_code)
        dental_medicine = School.objects.get(school_code=dental_medicine_code)
        school_of_arts_and_sciences = School.objects.get(
            school_code=school_of_arts_and_sciences_code
        )
        veterinary_medicine_canvas_name = veterinary_medicine.get_canvas_school_name()
        dental_medicine_canvas_name = dental_medicine.get_canvas_school_name()
        school_of_arts_and_sciences_canvas_name = (
            school_of_arts_and_sciences.get_canvas_school_name()
        )
        self.assertEqual(veterinary_medicine_canvas_name, "Penn Vet")
        self.assertEqual(dental_medicine_canvas_name, "Penn Dental Medicine")
        self.assertEqual(
            school_of_arts_and_sciences_canvas_name, "School of Arts and Sciences"
        )

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
        success_school_count = 2
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
    mock_instructors_response = (INSTRUCTORS[0],)
    mock_empty_response = ()
    canvas_course_code = f"SUBJ 1000-200 {CURRENT_TERM}"
    canvas_sis_code = f"SUBJ-1000-200 {CURRENT_TERM}"
    canvas_schedule_type_code = f"SUBJ 1000-200 {CURRENT_TERM} SCH"
    canvas_sis_id = f"BAN_SUBJ-1000-200 {CURRENT_TERM}"
    canvas_name = f"SUBJ 1000-200 {CURRENT_TERM} Course Title"

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
        cls,
        primary=True,
        other_course_section=False,
        canceled=False,
        unsynced=False,
        new_schedule_type=False,
        bad_value=False,
    ):
        course_num = "9999" if unsynced else COURSE_NUM
        section_num = SECTION_NUM + 1 if other_course_section else SECTION_NUM
        primary_course_id = f"{PRIMARY_SUBJECT_CODE}{course_num}"
        course_id = primary_course_id if primary else f"{SUBJECT_CODE}{course_num}"
        primary_section_id = f"{primary_course_id}{section_num}"
        section_id = primary_section_id if primary else f"{course_id}{section_num}"
        section_code = None if bad_value else f"{section_id}{TERM}"
        primary_subject = PRIMARY_SUBJECT_CODE
        subject = primary_subject if primary else SUBJECT_CODE
        schedule_type = "NEW" if new_schedule_type else SCHED_TYPE_CODE
        status_code = "X" if canceled else "A"
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
        mock_primary_section = self.get_mock_section_data()
        mock_canceled_section = self.get_mock_section_data(canceled=True)
        mock_unsynced_canceled_section = self.get_mock_section_data(
            canceled=True, unsynced=True
        )
        mock_secondary_section = self.get_mock_section_data(primary=False)
        mock_new_schedule_type_section = self.get_mock_section_data(
            new_schedule_type=True
        )
        mock_bad_value_section = self.get_mock_section_data(bad_value=True)
        new_schedule_type = (("NEW", f"New {SCHED_TYPE_DESC}"),)
        mock_primary_query_responses = [
            self.mock_instructors_response,
            self.mock_empty_response,
            self.mock_empty_response,
        ]
        mock_secondary_query_responses = [
            (mock_primary_section,),
            self.mock_instructors_response,
            self.mock_empty_response,
            self.mock_empty_response,
        ]
        mock_new_schedule_type_responses = [
            new_schedule_type,
            self.mock_instructors_response,
            self.mock_empty_response,
            self.mock_empty_response,
        ]
        mock_query_responses = (
            mock_primary_query_responses
            + mock_secondary_query_responses
            + mock_new_schedule_type_responses
        )
        mock_sections = [
            (
                mock_primary_section,
                mock_canceled_section,
                mock_unsynced_canceled_section,
                mock_secondary_section,
                mock_new_schedule_type_section,
                mock_bad_value_section,
            )
        ]
        side_effect = mock_sections + mock_query_responses
        mock_execute_query.side_effect = side_effect
        Section.sync_all()

    @patch(EXECUTE_QUERY)
    def test_sync(self, mock_execute_query):
        mock_execute_query.side_effect = [
            (self.get_mock_section_data(primary=False),),
            ((PRIMARY_SUBJECT_CODE, PRIMARY_SUBJECT_DESC_LONG, SCHOOL_CODE),),
            (self.get_mock_section_data(),),
            self.mock_instructors_response,
            self.mock_empty_response,
            self.mock_empty_response,
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

    def test_get_canvas_course_code(self):
        section = self.section
        canvas_course_code = section.get_canvas_course_code()
        self.assertEqual(canvas_course_code, self.canvas_course_code)
        sis_canvas_course_code = section.get_canvas_course_code(sis_format=True)
        self.assertEqual(sis_canvas_course_code, self.canvas_sis_code)
        schedule_type_canvas_course_code = section.get_canvas_course_code(
            include_schedule_type=True
        )
        self.assertEqual(
            schedule_type_canvas_course_code, self.canvas_schedule_type_code
        )

    def test_get_canvas_sis_id(self):
        section = self.section
        sis_id = section.get_canvas_sis_id()
        self.assertEqual(sis_id, self.canvas_sis_id)

    def test_get_canvas_name(self):
        section = self.section
        canvas_name = section.get_canvas_name(title_override="")
        self.assertEqual(canvas_name, self.canvas_name)


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
