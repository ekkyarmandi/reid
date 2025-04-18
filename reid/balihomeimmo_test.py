# date: 12 Jan 2024
# desc: Script to validate Bali Home Immo cookies session

from requests_html import HTMLSession
import requests
from parsel import Selector
from decouple import config


def get_html(url: str) -> requests.Response:
    headers = {
        "user-agent": config("USER_AGENT"),
        "cache-control": "no-cache",
        "cookie": "cf_clearance=" + config("BALIHOMEIMMO_COOKIES"),
    }
    print("Headers:", headers)
    session = HTMLSession()
    response = session.get(url, headers=headers)
    return response


if __name__ == "__main__":
    url = "https://bali-home-immo.com/realestate-property/for-rent/villa/yearly/canggu/3-bedroom-family-villa-with-garden-for-rent-in-bali-canggu-rf2698"
    response = get_html(url)
    title = response.html.find("title", first=True).text
    print(response, title)

