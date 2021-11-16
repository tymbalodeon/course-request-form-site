from celery import task
from celery.utils.log import get_task_logger

from course.terms import CURRENT_YEAR_AND_TERM, NEXT_YEAR_AND_TERM
from data_warehouse.data_warehouse import (
    delete_data_warehouse_canceled_courses,
    get_data_warehouse_courses,
    get_data_warehouse_instructors,
)

from .models import Request
from .utils import sync_crf_canvas_sites, update_all_users_courses

LOGGER = get_task_logger(__name__)
TERMS = [CURRENT_YEAR_AND_TERM, NEXT_YEAR_AND_TERM]


@task()
def sync_all(terms=TERMS):
    LOGGER.info("STARTING SYNC")
    if isinstance(terms, str):
        terms = [terms]
    for term in terms:
        get_data_warehouse_courses(term, logger=LOGGER)
        get_data_warehouse_instructors(term, logger=LOGGER)
        sync_crf_canvas_sites(term, logger=LOGGER)
        delete_data_warehouse_canceled_courses(term, logger=LOGGER)
    update_all_users_courses(logger=LOGGER)
    delete_canceled_requests()
    LOGGER.info("COMPLETED SYNC")


@task()
def delete_canceled_requests():
    for request in Request.objects.filter(status="CANCELED"):
        request.delete()
