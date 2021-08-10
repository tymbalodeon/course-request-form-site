from course.models import Course

GRADUATE_COURSE_MINIMUM_NUMBER = 500


def count_canvas_sites(year_and_term, separate=True):
    def is_grad_course(course):
        return int(course.course_number) >= GRADUATE_COURSE_MINIMUM_NUMBER

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

    if separate:
        courses = [course for course in courses if is_numeric_course_number(course)]
        undergraduate_course = [
            course for course in courses if not is_grad_course(course)
        ]
        gradudate_courses = [course for course in courses if is_grad_course(course)]

        return undergraduate_course, gradudate_courses
    else:
        return courses
