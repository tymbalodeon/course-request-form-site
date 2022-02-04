from celery import task
from celery.utils.log import get_task_logger

from canvas.api import create_canvas_sites
from course.management.commands.add_courses import get_open_data_courses
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


def get_args(celery, term=None):
    args = [term] if term else []
    if celery:
        args.append(LOGGER)
    return args


@task
def sync_all(terms=TERMS, celery=True):
    if isinstance(terms, str):
        terms = [terms]
    for term in terms:
        args = get_args(celery, term)
        get_open_data_courses(*args)
        get_data_warehouse_courses(*args)
        get_data_warehouse_instructors(*args)
        sync_crf_canvas_sites(*args)
        delete_data_warehouse_canceled_courses(*args)
    args = get_args(celery)
    update_all_users_courses(*args)
    delete_canceled_requests()


@task
def delete_canceled_requests():
    for request in Request.objects.filter(status="CANCELED"):
        request.delete()


@task
def process_approved_sites():
    create_canvas_sites()


@task
def sync_sites(term):
    sync_crf_canvas_sites(term)
