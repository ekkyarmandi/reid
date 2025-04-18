from itemloaders import ItemLoader
from reid.spiders.base import BaseSpider
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.func import (
    define_property_type,
    extract_currency,
    find_land_size,
    find_build_size,
    find_bedrooms,
    get_lease_years,
    identify_currency,
)


class HeritageBaliSpider(BaseSpider):
    name = "heritagebali"
    allowed_domains = ["heritagebali.com"]
    start_urls = ["https://www.heritagebali.com/property-listing/villas"]

    def parse(self, response):
        # collect property items
        urls = response.css(".property_listing h4 a::attr(href)").getall()
        for url in urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(url, callback=self.parse_detail)

        # pass the existing urls
        for url in self.existing_urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(url, callback=self.parse_detail)

        # go to the next url
        next_url = response.css("ul.pagination li.roundright a::attr(href)").get()
        if next_url and next_url != response.url:
            yield response.follow(next_url, callback=self.parse)

    def parse_detail(self, response):
        loader = ItemLoader(item=PropertyItem(), selector=response)
        loader.add_value("source", "Heritage Bali")
        loader.add_value("scraped_at", self.scraped_at)
        loader.add_value("url", response.url)
        loader.add_value("html", response.text)

        loader.add_css("title", "h1::text")
        loader.add_value("availability_label", "Available")

        # get price and lease years
        price = response.css("div.listing_detail:contains(Price) ::text").getall()
        is_leasehold = False
        if len(price) > 2:
            is_leasehold = "lease" in price[-1].lower()

        contract_type = "Leasehold" if is_leasehold else "Freehold"

        loader.add_css(
            "property_id",
            "#propertyid_display::text",
        )
        loader.add_css(
            "bathrooms",
            "div.listing_detail:contains(Bathrooms) ::text",
        )
        loader.add_css(
            "bedrooms",
            [
                "div.listing_detail:contains(Bedrooms) ::text",
                ".property_custom_detail_wrapper ::text",
            ],
            MapCompose(find_bedrooms),
        )
        loader.add_value(
            "price",
            price[1] if len(price) > 0 else "",
        )
        loader.add_css(
            "currency",
            "div.listing_detail:contains(Price) ::text",
            MapCompose(extract_currency, identify_currency),
        )
        loader.add_value(
            "leasehold_years",
            price[-1] if len(price) > 0 else "",
            MapCompose(get_lease_years),
        )
        currency = loader.get_output_value("currency")
        loader.add_css(
            "land_size",
            [
                "div.listing_detail:contains('Property Lot Size') ::text",
                ".property_custom_detail_wrapper ::text",
            ],
            MapCompose(find_land_size),
        )
        loader.add_css(
            "build_size",
            [
                "div.listing_detail:contains('Property Size') ::text",
                ".property_custom_detail_wrapper ::text",
            ],
            MapCompose(find_build_size),
        )
        loader.add_css(
            "description",
            ".property_custom_detail_wrapper ::text",
        )
        loader.add_value(
            "contract_type",
            contract_type,
        )
        loader.add_css(
            "property_type",
            "h1::text",
            MapCompose(define_property_type),
        )
        loader.add_css(
            "image_url",
            ".carousel-inner img::attr(src)",
        )
        loader.add_css(
            "location",
            ".wpestate_estate_property_design_intext_details:contains('Bali') a:last-child::text",
        )

        # response.css("#googleMapSlider::attr(data-cur_long)").get()
        loader.add_css(
            "longitude",
            "#googleMapSlider::attr(data-cur_long)",
        )
        loader.add_css(
            "latitude",
            "#googleMapSlider::attr(data-cur_lat)",
        )

        item = loader.load_item()

        # replace missing location that not in bali with real value
        loc = response.css(
            "div.wpestate_estate_property_design_intext_details:has(i.fa-map-marker-alt) a::Text"
        ).getall()
        item["location"] = ", ".join(loc)

        yield item
