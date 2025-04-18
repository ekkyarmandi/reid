from itemloaders.processors import TakeFirst
from typing import Callable, Union
from datetime import datetime, timedelta
from itemloaders.processors import MapCompose, TakeFirst, Join
from scrapy import Selector
from w3lib.html import remove_tags
import re
import json

### lambda functions
get_first = lambda text, sep: str(text).split(sep)[0]
get_last = lambda text, sep: str(text).split(sep)[-1]

delisted_item = dict(title="N/A", availability="Delisted")


### Custom Functions
def to_number(value):
    if type(value) == str:
        value = re.sub(",", "", value)
        result = re.findall(r"[0-9.]+", value)
        result = list(filter(lambda i: re.search(r"\d", i), result))
        dots = len(re.findall(r"\.", value))
        if len(result) > 0:
            result = "".join(result)
            dec = len(result.split(".")[-1]) if dots == 1 else 0
            if dots > 1 or dec > 2:
                result = result.replace(".", "")
            return eval(result)
        else:
            return ""
    return value


def get_domain(url: str) -> str | None:
    result = re.search(r"http[s]://(.*?)/", url).group(1)
    return result


def find_usd(text: str) -> int | None:
    """
    Find USD within the text and return it as integer or None value
    """
    result = re.search(r"USD\s*(?P<price>[0-9.,]+)", str(text), re.IGNORECASE)
    if result:
        price = result.group("price").replace(",", "")
        try:
            return int(price)
        except ValueError:
            price = price.replace(".", "")
            return int(price)


def find_idr(text: str) -> int | None:
    """
    Find IDR within the text and return it as integer or None value
    """
    result = re.search(r"IDR\s*(?P<price>[0-9.,]+)", text, re.IGNORECASE)
    if result:
        price = result.group("price").replace(",", "").replace(".", "")
        return int(price)


