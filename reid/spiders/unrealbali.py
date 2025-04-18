from scrapy.loader import ItemLoader
from datetime import datetime
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.database import get_db
from models.error import Error
import traceback
from reid.spiders.base import BaseSpider
from reid.func import (
    dimension_remover,
    extract,
    find_hold_state,
    find_idr,
    find_lease_years,
    find_usd,
    grab_first,
    get_first,
    get_last,
    delisted_item,
    to_number,
    standardize_property_type,
)


class UnrealBaliSpider(BaseSpider):
    name = "unrealbali"
    allowed_domains = ["unrealbali.com"]
    start_urls = [
        "https://www.unrealbali.com/search-results/?location%5B%5D=&status%5B%5D=&type%5B%5D=villa&max-price="
    ]

    def parse(self, response):
        items = response.css("div.item-wrap")
        for item in items:
            url = item.css("div.item-body h2.item-title a::attr(href)").get()
            yield response.follow(url, callback=self.parse_detail)

    def parse_detail(self, response):
        ## functions ##
        iso2date = lambda str: datetime.fromisoformat(str).strftime(r"%m/%d/%y")
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            # collect raw data
            loader.add_value("source", "Unreal Bali")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            ## main logic ##
            loader.add_css("property_id", "ul:contains('Property ID') li strong::text")
            loader.add_css("title", "h1::text")
            loader.add_css("location", "address::text")
            loader.add_css(
                "build_size",
                "ul li i[class*=plan] + strong::text",
                MapCompose(
                    lambda value: value.replace(",", "."),
                    lambda value: get_first(value, "+"),
                    lambda value: get_last(value, "/"),
                    lambda value: get_last(value, "-"),
                    lambda value: get_last(value, "to"),
                ),
            )
            loader.add_css(
                "land_size",
                "ul li i[class*=map] + strong::text",
                MapCompose(
                    lambda value: value.replace(",", "."),
                    lambda value: get_first(value, "+"),
                    lambda value: get_last(value, "/"),
                    lambda value: get_last(value, "-"),
                    lambda value: get_last(value, "to"),
                ),
            )
            price_text = response.css("li.item-price::text").get()
            usd = find_usd(price_text)
            idr = find_idr(price_text)
            if usd:
                loader.add_value("price", usd)
                loader.add_value("currency", "USD")
            elif idr:
                loader.add_value("price", idr)
                loader.add_value("currency", "IDR")
            loader.add_css(
                "listed_date",
                "meta[property='og:updated_time']::attr(content)",
                MapCompose(iso2date),
            )

            labels = response.css("div.property-labels-wrap > ::text").getall()
            is_leasehold, is_sold = find_hold_state(labels)

            availability = "Available" if not is_sold else "Sold"
            if availability == "Sold":
                loader.add_value("sold_at", self.scraped_at)

            loader.add_css(
                "property_type",
                "ul li.h-type span::text",
                MapCompose(standardize_property_type),
            )
            loader.add_value(
                "contract_type",
                "Leasehold" if is_leasehold else "Freehold",
            )
            loader.add_css(
                "leasehold_years",
                "div.property-overview-data ul li i.icon-calendar-3 + strong::text",
                MapCompose(lambda d: d.split("/")[0]),
            )
            loader.add_css(
                "bedrooms",
                "ul:contains(Bedroom) li strong::text",
                MapCompose(
                    grab_first,
                    lambda d: d.replace(",", "."),
                ),
            )
            loader.add_css(
                "bathrooms",
                "ul:contains(Bathroom) li strong::text",
                MapCompose(
                    grab_first,
                    lambda d: d.replace(",", "."),
                ),
            )
            loader.add_css(
                "image_url",
                "div.property-banner div.row img::attr(src)",
                MapCompose(dimension_remover),
            )
            loader.add_value("availability_label", availability)
            loader.add_css(
                "description",
                "#property-description-wrap div.block-content-wrap ::text",
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

            title = item.get("title")
            if not title or "not found" in title:
                yield delisted_item
            if not item.get("leasehold_years"):
                desc = item.get("description", "")
                item["leasehold_years"] = find_lease_years(desc)
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
