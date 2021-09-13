from os import mkdir
from pathlib import Path


def separate_year_and_term(year_and_term):
    return year_and_term[:-1], year_and_term[-1]


def get_data_directory():
    DATA_DIRECTORY = Path.cwd() / "data"

    if not DATA_DIRECTORY.exists():
        mkdir(DATA_DIRECTORY)

    return DATA_DIRECTORY