def clean_price_text(value: str) -> str:
    value = value.lower()

    # turn / as "per"
    value = re.sub(r"\/", " per ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"per$|-$", "", value)

    # fix numbering issue
    value = re.sub(r"^rp\.?", "", value)
    value = re.sub(r"rupia$|rupiah|bersih", "", value)
    value = re.sub(r"\.00$", r"\,00", value)

    # replace m2 to meter
    value = re.sub(r"m2", "meter", value)
    value = re.sub(r"per m$", "permeter", value)
    value = re.sub(r"per(.*?)meter", "permeter", value)
    value = re.sub(r"juta(.*?)per(.*?)meter", "juta permeter", value)
    value = re.sub(r"jjuta", "juta", value)
    value = re.sub(r"mete$|meteer", "meter", value)

    # remove word "pertahun"
    value = re.sub(r"per\s*tahun", "pertahun", value)
    value = re.sub(r"pertahun", "", value)

    # remove word "nego"
    value = re.sub(r"nego|neg$", "", value)
    value = re.sub(r"_|\)|\(", "", value)

    # split by dash
    value = value.split("-")[0]

    return value.strip()


def fix_price(text: str) -> str | float:
    dots = re.findall("\.", text)
    commas = re.findall("\,", text)
    if len(commas) == 1 and len(dots) == 1:
        text = text.replace(".", "")
        text = text.replace(",", ".")
    if len(commas) == 1:
        text = text.replace(",", ".")
    elif len(commas) > 1:
        text = text.replace(",", "")
    if len(dots) > 1:
        text = text.replace(".", "")
    text = float(re.search(r"[0-9.]+", text).group(0))
    return text


def check_per_meter(value: str) -> str:
    """
    Checking 'per meter' word in the text
    """
    value = clean_price_text(value)
    if re.search(r"per(.*?)meter", value):
        return True
    return False


def re_extract_price(value: str) -> str:
    text = clean_price_text(value)
    result = re.search(r"[0-9.,]+\s*m", text)
    if result:
        w = result.group(0)
        if re.match(r"\d", w):
            w = int(fix_price(w) * 1e9)
        return w
    result = re.search("[0-9.,]+", text)
    if result and not re.search(r"[a-z]", text):
        w = result.group(0)
        return int(fix_price(w))
    result = re.search(r"[0-9.,]+\s*(juta|jt)$", text)
    if result:
        w = result.group(0)
        if re.match(r"\d", w):
            return int(fix_price(w) * 1e6)
    result = re.search("(?P<price>[0-9.,]+)(.*?)ribu$", text)
    if result:
        w = result.group("price")
        return int(fix_price(w) * 1e3)
    result = re.search(r"(?P<price>[0-9.,]+)\s*per\s*meter", text)
    if result:
        w = result.group("price")
        return int(fix_price(w))
    result = re.search(r"(?P<price>[0-9.,]+)\s*(juta|jt)\s*per\s*meter", text)
    if result:
        w = result.group("price")
        return int(fix_price(w) * 1e6)
    result = re.search(r"(?P<price>[0-9.,]+)\s*(ribu|rb)\s*per\s*meter", text)
    if result:
        w = result.group("price")
        return int(fix_price(w) * 1e3)
    return 0


def find_property_type(text: str):
    types = ["villa", "apartement", "townhotel", "land", "loft", "house", "home"]
    for t in types:
        if t in text.lower():
            return t.title()


# TODO: deprecate soon
def property_type(item):
    title = item.get("title", "").lower()
    contract_type = item.get("leasehold_freehold", "")
    types = ["villa", "apartement", "hotel", "land", "house", "home"]
    for t in types:
        if t in title:
            if t in ["house", "home"]:
                return contract_type + " House"
            else:
                return " ".join([contract_type, t.title()])
    return contract_type  # the default is Villa


def get_img_src(str):
    result = re.search("\((.*?)\)", str)
    return result.group(1)


def find_hold_state(tags):
    # lambda function #
    lowercase = lambda tag: re.sub("\s+", "", tag).lower().strip()
    # main logic #
    tags = list(map(lowercase, tags))
    is_leasehold = any(list(map(lambda t: "lease" in t, tags)))
    is_sold = any(list(map(lambda t: "sold" in t, tags)))
    return is_leasehold, is_sold


def grab_first(value):
    if "/" in value:
        return value.split("/")[0]
    elif "-" in value:
        return value.split("-")[0]
    elif "+" in value:
        return value.split("+")[0]
    elif "or" in value:
        return value.split("or")[0]
    return value


def grab_first_word(text: str) -> str:
    result = re.search(r"\w+", text)
    if result:
        return result.group(0)


def get_icons(icons):
    details = {}
    for i in icons:
        k = i.split(":")[0].lower().strip().replace(" ", "_")
        v = i.split(":")[-1].lower().strip().replace("m2", "")
        details.update({k: v})
    return details


def get_uploaded_date(src, pattern=r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"):
    patterns = [
        r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})",  # 2023-12-01
        r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})",  # 20231201
        r"(?P<year>\d{4})/(?P<month>\d{2})/",  # /2023/11/
    ]
    for i, p in enumerate(patterns):
        if result := re.search(p, src):
            year = result.group("year")
            month = result.group("month")
            # validate the year
            if not re.search(r"^20\d{2}$", year):
                continue
            # validate the day
            if i == 2:
                day = "01"
            else:
                day = result.group("day")
            # validate the month
            if int(month) > 12:
                temp = month
                month = day
                day = temp
            try:
                date = datetime(year=int(year), month=int(month), day=int(day))
                return date.strftime("%m/%d/%y")
            except:
                continue
    return None


def get_background_image(value):
    result = re.search(r"background\-image\:url\((?P<src>.*)\)\;", value)
    if result:
        return result.group("src")
    return value


def remove_whitespace(value):
    return re.sub("\s+", " ", value).strip()


def price_request_to_zero(value):
    if type(value) == str and "price request" in value.lower():
        return 0
    return value


def time_ago_to_datetime(text):
    current_date = datetime.now()
    interval = to_number(text)
    if "year" in text:
        delta = current_date - timedelta(days=interval * 365)
    elif "month" in text:
        delta = current_date - timedelta(days=interval * 30)
    elif "week" in text:
        delta = current_date - timedelta(days=interval * 7)
    elif "day" in text:
        delta = current_date - timedelta(days=interval)
    else:
        return text
    return delta.strftime("%m/%d/%y")


def dot_to_comma(value):
    return value.replace(".", ",")


def remove_show_more_less(value):
    return value.replace("Show More", "").replace("Show Less", "")


def is_sold(value):
    if value.lower() == "sold":
        return "Sold"
    return "Available"


def safe_number(value):
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None  # Invalid input

    if isinstance(value, (int, float)):
        try:
            if value.is_integer():
                return int(value)
            else:
                rounded = round(value, 2)
                return rounded
        except AttributeError:
            return value
    else:
        return None  # Invalid input


