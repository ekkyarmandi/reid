import re


def find_page_number(url):
    result = re.search(r"cpage=(?P<cpage>\d+)", url)
    if result:
        return int(result.group("cpage"))
    else:
        return 0
