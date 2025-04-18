import scrapy
from datetime import datetime
import traceback
from models.listing import Listing
from reid.spiders.base import BaseSpider
from models.error import Error
from reid.database import get_db
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose
from reid.items import PropertyItem
from reid.func import (
    find_bedrooms_in_description,
    find_lease_years,
    find_land_size,
    find_build_size,
    remove_show_more_less,
    landsize_extractor,
    buildsize_extractor,
    first_month,
)


class LazudiSpider(BaseSpider):
    name = "lazudi"
    allowed_domains = ["lazudi.com"]
    start_urls = ["https://lazudi.com/id-en/properties/for-sale/bali"]

    def parse(self, response):
        urls = response.css("#properties_list a::attr(href)").getall()
        # filter out existing and visited listings
        urls = list(filter(lambda x: x not in self.existing_urls, urls))
        urls = list(filter(lambda x: x not in self.visited_urls, urls))
        # crawl new listings
        for url in urls:
            if not url in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                    meta=dict(redirected_from=url),
                )
        # crawl existing listings
        for url in self.existing_urls:
            if not url in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                    meta=dict(redirected_from=url),
                )
        next_page = response.css(
            "#properties_pagination li a[rel*=next]::attr(href)"
        ).get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def get_detail(self, rows):
        output = {"contract_type": "Leasehold"}
        for row in rows:
            row = row.strip()
            if ":" in row:
                key, value = list(map(str.strip, row.split(":")))
                key = key.lower()
                if key == "created":
                    output[key] = datetime.strptime(value, "%Y-%m-%d").strftime(
                        "%m/%d/%y"
                    )
                elif key in output:
                    prev = output.get(key)
                    if type(prev) != list:
                        prev = [prev]
                    prev.append(value)
                    output[key] = prev
                else:
                    output[key] = value
            elif "freehold" in row.lower():
                output["contract_type"] = "Freehold"
        return output

    def parse_detail(self, response):
        # check if it's redirected from
        origin_url = response.meta.get("redirected_from", None)
        if origin_url != response.url:
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
                "source": "Lazudi",
                "scraped_at": self.scraped_at,
                "url": origin_url,
                "skip": True,
            }
        try:
            # parse listing
            rows = response.css(
                "div#property_detail div.property-details::text"
            ).getall()
            details = self.get_detail(rows)

            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Lazudi")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            loader.add_value("listed_date", details.get("created", ""))
            loader.add_value("property_id", details.get("property id", ""))
            loader.add_css("title", "h1::text")
            loader.add_css("location", "h2 span:last-child::text")
            loader.add_value("contract_type", details.get("contract_type", "Leasehold"))
            loader.add_css(
                "property_type", "div > div.property-details:first-child::Text"
            )
            loader.add_css(
                "bedrooms", "div.prop-spec-detail div div:contains(Bed) span ::text"
            )
            loader.add_css(
                "bathrooms", "div.prop-spec-detail div div:contains(Bath) span ::text"
            )
            loader.add_value("land_size", details.get("plot", ""))
            loader.add_value("build_size", details.get("interior", ""))
            loader.add_css("price", "div.prop-detail-price div div:contains(Rp) ::text")
            loader.add_css("image_url", "#img-0 a::attr(href)")
            loader.add_value("currency", "IDR")
            loader.add_value("availability_label", "Available")
            loader.add_css(
                "description",
                "#property-detail-content ::text",
                MapCompose(remove_show_more_less),
            )
            item = loader.load_item()

            if "Lease" in item["contract_type"]:
                item["leasehold_years"] = find_lease_years(item["description"])
            else:
                item["leasehold_years"] = None

            if not item.get("leasehold_years"):
                item["contract_type"] = "Freehold"

            # find missing bedrooms
            zero_bedrooms = item.get("bedrooms") == None
            desc = item.get("description", "")
            if zero_bedrooms:
                item["bedrooms"] = find_bedrooms_in_description(desc)

            # find missing land_size
            build_size = item.get("build_size", 0)
            if not item.get("land_size"):
                item["land_size"] = landsize_extractor(desc)
            if not item.get("land_size"):
                land_size = find_land_size(desc)
                if land_size and build_size and land_size > build_size:
                    item["land_size"] = land_size

            # find missing build_size
            if not item.get("build_size"):
                item["build_size"] = buildsize_extractor(desc)
            if not item.get("build_size"):
                build_size = find_build_size(desc)
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