def are_to_sqm(value):
    # def asnumber(text):
    #     digits = re.findall(r"[0-9.]+", text)
    #     value = next(d for d in digits)
    #     return eval(value)

    # if type(value) == str:
    #     if "are" in value.lower():
    #         value = asnumber(value) * 100
    #         return safe_number(value)
    #     else:
    #         return to_number(value)

    if isinstance(value, str):
        result = re.search(r"(?P<are>[0-9.,]+)\s*are", value, re.IGNORECASE)
        if result:
            raw_value = result.group("are")
            raw_value = re.sub(",", ".", raw_value)
            try:
                value = int(float(raw_value) * 100)
            except:
                return None
    return value


def construct_description(rows_of_text: list):
    rows_of_text = list(map(str.strip, rows_of_text))
    rows_of_text = list(filter(lambda f: f != "", rows_of_text))
    description = "\n".join(rows_of_text).strip()
    return description


def find_location_in_desription(description: str) -> str:
    line = str(description).lower()
    if "location" in line:
        result = re.search(r"location:\s*(\w+)\b", line)
        if result:
            loc = result.group(1)
            ori = re.search(loc, line)
            a, b = ori.start(), ori.end()
            return description[a:b]


def find_location_in_title(title: str) -> str:
    try:
        return re.search("in (\w+)", title, re.IGNORECASE).group(1).title()
    except AttributeError:
        return None


def find_contract_type(value: str):
    result = re.search(r"leasehold|freehold", value.lower())
    if result:
        return result.group().title()
    return value


def get_contract_type(value: str):
    if result := re.search(r"leasehold|freehold", value.lower()):
        return result.group().title()
    return "Freehold"


def grab_price(price):
    idr = None
    usd = None
    price = price.lower()
    if "idr" in price:
        idr = price
    elif "usd" in price:
        usd = price
    return idr, usd


def find_leasehold_years_bahasa(text) -> str | None:
    pattern = r"harga(.*?)\d{1,2}(.*?)(utk|untuk)(.*?)(?P<years>\d{1,2})\s*tahun"
    text = re.sub(r"\n", " ", text)
    if result := re.search(pattern, text, re.IGNORECASE):
        try:
            return int(result.group("years"))
        except:
            return None
    return None


def count_lease_years(text: str) -> int | None:
    # local scope function
    def calc_yr_range(year: int):
        if type(year) != int:
            year = int(year)
        current_year = datetime.now().year
        return year - current_year

    def purify_number(text: str):
        numbers = re.findall(r"[0-9,.]+", text)
        for v in numbers:
            number = re.sub("\,|\.", "", v)
            text = text.replace(v, number)
        return text

    # turn the description into list of sentences
    sentences = []
    text = text.lower().split("\n")
    for t in text:
        s = t.split(".")
        sentences.extend(s)
    # find the sentence that contains years or lease word at least
    years = []
    for stc in sentences:
        if "year" in stc or "lease" in stc:
            # find four digit lease until year
            stc = purify_number(stc)
            result = re.findall(r"\b\d{4}\b", stc)
            if len(result) > 0:
                result = list(filter(lambda y: re.match(r"^2", y), result))
                result = list(map(calc_yr_range, result))
                years.extend(result)
            # find 2 digit with years word in the back
            if "year" in stc:
                result = re.findall(r"\b\d{1,2}\b", stc)
                if len(result) > 0:
                    result = list(map(int, result))
                    years.extend(result)
    if len(years) > 0:
        years = list(map(int, years))
        return max(years)


def find_size(text: str, patterns: list, keyword: str):
    def evaluate(pattern_result: str, value: str):
        # validate the build size
        if not re.search("\d", value):
            return None
        # evaluate build size value
        if re.search(r"are$", pattern_result):
            return eval(value) * 100
        else:
            return eval(value)

    results = []
    for p in patterns:
        result = re.search(p, text)
        if result:
            # extract the build size value
            try:
                build_size = result.group(keyword).replace(",", ".")
                results.append(evaluate(result.group(), build_size))
            except SyntaxError:
                build_size = result.group(keyword).replace(",", "")
                results.append(evaluate(result.group(), build_size))
    results = list(filter(lambda s: s != None, results))
    if len(results) > 0:
        return results[0]
    else:
        return None


def find_land_size(desc: str):
    desc = desc.lower()
    patterns = [
        r"(land size|luas tanah|land area|total area).*?(?P<land_size>[0-9.,]+)\s*(m2|sqm|sq\. meter|square meter|are)",
        r"(?P<land_size>[0-9.,]+)\s*(sqm of land|square meter(s)? of land|sqm|are)",
    ]
    return find_size(desc, patterns, "land_size")


