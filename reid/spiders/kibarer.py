import traceback
import re
from reid.spiders.base import BaseSpider
from models.error import Error
from reid.database import get_db
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose
from models.listing import Listing
from reid.items import PropertyItem
from reid.func import (
    find_lease_years,
    are_to_sqm,
    find_idr,
    find_usd,
    dimension_remover,
    find_property_type,
    delisted_item,
    find_contract_type,
    get_lease_years,
)


class KibarerSpider(BaseSpider):
    name = "kibarer"
    allowed_domains = ["villabalisale.com"]
    start_urls = ["https://www.villabalisale.com/search/villas-for-sale/"]

    def parse(self, response):
        urls = response.css(
            "#box div.property-item a::attr(href), div.properties-lists div.property-info > a::attr(href)"
        ).getall()
        for url in urls:
            if url not in self.start_urls and url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                    meta={"redirect_from": url},
                )
        # Iterate the existing urls
        for url in self.existing_urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                    meta={"redirect_from": url},
                )
        # Do paginating
        next_url = response.css(
            "div#pagination ul li a[aria-label=Next]::attr(href)"
        ).get()
        if next_url and "http" in next_url:
            yield response.follow(next_url, callback=self.parse)

    def parse_detail(self, response):
        redirected_url = response.meta.get("redirect_from")
        if redirected_url != response.url:
            db = next(get_db())
            listing = db.query(Listing).filter(Listing.url == redirected_url).first()
            listing.is_available = False
            listing.availability = "Delisted"
            listing.sold_at = self.scraped_at
            db.commit()
            delisted_item.update({"url": redirected_url, "skip": True})
            yield delisted_item
        try:
            raw_contract_type = response.css(
                "div.property-badges > div.property-badge:first-child ::Text"
            ).getall()
            raw_contract_type = list(map(str.strip, raw_contract_type))
            contract_type = ",".join(raw_contract_type)
            if re.search("hold", contract_type, re.IGNORECASE):
                loader = ItemLoader(item=PropertyItem(), selector=response)
                # Define the price
                price_text = response.css("div#property-price button span::Text").get()
                price_idr = find_idr(price_text)
                price_usd = find_usd(price_text)
                if price_idr:
                    loader.add_value("price", price_idr)
                    loader.add_value("currency", "IDR")
                elif price_usd:
                    loader.add_value("price", price_usd)
                    loader.add_value("currency", "USD")
                else:
                    loader.add_value("price", "-1")
                    loader.add_value("currency", "USD")
                # Add values to loader
                loader.add_value("source", "Kibarer")
                loader.add_value("scraped_at", self.scraped_at)
                loader.add_value("url", response.url)
                loader.add_value("html", response.text)
                loader.add_value("availability_label", "Available")
                loader.add_css("title", "h1#property-name::Text")
                loader.add_css("property_id", "div:has(dd):contains(Code) dt::Text")
                loader.add_css("location", "div:has(dd):contains(Location) dt::Text")
                loader.add_value(
                    "contract_type",
                    contract_type,
                    MapCompose(find_contract_type),
                )
                contract_type = loader.get_output_value("contract_type")
                if contract_type == "Leasehold":
                    loader.add_css(
                        "leasehold_years",
                        "div.property-badge:first-child ::Text",
                        MapCompose(get_lease_years),
                    )
                loader.add_css(
                    "property_type",
                    "h1#property-name::Text",
                    MapCompose(find_property_type),
                )
                loader.add_css(
                    "bedrooms", "div.property-badge img[src*=bed] + span::Text"
                )
                loader.add_css(
                    "bathrooms", "div.property-badge img[src*=bathtub] + span::Text"
                )
                loader.add_css(
                    "land_size",
                    "img[src*=scale-frame-enlarge] + div::Text",
                    MapCompose(are_to_sqm),
                )
                loader.add_css(
                    "build_size",
                    "img[src*=scale-frame-reduce] + div::Text",
                )
                loader.add_css(
                    "image_url",
                    "figure img.object-cover::attr(src)",
                    MapCompose(dimension_remover),
                )
                loader.add_css("description", "div.description ::Text")
                loader.add_css("longitude", "div[data-longitude]::attr(data-longitude)")
                loader.add_css("latitude", "div[data-latitude]::attr(data-latitude)")

                item = loader.load_item()

                # set the default property type if missings
                if item.get("property_type") is None:
                    item["property_type"] = "Villa"

                # refind the leasehold years in the description
                leasehold_years = item.get("leasehold_years", 0)
                contract_type = item.get("contract_type", "").lower()
                is_leasehold = re.search("lease", contract_type, re.IGNORECASE)
                if is_leasehold and not leasehold_years:
                    desc = item.get("description", "")
                    item["leasehold_years"] = find_lease_years(desc)
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
            try:
                db.add(error)
                db.commit()
            except Exception as e:
                db.rollback()
                self.logger.error(f"Error adding error to database: {e}")
