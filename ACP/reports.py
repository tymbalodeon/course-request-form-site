from course.models import Course


def count_canvas_sites(
    year_and_term, separate=True, graduate_course_minimum_number=500
):
    def is_grad_course(course):
        return int(course.course_number) >= graduate_course_minimum_number

    def is_numeric_course_number(course):
        try:
            return bool(int(course.course_number))
        except Exception:
            return False

    year = "".join(character for character in year_and_term if not character.isalpha())
    term = "".join(character for character in year_and_term if character.isalpha())
    courses = list(Course.objects.filter(year=year, course_term=term))
    course_numbers = set()

    for course in courses:
        if course.course_number in course_numbers:
            courses.remove(course)
        else:
            course_numbers.add(course.course_number)

    courses = [course for course in courses if is_numeric_course_number(course)]

    if separate:
        undergraduate_course = [
            course for course in courses if not is_grad_course(course)
        ]
        gradudate_courses = [course for course in courses if is_grad_course(course)]

        return len(undergraduate_course), len(gradudate_courses)
    else:
        return len(courses)
