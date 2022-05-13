from django.core.management.base import BaseCommand

from form.models import ScheduleType, School, Section, Subject


class Command(BaseCommand):
    help = "Sync data from Pennant Student Records and Canvas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schedule-types", action="store_true", help="Sync Schedule Types"
        )
        parser.add_argument("--schools", action="store_true", help="Sync Schools")
        parser.add_argument("--subjects", action="store_true", help="Sync Subjects")
        parser.add_argument("--sections", action="store_true", help="Sync Sections")

    def handle(self, *args, **options):
        sync_schedule_types = options["schedule_types"]
        sync_schools = options["schools"]
        sync_subjects = options["subjects"]
        sync_sections = options["sections"]
        sync_all = not any(
            (sync_schedule_types, sync_schools, sync_subjects, sync_sections)
        )
        if sync_all or sync_schedule_types:
            ScheduleType.sync_all()
        if sync_all or sync_schools:
            School.sync_all()
        if sync_all or sync_subjects:
            Subject.sync_all()
        if sync_all or sync_sections:
            Section.sync_all()
