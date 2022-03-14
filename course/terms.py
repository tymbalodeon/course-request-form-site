from datetime import datetime

CURRENT_DATE = datetime.now()
CURRENT_YEAR = CURRENT_DATE.year
CURRENT_MONTH = CURRENT_DATE.month
NEXT_YEAR = CURRENT_YEAR + 1
USE_BANNER = CURRENT_DATE >= datetime(2022, 4, 14)


def get_term_letters():
    return "A", "B", "C"


def get_term_numbers():
    return "10", "20", "30"


SPRING, SUMMER, FALL = get_term_numbers() if USE_BANNER else get_term_letters()


def get_term_by_month(month):
    if month >= 9:
        return FALL
    elif month >= 5:
        return SUMMER
    else:
        return SPRING


def get_current_term():
    return {month: get_term_by_month(month) for month in range(1, 13)}.get(
        CURRENT_MONTH, FALL
    )


CURRENT_TERM = get_current_term()


def get_next_term():
    return {SPRING: SUMMER, SUMMER: FALL, FALL: SPRING}.get(get_current_term())


NEXT_TERM = get_next_term()
CURRENT_YEAR_AND_TERM = f"{CURRENT_YEAR}{CURRENT_TERM}"
NEXT_YEAR_AND_TERM = f"{NEXT_YEAR if CURRENT_TERM == FALL else CURRENT_YEAR}{NEXT_TERM}"
