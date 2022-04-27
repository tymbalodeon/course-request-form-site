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


def get_single_item_from_cursor(row) -> Optional[str]:
    return next(iter(row), None)


def get_user_field_query(field: str) -> str:
    return f"SELECT {field} FROM employee_general WHERE pennkey = :username"


def get_dw_user_check_message(pennkey: str, field: str) -> str:
    return f"Checking Data Warehouse for {pennkey}'s {field}..."


def get_dw_user_found_message(pennkey: str, field: str, value: str) -> str:
    return f"FOUND {field} '{value}' for {pennkey}..."


def get_dw_user_not_found_message(username: str, field: str) -> str:
    return f"{field.title()} NOT FOUND for {username}..."


def get_user_field_from_dw(pennkey: str, field: str, logger: Logger) -> Optional[str]:
    logger.info(get_dw_user_check_message(pennkey, field))
    cursor = get_cursor()
    query = get_user_field_query(field)
    cursor.execute(query, username=pennkey)
    value = None
    for row in cursor:
        value = get_single_item_from_cursor(row)
    if value:
        logger.info(get_dw_user_found_message(pennkey, field, value))
    else:
        logger.warning(get_dw_user_not_found_message(pennkey, field))
    return value
