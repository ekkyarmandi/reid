import traceback
import re
from models.error import Error
from reid.database import get_db
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from datetime import datetime
from reid.func import (
    dimension_remover,
    count_lease_years,
    extract,
    find_property_type,
    identify_currency,
    to_number,
    get_first,
    get_last,
    find_bedrooms,
    find_build_size,
    find_land_size,
)


class BaliRealEstateConsultantsSpider(BaseSpider):
    name = "balirealestateconsultants"
    allowed_domains = ["balirealestateconsultants.com"]
    start_urls = [
        "https://balirealestateconsultants.com/properties/?tab=for-sale&tax=property_status",
    ]

    def parse(self, response):
        # collect property items
        items = response.css("#module_properties > .card")
        for item in items:
            url = item.css("h2 a::attr(href)").get()
            yield response.follow(url, callback=self.parse_detail)

        # go to the next page
        next_url = response.css("ul.pagination li a[aria-label=Next]::attr(href)").get()
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_detail(self, response):
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Bali Real Estate Consultants")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)

            ## lambda functions ##
            to_key = lambda str: str.strip().lower().replace(" ", "_")

            ## main logic ##
            loader.add_css(
                "image_url",
                ".top-gallery-section img::attr(src)",
                MapCompose(dimension_remover),
            )

            # get details
            d = {}
            details = response.css("#property-overview-wrap ul")
            for ul in details:
                key = ul.css("li:nth-child(2)::text").get()
                key = to_key(key.replace("m²", ""))
                if "bathroom" in key:
                    key = "bathrooms"
                elif "bedroom" in key:
                    key = "bedrooms"
                value = ul.css("li:nth-child(1) strong::text").get()
                d.update({key: value})

            # Notes:
            # get the land (map) and build (map) size seperately
            # the logic: land size is mostly larger than the building size
            subsnowyears = lambda y: abs(y - datetime.now().year)

            lease_years = d.get("leasehold")
            if lease_years:
                contract_type = "Leasehold"
                if to_number(lease_years) > 0:
                    loader.add_value("leasehold_years", lease_years)
                else:
                    loader.add_css(
                        "leasehold_years",
                        "div.detail-wrap li:contains('Leasehold Expiration') span::text",
                        MapCompose(to_number, subsnowyears),
                    )
            else:
                contract_type = "Freehold"

            # contract type
            loader.add_value("contract_type", contract_type)
            loader.add_value("property_id", d.get("property_id"))
            loader.add_value("bedrooms", d.get("bedrooms"))
            loader.add_value("bathrooms", d.get("bathrooms"))
            loader.add_css(
                "land_size",
                "#property-overview-wrap ul li i[class*=dimensions-map] + *::Text",
                MapCompose(
                    lambda value: value.replace(",", "."),
                    lambda value: value.replace("m2", ""),
                    lambda value: get_first(value, "+"),
                    lambda value: get_last(value, "-"),
                ),
            )
            loader.add_css(
                "build_size",
                "#property-overview-wrap ul li i[class*=dimensions-plan] + *::Text",
                MapCompose(
                    lambda value: value.replace(",", "."),
                    lambda value: value.replace("m2", ""),
                    lambda value: get_first(value, "+"),
                    lambda value: get_last(value, "-"),
                ),
            )
            loader.add_css("title", "h1::text")
            loader.add_css("availability_label", "div.property-labels-wrap a::text")
            loader.add_css("price", "li.item-price::Text")
            loader.add_css(
                "currency",
                "li.item-price::Text",
                MapCompose(identify_currency),
            )
            loader.add_css("location", "address.item-address::text")
            loader.add_css(
                "description", ".property-description-wrap .block-content-wrap p ::text"
            )
            loader.add_css(
                "property_type",
                "h1::text",
                MapCompose(find_property_type),
            )
            loader.add_css(
                "longitude",
                "#houzez-single-property-map-js-extra::text",
                MapCompose(lambda x: extract(r'"lng"\s*:\s*"(-?[\d.]+)"', x)),
            )
            loader.add_css(
                "latitude",
                "#houzez-single-property-map-js-extra::text",
                MapCompose(lambda x: extract(r'"lat"\s*:\s*"(-?[\d.]+)"', x)),
            )

            item = loader.load_item()

            # find missing bedrooms
            title = item.get("title", "")
            bedrooms = item.get("bedrooms")
            if not bedrooms:
                item["bedrooms"] = find_bedrooms(title)

            # find missing build_size
            build_size = item.get("build_size", None)
            description = item.get("description", "")
            if not build_size:
                item["build_size"] = find_build_size(description)

            # find missing land_size gate 1
            land_size = item.get("land_size", None)
            if not land_size:
                item["land_size"] = find_land_size(description)

            is_contain_plot = lambda text: re.search(r"plot|land", text, re.IGNORECASE)

            # define property type as land
            bedrooms = item.get("bedrooms", 0)
            bathrooms = item.get("bathrooms", 0)
            contract_type = item.get("contract_type", "")
            if (
                not bedrooms
                and not bathrooms
                and is_contain_plot(title)
                and is_contain_plot(description)
            ):
                item["property_type"] = "Land"

            if bathrooms > 0 and not bedrooms:
                item["bedrooms"] = bathrooms

            # find leasehold years in description
            if not item.get("leasehold_years", 0) and "Leasehold" in contract_type:
                item["leasehold_years"] = count_lease_years(description)

            # reasses the land and build size
            land_size = item.get("land_size", 0)
            build_size = item.get("build_size", 0)
            if land_size == build_size:
                item["build_size"] = None
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
