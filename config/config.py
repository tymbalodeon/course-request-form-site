from configparser import ConfigParser

config = ConfigParser()
config.read("config/config.ini")

DJANGO_SECTION = "django"
CANVAS_SECTION = "canvas"
DEBUG_VALUE = config.getboolean(DJANGO_SECTION, "debug", fallback=False)
SECRET_KEY_VALUE = config.get(DJANGO_SECTION, "secret_key", raw=True)


def get_config_section_values(section):
    return (config.get(section, option) for option in config.options(section))


USERNAME, PASSWORD, EMAIL = get_config_section_values("user")
PROD_URL = config.get(CANVAS_SECTION, "prod_url")
PROD_KEY = config.get(CANVAS_SECTION, "prod_key")
TEST_URL = config.get(CANVAS_SECTION, "test_url")
TEST_KEY = config.get(CANVAS_SECTION, "test_key")
USE_TEST_ENV = config.getboolean(CANVAS_SECTION, "use_test_env", fallback=True)
(
    DATA_WAREHOUSE_USERNAME,
    DATA_WAREHOUSE_PASSWORD,
    DATA_WAREHOUSE_SERVICE,
) = get_config_section_values("data_warehouse")
LIB_DIR = config.get("cx_oracle", "lib_dir")
