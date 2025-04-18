from datetime import datetime
import json
import jmespath
import scrapy
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose
from models.listing import Listing
from reid.customs.dotproperty import (
    after_colon,
    leasehold_years_finders,
)
from reid.func import (
    extract,
    find_land_size,
    find_build_size,
    get_contract_type,
)
from reid.spiders.base import BaseSpider
from reid.items import PropertyItem
from reid.database import get_db
from models.error import Error
import traceback
import re


class DotPropertySpider(BaseSpider):
    name = "dotproperty"
    allowed_domains = ["dotproperty.id"]

    def start_requests(self):
        for i in range(50):
            url = "https://www.dotproperty.id/en/properties-for-sale/bali"
            yield scrapy.Request(url + "?page=" + str(i + 1), callback=self.parse)

    def parse(self, response):
        urls = response.css(
            "#search-results > article > div.block > a::attr(href)"
        ).getall()
        urls = list(filter(lambda u: "https" in u, urls))
        for url in urls:
            yield response.follow(
                url,
                callback=self.parse_detail,
                errback=self.handle_error,
                meta=dict(redirected_from=url),
            )
        # iterate existing urls
        for url in self.existing_urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                    meta=dict(redirected_from=url),
                )

    def parse_detail(self, response):
        origin_url = response.meta.get("redirected_from", None)
        if origin_url not in response.url:
            # update the availability status to delisted
            db = next(get_db())
            db.query(Listing).filter(Listing.url == origin_url).update(
                {
                    "availability": "Delisted",
                    "is_available": False,
                    "sold_at": datetime.now().replace(
                        day=1,
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    ),
                }
            )
            db.commit()
            yield {
                "source": "Dot Property",
                "scraped_at": self.scraped_at,
                "url": origin_url,
                "skip": True,
            }
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Dot Property")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            # script application/ld+json
            script = response.css("script[type='application/ld+json']::text").get()
            data = json.loads(script)

            loader.add_css("title", "h1::text")
            loader.add_css("location", "div.location::text")
            loader.add_css(
                "property_id", "p.internal-ref::text", MapCompose(after_colon)
            )
            loader.add_css("property_type", "#breadcrumb a::attr(title)")
            loader.add_css("bedrooms", "ul.key-featured li:contains(Bed) span::text")
            loader.add_css("bathrooms", "ul.key-featured li:contains(Bath) span::text")
            loader.add_css("land_size", "ul.key-featured li:contains(Land) span::text")
            loader.add_css(
                "build_size", "ul.key-featured li:contains('Usable area') span::text"
            )
            loader.add_value("price", jmespath.search("offers.price", data))
            loader.add_value("currency", jmespath.search("offers.priceCurrency", data))
            loader.add_value("availability_label", "Available")
            loader.add_css("image_url", "a.open-gallery img::attr(src)")
            loader.add_css("description", "div.text-description ::text")
            loader.add_css(
                "leasehold_years",
                "div.text-description ::text",
                MapCompose(leasehold_years_finders),
            )

            # define the contract type
            leasehold_years = loader.get_output_value("leasehold_years")
            if leasehold_years:
                loader.add_value("contract_type", "Leasehold")
            elif "for-sale" in response.url:
                loader.add_value("contract_type", "Freehold")
            else:
                loader.add_css(
                    "contract_type",
                    "h1::text, div.text-description ::text",
                    MapCompose(get_contract_type),
                )
            # response.css("script:contains(gps_lon)::text").re_first(r'=\s*"(-?[\d.]+)"')
            loader.add_css(
                "longitude",
                "script:contains(gps_lon)::text",
                MapCompose(lambda x: extract(r'=\s*"(-?[\d.]+)"', x)),
            )
            loader.add_css(
                "latitude",
                "script:contains(gps_lat)::text",
                MapCompose(lambda x: extract(r'=\s*"(-?[\d.]+)"', x)),
            )

            item = loader.load_item()

            # lease years
            desc = item.get("description", "")
            bedrooms_pattern = [
                r"(?P<bedrooms>\d)\s*bedrooms",
                r"bedrooms\s*(?P<bedrooms>\d)",
            ]
            for pattern in bedrooms_pattern:
                beds = item.get("bedrooms")
                if not beds:
                    result = re.search(pattern, desc, re.IGNORECASE)
                    if result:
                        item["bedrooms"] = int(result.group("bedrooms"))
                        break

            # find missing land size in the description
            land_size = item.get("land_size")
            if not land_size:
                item["land_size"] = find_land_size(desc)

            # find missing build size in the description
            build_size = item.get("build_size")
            if not build_size:
                item["build_size"] = find_build_size(desc)

            # find missing land size in the description
            if not item.get("land_size"):
                land_size = None
                try:
                    item["land_size"] = find_land_size(desc)
                except AttributeError:
                    pass

            # find missing build size in the description
            if not item.get("build_size"):
                build_size = None
                try:
                    item["build_size"] = find_build_size(desc)
                except AttributeError:
                    pass
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
