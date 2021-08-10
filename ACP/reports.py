from course.models import Course

GRADUATE_COURSE_MINIMUM_NUMBER = 500


def count_canvas_courses(year_and_term, separate=True):
    def is_grad_course(course):
        return course.course_number >= GRADUATE_COURSE_MINIMUM_NUMBER

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
        undergraduate_course = [
            course for coruse in courses if not is_grad_course(courses)
        ]
        gradudate_courses = [course for coruse in courses if is_grad_course(courses)]

        return undergraduate_course, gradudate_courses
    else:
        return courses
