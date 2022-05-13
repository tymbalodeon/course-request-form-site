from datetime import datetime
from typing import Optional

CURRENT_DATE = datetime.now()
CURRENT_YEAR = CURRENT_DATE.year
NEXT_YEAR = CURRENT_YEAR + 1
CURRENT_MONTH = CURRENT_DATE.month
SPRING, SUMMER, FALL = 10, 20, 30
TERM_CODE_LENGTH = 2


def get_term_code_by_month(month: int) -> int:
    if month >= 9:
        return FALL
    elif month >= 5:
        return SUMMER
    else:
        return SPRING


def get_current_term_code() -> int:
    return {month: get_term_code_by_month(month) for month in range(1, 13)}.get(
        CURRENT_MONTH, FALL
    )


def get_next_term_code(term_code: Optional[int] = None) -> int:
    term_code = term_code or get_current_term_code()
    return {SPRING: SUMMER, SUMMER: FALL, FALL: SPRING}.get(term_code, FALL)


def get_future_term_year(two_terms_ahead=False):
    term_code = SUMMER if two_terms_ahead else FALL
    return NEXT_YEAR if CURRENT_TERM_CODE == term_code else CURRENT_YEAR


def get_term(year: int, term_code: int) -> int:
    return int(f"{year}{term_code}")


CURRENT_TERM_CODE = get_current_term_code()
NEXT_TERM_CODE = get_next_term_code()
TWO_TERM_CODES_AHEAD = get_next_term_code(NEXT_TERM_CODE)
NEXT_TERM_YEAR = get_future_term_year()
TWO_TERMS_AHEAD_YEAR = get_future_term_year(two_terms_ahead=True)
CURRENT_TERM = get_term(CURRENT_YEAR, CURRENT_TERM_CODE)
NEXT_TERM = get_term(NEXT_TERM_YEAR, NEXT_TERM_CODE)
TWO_TERMS_AHEAD = get_term(TWO_TERMS_AHEAD_YEAR, TWO_TERM_CODES_AHEAD)
