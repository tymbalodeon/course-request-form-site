from dataclasses import dataclass, field
from typing import Optional

from canvasapi.exceptions import CanvasException
from canvasapi.user import User as CanvasUser
from form.terms import CURRENT_TERM

SUB_ACCOUNTS = ["SubAccount"]
LOGIN_ID = "testuser"
CANVAS_ID = 7654321


@dataclass
class MockUser:
    id: int
    unique_id: str
    sis_user_id: str
    name: str
    email: str


@dataclass
class MockSection:
    id: int
    name: str
    sis_course_id: str
    sis_section_id: str
    enable_sis_reactivation: bool


@dataclass
class MockEnrollment:
    canvas_id: int
    enrollment_type: str
    enrollment_state: str
    course_section_id: int


@dataclass
class MockProgress:
    workflow_state: str


@dataclass
class MockMigration:
    migration_type: str
    source_course_id: int
    workflow_state: str

    def get_progress(self) -> MockProgress:
        return MockProgress(self.workflow_state)


@dataclass
class MockTab:
    requester: str
    reserves_tab: dict
    hidden: Optional[bool] = True

    def update(self, hidden: bool):
        self.hidden = hidden


@dataclass
class MockAnnouncement:
    title: str
    deleted: bool = False

    def delete(self):
        self.deleted = True


def create_announcements() -> list[MockAnnouncement]:
    announcement = MockAnnouncement("Announcement")
    return [announcement]


@dataclass
class MockCourse:
    id: int
    name: str
    sis_course_id: str
    term_id: int
    storage_quota_mb: int
    migration: Optional[MockMigration] = None
    _requester: str = ""
    sections: list[MockSection] = field(default_factory=list)
    enrollments: list[MockEnrollment] = field(default_factory=list)
    announcements: list[MockAnnouncement] = field(default_factory=create_announcements)
    workflow_state: str = "complete"

    def get_sections(self) -> list[MockSection]:
        return self.sections

    def enroll_user(
        self, canvas_id: int, enrollment_type: str, enrollment: dict
    ) -> MockEnrollment:
        enrollment_state = enrollment["enrollment_state"]
        course_section_id = enrollment["course_section_id"]
        mock_enrollment = MockEnrollment(
            canvas_id, enrollment_type, enrollment_state, course_section_id
        )
        self.enrollments.append(mock_enrollment)
        return mock_enrollment

    def create_course_section(
        self, course_section: dict, enable_sis_reactivation: bool
    ):
        name = course_section["name"]
        sis_section_id = course_section["sis_section_id"]
        section_id = len(self.sections) + 1
        mock_section = MockSection(
            section_id,
            name,
            self.sis_course_id,
            sis_section_id,
            enable_sis_reactivation,
        )
        self.sections.append(mock_section)

    def create_content_migration(
        self, migration_type: str, settings: dict
    ) -> MockMigration:
        source_course_id = settings["source_course_id"]
        mock_migration = MockMigration(
            migration_type, source_course_id, self.workflow_state
        )
        self.migration = mock_migration
        return self.migration

    def get_discussion_topics(self, only_announcements: bool) -> list[MockAnnouncement]:
        return self.announcements

    def update(self, course: dict):
        name = course["name"]
        sis_course_id = course["sis_course_id"]
        term_id = course["term_id"]
        storage_quota_mb = course["storage_quota_mb"]
        self.name = name
        self.sis_course_id = sis_course_id
        self.term_id = term_id
        self.storage_quota_mb = storage_quota_mb


@dataclass
class MockEnrollmentTerm:
    id: int
    name: str = str(CURRENT_TERM)


def create_enrollment_terms() -> list[MockEnrollmentTerm]:
    mock_enrollment_term = MockEnrollmentTerm(1)
    return [mock_enrollment_term]


@dataclass
class MockAccount:
    id: int
    name: str = "Mock Account"
    users: list[MockUser] = field(default_factory=list)
    courses: list[MockCourse] = field(default_factory=list)
    enrollment_terms: list[MockEnrollmentTerm] = field(
        default_factory=create_enrollment_terms
    )

    @staticmethod
    def get_subaccounts(recursive: bool):
        if recursive:
            return SUB_ACCOUNTS

    def create_user(
        self, pseudonym: dict, user: dict, communication_channel: dict
    ) -> MockUser:
        unique_id = pseudonym["unique_id"]
        sis_user_id = pseudonym["sis_user_id"]
        name = user["name"]
        email = communication_channel["address"]
        user_id = len(self.users) + CANVAS_ID
        mock_user = MockUser(user_id, unique_id, sis_user_id, name, email)
        self.users.append(mock_user)
        return mock_user

    def create_course(self, course: dict) -> MockCourse:
        name = course["name"]
        sis_course_id = course["sis_course_id"]
        term_id = course["term_id"]
        storage_quota_mb = course["storage_quota_mb"]
        course_id = len(self.courses) + 1
        mock_course = MockCourse(
            course_id, name, sis_course_id, term_id, storage_quota_mb
        )
        self.courses.append(mock_course)
        return mock_course

    def get_enrollment_terms(self) -> list[MockEnrollmentTerm]:
        return self.enrollment_terms


@dataclass
class MockDeleted:
    title: str


@dataclass
class MockCalendarEvent:
    id: int
    location_name: str
    description: str
    title: str
    deleted: bool = False
    cancel_reason: Optional[str] = None

    def delete(self, cancel_reason: str) -> MockDeleted:
        self.cancel_reason = cancel_reason
        self.deleted = True
        return MockDeleted(self.title)


def create_calendar_events():
    zoom_location_event = MockCalendarEvent(1, "Zoom", "", "")
    zoom_description_event = MockCalendarEvent(2, "", "Zoom", "")
    zoom_title_event = MockCalendarEvent(3, "", "", "Zoom")
    non_zoom_event = MockCalendarEvent(4, "In Person", "In Person", "In Person")
    return [
        zoom_location_event,
        zoom_description_event,
        zoom_title_event,
        non_zoom_event,
    ]


def create_courses() -> list[MockCourse]:
    mock_course = MockCourse(
        1, "Mock Course", f"BAN_SUBJ-1000-200 {CURRENT_TERM}", 1, 2000
    )
    return [mock_course]


@dataclass
class MockCanvas:
    calendar_events: list[MockCalendarEvent] = field(
        default_factory=create_calendar_events
    )
    courses: list[MockCourse] = field(default_factory=create_courses)

    def get_calendar_event(self, event_id: int) -> MockCalendarEvent:
        return next(event for event in self.calendar_events if event.id == event_id)

    def get_calendar_events(
        self, context_codes: list, all_events: bool
    ) -> list[MockCalendarEvent]:
        return self.calendar_events

    @staticmethod
    def get_user(login_id, login_type):
        if login_id == LOGIN_ID and login_type == "sis_login_id":
            return CanvasUser(None, {"login_id": login_id})
        else:
            raise CanvasException("")

    @staticmethod
    def get_account(account_id):
        return MockAccount(account_id)

    def get_course(self, sis_course_id: str, use_sis_id: bool):
        return next(
            course for course in self.courses if course.sis_course_id == sis_course_id
        )
