from csv import writer
from datetime import datetime
from pprint import PrettyPrinter

from course.models import Request, School
from django.db.models import Q

from .helpers import get_data_directory, separate_year_and_term

CURRENT_MONTH = datetime.now().month
SCHOOLS = list(School.objects.all())


def get_requests(year_and_term, start_month=5):
    year, term = separate_year_and_term(year_and_term)
    individual_requests = Request.objects.filter(
        Q(
            course_requested__year=year,
            course_requested__course_term=term,
            created__month__gte=start_month,
        )
        & ~Q(additional_instructions__contains="Request automatically generated")
    )
    bulk_created_requests = Request.objects.filter(
        Q(
            course_requested__year=year,
            course_requested__course_term=term,
            created__month__gte=start_month,
        )
        & Q(additional_instructions__contains="Request automatically generated")
    )
    return individual_requests, bulk_created_requests


def make_requests_object(requests, months, verbose=False):
    individual_requests, bulk_created_requests = requests
    total_requests = individual_requests.count()
    total_bulk_created_requests = bulk_created_requests.count()
    TOTALS = {
        "TOTAL CRF": total_requests + total_bulk_created_requests,
        "TOTAL NOT PROVISIONED": total_requests,
        "TOTAL PROVISIONED": total_bulk_created_requests,
    }
    requests_by_month = [
        (month, individual_requests.filter(created__month=month)) for month in months
    ]

    for month, requests in requests_by_month:
        TOTALS[month] = {"TOTAL": len(requests)}

    requests_by_month = [
        (
            month,
            [
                (
                    school.abbreviation,
                    request_list.filter(course_requested__course_schools=school),
                )
                for school in SCHOOLS
            ],
        )
        for month, request_list in requests_by_month
    ]

    for month, requests in requests_by_month:
        for school, schools in requests:
            TOTALS[month][school] = len(schools)

    for month in months:
        month_name = datetime.strptime(str(month), "%m").strftime("%b")
        TOTALS[month_name] = TOTALS.pop(month)

    for request_list in [individual_requests, bulk_created_requests]:
        requests_by_school = [
            (
                school.abbreviation,
                request_list.filter(course_requested__course_schools=school).count(),
            )
            for school in SCHOOLS
        ]

        for school, count in requests_by_school:
            TOTALS[
                f"{school}{' PROVISIONED' if request_list is bulk_created_requests else ''}"
            ] = count

    if verbose:
        PrettyPrinter().pprint(TOTALS)

    return TOTALS


def write_requests(requests, individual_path, bulk_created_path):
    individual_requests, bulk_created_requests = requests
    DATA_DIRECTORY = get_data_directory()
    fields = Request._meta.fields
    fields = [field.name for field in fields]

    for requests, output_file in [
        (individual_requests, individual_path),
        (bulk_created_requests, bulk_created_path),
    ]:
        with open(output_file, "w", newline="") as output_writer:
            output = writer(output_writer)
            output.writerow(fields)
            rows = [
                [getattr(request, field) for field in fields] for request in requests
            ]
            output.writerows(rows)


def write_requests_summary(year_and_term, start_month=5, verbose=False):
    DATA_DIRECTORY = get_data_directory()
    file_path = DATA_DIRECTORY / f"{year_and_term}_requests_summary.csv"
    individual_path = DATA_DIRECTORY / f"{year_and_term}_individual_requests.csv"
    bulk_created_path = DATA_DIRECTORY / f"{year_and_term}_bulk_created_requests.csv"
    MONTHS = list(range(start_month, CURRENT_MONTH + 1))
    individual_requests, bulk_create_requests = get_requests(year_and_term, start_month)

    write_requests(
        (individual_requests, bulk_create_requests), individual_path, bulk_created_path
    )

    TOTALS = make_requests_object(
        (individual_requests, bulk_create_requests), MONTHS, verbose
    )

    with open(file_path, "w", newline="") as output_writer:
        output = writer(output_writer)
        output.writerow(["Month", "School", "Requests"])
        rows = list()

        for key, value in TOTALS.items():
            if isinstance(value, dict):
                for school_key, school_value in value.items():
                    rows.append([key, school_key, school_value])
            elif "TOTAL" in key:
                rows.append(["TOTAL", key, value])
            else:
                rows.append(["TOTAL", key, value])

        output.writerows(rows)
