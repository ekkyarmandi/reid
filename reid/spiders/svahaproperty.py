from itemloaders import ItemLoader
from itemloaders.processors import MapCompose
from reid.func import (
    define_property_type,
    extract,
    find_lease_years,
    get_uploaded_date,
    grab_first,
    identify_currency,
)
from reid.items import PropertyItem
from reid.spiders.base import BaseSpider
from reid.database import get_db
from models.error import Error
import traceback
import re


class SvahaPropertySpider(BaseSpider):
    name = "svahaproperty"
    allowed_domains = ["svahaproperty.com"]
    start_urls = [
        "https://www.svahaproperty.com/listing-category/villa/page/1/?s&filters%5Bad_type%5D=sell"
    ]

    def parse(self, response):
        # collect the items
        urls = response.css("div.listing-item h3 a::attr(href)").getall()
        urls = list(map(lambda x: response.urljoin(x), urls))
        urls = list(filter(lambda x: x not in self.visited_urls, urls))
        for url in urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(url, callback=self.parse_detail)

        # fetch existing urls
        # for url in self.existing_urls:
        #     if url not in self.visited_urls:
        #         self.visited_urls.append(url)
        #         yield response.follow(url, callback=self.parse_detail)

        # pagination
        next_url = response.css("nav.rtcl-pagination ul li a.next::attr(href)").get()
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_detail(self, response):
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Svaha Property")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            loader.add_css("title", "h2::text")
            loader.add_css("location", "ul.entry-meta li::text")
            loader.add_css("image_url", "div.product-thumb img::attr(src)")
            loader.add_css(
                "listed_date",
                "div.product-thumb img::attr(src)",
                MapCompose(get_uploaded_date),
            )

            # get property details
            d = {}
            details = response.css("div.product-details ul li")
            remove_bracket = lambda str: re.sub(r"\((.*)\)", "", str)
            for li in details:
                key = li.css("span:first-child::text").get().strip()
                value = li.css("span:nth-child(2)::text").get().strip()
                d.update({remove_bracket(key): value})

            # contract type
            contract_type = d.get("Status", d.get("Purpose", ""))
            if "sale" in contract_type.lower():
                loader.add_value("contract_type", "Freehold")
            else:
                loader.add_value("contract_type", "Leasehold")
            loader.add_value("property_type", d.get("Type", ""))
            # assign data into item loader
            loader.add_value("availability_label", "Available")
            loader.add_css("price", "div.product-price ::text")
            loader.add_css(
                "currency",
                "div.product-price ::text",
                MapCompose(identify_currency),
            )
            loader.add_value("property_id", d.get("Villa ID"))
            loader.add_value("bedrooms", d.get("Bedroom"))
            loader.add_value("bathrooms", d.get("Bath"))
            loader.add_value(
                "land_size",
                d.get("Land"),
                MapCompose(
                    lambda d: d.replace(",", "."),
                    grab_first,
                ),
            )
            loader.add_value(
                "build_size",
                d.get("Building"),
                MapCompose(
                    lambda d: d.replace(",", "."),
                    grab_first,
                ),
            )
            loader.add_css("description", "div.product-description p ::Text")
            if contract_type == "Leasehold":
                loader.add_css(
                    "leasehold_years",
                    "div.product-details li:contains(Leasehold) span[class*=value]::text",
                )
            loader.add_css(
                "longitude",
                "#rtcl-map-js-extra",
                MapCompose(lambda x: extract(r'"lng"\s*:\s*"(-?[\d.]+)"', x)),
            )
            loader.add_css(
                "latitude",
                "#rtcl-map-js-extra",
                MapCompose(lambda x: extract(r'"lat"\s*:\s*"(-?[\d.]+)"', x)),
            )
            item = loader.load_item()
            # refind the leasehold years
            years = item.get("leasehold_years")
            if "lease" in contract_type.lower() and (not years or years > 99):
                if not years:
                    item["leasehold_years"] = find_lease_years(
                        item.get("description", "")
                    )
                elif years > 99:
                    years = response.css(
                        "div.product-details li:contains(Leasehold) span[class*=value]::text"
                    ).get()
                    item["leasehold_years"] = find_lease_years(years)

            # (alternative) contract type
            if not item.get("contract_type"):
                title = item.get("title", "")
                if not contract_type or contract_type == "":
                    result = re.search(r"leasehold|freehold", title.lower())
                    if result:
                        a, b = result.start(), result.end()
                        contract_type = title[a:b].title()
                if not property_type or property_type == "":
                    property_type = define_property_type(title)
                item["contract_type"] = contract_type
                item["property_type"] = property_type
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
            db.close()
