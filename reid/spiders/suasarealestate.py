from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from reid.func import (
    find_published_date,
    get_lease_years,
    delisted_item,
)
from models.error import Error
from reid.database import get_db
import traceback
import scrapy
import urllib.parse


class SuasaRealEstateSpider(BaseSpider):
    name = "suasarealestate"
    allowed_domains = ["suasarealestate.com"]
    start_urls = ["https://www.suasarealestate.com/wp-admin/admin-ajax.php"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    def start_requests(self):
        form_data = {
            "action": "search_property",
            "nonce": "5407175caa",
            "source": "search-form",
            "page": "1",
            "ppp": "-1,-1,20,20,20",
            "args": "paging=1&ppp=-1%2C-1%2C20%2C20%2C20&cat=sale&ref=&term=&bedroom=&curr=usd&min-budget=&max-budget=&sort-by=date-latest&ppp=20",
            "sortby[0][name]": "sort-by",
            "sortby[0][value]": "date-latest",
            "sortby[1][name]": "ppp",
            "sortby[1][value]": "20",
        }
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                method="POST",
                body=urllib.parse.urlencode(form_data),
                headers=self.headers,
            )

    def parse(self, response):
        items = response.css(".property-item")
        for item in items:
            url = item.css(".property-content a::attr(href)").get()
            yield response.follow(url, callback=self.parse_detail)

    def parse_detail(self, response):
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Suasa Real Estate")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)

            # Price handling
            price = response.css(
                ".prop-price select > option[value=usd]::attr(data-rate)"
            ).get()
            if not price:
                delisted_item.update(
                    {"source": "Suasa Real Estate", "url": response.url}
                )
                yield delisted_item
            if price:
                if "idr" in price.lower():
                    loader.add_value("price", price)
                    loader.add_value("currency", "IDR")
                elif "usd" in price.lower():
                    loader.add_value("price", price)
                    loader.add_value("currency", "USD")

            # Basic info
            loader.add_css("title", "h1::text")
            loader.add_css("property_id", "a[data-ref]::attr(data-ref)")
            loader.add_css("image_url", "div.photoswipe-item img::attr(src)")
            loader.add_css(
                "location",
                "h1::text",
                MapCompose(
                    lambda x: x.split("|")[-1].strip(),
                    lambda x: x.split(" in ")[-1].strip(),
                ),
            )

            # Sizes
            loader.add_css(
                "land_size",
                "ul.prop-icon li span:contains(Land) + span::text",
            )
            loader.add_css(
                "build_size",
                "ul.prop-icon li span:contains(Build) + span::text",
            )

            # Contract type
            contract_type = response.css(
                "#main .content-table tr:contains(Term) td:nth-child(2)::text"
            ).get()
            # url = response.css("meta[property='og:url']::attr(content)").get()
            property_type = response.url.split("/")[3].title()
            loader.add_value("contract_type", contract_type)
            loader.add_value("property_type", property_type)

            # Availability
            availability = response.css(
                "#main .content-table tr:contains(Available) td:nth-child(2)::text"
            ).get()
            if availability and "sold" in availability.lower():
                availability = "Sold"
            else:
                availability = "Available"
            loader.add_value("availability_label", availability)

            # Rooms
            loader.add_css(
                "bedrooms",
                "#main .content-table tr:contains(Bedroom) td:nth-child(2)::text",
            )
            loader.add_css(
                "bathrooms",
                "#main .content-table tr:contains(Bathroom) td:nth-child(2)::text",
            )

            # Lease years
            if "lease" in contract_type.lower():
                loader.add_css(
                    "leasehold_years",
                    '#main .content-table tr:contains("End of Lease") td:nth-child(2)::text',
                    MapCompose(get_lease_years),
                )

            # Published date
            loader.add_css(
                "listed_date",
                "script[type='application/ld+json']::text",
                MapCompose(find_published_date),
            )

            # Description
            loader.add_css("description", "#main .prop-desc-wrapper ::text")

            # data-lat="-8.6570802241001" data-lng="115.15172428426"
            loader.add_css("longitude", "#map::attr(data-lng)")
            loader.add_css("latitude", "#map::attr(data-lat)")
            item = loader.load_item()

            # Additional processing
            title = item.get("title")
            location = item.get("location")
            if title and not location and "|" in title:
                item["location"] = title.split("|")[-1].strip()

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
