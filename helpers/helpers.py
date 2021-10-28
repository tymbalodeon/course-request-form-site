from configparser import ConfigParser
from os import mkdir
from pathlib import Path

config = ConfigParser()
config.read("config/config.ini")

MAIN_ACCOUNT_ID = 96678


def get_config_boolean_value(key, value):
    return config.getboolean(key, value)


def get_config_value(key, value, raw=False):
    return config.get(key, value, raw=raw)


def get_config_values(key):
    return [value[1] for value in config.items(key)]


def get_config_username_and_password():
    username = next((name for name in config["users"]))
    password = config.get("users", username)

    return username, password


def get_config_username():
    return get_config_username_and_password()[0]


def separate_year_and_term(year_and_term):
    return year_and_term[:-1], year_and_term[-1]


def get_data_directory():
    DATA_DIRECTORY = Path.cwd() / "data"

    if not DATA_DIRECTORY.exists():
        mkdir(DATA_DIRECTORY)

    return DATA_DIRECTORY
