from django.core.management.base import BaseCommand

from course.models import Activity
from helpers.helpers import get_config_values
from open_data.open_data import OpenData

ACTIVITY_CHOICES = (
    ("LEC", "Lecture"),
    ("SEM", "Seminar"),
    ("LAB", "Laboratory"),
    ("CLN", "Clinic"),
    ("IND", "Independent Study"),
    ("ONL", "Online Course"),
    ("PRC", "SCUE Preceptorial"),
    ("PRO", "NSO Proseminar"),
    ("REC", "Recitation"),
    ("SEM", "Seminar"),
    ("SRT", "Senior Thesis"),
    ("STU", "Studio"),
    ("MST", "Masters Thesis"),
    ("UNK", "Unknown"),
)


class Command(BaseCommand):
    help = "Add activities."

    def add_arguments(self, parser):
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
        opendata = kwargs["opendata"]

        if opendata:
            open_data_id, key, domain = get_config_values("opendata")[:3]
            Open_Data = OpenData(base_url=domain, id=open_data_id, key=key)
            activities = Open_Data.get_available_activity().items()
        else:
            activities = ACTIVITY_CHOICES

            if not activities:
                return "NO ACTIVITIES FOUND"

            for abbreviation, name in activities:
                try:
                    Activity.objects.create(name=name, abbr=abbreviation)

                    print(f"- ADDED activity: {name} ({abbreviation})")
                except Exception:
                    print(f"- FAILED to add activity: {name} ({abbreviation})")

            print("FINISHED")
