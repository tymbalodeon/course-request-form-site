from datetime import datetime

from course.models import Request, School

from .helpers import separate_year_and_term

CURRENT_MONTH = datetime.now().month
SCHOOLS = list(School.objects.all())


def write_requests_summary(year_and_term, start_month=5):
    year, term = separate_year_and_term(year_and_term)
    requests = Request.objects.filter(
        course_requested__year=year,
        course_requested__course_term=term,
        created__month__gte=start_month,
    )
    TOTAL = requests.count()
    months = list(range(start_month, CURRENT_MONTH + 1))
    requests_by_month = [
        (month, requests.filter(created__month=month)) for month in months
    ]
    TOTALS = {"total_crf": TOTAL}

    for month, requests in requests_by_month:
        TOTALS[month] = {"total": len(requests)}

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

    print(TOTALS)
