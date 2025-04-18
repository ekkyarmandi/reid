# date: 10 July 2024
# desc: Script to validate Bali Realty cloudflare session

from parsel import Selector
import requests
from decouple import config


def get_html(url: str) -> requests.Response:
    headers = {
        "user-agent": config("USER_AGENT"),
        "cache-control": "no-cache",
        "cookie": "cf_clearance=" + config("BALIREALTY_COOKIES"),
    }
    print(headers)
    response = requests.get(url, headers=headers)
    return response


if __name__ == "__main__":
    url = "https://www.balirealty.com/properties/ready-to-build-850sqm-residential-land-with-long-lease-in-padonan-canggu-2666/"
    response = get_html(url)
    selector = Selector(text=response.text)
    title = selector.css("title::text").get()
    print(response.status_code, title)
