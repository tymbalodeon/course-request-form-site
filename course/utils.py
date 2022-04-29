from logging import getLogger
from os import mkdir
from pathlib import Path

from django.db.models import Q

from canvas.api import get_canvas

from .models import Request

DATA_DIRECTORY_NAME = "data"
logger = getLogger(__name__)


def split_year_and_term(year_and_term):
    return (
        (year_and_term[:-2], year_and_term[-2:])
        if year_and_term.isnumeric()
        else (year_and_term[:-1], year_and_term[-1])
    )


def get_data_directory(data_directory_name):
    data_directory_parent = Path.cwd() / data_directory_name
    if not data_directory_parent.exists():
        mkdir(data_directory_parent)
    return data_directory_parent


def sync_crf_canvas_sites(year_and_term, logger=logger):
    year, term = split_year_and_term(year_and_term)
    logger.info(f"Updating site info for {term} courses...")
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
                logger.info(
                    f"Changing name for {crf_canvas_site.sis_course_id} from"
                    f" {crf_canvas_site.name} to {site.name}"
                )
                crf_canvas_site.name = site.name
                crf_canvas_site.save()
            if site.workflow_state != crf_canvas_site.workflow_state:
                logger.info(
                    f"Changing workflow_state for {crf_canvas_site.sis_course_id} from"
                    f" {crf_canvas_site.workflow_state} to {site.workflow_state}"
                )
                crf_canvas_site.workflow_state = site.workflow_state
                crf_canvas_site.save()
            logger.info(f"SYNCED Canvas site for {crf_canvas_site.sis_course_id}")
        except Exception as error:
            logger.error(
                "ERROR: Failed to find Canvas site:"
                f" {crf_canvas_site.sis_course_id} ({error})"
            )
            crf_canvas_site.workflow_state = "deleted"
            crf_canvas_site.save()
    logger.info("FINISHED")
