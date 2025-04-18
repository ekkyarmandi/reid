from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from reid.spiders.base import BaseSpider
from itemloaders.processors import MapCompose
from reid.func import (
    cari_luas_tanah,
    check_per_meter,
    count_lease_years,
    delisted_item,
)
from models.error import Error
from reid.database import get_db
import traceback
import re
import json
import jmespath
import scrapy
import math


class RayWhiteSpider(BaseSpider):
    name = "raywhite"
    allowed_domains = ["raywhite.co.id"]
    start_urls = [
        "https://www.raywhite.co.id/jual?provinsi=Bali&order=newest&limit=9&defaultlang=en"
    ]
    visited = []

    def parse(self, response):
        try:
            # Collect property URLs
            urls = response.css("a[href*='/properti/']::attr(href)").getall()
            for url in urls:
                yield scrapy.Request(url, callback=self.parse_detail)

            # Pagination
            total = response.css("div:contains(Showing)").re_first(
                r"Showing \d+ - \d+ of (\d+) result"
            )
            if total and response.url not in self.visited:
                max_page = math.ceil(int(total) / 9) + 2
                for i in range(2, max_page):
                    next_url = response.url + f"&page={i}"
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
            loader.add_value("source", "Ray White Indonesia")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)

            # Extract JSON-LD data
            script = response.css("script[type='application/ld+json']::text").get()
            if script:
                d = json.loads(script)

                # Dates
                dates = []
                images = jmespath.search("image", d)
                if images:
                    for i in images:
                        extracted_date = re.findall(
                            r"\d{4}/\d{2}/\d{2}|\d{4}-\d{2}-\d{2}", i
                        )
                        dates.extend(extracted_date)

                if dates:
                    dates = [re.sub(r"\/", "-", date) for date in dates]
                    dates = list(set(dates))
                    list_date = min(dates)
                    loader.add_value("listed_date", list_date)

                # Price and currency
                loader.add_value("currency", jmespath.search("offers.priceCurrency", d))
                loader.add_value("price", jmespath.search("offers.price", d))

            # Basic info
            loader.add_css("title", "h1::Text")
            loader.add_css("location", "h1 + p::Text")
            loader.add_css("description", "h2 + p ::Text")
            loader.add_css("image_url", "div#mainCarousel img::attr(src)")

            # Extract specification table
            table = {}
            for tr in response.css("table.table tr"):
                key = tr.css("td:nth-child(2)::Text").get()
                value = tr.css("td:nth-child(3)::Text").get()
                if key and value:
                    table[key.strip()] = value.strip(":").strip()

            loader.add_value("property_id", table.get("Listing ID"))
            loader.add_value("bedrooms", table.get("Bedroom"))
            loader.add_value("bathrooms", table.get("Bathroom"))
            loader.add_value("land_size", table.get("Land Size"))
            loader.add_value("build_size", table.get("Building Size"))

            land_size = loader.get_output_value("land_size")
            if not land_size:
                loader.add_value(
                    "land_size",
                    "h2 + p ::Text",
                    MapCompose(cari_luas_tanah),
                )

            # Availability
            loader.add_value("availability_label", "Available")

            # Property type and contract
            state = response.css("h2::Text").get()
            certificate = table.get("Certificate")
            property_type = "Unknown"
            contract_type = ""

            if "Rumah" in state:
                property_type = "House"
            elif any(
                x in state for x in ["Gudang", "Pabrik", "Komersial", "Ruko", "Kantor"]
            ):
                property_type = "Commercial"
            elif "Villa" in state or "Vila" in state:
                property_type = "Villa"
            elif "Apartemen" in state:
                property_type = "Apartement"
            elif "Tanah" in state:
                property_type = "Land"

            if certificate and "HGB" in certificate:
                contract_type = "Leasehold"
                loader.add_value("leasehold_years", 30)
            elif "for Sale" in state:
                contract_type = "Freehold"

            # Find contract type in description
            desc = loader.get_output_value("description")
            if desc:
                years = count_lease_years(desc)
                if years:
                    contract_type = "Leasehold"
                    loader.add_value("leasehold_years", years)

            loader.add_value("contract_type", contract_type)
            loader.add_value("property_type", property_type)

            # Additional processing
            item = loader.load_item()

            # Calculate price per meter
            price_idr = response.css(
                "p.h3 + div > label:contains(IDR)::attr(for)"
            ).get()
            if price_idr:
                has_permeter = check_per_meter(price_idr)
                land_size = item.get("land_size", 0)
                price = item.get("price", 0)
                if land_size > 0 and has_permeter:
                    item["price"] = price * land_size
                    item["currency"] = "IDR"

            # Bedrooms validation
            bedrooms = item.get("bedrooms", 0)
            if not bedrooms and property_type == "Villa":
                delisted_item.update(
                    {
                        "url": item.get("url"),
                        "source": "Ray White Indonesia",
                    }
                )
                yield delisted_item
            else:
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