def find_build_size(desc: str):
    desc = desc.lower()
    patterns = [
        r"build(ing)? size.*?(?P<build_size>[0-9.,]+)\s*(m2|m²|sqm|are)?",
        r"build(ing)?\s*(?P<build_size>[0-9.,]+)\s*(m2|m²|sqm|are)?",
        r"(?P<build_size>[0-9.,]+)\s*(sqm built area|square meter(s)? build|sqm|are)",
        r"(?P<build_size>[0-9.,]+) sqm building size",
    ]
    return find_size(desc, patterns, "build_size")


def find_lease_years(description) -> int | None:
    """
    Find leasehold years in the description.
    """

    # sub functions
    def validate_year(value: str):
        if len(value) == 2 and not re.search(r"^0", value):
            return True
        elif len(value) == 4 and re.search(r"^2", value):
            return True
        return False

    def re_number(value: str):
        value = re.sub(",", ".", value)
        result = re.search(r"[0-9.]+", value)
        if result:
            return result.group()
        else:
            return "00"

    # lambda functions
    has_years = lambda str: re.search(r"price(.*?)(20\d{2}$)", str)
    # function main logic
    description = description.lower()
    paragraph = description.split("\n")
    sentences = []
    for p in paragraph:
        sentences.extend(p.split("."))
    for s in sentences:
        if "years" in s or "lease" in s or has_years(s):
            # find date and extract the years only
            dates = re.findall(r"\d+\/\d+\/\d+", s)
            dates_month_day_only = list(
                map(lambda d: re.findall(r"\d{2}\/\d{2}\/", d), dates)
            )
            dates_month_day_only = [
                item for sublist in dates_month_day_only for item in sublist
            ]

            for d in dates_month_day_only:
                s = s.replace(d, "")

            # find any value indicates the leasehold years
            years = re.findall(
                r"\d{2}\s{0,1}th|\d{1,2}\s{0,1}year|\b\d{2}\b|\b\d{4}\b", s
            )
            years = list(map(re_number, years))
            years = list(filter(validate_year, years))
            years = list(map(to_number, years))
            years = list(filter(lambda d: len(str(d)) == 2 or len(str(d)) == 4, years))
            years = sorted(years, key=lambda d: len(str(d)))
            if len(years) > 0:
                today = datetime.now()
                d = years[0]
                if len(str(d)) == 4 and int(d) >= today.year:
                    return int(d) - today.year
                elif len(str(d)) == 2:
                    return int(d)


def get_lease_years(text):
    text = text.lower()
    if "year" in text or "lease" in text or re.search(r"\d{4}", text):
        years = re.findall(r"\b\d{4}\b|\d{2} years|\d{2} year", text)
        years = list(map(lambda d: re.search(r"\d{2,4}", d).group(), years))
        years = list(filter(lambda d: len(d) == 2 or len(d) == 4, years))
        years = sorted(years, key=lambda d: len(d))
        years = list(map(int, years))
        if len(years) > 0:
            years = years[0]
            if len(str(years)) == 4:
                today = datetime.now()
                return int(years) - today.year
            elif len(str(years)) == 2:
                return int(years)
        # developed based on rajavilla case
        elif "year" in text:
            to_dot = lambda str: str.replace(",", ".") if "," in str else str
            results = re.findall(r"[0-9.,]+", text)
            results = list(filter(lambda i: re.search(r"\d", i), results))
            results = list(map(to_dot, results))
            results = list(map(to_number, results))
            if len(results) > 0:
                return min(results)


def search_leasehold_years(description):
    # lambda functions
    def validate_years(value):
        """
        Start with non-zero and has digit between 2 and 4
        """
        digit = len(value)  # get digit len
        prime = int(value[0])  # start with non-zero
        if digit < 4:
            return digit > 1 and prime > 0 and int(value) <= 100
        else:
            return digit > 1 and prime > 0

    def years_to_numeric(value):
        if len(value) == 4:
            delta = int(value) - datetime.now().year
            return delta
        else:
            return int(value)

    has_leasehold = lambda text: "year" in text or "lease" in text
    # main logic
    desc = description.lower().split("\n")
    desc = list(filter(has_leasehold, desc))
    results = []
    for line in desc:
        patterns = (
            r"lease(hold)?.*?(?P<year>\d{2,4})\s*",
            r"lease(hold)?.*?(?P<year>\d{2})\s+year",
            r"(\s*)(?P<year>\d{2,4})\s+year.*?lease",
        )
        for p in patterns:
            result = [match[1] for match in re.findall(p, line)]
            result = list(filter(validate_years, result))
            for r in result:
                if r not in results:
                    results.append(r)
    results = list(map(years_to_numeric, results))
    return results


