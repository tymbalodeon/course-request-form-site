from configparser import ConfigParser
from logging import Logger
from typing import Optional

from cx_Oracle import connect


def get_cursor():
    config = ConfigParser()
    config.read("config/config.ini")
    values = dict(config.items("data_warehouse"))
    connection = connect(values["user"], values["password"], values["service"])
    return connection.cursor()


def get_query_cursor(query: str, kwargs: Optional[dict] = None):
    cursor = get_cursor()
    cursor.execute(query, **kwargs)
    return cursor


def log_field_found(logger: Logger, field: str, value: str, pennkey: str):
    logger.info(f"FOUND {field} '{value}' for {pennkey}")


def log_field_not_found(logger: Logger, field: str, pennkey: str):
    logger.warning(f"{field} NOT FOUND for {pennkey}")


def log_field(logger: Logger, field: str, value: str, pennkey: str):
    if value:
        log_field_found(logger, field, value, pennkey)
    else:
        log_field_not_found(logger, field, pennkey)
