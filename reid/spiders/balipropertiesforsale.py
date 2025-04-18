from scrapy.loader import ItemLoader
from reid.customs.balipropertiesforsale import to_mmddyy
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from reid.func import (
    dimension_remover,
    extract,
    find_lease_years,
    define_property_type,
    json_string_to_dict,
)
from models.error import Error
from reid.database import get_db
import jmespath
import traceback
import json
import re
import html2text
import urllib.parse
from math import ceil
import scrapy

md_converter = html2text.HTML2Text()

PARAMS = {
    "page": 1,
    "posts_per_page": 12,
    "search_by_id": True,
    "sortby": "a_price",
    "status[0]": "leasehold",
    "touched": False,
    "type[0]": "Villa",
}


class BaliPropertiesForSaleSpider(BaseSpider):
    name = "balipropertiesforsale"
    allowed_domains = ["balipropertiesforsale.com"]
    start_urls = ["https://balipropertiesforsale.com/wp-json/properties/v1/list/"]
    visited = []

    def start_requests(self):
        query_string = urllib.parse.urlencode(PARAMS)
        url = self.start_urls[0] + "?" + query_string
        yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        try:
            data = response.json()
            items = data.get("results", [])

            for item in items:
                url = f"https://balipropertiesforsale.com/property/{item['post']['post_name']}/"
                if url not in self.visited_urls:
                    self.visited_urls.append(url)
                    yield scrapy.Request(
                        url, callback=self.parse_detail, meta={"json_data": item}
                    )

            # fetch existing urls
            for url in self.existing_urls:
                if url not in self.visited_urls:
                    self.visited_urls.append(url)
                    yield scrapy.Request(url, callback=self.parse_detail)

            # Pagination
            count = data.get("count", 1)
            max_page = ceil(count / 12)
            for i in range(2, max_page + 1):
                PARAMS["page"] = i
                query_string = urllib.parse.urlencode(PARAMS)
                next_url = self.start_urls[0] + "?" + query_string
                if next_url not in self.visited:
                    self.visited.append(next_url)
                    yield scrapy.Request(next_url, callback=self.parse)

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

    def parse_detail(self, response):
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Bali Properties for Sale")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)

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

            json_data = response.meta.get("json_data", {})
            if json_data:
                i = json_data

                # Basic info
                loader.add_value("title", i["post"]["post_title"])
                loader.add_value("property_id", i["overlay"]["property_id"])

                # Prices
                loader.add_value("price", jmespath.search("overlay.price_raw", i))
                loader.add_value(
                    "currency", jmespath.search("overlay.price_currency", i)
                )

                # Images
                if i["overlay"]["images"]:
                    loader.add_value(
                        "image_url",
                        i["overlay"]["images"][0],
                        MapCompose(dimension_remover),
                    )

                # List date
                loader.add_value(
                    "listed_date",
                    i["post"]["post_date"],
                    MapCompose(to_mmddyy),
                )

                # Location and sizes
                loader.add_value("location", i["overlay"]["area"])
                loader.add_value(
                    "land_size",
                    i["overlay"]["area_size"],
                    MapCompose(lambda value: value.replace(",", ".")),
                )
                loader.add_value(
                    "build_size",
                    i["overlay"]["building_size"],
                    MapCompose(lambda value: value.replace(",", ".")),
                )

                # Rooms
                loader.add_value("bedrooms", i["overlay"]["bedrooms"])
                loader.add_value(
                    "bathrooms",
                    i["overlay"]["bathrooms"],
                    MapCompose(lambda value: value.replace(",", ".")),
                )

                # Availability
                is_sold = jmespath.search("overlay.is_sold", i)
                if is_sold:
                    price = jmespath.search("overlay.price_raw", i)
                    if not price:
                        loader.add_value("price", -1)
                    loader.add_value("sold_at", i["post"]["post_date"])
                    loader.add_value("availability_label", "Sold")
                else:
                    loader.add_value("availability_label", "Available")

                # Contract and property type
                contract_type = jmespath.search("overlay.property_status", i)
                property_type = jmespath.search("overlay.property_type", i)
                loader.add_value("contract_type", contract_type)
                loader.add_value("property_type", property_type.split(",")[0])

                # Description
                desc = md_converter.handle(i["post"]["post_content"])
                loader.add_value("description", desc)

                # Leasehold years
                if "Leasehold" in contract_type:
                    loader.add_value("leasehold_years", i["overlay"]["expiration"])

            else:
                property_data = response.css(
                    "#PropertyAgentPanel::attr(data-data)"
                ).get()
                data = json_string_to_dict(property_data)
                ## source data
                loader.add_value("json", json.dumps(data))
                ## property data
                loader.add_value("title", data.get("title"))
                loader.add_value("property_id", data.get("property_id"))
                loader.add_value("description", data.get("description"))
                loader.add_value("price", data.get("price_raw"))
                loader.add_value("currency", data.get("price_currency"))
                loader.add_value("contract_type", data.get("property_status"))
                loader.add_value("property_type", data.get("property_type"))
                loader.add_value("bedrooms", data.get("bedrooms"))
                loader.add_value("bathrooms", data.get("bathrooms"))
                loader.add_value("land_size", data.get("area_size"))
                loader.add_value("build_size", data.get("building_size"))
                loader.add_value("location", data.get("area"))
                if "lease" in data.get("property_status"):
                    loader.add_value("leasehold_years", data.get("expiration"))
                is_sold = data.get("is_sold")
                if is_sold:
                    price = data.get("price_raw", -1)
                    if not price:
                        loader.add_value("price", -1)
                    loader.add_value("sold_at", data.get("sold_at"))
                    loader.add_value("availability_label", "Sold")
                else:
                    loader.add_value("availability_label", "Available")

            item = loader.load_item()

            # Additional processing
            if not item.get("location"):
                if result := re.search(
                    r"in (?P<location>[A-Za-z ]+)", item.get("title", "")
                ):
                    item["location"] = result.group("location")

            if not item.get("leasehold_years") and "Leasehold" in item.get(
                "contract_type", ""
            ):
                item["leasehold_years"] = find_lease_years(item.get("description", ""))

            # Define property type if not set
            if not item.get("property_type"):
                item["property_type"] = define_property_type(item.get("title", ""))

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
