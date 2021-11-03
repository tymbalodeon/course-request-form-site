from configparser import ConfigParser

config = ConfigParser()
config.read("config/config.ini")

DJANGO_SECTION = "django"
USER_SECTION = "user"

DEBUG_VALUE = config.getboolean(DJANGO_SECTION, "debug", fallback=False)
SECRET_KEY_VALUE = config.get(DJANGO_SECTION, "secret_key", raw=True)


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
