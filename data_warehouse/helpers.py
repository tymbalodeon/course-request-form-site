from configparser import ConfigParser

from cx_Oracle import connect


def get_cursor():
    config = ConfigParser()
    config.read("config/config.ini")
    values = dict(config.items("data_warehouse"))
    connection = connect(values["user"], values["password"], values["service"])
    return connection.cursor()
