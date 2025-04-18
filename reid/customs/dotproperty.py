import re
from datetime import datetime
from reid.func import (
    count_lease_years,
    find_lease_years,
    find_leasehold_years_bahasa,
    to_number,
)


def after_colon(text):
    try:
        results = text.split(":")
        if len(results) > 1:
            return results[-1].strip()
        elif len(results) == 1:
            return results[0]
    except:
        return ""


def find_years(value) -> int | None:
    ## lambda functions
    is_not_empty_string = lambda text: str(text).strip() != ""
    is_start_with_two = lambda d: (
        re.search(r"^2", str(d)) if len(str(d)) == 4 else True
    )
    ## main logic
    if type(value) == str:
        text = value
        current = datetime.now()
        years = re.findall(r"\d{4}|\d{2}\s*th", text)
        years = list(filter(is_not_empty_string, years))
        years = list(map(to_number, years))
        years = list(filter(is_start_with_two, years))

        if len(years) == 0:
            return None

        for i, y in enumerate(years):
            if len(str(y)) == 4:
                years[i] = y - current.year

        years = list(filter(lambda d: d > 0, years))
        if len(years) > 0:
            return next(y for y in years)

    elif type(value) == int:
        return value


def leasehold_years_finders(text: str) -> int | None:
    """
    Find the leasehold years from the text using multiple strategies
    """
    if not text:
        return None

    # Try all the different methods in sequence
    years = (
        find_lease_years(text)
        or find_years(text)
        or count_lease_years(text)
        or find_leasehold_years_bahasa(text)
    )

    return years
