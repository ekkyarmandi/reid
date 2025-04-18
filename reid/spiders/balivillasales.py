from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from reid.func import (
    find_build_size,
    find_land_size,
    find_lease_years,
    find_location_in_desription,
    get_uploaded_date,
    get_first,
    find_bedrooms,
    delisted_item,
)
from models.error import Error
from reid.database import get_db
import traceback
import re

from reid.customs.balivillasales import get_balivillasales_price


class BaliVillaSalesSpider(BaseSpider):
    name = "balivillasales"
    allowed_domains = ["balivillasales.com"]
    start_urls = ["https://www.balivillasales.com"]

    def parse(self, response):
        # collect items
        items = response.css(".product-types .read-more")
        for item in items:
            url = item.css("a[target]::attr(href)").get()
            yield response.follow(url, callback=self.parse_detail)
        # go to next url
        next_url = response.css("#wp_page_numbers ul li:last-child a::attr(href)").get()
        if next_url and next_url != response.url:
            yield response.follow(next_url, callback=self.parse)

    def parse_detail(self, response):
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Villas of Bali")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)

            # Price handling
            # TODO: debug the price here
            price = response.css(".single-price::text").get("Empty")
            result = get_balivillasales_price(price)
            if "IDR" in price:
                loader.add_value("price", price)
                loader.add_value("currency", "IDR")
            elif "USD" in price:
                loader.add_value("price", price)
                loader.add_value("currency", "USD")

            # NOTE: consider this code for finding the price
            # currency = response.css("#currency::attr(rel)").get()
            # if currency:
            #     currency = eval(currency)
            #     currency["price"] = int(currency.get("price", 0))
            #     if currency["cur"] == "USD":
            #         item["price_usd"] = currency["price"]
            #         item["price"] = 0
            #     elif currency["cur"] == "IDR":
            #         item["price_usd"] = 0
            #         item["price"] = currency["price"]

            # Image and date handling
            loader.add_css("image_url", "img[u]::attr(src)")
            loader.add_css(
                "listed_date",
                "img[u]::attr(src)",
                MapCompose(get_uploaded_date),
            )

            # Availability handling
            availability = "Sold" if "Sold" in price else "Available"
            loader.add_value("availability_label", availability)

            # Property details
            loader.add_css("contract_type", "span[class*=key]::text")
            loader.add_css(
                "land_size",
                ".details span[title*=Land]::text",
                MapCompose(
                    lambda str: str.replace("m2", "").replace(",", "."),
                    lambda str: get_first(str, "-"),
                ),
            )
            loader.add_css(
                "build_size",
                ".details span[title*=Building]::text",
                MapCompose(
                    lambda str: str.replace("m2", "").replace(",", "."),
                    lambda str: get_first(str, "-"),
                ),
            )
            loader.add_css("bathrooms", ".details span:contains(Bathroom)::text")
            loader.add_css("bedrooms", ".details span:contains(Bedroom)::text")
            loader.add_css("title", "h1#stitle::text")
            loader.add_css("property_id", ".code-location span::text")
            loader.add_css("location", ".code-location span span::text")
            loader.add_css("description", ".the_content ::Text")
            loader.add_css("property_type", "h1#stitle::text")

            item = loader.load_item()

            # Get the values
            title = item.get("title", "")
            contract_type = item.get("contract_type")
            location = item.get("location")
            description = item.get("description", "")
            land_size = item.get("land_size", 0)
            build_size = item.get("build_size", 0)
            leasehold_years = item.get("leasehold_years")
            bedrooms = item.get("bedrooms")
            # Property type handling
            if title == "":
                yield delisted_item
            elif not contract_type:
                yield delisted_item

            # Location handling
            if not location:
                item["location"] = find_location_in_desription(description)

            location = item.get("location")
            result = re.search(r"in (?P<location>[A-Za-z ]+)", title)
            if not location and result:
                item["location"] = result.group("location")

            # Size handling
            if not land_size:
                land_size = find_land_size(description)
            if not build_size:
                build_size = find_build_size(description)

            # Fix land and build size
            if land_size == build_size:
                item["land_size"] = land_size
                item["build_size"] = None
                item["property_type"] = "Land"
            else:
                item["land_size"] = land_size
                item["build_size"] = build_size

            # Leasehold years handling
            if not leasehold_years and "leasehold" in contract_type:
                item["leasehold_years"] = find_lease_years(description)

            # Bedrooms handling
            if not bedrooms:
                item["bedrooms"] = find_bedrooms(description)

            yield item

        except Exception as err:
            error = Error(
                url=response.url,
                source="Spider",
                error_message=str(err),
            )
            # Capture the traceback and add it to the error message
            tb = traceback.format_exc()
            error.error_message += f"\nTraceback:\n{tb}"
            db = next(get_db())
            db.add(error)
            db.commit()
