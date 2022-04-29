from datetime import datetime

CURRENT_DATE = datetime.now()
CURRENT_YEAR = CURRENT_DATE.year
CURRENT_MONTH = CURRENT_DATE.month
YEAR_PLUS_ONE = CURRENT_YEAR + 1


def get_term_numbers():
    return "10", "20", "30"


SPRING, SUMMER, FALL = get_term_numbers()


def get_term_by_month(month):
    if month >= 9:
        return FALL
    elif month >= 5:
        return SUMMER
    else:
        return SPRING


def get_current_term():
    month_terms = {month: get_term_by_month(month) for month in range(1, 13)}
    return month_terms.get(CURRENT_MONTH, FALL)


CURRENT_TERM = get_current_term()


def get_next_term(term=None):
    if not term:
        term = get_current_term()
    return {SPRING: SUMMER, SUMMER: FALL, FALL: SPRING}.get(term)


NEXT_TERM = get_next_term()
CURRENT_YEAR_AND_TERM = f"{CURRENT_YEAR}{CURRENT_TERM}"


def is_fall():
    return CURRENT_TERM == FALL


def get_next_year():
    return YEAR_PLUS_ONE if is_fall() else CURRENT_YEAR


TWO_TERMS_AHEAD = get_next_term(NEXT_TERM)


def get_two_year_and_terms_ahead():
    year = YEAR_PLUS_ONE if is_fall() else CURRENT_YEAR
    return f"{year}{TWO_TERMS_AHEAD}"


NEXT_YEAR = get_next_year()
NEXT_YEAR_AND_TERM = f"{NEXT_YEAR}{NEXT_TERM}"
TWO_YEAR_AND_TERMS_AHEAD = get_two_year_and_terms_ahead()


def split_year_and_term(year_and_term):
    dividing_index = -2
    return year_and_term[:dividing_index], year_and_term[dividing_index]
