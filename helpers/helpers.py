from os import mkdir
from pathlib import Path

DATA_DIRECTORY_NAME = "data"


def separate_year_and_term(year_and_term):
    return year_and_term[:-1], year_and_term[-1]


def get_data_directory(data_directory_name):
    data_directory_parent = Path.cwd() / data_directory_name

    if not data_directory_parent.exists():
        mkdir(data_directory_parent)

    return data_directory_parent
