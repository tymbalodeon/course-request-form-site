from canvas.helpers import create_canvas_sites
from data_warehouse.data_warehouse import get_data_warehouse_courses

from celery import shared_task
from celery.utils.log import get_task_logger
from course.terms import CURRENT_YEAR_AND_TERM, NEXT_YEAR_AND_TERM

from .models import Request
from .utils import sync_crf_canvas_sites

LOGGER = get_task_logger(__name__)
TERMS = [CURRENT_YEAR_AND_TERM, NEXT_YEAR_AND_TERM]


@shared_task
def sync_all(terms=TERMS, celery=True):
    if isinstance(terms, str):
        terms = [terms]
    for term in terms:
        args = [term]
        if celery:
            args.append(LOGGER)
        get_data_warehouse_courses(*args)
        sync_crf_canvas_sites(*args)
    delete_canceled_requests()


@shared_task
def delete_canceled_requests():
    for request in Request.objects.filter(status="CANCELED"):
        request.delete()


@shared_task
def process_approved_sites():
    create_canvas_sites()


@shared_task
def sync_sites():
    sync_crf_canvas_sites(CURRENT_YEAR_AND_TERM)
