from configparser import ConfigParser

config = ConfigParser()
config.read("config/config.ini")

DJANGO_SECTION = "django"
DEBUG_VALUE = config.getboolean(DJANGO_SECTION, "debug", fallback=False)
SECRET_KEY_VALUE = config.get(DJANGO_SECTION, "secret_key", raw=True)


def get_config_section_values(section):
    return (config.get(section, option) for option in config.options(section))


USERNAME, PASSWORD, EMAIL = get_config_section_values("user")


OPEN_DATA_ID, OPEN_DATA_KEY, OPEN_DATA_DOMAIN = get_config_section_values("open_data")
PROD_URL, PROD_KEY, TEST_URL, TEST_KEY = get_config_section_values("canvas")
(
    DATA_WAREHOUSE_USERNAME,
    DATA_WAREHOUSE_PASSWORD,
    DATA_WAREHOUSE_SERVICE,
) = get_config_section_values("data_warehouse")
LIB_DIR = config.get("cx_oracle", "lib_dir")
