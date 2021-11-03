from configparser import ConfigParser
from os import mkdir
from pathlib import Path

config = ConfigParser()
config.read("config/config.ini")

MAIN_ACCOUNT_ID = 96678
DATA_DIRECTORY_NAME = "data"
USER_SECTION = "user"


def get_config_boolean(section, option):
    return config.getboolean(section, option, fallback=False)


def get_config_option(section, option, raw=False):
    return config.get(section, option, raw=raw)


def get_config_options(section):
    return [get_config_option(section, option) for option in config.options(section)]


def get_config_username():
    return get_config_option(USER_SECTION, "username")


def get_config_username_and_password():
    username = get_config_username()
    password = get_config_option(USER_SECTION, "password")

    return username, password


def get_config_email():
    return get_config_option(USER_SECTION, "email")


def separate_year_and_term(year_and_term):
    return year_and_term[:-1], year_and_term[-1]


def get_data_directory(data_directory_name):
    data_directory_parent = Path.cwd() / data_directory_name

    if not data_directory_parent.exists():
        mkdir(data_directory_parent)

    return data_directory_parent
