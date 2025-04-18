from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from reid.func import (
    define_property_type,
    dimension_remover,
    find_published_date,
    get_lease_years,
    identify_currency,
    landsize_extractor,
    recalculate_price_by_land_size,
)
from models.error import Error
from reid.database import get_db
import traceback
import re


class RajaVillaPropertySpider(BaseSpider):
    name = "rajavillaproperty"
    allowed_domains = ["rajavillaproperty.com"]
    start_urls = ["https://rajavillaproperty.com/villa-for-sale/"]

    def parse(self, response):
        items = response.css("#main div.col-property-box")
        for item in items:
            url = item.css("h3 a::attr(href)").get()
            yield response.follow(url, callback=self.parse_detail)
        # go to next page
        next_url = response.css("nav.pagination a.next::attr(href)").get()
        if next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_detail(self, response):
        try:
            ## lambda functions
            get_first = lambda str, separator: str.split(separator)[0]
            get_last = lambda str, separator: str.split(separator)[-1]
            ## extractors main functions
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Raja Villa Property")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            loader.add_css(
                "property_id",
                ".preoperty-overview ul li:contains(Property)::text",
            )
            loader.add_css("bedrooms", "li:contains(Bed) ::Text")
            loader.add_css("bathrooms", "li:contains(Bath) ::Text")
            loader.add_css("location", ".address ::text")

            # Price and currency handling
            loader.add_css("price", "div.price::text")
            loader.add_css("currency", "div.price::text", MapCompose(identify_currency))

            title = response.css("h1::text").get()
            if "leasehold" in title.lower():
                contract_type = "Leasehold"
            else:
                contract_type = "Freehold"
            loader.add_value("title", title, MapCompose(str.strip))
            loader.add_value("contract_type", contract_type)

            # get the published date in the script application/ld+json
            loader.add_css(
                "listed_date",
                "script[type='application/ld+json']::text",
                MapCompose(find_published_date),
            )

            # Property type handling
            loader.add_css(
                "property_type",
                "h1::text",
                MapCompose(define_property_type),
            )

            # Lease years handling
            years_result = response.css('li:contains("Lease Period") ::Text').getall()
            years = " ".join(years_result)
            lease_years = get_lease_years(years) if years else None
            loader.add_value("leasehold_years", lease_years)

            # Description handling
            desc = (
                response.css(".property-description")
                .css("p ::text, div ::text")
                .getall()
            )
            loader.add_value("description", desc)

            # Availability handling
            labels = response.css(".property-gallery .property-badge::text").getall()
            availability = "Sold" if "Sold" in labels else "Available"
            loader.add_value("availability_label", availability)

            # Sizes handling
            loader.add_css(
                "build_size",
                '.property-overview li:contains("Home area")::text',
            )
            loader.add_css(
                "land_size",
                '.property-overview li:contains("Lot area")::Text, li:contains("Land") ::Text',
            )

            # Image handling
            loader.add_css(
                "image_url",
                "div.property-gallery-preview-owl img::attr(src)",
                MapCompose(dimension_remover),
            )

            item = loader.load_item()

            # Additional processing
            land_size = item.get("land_size", None)
            title = item.get("title", "")

            # Find missing land size in title
            if not land_size:
                item["land_size"] = landsize_extractor(title)

            # Remove lease years from price tag if needed
            price = str(item.get("price", 0))
            result = re.search(f"{lease_years}$", price)
            if lease_years and result:
                price = re.sub(f"{lease_years}$", "", price)
                item["price"] = int(price)

            # Find missing location in title
            if not item.get("location"):
                if result := re.search(r"in (.+) -", title):
                    item["location"] = result.group(1)

            # Recalculate the price by land size
            if isinstance(land_size, int) and land_size > 0:
                price_text = response.css("div.price::text").get()
                new_price = recalculate_price_by_land_size(price_text, price, land_size)
                if new_price:
                    item["price"] = new_price

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
