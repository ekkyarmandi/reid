from datetime import datetime
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose
from reid.func import identify_currency
from reid.spiders.base import BaseSpider
from reid.items import PropertyItem
import re

from reid.customs.exotiqproperty import lease_or_free_hold


class ExotiqPropertySpider(BaseSpider):
    name = "exotiqproperty"
    allowed_domains = ["exotiqproperty.com"]
    start_urls = ["https://www.exotiqproperty.com/villas-for-sale/bali"]

    def parse(self, response):
        items = response.css("div[role=list] div[role=listitem].listing_item")
        for item in items:
            url = item.css("a::attr(href)").get()
            yield response.follow(response.urljoin(url), callback=self.parse_detail)

    def parse_detail(self, response):
        loader = ItemLoader(item=PropertyItem(), selector=response)
        loader.add_value("source", "Exotiq Property")
        loader.add_value("scraped_at", self.scraped_at)
        loader.add_value("url", response.url)
        loader.add_value("html", response.text)

        loader.add_css(
            "contract_type",
            "#listing-primary-infos div:contains(Ownership) + div::text",
            MapCompose(lease_or_free_hold),
        )
        loader.add_css(
            "property_type", 'div.info_title:contains("Type of property") + div::text'
        )

        # get property ownership
        ownership = response.css("div.info_title:contains(Ownership) + div::text").get()

        # grab lease years
        lease_years = None
        contract_type = loader.get_output_value("contract_type")
        if contract_type or ownership:
            if "lease" in contract_type.lower() or "lease" in ownership.lower():
                loader.add_css("leasehold_years", ".ownership-details:contains(years)")

        # assign data into item loader
        loader.add_value("availability_label", "Available")
        loader.add_css(
            "property_id", "div.info_title:contains('Property ID') + div::text"
        )
        loader.add_css("title", "h1::text")
        loader.add_css(
            "location",
            "div.listing-location_wrapper div::text, div.listing-location_wrapr div::text",
        )
        loader.add_css("bedrooms", "div.info_title:contains(Bed) + div ::text")
        loader.add_css("bathrooms", "div.info_title:contains(Bath) + div ::text")
        loader.add_css("land_size", "div.info_title:contains(Land) + div ::text")
        loader.add_css("build_size", "div.info_title:contains(Building) + div ::text")
        loader.add_css(
            "price",
            "div.info_title:contains(Price) + div.info-price span::text",
        )
        loader.add_css(
            "currency",
            "div.info_title:contains(Price) + div.info-price span::text",
            MapCompose(identify_currency),
        )
        loader.add_css(
            "image_url", "div.listing-slider div[role=listitem] img::attr(src)"
        )
        loader.add_css("description", "div.listing_description p::text")

        item = loader.load_item()
        yield item