def dimension_remover(src):
    patterns = [
        r"(-\d+x\d+)\.jpg",
        r"(-\d+x\d+)\.jpeg",
        r"(-\d+x\d+)\.png",
        r"(-\d+x\d+)\.webp",
    ]
    result = re.search("|".join(patterns), src)
    if result:
        for i in range(1, 4):
            dim = result.group(i)
            if dim:
                src = src.replace(dim, "")
    return src


def find_published_date(script):
    result = re.search(r'"datePublished":"(?P<date>[T0-9\-\:\+]+)"', script)
    if result:
        date = result.group("date")
        return datetime.fromisoformat(date).strftime("%m/%d/%y")
    return ""


def define_property_type(text: str, default: str = "Villa") -> str:
    types = [
        "apartment",
        "apartement",
        "townhotel",
        "hotel",
        "land",
        "loft",
        "plot",
        "house|home",
        "villa",
    ]
    for t in types:
        result = re.search(t, text, re.IGNORECASE)
        if result:
            word = result.group().lower()
            if "home" in word or "house" in word:
                return "House"
            elif "plot" in word:
                return "Land"
            else:
                return t.title()
    return default  # the default is Villa


class FindLeaseYears:
    def __call__(self, values):
        for v in values:
            result = get_lease_years(v)
            if type(result) == int:
                return result


class AnySoldDelisted(TakeFirst):
    def __call__(self, values):
        is_sold = lambda f: "sold" in f.lower()
        is_delisted = lambda f: "delisted" in f.lower()
        if any(list(map(is_sold, values))):
            return "Sold"
        elif any(map(is_delisted, values)):
            return "Delisted"
        return "Available"


class SplitOn(TakeFirst):
    def __init__(self, splitter: str = "-", index: int = 0):
        self.splitter = splitter
        self.index = index

    def __call__(self, values: list):
        for value in values:
            if type(value) == str:
                return value.split(self.splitter)[self.index].strip()
            elif type(value) == int:
                return value


class TakeNth:
    def __init__(self, position):
        self.position = position

    def __call__(self, values):
        new_values = []
        for v in values:
            if type(v) == str:
                v = v.strip()
            new_values.append(v)
        try:
            return new_values[self.position]
        except IndexError:
            return None


class Max(TakeFirst):
    def __call__(self, values):
        return max(values)


class JoinAndStrip(Join):
    def __call__(self, values):
        values = list(map(str.strip, values))
        values = list(filter(lambda v: v != "", values))
        return self.separator.join(values)


def find_sold_out(labels: list) -> str:
    if len(labels) > 0:
        has_sold = lambda str: "sold" in str.lower()
        labels = list(map(has_sold, labels))
        if any(labels):
            return "Sold"
    return "Available"


def find_off_plan(title: str, description: str, labels: list = []) -> bool:
    # values to look
    off_plan = ["off plan", "offplan", "off-plan"]
    # lambda function
    has_off_plan = lambda str: any([i in str.strip().lower() for i in off_plan])
    # main logic
    # check off-plan word in title and description
    if has_off_plan(title) or has_off_plan(description):
        return True
    # check off-plan in labels
    if any(list(map(has_off_plan, labels))):
        return True
    return False


def find_bedrooms(text: str) -> Union[str, None]:
    result = re.search(r"(\d{1,2}) bedroom(s?)", str(text), re.IGNORECASE)
    if result:
        return int(result.group(1))
    return None


def extractor(pattern: str, text: str, func: Callable) -> Union[int, None]:
    results = []
    text = str(text)
    for line in text.split("\n"):
        if not func(line):
            continue
        output = re.findall(pattern, line)
        output = list(map(lambda i: to_number(i[0]), output))
        if len(output) == 1:
            return output[0]
        elif len(output) > 0:
            results.extend(output)
    if len(results) > 0:
        return max(results)


def landsize_extractor(text: str) -> Union[int, None]:
    pattern = r"\b([0-9.,]+)(\s*)(sqm|m2|are)\b"
    has_landsize = (
        lambda str: "landsize" in str.lower()
        or "land size" in str.lower()
        or "land for sale" in str.lower()
    )
    result = extractor(pattern, text, has_landsize)
    return result


