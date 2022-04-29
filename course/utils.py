from logging import getLogger
from os import mkdir
from pathlib import Path

DATA_DIRECTORY_NAME = "data"
logger = getLogger(__name__)


def get_data_directory(data_directory_name):
    data_directory_parent = Path.cwd() / data_directory_name
    if not data_directory_parent.exists():
        mkdir(data_directory_parent)
    return data_directory_parent
