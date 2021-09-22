from configparser import ConfigParser

config = ConfigParser()
config.read("config/config.ini")


def get_config_value(key, value):
    return config.get(key, value)


def get_config_items(key):
    return config.items(key)


def get_username_and_password():
    username = [name for name in config["users"]][0]
    password = config.get("users", username)

    return username, password
