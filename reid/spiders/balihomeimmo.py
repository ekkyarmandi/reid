import scrapy
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.func import identify_currency
from models.error import Error
from reid.database import get_db, get_cloud_db
import traceback
import requests
import re
from decouple import config
from reid.spiders.base import BaseSpider
from reid.func import define_property_type, delisted_item
from models import Property
from sqlalchemy import func
from datetime import date


class BaliHomeImmoSpider(BaseSpider):
    name = "balihomeimmo"
    allowed_domains = ["bali-home-immo.com", "https://jsonplaceholder.typicode.com"]

    def start_requests(self):
        # --- Added SQLAlchemy Query ---
        db = next(get_cloud_db())
        try:
            query_date = date(2025, 4, 2)  # Note: This is a future date
            self.visited_urls = (
                db.query(Property.url)
                .filter(
                    Property.url.like("%bali-home-immo%"),
                    Property.created_at >= query_date,
                )
                .all()
            )
            self.visited_urls = [i[0] for i in self.visited_urls]
            count = len(self.visited_urls)
            self.logger.info(
                f"Found {count} properties from bali-home-immo created since {query_date}"
            )
        finally:
            db.close()
        # --- End Added Query ---

        self.numbers = []
        self.fakeurl = "https://jsonplaceholder.typicode.com/comments/1"
        url = "https://bali-home-immo.com/realestate-property/for-sale/villa"
        yield scrapy.Request(
            self.fakeurl,
            meta={"response": self._get_response(url)},
            dont_filter=True,
        )

    def _get_response(self, url):
        headers = {
            "Cookie": "cf_clearance=" + config("BALIHOMEIMMO_COOKIES"),
            "User-Agent": config("USER_AGENT"),
            "cache-control": "no-cache",
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                self.logger.warning(f"Received {response.status_code} for URL: {url}")
                return scrapy.http.TextResponse(
                    url=url,
                    body="",
                    status=response.status_code,
                    encoding="utf-8",
                )
            return scrapy.http.TextResponse(
                url=response.url,
                body=response.text,
                encoding="utf-8",
            )
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            return scrapy.http.TextResponse(
                url=url,
                body="",
                status=500,
                encoding="utf-8",
            )

    def parse(self, response):
        response = response.meta.get("response")
        # collect urls
        items = response.css(".properties-holder .property-item")
        urls = items.css("a::attr(href)").getall()
        urls = list(filter(lambda x: x.startswith("http"), urls))
        urls = list(dict.fromkeys(urls))
        urls = list(filter(lambda x: x not in self.visited_urls, urls))
        urls = list(filter(lambda x: x not in self.existing_urls, urls))
        for url in urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield scrapy.Request(
                    self.fakeurl,
                    callback=self.parse_detail,
                    meta={"response": self._get_response(url)},
                    dont_filter=True,
                )

        # paginate
        if len(items) > 0:
            if "?page" not in response.url:
                next_url = response.url + "?page=2"
            else:
                page = int(response.url.split("=")[-1])
                next_url = response.url.replace(f"page={page}", f"page={page+1}")
            yield scrapy.Request(
                self.fakeurl,
                callback=self.parse,
                meta={"response": self._get_response(next_url)},
                dont_filter=True,
            )

        # fetch existing urls
        # for url in self.existing_urls:
        #     if url not in self.visited_urls:
        #         self.visited_urls.append(url)
        #         yield scrapy.Request(
        #             url, callback=self.parse_detail, errback=self.handle_error
        #         )

    def parse_detail(self, response):
        response = response.meta.get("response")
        ## lambda functions
        has_leasehold = lambda values: any("lease" in v.lower() for v in values)
        has_freehold = lambda values: any("free" in v.lower() for v in values)
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            ## collect raw data
            loader.add_value("source", "Bali Home Immo")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            ## extractions main logic
            loader.add_css("title", "h2.title::text")
            loader.add_css("location", ".side-location span::text")
            loader.add_css("image_url", ".swiper-slide img::attr(src)")
            loader.add_css(
                "property_type",
                "h2.title::text",
                MapCompose(define_property_type),
            )
            loader.add_css(
                "property_id",
                "h2.title::text",
                MapCompose(lambda x: x.split("-")[-1].strip()),
            )
            # find details
            d = {}
            table = response.css(".property-list-item-for-details table tr")
            for tr in table:
                key = tr.css("td:first-child::text").get().lower().replace(" ", "_")
                key = re.sub(r"\s*", "", key.strip("_")).strip("_")
                value = tr.css("td:nth-child(3)::text").get()
                d.update({key: value})
            # get side info contract types
            leasehold_years = d.get("leasehold_period", "")
            contracts = response.css(".side-info .action span ::Text").getall()
            if has_leasehold(contracts):
                loader.add_value("leasehold_years", leasehold_years)
                loader.add_value("contract_type", "Leasehold")
            elif has_freehold(contracts):
                loader.add_value("contract_type", "Freehold")
            else:
                delisted_item.update({"source": "Bali Home Immo", "url": response.url})
                yield delisted_item

            is_sold = response.css(
                ".property-thumbnail__watermark:contains(Sold)::Text"
            )
            if is_sold:
                loader.add_value("availability_label", "Sold")
                loader.add_value("sold_at", self.scraped_at)
            else:
                loader.add_value("availability_label", "Available")

            contract_type = loader.get_output_value("contract_type")
            if contract_type:
                contract_type = contract_type.lower()
            loader.add_css(
                "price",
                f"span[data-price-category={contract_type}]::attr(data-price)",
            )
            loader.add_css(
                "currency",
                "select option[selected]::attr(value)",
                MapCompose(identify_currency),
            )
            loader.add_value("bedrooms", d.get("bedroom", ""))
            loader.add_value("land_size", d.get("land_size", ""))
            loader.add_value("build_size", d.get("building_size", ""))
            loader.add_css("bathrooms", "tr:contains(Bathroom) td:last-child::text")
            loader.add_css("description", "div.property-info-desc ::text")
            item = loader.load_item()
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
