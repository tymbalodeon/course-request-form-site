from configparser import ConfigParser
from logging import getLogger

from cx_Oracle import connect

logger = getLogger(__name__)


def get_cursor():
    config = ConfigParser()
    config.read("config/config.ini")
    values = dict(config.items("data_warehouse"))
    try:
        connection = connect(values["user"], values["password"], values["service"])
    except Exception as error:
        logger.error(f"FAILED to connect to Data Warehouse: '{error}'")
        return None
    return connection.cursor()
