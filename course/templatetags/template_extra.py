from django import template
from django.contrib.auth.models import User
from django.utils.encoding import iri_to_uri
from django.utils.html import escape
from rest_framework.utils.urls import remove_query_param

from course.models import PageContent

register = template.Library()


@register.simple_tag
def delete_query_param(request, key):
    iri = request.get_full_path()
    uri = iri_to_uri(iri)
    value = remove_query_param(uri, key) if uri else None
    return escape(value)


@register.simple_tag
def get_user(user):
    try:
        return User.objects.get(username=user)
    except User.DoesNotExist:
        return None


@register.filter
def course_code_to_string(course_code):
    includes_year = len(course_code) >= 13
    if includes_year:
        srs_course = course_code[-1].isalpha()
    else:
        srs_course = (
            len(
                "".join(character for character in course_code if character.isnumeric())
            )
            == 6
        )
    if srs_course:
        year = course_code[-5:] if includes_year else ""
        section = course_code[:-5][-3:] if includes_year else course_code[-3:]
        course = course_code[:-8][-3:] if includes_year else course_code[:-3][-3:]
    else:
        year = course_code[-6:] if includes_year else ""
        section = course_code[:-5][-3:] if includes_year else course_code[-3:]
        course = course_code[:-9][-4:] if includes_year else course_code[:-3][-3:]
    if course_code[2].isnumeric():
        subject = course_code[:2]
    elif course_code[3].isnumeric():
        subject = course_code[:3]
    else:
        subject = course_code[:4]
    return f"{subject}-{course}-{section}{' ' if year else ''}{year}"


@register.filter
def course_to_course_code(course):
    return (
        f"{course['course_subject']}-"
        f"{course['course_number']}-"
        f"{course['course_section']}"
        f" {course['year']}{course['course_term']}"
    )


@register.simple_tag
def get_markdown(location):
    return (
        PageContent.objects.get(location=location).get_html()
        if PageContent.objects.filter(location=location).exists()
        else ""
    )


@register.simple_tag
def get_markdown_id(location):
    return (
        PageContent.objects.get(location=location).pk
        if PageContent.objects.filter(location=location).exists()
        else ""
    )


@register.filter()
def truncate_course_name(value, max_length):
    def get_longest_whole_words(words, max_length):
        phrase = " ".join(words)
        return (
            get_longest_whole_words(words[:-1], max_length)
            if len(phrase) > max_length
            else phrase
        )

    if not len(value) > max_length:
        return value
    else:
        words = value.split()
        return get_longest_whole_words(words, max_length)
