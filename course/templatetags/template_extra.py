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
    value = remove_query_param(uri, key)

    return escape(value)


@register.simple_tag
def get_user(user):
    try:
        return User.objects.get(username=user)
    except User.DoesNotExist:
        return None


@register.filter
def course_code_to_string(course_code):
    print(course_code)
    middle = course_code[:-5][4:]

    return f"{course_code[:-11]}-{middle[:3]}-{middle[3:]} {course_code[-5:]}"


@register.filter
def course_to_course_code(course):
    term = f'{course["year"]}{course["course_term"]}'

    return (
        f'{course["course_subject"]}-'
        f'{course["course_number"]}-'
        f'{course["course_section"]} {term}'
    )


@register.simple_tag
def get_markdown(location):
    return (
        PageContent.objects.get(location=location).get_page_as_markdown()
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


@register.filter("crf_truncate_chars")
def truncate_chars(value, max_length):
    if not len(value) > max_length:
        return value
    else:
        truncated_value = value[:max_length]

        if not len(value) == max_length + 1 and value[max_length + 1] != " ":
            truncated_value = truncated_value[: truncated_value.rfind(" ")]

        return truncated_value
