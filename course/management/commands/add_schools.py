from django.core.management.base import BaseCommand

from course.models import School

from .school_data import school_data


class Command(BaseCommand):
    help = "Add schools."

    def handle(self):
        print(") Adding schools...")

        for index, school in enumerate(school_data):
            index_display = f"- ({index + 1}/{len(school_data)})"

            try:
                if school.get("canvas_subaccount"):
                    school_object, created = School.objects.update_or_create(
                        name=school["name"],
                        abbreviation=school["abbreviation"],
                        defaults={
                            "visible": school["visibility"],
                            "opendata_abbr": school["opendata_abbr"],
                            "canvas_subaccount": school["canvas_subaccount"],
                        },
                    )
                else:
                    school_object, created = School.objects.update_or_create(
                        name=school["name"],
                        abbreviation=school["abbreviation"],
                        defaults={
                            "visible": school["visibility"],
                            "opendata_abbr": school["opendata_abbr"],
                        },
                    )

                if created:
                    print(f"{index_display} ADDED {school_object}")
                else:
                    print(f"{index_display} UPDATED {school_object}")
            except Exception as error:
                print(f"{index_display} ERROR: FAILED for {school} ({error})")

        print("FINISHED")
