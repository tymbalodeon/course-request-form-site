from course.models import ScheduleType, School, Subject
from data_warehouse.data_warehouse import (
    get_data_warehouse_courses,
    get_data_warehouse_instructors,
)
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync"

    def add_arguments(self, parser):
        parser.add_argument("--schools", type=bool, help="Add schools")
        parser.add_argument("--subjects", type=bool, help="Add subjects")
        parser.add_argument("--schedule-type", type=bool, help="Add schedule types")
        parser.add_argument("--courses", type=bool, help="Add courses")
        parser.add_argument("--term", type=str, help="The term to sync")

    def handle(self, **options):
        if options["schools"]:
            School.sync()
        if options["subjects"]:
            Subject.sync()
        if options["schedule-type"]:
            ScheduleType.sync()
        if options["courses"]:
            year_and_term = options["term"]
            get_data_warehouse_courses(year_and_term)
            get_data_warehouse_instructors(year_and_term)
