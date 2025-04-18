from datetime import datetime as dt
import re

CURRENT_YEAR = dt.now().year


def find_code(text: str) -> str:
    result = re.search(r"(?P<code>.*?) \(", text)
    if result:
        return result.group("code")
    return ""


def extract_publish_date(text: str) -> dt | None:
    result = re.search(r"\d{8}", text)
    if result:
        try:
            date_str = result.group(0)
            date = dt.strptime(date_str, r"%Y%m%d")
            return date
        except ValueError:
            return None


def find_leasehold_years(text: str) -> str | float:
    results = re.findall(r"[0-9.]+ [Yy]ear|\d{4}", text)
    results = list(map(str.lower, results))
    results = list(filter(lambda x: "year" in x or int(x) > 2023, results))
    results = list(
        map(
            lambda x: (
                abs(int(x) - CURRENT_YEAR)
                if "year" not in x
                else float(x.strip(" year"))
            ),
            results,
        )
    )
    if not results:
        return None
    return max(results)
