from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from reid.func import (
    construct_description,
    dimension_remover,
    find_contract_type,
    find_lease_years,
    grab_price,
    delisted_item,
)
from models.error import Error
from reid.database import get_db
import traceback
import re
from datetime import datetime
import scrapy
from decouple import config
import requests


class BaliRealtySpider(BaseSpider):
    name = "balirealty"
    allowed_domains = ["balirealty.com", "jsonplaceholder.typicode.com"]

    def start_requests(self):
        self.fakeurl = "https://jsonplaceholder.typicode.com/comments/1"
        url = "https://www.balirealty.com/properties/?filter-contract=SALE&filter-location=&filter-property-type=75"
        yield scrapy.Request(
            self.fakeurl,
            meta=dict(response=self._get_response(url)),
            dont_filter=True,
        )

    def _get_response(self, url):
        headers = {
            "Cookie": "cf_clearance=" + config("BALIREALTY_COOKIES"),
            "User-Agent": config("USER_AGENT"),
            "cache-control": "no-cache",
        }
        response = requests.get(url, headers=headers)
        return scrapy.http.TextResponse(
            url=url,
            body=response.text,
            encoding="utf-8",
        )

    def parse(self, response):
        response = response.meta.get("response")
        items = response.css("div.content div.row div.property-content-list")
        for item in items:
            url = item.css("h3 a::attr(href)").get()
            yield scrapy.Request(
                self.fakeurl,
                callback=self.parse_detail,
                meta=dict(url=url, response=self._get_response(url)),
                dont_filter=True,
            )

        # Pagination
        next_url = response.css("nav.pagination div a.next::attr(href)").get()
        if next_url:
            yield scrapy.Request(
                self.fakeurl,
                callback=self.parse,
                meta=dict(response=self._get_response(next_url)),
                dont_filter=True,
            )

    def parse_detail(self, response):
        not_valid_contract = (
            lambda x: "free" not in x.lower() and "lease" not in x.lower()
        )
        try:
            response_url = response.meta.get("url")
            response = response.meta.get("response")
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Bali Realty")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response_url)
            loader.add_value("html", response.text)

            # Price handling
            price = response.css("#currentprice::attr(value)").get()
            if price:
                price_idr, price_usd = grab_price(price)
                if price_idr:
                    loader.add_value("price", price_idr)
                    loader.add_value("currency", "IDR")
                elif price_usd:
                    loader.add_value("price", price_usd)
                    loader.add_value("currency", "USD")
            else:
                delisted_item.update({"source": "Bali Realty", "url": response_url})
                yield delisted_item

            # Published date
            script = response.css("script[type='application/ld+json']::text").get()
            result = re.search(r'"datePublished":"(?P<date>[T0-9\-\:\+]+)"', script)
            if result:
                date = result.group("date")
                list_date = datetime.fromisoformat(date).strftime("%m/%d/%Y")
                loader.add_value("listed_date", list_date)

            # Property details
            details = {}
            for li in response.css("div.property-overview ul li"):
                k = li.css("span::text").get()
                v = " ".join(li.css("strong ::text").getall()).strip()
                details[k] = v

            # Availability
            availability = "Sold" if details.get("Sold", "") == "Yes" else "Available"
            loader.add_value("availability_label", availability)

            # Description
            desc = construct_description(
                response.css("div.property-description ::Text").getall()
            )
            loader.add_value("description", desc)

            # Contract type
            contract_type = find_contract_type(details.get("Status"))
            if not_valid_contract(contract_type):
                contract = details.get("Contract")
                if "sale" in contract.lower():
                    contract_type = "Freehold"
            loader.add_value("contract_type", contract_type)

            # Property type
            loader.add_value("property_type", details.get("Type"))

            # Images
            loader.add_css(
                "image_url",
                "div.carousel-inner div.item img::attr(data-src)",
                MapCompose(dimension_remover),
            )

            # Basic info
            loader.add_css("title", "h2::text")
            loader.add_css("property_id", "span:contains(Ref) + strong::text")
            loader.add_css("location", "h1 + p::text")
            loader.add_css(
                "bedrooms", "ul.property-main-features li[class*=bed] span::text"
            )
            loader.add_css(
                "bathrooms", "ul.property-main-features li[class*=bath] span::text"
            )
            loader.add_value("land_size", details.get("Land Size"))
            loader.add_value("build_size", details.get("Building Size"))

            # Leasehold years
            lease_years = find_lease_years(desc)
            loader.add_value("leasehold_years", lease_years)

            item = loader.load_item()

            # Additional processing
            desc = item.get("description", "")
            if not item.get("land_size"):
                if result := re.search(
                    r"land.*?:\s*(?P<land>\d+)\s*sqm", desc, re.IGNORECASE
                ):
                    item["land_size"] = result.group("land")
            if not item.get("build_size"):
                if result := re.search(
                    r"build.*?:\s*(?P<build>\d+)\s*sqm", desc, re.IGNORECASE
                ):
                    item["build_size"] = result.group("build")

            yield item

        except Exception as err:
            error = Error(
                url=response.url,
                source="Spider",
                error_message=str(err),
            )
            tb = traceback.format_exc()
            error.error_message += f"\nTraceback:\n{tb}"
            db = next(get_db())
            db.add(error)
            db.commit()
