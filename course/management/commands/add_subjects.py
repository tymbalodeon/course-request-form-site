import logging

from django.core.management.base import BaseCommand

from config.config import get_config_options
from course.models import School, Subject
from open_data.open_data import OpenData


class Command(BaseCommand):
    help = "Add subjects."

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--open-data",
            action="store_true",
            help="Pull from the OpenData API.",
        )

    def handle(self, **kwargs):
        print(") Adding subjects...")

        missing_schools = list()
        fails = 0
        open_data_id, key, domain = get_config_options("open_data")
        Open_Data = OpenData(base_url=domain, id=open_data_id, key=key)
        subjects = Open_Data.get_available_subj()

        if type(subjects) != dict:
            print(f"- ERROR: {subjects}")
        else:
            total_subjects = len(subjects)

            try:
                for index, subject in enumerate(subjects.items()):
                    abbreviation, name = subject
                    index_display = f"- ({index + 1}/{total_subjects})"

                    if not Subject.objects.filter(abbreviation=abbreviation).exists():
                        try:
                            school_code = Open_Data.find_school_by_subj(abbreviation)
                            school_name = School.objects.get(
                                open_data_abbreviation=school_code
                            )
                            Subject.objects.update_or_create(
                                abbreviation=abbreviation,
                                defaults={
                                    "name": name,
                                    "visible": True,
                                    "schools": school_name,
                                },
                            )
                            print(f"{index_display} ADDED {name} ({abbreviation}).")
                        except Exception as error:
                            school_code = Open_Data.find_school_by_subj(abbreviation)
                            missing_schools.append(school_code)
                            index_display = (
                                f"{index_display} ERROR: FAILED to add {abbreviation}"
                                f" ({error})"
                            )
                            logging.getLogger("error_logger").error(index_display)
                            print(index_display)
                            fails += 1
                    else:
                        print(
                            f"{index_display} ALREADY EXISTS: {name} ({abbreviation})."
                        )

                if fails > 0 or len(missing_schools) > 0:
                    print("SUMMARY")

                    if fails > 0:
                        print(
                            f"- Failed to find {fails} out of {total_subjects}"
                            " total subjects."
                        )

                    if len(missing_schools) > 0:
                        missing_schools = list(set(missing_schools))
                        print("- Missing schools:")
                        for school in missing_schools:
                            print(f"\t{school}")

            except Exception as error:
                print(f"- ERROR: {error}")

        print("FINISHED")
