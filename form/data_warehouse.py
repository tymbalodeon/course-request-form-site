from logging import getLogger
from typing import Optional

from cx_Oracle import connect

from config.config import (
    DATA_WAREHOUSE_PASSWORD,
    DATA_WAREHOUSE_SERVICE,
    DATA_WAREHOUSE_USERNAME,
)

logger = getLogger(__name__)


def get_cursor():
    connection = connect(
        DATA_WAREHOUSE_USERNAME, DATA_WAREHOUSE_PASSWORD, DATA_WAREHOUSE_SERVICE
    )
    return connection.cursor()


def execute_query(query: str, kwargs: Optional[dict] = None):
    kwargs = kwargs or {}
    try:
        cursor = get_cursor()
        cursor.execute(query, **kwargs)
        return cursor
    except Exception as error:
        logger.error(f"FAILED to connect to Data Warehouse: '{error}'")
        return ()