def buildsize_extractor(text):
    pattern = r"(?:[Vv]illa|[Bb]uilding)(.*?)(?P<value>[0-9.,]+)(sqm|m2|are)"
    for line in text.split("\n"):
        result = re.match(pattern, line)
        if result:
            value = result.group("value")
            return to_number(value)


def recalculate_price_by_land_size(text: str, price: int, land_size: int) -> int:
    # WARNING: assumed the land size is in square meter
    # check the price and land size type
    if isinstance(price, str):
        price = int(price)
    if isinstance(land_size, str):
        land_size = int(land_size)
    # check if the has something like /m2 or /are
    pattern = r"\/\w+"
    per = list(set(re.findall(pattern, text)))
    devider = " ".join(per)
    ## calculate price based on land_size ##
    if "are" in devider or "m2" in devider:
        if "are" in devider and land_size > 0:
            per_are = land_size / 100
            new_price = price * per_are
            return new_price
        # elif "m2" in devider and land_size > 0:
        #     result = re.search(r"\d+", devider)
        #     if result:
        #         sqm = int(result.group(0))
        #         per_sqm = land_size / sqm
        #         new_price = price * per_sqm


def finder(
    pattern: str, text: str = "", key: str | int = 0, dtype: str = str
) -> str | None:
    """
    REGEX API for finding specific pattern with defined target key
    """
    try:
        return dtype(re.search(pattern, text).group(key))
    except AttributeError:
        return None


### Item Classes


class IsOffPlan(TakeFirst):
    def __call__(self, values: list):
        any_sold = any(list(map(find_off_plan, values)))
        return any_sold


def standardize_property_type(property_type: str) -> str:
    # define the property type
    if re.search(r"land", property_type, re.IGNORECASE):
        property_type = "Land"
    elif re.search(r"townhouse", property_type, re.IGNORECASE):
        property_type = "Townhouse"
    elif re.search(r"house|home", property_type, re.IGNORECASE):
        property_type = "House"
    elif re.search(r"apartment|apartement", property_type, re.IGNORECASE):
        property_type = "Apartment"
    elif re.search(r"commercial", property_type, re.IGNORECASE):
        property_type = "Commercial"
    elif re.search(r"^hotel", property_type, re.IGNORECASE):
        property_type = "Hotel"
    elif re.search(r"villa", property_type, re.IGNORECASE):
        property_type = "Villa"
    # remove "for Sale" keywords from property type
    property_type = str(property_type).replace(" for Sale", "")
    return property_type


def find_bedrooms_in_description(text):
    if "bedroom" in text:
        result = re.search(r"\b\d{1,2}.*?bedroom", text, re.IGNORECASE)
        if result:
            text = result.group()
            numbers = re.findall(r"\d{1,2}", text)
            n = re.search(r"bedroom", text).start()
            p = "({}).*?bedroom"
            closest = [n - re.search(p.format(i), text).start() for i in numbers]
            x = closest.index(min(closest))
            beds = numbers[x]
            return int(beds)


def first_month() -> datetime:
    date = datetime.now()
    date = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month = date.month - 1
    date = date.replace(month=month)
    return date.strftime("%Y-%m-%d")


def extract_currency(text):
    match = re.search(
        r"\b(IDR)\b|\b(USD)\b|\b(Rp)\b|(IDR)\d+|(USD)\d+|\b(Rp)\s*\d+",
        text,
        re.IGNORECASE,
    )
    if match:
        try:
            result = match.group(1)
            if not result:
                return match.group()
            else:
                return result
        except IndexError:
            return match.group()
    return text


def identify_currency(text: str) -> str:
    if re.search(r"\bIDR\b|\bRp\b|\bIDR\d+", text, re.IGNORECASE):
        return "IDR"
    elif re.search(r"\bUSD\b|\bUSD\d+", text, re.IGNORECASE):
        return "USD"
    else:
        return None


def json_string_to_dict(json_str):
    """
    Convert a JSON string to a Python dictionary.

    Args:
        json_str (str): A string in JSON format

    Returns:
        dict: The converted Python dictionary
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None


def cari_luas_tanah(text: str) -> Union[int, None]:
    pattern = r"(land size|luas tanah|land area|total area).*?(?P<land_size>[0-9.,]+)\s*(m2|sqm|sq\. meter|square meter|are)"
    if result := re.search(pattern, text, re.IGNORECASE):
        return result.group("land_size")


def join_strings(values: list[str]) -> str:
    values = [f"'{value}'" for value in values]
    return ", ".join(values)


def extract(pattern: str, text: str) -> str:
    if result := re.search(pattern, text):
        return result.group(1)
    return None
