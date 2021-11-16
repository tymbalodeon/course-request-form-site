from logging import getLogger
from os import mkdir
from pathlib import Path

from django.db.models import Q

from canvas.api import get_canvas, get_user_courses

from .models import CanvasSite, Request, User

DATA_DIRECTORY_NAME = "data"
logger = getLogger(__name__)


def split_year_and_term(year_and_term):
    return year_and_term[:-1], year_and_term[-1]


def get_data_directory(data_directory_name):
    data_directory_parent = Path.cwd() / data_directory_name
    if not data_directory_parent.exists():
        mkdir(data_directory_parent)
    return data_directory_parent


def sync_crf_canvas_sites(year_and_term, logger=logger):
    logger.info("Updating site info for {term} courses...")
    year, term = split_year_and_term(year_and_term)
    canvas_sites = Request.objects.filter(~Q(canvas_instance__isnull=True)).filter(
        status="COMPLETED",
        course_requested__year=year,
        course_requested__course_term=term,
    )
    canvas = get_canvas()
    for canvas_site in canvas_sites:
        crf_canvas_site = canvas_site.canvas_instance
        try:
            site = canvas.get_course(crf_canvas_site.canvas_id)
            if site.name != crf_canvas_site.name:
                crf_canvas_site.name = site.name
                crf_canvas_site.save()
            if site.workflow_state != crf_canvas_site.workflow_state:
                crf_canvas_site.workflow_state = site.workflow_state
                crf_canvas_site.save()
        except Exception:
            logger.error(
                "ERROR: Failed to find Canvas site: {crf_canvas_site.sis_course_id}"
            )
            crf_canvas_site.workflow_state = "deleted"
            crf_canvas_site.save()
    logger.info("FINISHED")


def update_user_courses(penn_key, logger=logger):
    canvas_courses = get_user_courses(penn_key)
    for canvas_course in canvas_courses:
        try:
            course, created = CanvasSite.objects.update_or_create(
                canvas_id=str(canvas_course.id),
                defaults={
                    "workflow_state": canvas_course.workflow_state,
                    "sis_course_id": canvas_course.sis_course_id,
                    "name": canvas_course.name,
                },
            )
            course.owners.add(User.objects.get(username=penn_key))
            logger.info(f"{'CREATED' if created else 'UPDATED'} {course}.")
        except Exception as error:
            logger.error(f"FAILED to add course {canvas_course} ({error}).")


def update_all_users_courses(logger=logger):
    for user in User.objects.all():
        logger.info(f") Adding courses for {user.username}...")
        update_user_courses(user.username, logger=logger)
